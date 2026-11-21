"""Sample historical XAUUSD ticks from the guarded demo connection."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from math import isfinite
from pathlib import Path
import sys

import MetaTrader5 as mt5

from goldbot.core.config import SYMBOL
from goldbot.core.connection import demo_connection
from goldbot.market_data.tick_data import audit_ticks, spread
from goldbot.risk.broker_spec_validator import DiagnosticError, require, require_demo
from tools.diagnose_time import EXPECTED_SERVER


ROOT = Path(__file__).resolve().parents[1]
CHUNK_SECONDS = 15


def sample_plan(root):
    inventory = {}
    anchors = {}
    for frame, step in (("H1", 3600), ("M15", 900)):
        path = root / "data" / f"{SYMBOL}_{frame}.csv"
        payload = path.read_bytes()
        labels = [int(row["mt5_time_epoch"])
                  for row in csv.DictReader(io.StringIO(payload.decode("ascii")))]
        gaps = [(right - left, left, right) for left, right in zip(labels, labels[1:])
                if right - left > step]
        inventory[frame] = {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(), "rows": len(labels),
            "first_raw_label": labels[0], "last_raw_label": labels[-1],
            "nominal_step_seconds": step, "gap_count": len(gaps),
            "selected_gaps": {},
        }
        for label, start in (("first", labels[0]), ("midpoint_row", labels[len(labels) // 2]),
                             ("last", labels[-1])):
            anchors.setdefault(start, []).append(f"{frame}:{label}")
        for label, gap in (("shortest", min(gaps)), ("longest", max(gaps))) if gaps else ():
            delta, left, right = gap
            inventory[frame]["selected_gaps"][label] = {
                "previous_label": left, "next_label": right, "delta_seconds": delta,
                "absent_nominal_labels": (delta - 1) // step,
            }
            for point, start in (("before", left + step - CHUNK_SECONDS),
                                 ("inside", left + step + (right - left - step) // 2),
                                 ("after", right)):
                anchors.setdefault(start, []).append(f"{frame}:{label}_gap:{point}")
    return inventory, sorted(anchors.items())


def preserve_scalar(value):
    value = value.item()
    if isinstance(value, float) and not isfinite(value):
        return repr(value)
    return value


def sample(start, reasons):
    end = start + CHUNK_SECONDS - 1
    requested_at = datetime.now(timezone.utc).isoformat()
    data = mt5.copy_ticks_range(SYMBOL, start, end, mt5.COPY_TICKS_ALL)
    code = mt5.last_error()[0]
    chunk = {
        "reasons": reasons, "integer_seconds_from": start, "integer_seconds_to": end,
        "host_request_utc": requested_at,
        "host_response_utc": datetime.now(timezone.utc).isoformat(),
        "api_code": code, "returned_count": None if data is None else len(data),
    }
    if data is None:
        return dict(chunk, status="API_ERROR")
    fields = data.dtype.names
    rows = [{key: preserve_scalar(row[key]) for key in fields} for row in data]
    audit = audit_ticks(rows, bounds=(start * 1000, end * 1000 + 999))
    return dict(chunk, status="RETURNED" if rows else "EMPTY", dtype=data.dtype.descr,
                raw_rows=rows, spread_price_units_by_index=[spread(row) for row in rows],
                rows_sha256=hashlib.sha256(json.dumps(
                    rows, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest(),
                issue_counts=dict(Counter(issue.code for issue in audit.issues)),
                row_issues=[vars(issue) for issue in audit.issues],
                observations=audit.observations, largest_raw_spacing_ms=audit.largest_raw_spacing_ms)


def capture(root=ROOT, *, progress=None, checkpoint=None):
    inventory, anchors = sample_plan(root)
    report = {
        "captured_host_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL, "expected_demo_server": EXPECTED_SERVER,
        "package_version": mt5.__version__,
        "api_available": {name: callable(getattr(mt5, name, None))
                          for name in ("copy_ticks_range", "copy_ticks_from")},
        "coverage": "SAMPLES_ONLY", "historical_execution_ready": False,
        "coordinate_semantics": (
            "Integer seconds taken from CSV raw labels or raw arithmetic around them. "
            "MetaQuotes describes epoch UTC inputs; broker-specific mapping, alignment and "
            "Python endpoint precision are unverified. Native range documents inclusive bounds."
        ),
        "bounds_audit": "Start second through last millisecond of end second; not a completeness claim.",
        "nonfinite_encoding": "Nonfinite floating fields, if present, are encoded as repr strings.",
        "planned_chunk_count": len(anchors), "chunk_seconds_budget": CHUNK_SECONDS,
        "datasets": inventory, "chunks": [], "status": "IN_PROGRESS",
    }
    if checkpoint is not None:
        checkpoint(report)
    try:
        with demo_connection() as account:
            require_demo(mt5, account, EXPECTED_SERVER)
            info = mt5.symbol_info(SYMBOL)
            require(info is not None and info.name == SYMBOL and info.custom is False, "SYMBOL_UNVERIFIED")
            report["terminal_version"] = mt5.version()
            report["current_metadata_only"] = {
                "account_currency": account.currency, "chart_mode": getattr(info, "chart_mode", None),
                "swap_mode": info.swap_mode, "swap_long": info.swap_long, "swap_short": info.swap_short,
            }
            require(report["api_available"]["copy_ticks_range"], "RANGE_API_UNAVAILABLE")
            report["copy_ticks_all_flag"] = mt5.COPY_TICKS_ALL
            for index, (start, reasons) in enumerate(anchors, start=1):
                require_demo(mt5, account, EXPECTED_SERVER)
                if progress is not None:
                    progress(index, len(anchors), start)
                report["pending_request"] = {
                    "integer_seconds_from": start, "integer_seconds_to": start + CHUNK_SECONDS - 1,
                    "reasons": reasons,
                }
                if checkpoint is not None:
                    checkpoint(report)
                chunk = sample(start, reasons)
                require_demo(mt5, account, EXPECTED_SERVER)
                report["chunks"].append(chunk)
                report.pop("pending_request")
            report["status"] = "SAMPLES_CAPTURED"
    except DiagnosticError as error:
        report["status"] = error.reason
        report["connection_api_code"] = error.api_code
    except RuntimeError as error:
        report["status"] = "DEMO_CONNECTION_REJECTED"
        report["connection_detail"] = str(error)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New JSON evidence file")
    args = parser.parse_args()

    def progress(index, total, start):
        print(f"Request {index}/{total}, raw seconds {start} through "
              f"{start + CHUNK_SECONDS - 1}", file=sys.stderr, flush=True)

    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        def checkpoint(report):
            payload = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)
            output.seek(0)
            output.write(payload + "\n")
            output.truncate()
            output.flush()

        checkpoint(capture(progress=progress, checkpoint=checkpoint))
    return 1  # Samples cannot authorize historical execution.


if __name__ == "__main__":
    raise SystemExit(main())
