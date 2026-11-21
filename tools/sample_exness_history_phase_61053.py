"""Retrieve small, read-only Exness XAUUSD tick chunks in raw coordinates."""

import argparse
import json
from pathlib import Path
import sys

from goldbot.core.exness_demo import VerificationError, running_terminals
from goldbot.market_data.tick_data import audit_ticks
from tools.collect_exness_phase_695 import Reader, RetryableRead
from tools.verify_exness_precision_phase_61051 import INSTALLATION, confirmed_profile
from tools.verify_exness_time_history import SERVER, SUFFIX, SYMBOL


LIMIT = 256


def audit_capture(chunk):
    ticks = chunk.get("ticks", [])
    start_ms = chunk["request_start_raw_s"] * 1000
    audit = audit_ticks(ticks)
    labels = [tick["time_msc"] for tick in ticks]
    repeated = len(ticks) - len({tuple(sorted(tick.items())) for tick in ticks})
    return dict(status=chunk["status"], rows=len(ticks), repeated_payload_rows=repeated,
                observations=audit.observations,
                issues=[dict(index=issue.index, code=issue.code) for issue in audit.issues],
                largest_raw_spacing_ms=audit.largest_raw_spacing_ms,
                first_raw_ms=labels[0] if labels else None,
                last_raw_ms=labels[-1] if labels else None,
                first_minus_request_ms=labels[0] - start_ms if labels else None,
                count_limit_reached=chunk.get("count_limit_reached", False),
                error_code=chunk.get("error_code"),
                utc_mapping="UNVERIFIED", coverage="UNVERIFIED")


def sample(reader, profile, anchors):
    if (profile.server != SERVER or not str(profile.login).endswith(SUFFIX)
            or profile.terminal.resolve() != INSTALLATION.resolve()):
        raise VerificationError("Expected the exact independently pinned Exness installation and demo.")
    try:
        identity = reader.attach()
        captures = []
        for start in anchors:
            chunk = {"request_start_raw_s": start, "requested_count": LIMIT}
            try:
                rows, timing = reader.read(reader.api.copy_ticks_from, SYMBOL, start, LIMIT,
                                           reader.api.COPY_TICKS_ALL)
            except RetryableRead as error:
                reader.identity()
                captures.append(dict(chunk, status="UNAVAILABLE", error_code=error.error_code))
                continue
            if len(rows) > LIMIT:
                raise VerificationError("History exceeded the requested count.")
            data = [{name: row[name].item() for name in rows.dtype.names} for row in rows]
            captures.append(dict(chunk, status="RETURNED", timing=timing, ticks=data,
                                 count_limit_reached=len(rows) == LIMIT))
        return dict(identity=identity, captures=captures)
    finally:
        reader.api.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anchor", type=int, action="append", required=True)
    args = parser.parse_args()
    if not 1 <= len(args.anchor) <= 2 or any(value <= 0 for value in args.anchor):
        parser.error("Supply one or two positive raw-second anchors.")
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        try:
            profile = confirmed_profile(sys.stdin)
            import MetaTrader5 as mt5

            report = sample(Reader(mt5, profile, running_terminals), profile, args.anchor)
        except VerificationError as error:
            report = dict(status="STOPPED", reason=str(error), captures=[])
        json.dump(report, output, sort_keys=True, indent=2, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()
