"""Collect bounded read-only clock, quote and history evidence from MT5 demo."""

import argparse
import json
import math
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import MetaTrader5 as mt5

from goldbot.core.config import SYMBOL
from goldbot.core.connection import demo_connection


NIST = "time.nist.gov"
EXPECTED_SERVER = "MetaQuotes-Demo"
CLOCK_TOLERANCE = 2.0
SOURCE_ALLOWANCE = 1.0
WALL_STEP_TOLERANCE = 0.1
HISTORY_LIMIT = 128
BAR_LIMIT = 16


def mark():
    return {"monotonic": time.monotonic(), "wall_utc": datetime.now(timezone.utc).isoformat()}


def wall(marking):
    return datetime.fromisoformat(marking["wall_utc"])


def clock_bounds(line, before, after):
    """Bound real UTC minus host wall time at a healthy NIST observation."""
    mjd, date, stamp, _, leap, health, advance, source, marker = line.split()
    if (leap != "0" or health != "0" or source != "UTC(NIST)" or marker != "*"):
        raise ValueError("NIST status or on-time marker invalid")
    advance = float(advance)
    if not 0 <= advance <= 1000:
        raise ValueError("Invalid NIST advance")
    tag = datetime.strptime(f"{date} {stamp}", "%y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    if (tag - datetime(1858, 11, 17, tzinfo=timezone.utc)).days != int(mjd):
        raise ValueError("NIST date fields disagree")
    elapsed = after["monotonic"] - before["monotonic"]
    wall_elapsed = (wall(after) - wall(before)).total_seconds()
    if not 0 <= elapsed <= 5 or abs(wall_elapsed - elapsed) > WALL_STEP_TOLERANCE:
        raise ValueError("Invalid clock bracket")
    sent = tag - timedelta(milliseconds=advance)
    allowance = SOURCE_ALLOWANCE + WALL_STEP_TOLERANCE
    return [(sent - wall(after)).total_seconds() - allowance,
            (sent - wall(before)).total_seconds() + allowance]


def clock_probe():
    before = mark()
    result = {"source": NIST, "protocol": "TCP Daytime", "before": before}
    try:
        with socket.create_connection((NIST, 13), timeout=3) as peer:
            message = b""
            while b"*" not in message and len(message) < 128:
                peer.settimeout(max(0.001, 3 - (time.monotonic() - before["monotonic"])))
                chunk = peer.recv(128 - len(message))
                if not chunk:
                    break
                message += chunk
        result["after"] = mark()
        result["response"] = message.decode("ascii").strip()
        result["correction_bounds_s"] = clock_bounds(result["response"], before, result["after"])
    except (OSError, ValueError) as exc:
        result["after"] = mark()
        result["error"] = type(exc).__name__
    return result


def assess_clock(first, last, samples):
    bounds = [probe.get("correction_bounds_s") for probe in (first, last)]
    if any(bound is None for bound in bounds):
        return {"status": "INDEPENDENT_TIME_UNAVAILABLE"}
    origin = first["before"]
    marks = [sample[key] for sample in samples for key in ("before", "after")]
    marks.extend((first["after"], last["before"], last["after"]))
    if any(abs((wall(item) - wall(origin)).total_seconds()
               - (item["monotonic"] - origin["monotonic"])) > WALL_STEP_TOLERANCE
           for item in marks):
        return {"status": "WALL_CLOCK_DISCONTINUITY"}
    if max(bound[0] for bound in bounds) > min(bound[1] for bound in bounds):
        return {"status": "INDEPENDENT_TIME_DISAGREES"}
    lower = min(bound[0] for bound in bounds) - WALL_STEP_TOLERANCE
    upper = max(bound[1] for bound in bounds) + WALL_STEP_TOLERANCE
    return {"status": ("UTC_WITHIN_TOLERANCE" if -CLOCK_TOLERANCE <= lower <= upper
                       <= CLOCK_TOLERANCE else "CLOCK_ERROR_OR_UNCERTAINTY_TOO_LARGE"),
            "correction_bounds_s": [lower, upper], "tolerance_s": CLOCK_TOLERANCE}


def connected():
    terminal = mt5.terminal_info()
    return None if terminal is None else bool(terminal.connected)


def tick_fields(tick):
    return {"raw_s": int(tick.time), "raw_ms": int(tick.time_msc),
            "bid": float(tick.bid) if math.isfinite(tick.bid) else None,
            "ask": float(tick.ask) if math.isfinite(tick.ask) else None,
            "flags": int(tick.flags)}


def valid_tick(tick):
    return (tick["raw_s"] > 0 and tick["raw_ms"] // 1000 == tick["raw_s"]
            and tick["bid"] is not None and tick["ask"] is not None
            and 0 < tick["bid"] <= tick["ask"])


def quote_state(samples):
    if not samples or any(sample["connected_before"] is not True
                          or sample["connected_after"] is not True for sample in samples):
        return "DISCONNECTED_OR_UNAVAILABLE"
    ticks = [sample["tick"] for sample in samples]
    if any(tick is None or not valid_tick(tick) for tick in ticks):
        return "INVALID_OR_MISSING_QUOTE"
    times = [tick["raw_ms"] for tick in ticks]
    if any(a > b for a, b in zip(times, times[1:])):
        return "RAW_TIME_REGRESSED"
    if len(set(times)) == 1:
        return "STATIC_TIMESTAMP"
    if len({(tick["bid"], tick["ask"]) for tick in ticks}) == 1:
        return "TIMESTAMP_ADVANCED_PRICE_STATIC"
    return "TIMESTAMP_AND_PRICES_ADVANCED_FRESHNESS_UNVERIFIED"


def history_evidence(tick):
    """Compare records in raw coordinates, using capped read-only requests."""
    result = {"before": mark(), "connected_before": connected(),
              "tick_limit": HISTORY_LIMIT, "bar_limit": BAR_LIMIT}
    if result["connected_before"] is not True:
        return result
    ticks = mt5.copy_ticks_from(SYMBOL, tick["raw_s"], HISTORY_LIMIT, mt5.COPY_TICKS_ALL)
    result["tick_error_code"] = mt5.last_error()[0] if ticks is None else None
    bars = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, BAR_LIMIT)
    result["bar_error_code"] = mt5.last_error()[0] if bars is None else None
    result["connected_after"] = connected()
    result["after"] = mark()
    result["tick_count"] = None if ticks is None else len(ticks)
    result["bar_count"] = None if bars is None else len(bars)
    result["tick_rows"] = [] if ticks is None else [
        tick_fields(SimpleNamespace(**{name: row[name]
                                      for name in ("time", "time_msc", "bid", "ask", "flags")}))
        for row in ticks[:HISTORY_LIMIT]
    ]
    result["timestamp_price_matches"] = [
        row for row in result["tick_rows"]
        if all(row[key] == tick[key] for key in ("raw_s", "raw_ms", "bid", "ask"))
    ]
    result["exact_tick_matches"] = [row for row in result["timestamp_price_matches"]
                                    if row["flags"] == tick["flags"]]
    result["raw_bar_opens"] = [] if bars is None else [int(row["time"]) for row in bars[:BAR_LIMIT]]
    result["matching_raw_minute_bar_opens"] = [
        raw for raw in result["raw_bar_opens"] if 0 <= tick["raw_s"] - raw < 60
    ]
    return result


