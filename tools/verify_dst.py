"""Compare broker demo M1 weekend gaps with US and EU DST hypotheses."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from goldbot.core.config import SYMBOL
from goldbot.core.connection import demo_connection


CME_REFERENCE = "https://www.cmegroup.com/trading/metals/files/metals-prod-guide-2022.pdf"
UTC = timezone.utc
CHICAGO = ZoneInfo("America/Chicago")
EUROPE = ZoneInfo("Europe/Berlin")


def dst_hours(sunday, zone):
    return int(sunday.astimezone(zone).dst() / timedelta(hours=1))


def weeks(year, today):
    sunday = datetime(year, 1, 1, 12, tzinfo=UTC)
    sunday += timedelta(days=(6 - sunday.weekday()) % 7)
    while sunday.year == year and sunday + timedelta(days=1) < today:
        if any(dst_hours(day, CHICAGO) != dst_hours(day, EUROPE)
               for day in (sunday - timedelta(days=7), sunday, sunday + timedelta(days=7))):
            yield sunday
        sunday += timedelta(days=7)


def sample_week(symbol, sunday):
    # These integers explore raw coordinates around the calendar weekend.
    # They do not assert that the terminal's history bounds are UTC.
    start = int(sunday.timestamp()) - 2 * 86400
    end = int(sunday.timestamp()) + 86400
    cme_open = sunday.astimezone(CHICAGO).replace(hour=17).astimezone(UTC)
    sample = {"week": sunday.date().isoformat(), "request_raw_s": [start, end],
              "cme_proxy_open_utc": cme_open.isoformat(),
              "us_dst_hours": dst_hours(cme_open, CHICAGO),
              "eu_dst_hours": dst_hours(cme_open, EUROPE)}
    terminal = mt5.terminal_info()
    if terminal is None or not terminal.connected:
        return dict(sample, status="DISCONNECTED")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
    if rates is None:
        return dict(sample, status="HISTORY_UNAVAILABLE", error_code=mt5.last_error()[0])
    terminal = mt5.terminal_info()
    if terminal is None or not terminal.connected:
        return dict(sample, status="DISCONNECTED")
    if len(rates) > (end - start) // 60 + 1:
        return dict(sample, status="EXCESS_HISTORY", bar_count=len(rates))
    raw = [int(row["time"]) for row in rates]
    summary = dict(sample, bar_count=len(raw), first_raw_s=raw[0] if raw else None,
                   last_raw_s=raw[-1] if raw else None)
    if len(raw) < 2:
        return dict(summary, status="INSUFFICIENT_HISTORY")
    if (raw[0] < start or raw[-1] > end or any(a >= b for a, b in zip(raw, raw[1:]))):
        return dict(summary, status="RAW_RANGE_OR_ORDER_INVALID")
    gaps = [(before, after) for before, after in zip(raw, raw[1:])
            if 86400 < after - before < 60 * 3600]
    if len(gaps) != 1:
        return dict(summary, status="AMBIGUOUS_GAP", candidate_count=len(gaps))
    before, after = gaps[0]
    return dict(summary, status="PROXY_SAMPLE", gap_raw_s=[before, after],
                raw_minus_cme_proxy_s=after - int(cme_open.timestamp()))


def compare(samples, zone):
    valid = [sample for sample in samples if sample["status"] == "PROXY_SAMPLE"]
    states = {sample[f"{zone}_dst_hours"] for sample in valid}
    deltas = sorted({sample["raw_minus_cme_proxy_s"] - 3600 * sample[f"{zone}_dst_hours"]
                     for sample in valid})
    return {"sample_count": len(valid), "dst_states": sorted(states),
            "proxy_residuals_s": deltas,
            "proxy_pattern_matches": states == {0, 1} and len(deltas) == 1}


def collect(year, symbol, today):
    samples = []
    for sunday in weeks(year, today):
        sample = sample_week(symbol, sunday)
        samples.append(sample)
        if sample["status"] == "DISCONNECTED":
            break
    return {"samples": samples, "hypotheses": {zone.upper(): compare(samples, zone)
                                                for zone in ("us", "eu")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    today = datetime.now(UTC)
    parser.add_argument("--year", type=int, default=today.year)
    parser.add_argument("--server", default="MetaQuotes-Demo")
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 2007 <= args.year <= today.year:
        parser.error("year must be between 2007 and the current year")
    report = {"year": args.year, "symbol": args.symbol, "status": "UNVERIFIED",
              "cme_proxy_reference": CME_REFERENCE, "broker_session_schedule": "UNAVAILABLE",
              "broker_timestamp_convention": "UNVERIFIED", "samples": []}
    try:
        with demo_connection() as account:
            if account.server != args.server:
                raise RuntimeError("Expected demo server mismatch.")
            report.update(collect(args.year, args.symbol, today))
    except RuntimeError as error:
        report["connection_error"] = str(error)
    payload = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