def observe(samples, interval):
    records = []
    previous = None
    for index in range(samples):
        before, connected_before = mark(), connected()
        tick = mt5.symbol_info_tick(SYMBOL) if connected_before is True else None
        error = mt5.last_error()[0] if connected_before is True and tick is None else None
        connected_after, after = connected(), mark()
        fields = None if tick is None else tick_fields(tick)
        records.append({"before": before, "after": after, "connected_before": connected_before,
                        "connected_after": connected_after, "tick": fields, "error_code": error,
                        "raw_ms_delta": None if previous is None or fields is None else
                        fields["raw_ms"] - previous["raw_ms"],
                        "bid_ask_changed": None if previous is None or fields is None else
                        (fields["bid"], fields["ask"]) != (previous["bid"], previous["ask"])})
        previous = fields
        if connected_before is not True or connected_after is not True:
            break
        if index + 1 < samples:
            time.sleep(interval)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--expected-server", default=EXPECTED_SERVER)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (2 <= args.samples <= 600 and 0.1 <= args.interval <= 60
            and (args.samples - 1) * args.interval <= 120):
        parser.error("Use 2–600 samples, 0.1–60 seconds apart, spanning at most 120 seconds")

    first = clock_probe()
    report = {"symbol": SYMBOL, "status": "REJECTED", "samples": [],
              "timestamp_convention": "UNVERIFIED", "session_status": "UNVERIFIED"}
    try:
        with demo_connection() as account:
            if account.server != args.expected_server:
                raise RuntimeError("Expected demo server mismatch.")
            report["samples"] = observe(args.samples, args.interval)
            final = report["samples"][-1]
            if final["connected_after"] is True and final["tick"] and valid_tick(final["tick"]):
                report["history"] = history_evidence(final["tick"])
    except RuntimeError as exc:
        report["connection_error"] = str(exc)
    last = clock_probe()
    report["external_clock_probes"] = [first, last]
    report["clock"] = assess_clock(first, last, report["samples"])
    report["quote_state"] = quote_state(report["samples"])
    report["reasons"] = [report["quote_state"], report["clock"]["status"],
                         "NO_VERIFIED_SERVER_TIMESTAMP_CONVENTION_OR_OFFSET_WINDOW"]
    payload = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
