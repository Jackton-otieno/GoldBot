"""Offline validation of the original GoldBot candle exports."""

import argparse
import csv
import hashlib
import io
from collections import Counter
from math import isfinite
from pathlib import Path
from statistics import mean, median, stdev

FIELDS = ("mt5_time_epoch", "open", "high", "low", "close",
          "tick_volume", "spread", "real_volume")
PRICES = FIELDS[1:5]
INTERVALS = {"M15": 900, "H1": 3600}
EXPECTED_ROWS = 10_000


def describe(values):
    if not values:
        return "unavailable"
    deviation = f"{stdev(values):.6g}" if len(values) > 1 else "unavailable"
    return (f"n={len(values):,}, min={min(values):.8g}, median={median(values):.8g}, "
            f"mean={mean(values):.8g}, max={max(values):.8g}, sample SD={deviation}")


def analyze(path, timeframe):
    interval = INTERVALS[timeframe]
    source = path.read_bytes()
    reader = csv.reader(io.StringIO(source.decode("utf-8-sig"), newline=""), strict=True)
    if tuple(next(reader, ())) != FIELDS:
        raise ValueError(f"{path}: unexpected CSV header")

    issues = {kind: Counter() for kind in ("Missing", "Nonfinite", "Invalid")}
    prices = {field: [] for field in PRICES}
    timestamps = Counter()
    deltas = Counter()
    returns = {"Nominal-interval pairs": [], "Longer-interval pairs": []}
    gaps = []
    rows = malformed = nonpositive = inconsistent = unchecked = invalid_returns = 0
    previous_time = previous_close = last_label = None

    for rows, record in enumerate(reader, start=1):
        malformed += len(record) != len(FIELDS)
        values = {}
        for index, field in enumerate(FIELDS):
            raw = record[index].strip() if index < len(record) else ""
            if not raw:
                issues["Missing"][field] += 1
                continue
            try:
                value = float(raw) if field in PRICES else int(raw)
            except ValueError:
                try:
                    nonfinite = not isfinite(float(raw))
                except ValueError:
                    nonfinite = False
                issues["Nonfinite" if nonfinite else "Invalid"][field] += 1
                continue
            if field in PRICES and not isfinite(value):
                issues["Nonfinite"][field] += 1
                continue
            if (field == FIELDS[0] and value <= 0) or (field in FIELDS[5:] and value < 0):
                issues["Invalid"][field] += 1
                continue
            values[field] = value

        ohlc = [values.get(field) for field in PRICES]
        nonpositive += any(value is not None and value <= 0 for value in ohlc)
        if None in ohlc:
            unchecked += 1
        else:
            opening, high, low, close = ohlc
            inconsistent += not low <= min(opening, close) <= max(opening, close) <= high
        for field in PRICES:
            if field in values and values[field] > 0:
                prices[field].append(values[field])

        timestamp = values.get(FIELDS[0])
        close = values.get("close")
        close = close if close is not None and close > 0 else None
        if timestamp is not None:
            timestamps[timestamp] += 1
            last_label = timestamp
        if previous_time is not None and timestamp is not None:
            delta = timestamp - previous_time
            deltas[delta] += 1
            if delta > interval:
                gaps.append((delta, rows - 1, previous_time, timestamp))
            if delta >= interval and previous_close is not None and close is not None:
                change = 100 * (close / previous_close - 1)
                if isfinite(change):
                    key = "Nominal-interval pairs" if delta == interval else "Longer-interval pairs"
                    returns[key].append(change)
                else:
                    invalid_returns += 1
        previous_time, previous_close = timestamp, close

    return {
        "sha256": hashlib.sha256(source).hexdigest(), "rows": rows, "malformed": malformed,
        "issues": issues, "prices": prices, "timestamps": timestamps, "last_label": last_label, "deltas": deltas,
        "returns": returns, "gaps": gaps, "nonpositive": nonpositive,
        "inconsistent": inconsistent, "unchecked": unchecked, "invalid_returns": invalid_returns,
    }


def render(result, path, timeframe):
    interval = INTERVALS[timeframe]
    timestamps = result["timestamps"]
    deltas = result["deltas"]
    gaps = result["gaps"]
    lines = [
        f"# XAUUSD {timeframe} data validation", "",
        f"Input `{path.name}`  ",
        f"SHA-256 `{result['sha256']}`  ",
        f"CSV data rows **{result['rows']:,}** of {EXPECTED_ROWS:,} expected  ",
        f"Rows with unexpected field count **{result['malformed']:,}**", "",
        "## Field and OHLC checks", "",
        "| Field | Missing or blank | Nonfinite | Invalid type or domain |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in FIELDS:
        counts = [counter[field] for counter in result["issues"].values()]
        lines.append(f"| {field} | {counts[0]} | {counts[1]} | {counts[2]} |")
    lines.extend([
        "", f"- Rows with a nonpositive OHLC price: {result['nonpositive']:,}",
        f"- Rows violating low ≤ open/close ≤ high: {result['inconsistent']:,}",
        f"- Rows with insufficient finite prices for the OHLC check: {result['unchecked']:,}",
        "", "## Raw server-clock labels", "",
        "The integer `mt5_time_epoch` values are treated as raw server-clock labels. "
        "The checks use original file order and arithmetic differences between neighboring labels. "
        "The server offset and DST behavior are unverified. Differences can reflect clock shifts, "
        "session breaks, missing observations, or other causes. The two timeframes are analyzed independently.",
        "",
    ])
    if timestamps:
        lines.append(f"- First and last valid labels in file order: `{next(iter(timestamps))}` and "
                     f"`{result['last_label']}`")
    lines.extend([
        f"- Repeated labels (distinct / extra occurrences): "
        f"{sum(count > 1 for count in timestamps.values()):,} / "
        f"{sum(count - 1 for count in timestamps.values()):,}",
        f"- Backward / equal adjacent pairs: {sum(n for d, n in deltas.items() if d < 0):,} / {deltas[0]:,}",
        f"- Adjacent pairs with an unusable label: {max(result['rows'] - 1, 0) - sum(deltas.values()):,}",
        f"- Nominal / shorter positive / longer differences: {deltas[interval]:,} / "
        f"{sum(n for d, n in deltas.items() if 0 < d < interval):,} / {len(gaps):,}",
        f"- Positive differences off the {interval:,}-second grid: "
        f"{sum(n for d, n in deltas.items() if d > 0 and d % interval):,}",
        "", "| Adjacent label difference (seconds) | Pairs |", "| ---: | ---: |",
    ])
    lines.extend(f"| {delta:,} | {count:,} |" for delta, count in sorted(deltas.items()))
    if gaps:
        lines.extend([
            "", "Ten largest gaps by raw label difference, with ties in file order.", "",
            "| Seconds | Data row after gap | Previous raw label | Next raw label |",
            "| ---: | ---: | ---: | ---: |",
        ])
        for delta, row, before, after in sorted(gaps, key=lambda gap: -gap[0])[:10]:
            lines.append(f"| {delta:,} | {row + 1:,} | `{before}` | `{after}` |")
    lines.extend(["", "## OHLC price statistics", "", "Finite positive observations per field.", ""])
    lines.extend(f"- {field}: {describe(values)}" for field, values in result["prices"].items())
    lines.extend([
        "", "## Close-to-close returns and volatility", "",
        "Simple returns in percent use consecutive CSV rows with finite positive closes. "
        "Pairs with unusable labels, backward or repeated labels, or shorter positive differences "
        "are excluded. Longer differences may span unequal amounts of elapsed time and are summarized separately. "
        "Volatility is the sample standard deviation in percentage points, without annualization.",
        "",
    ])
    lines.extend(f"- {label}: {describe(values)}" for label, values in result["returns"].items())
    lines.append(f"- Eligible pairs with a nonfinite computed return: {result['invalid_returns']:,}")
    return "\n".join(lines) + "\n"


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data")
    parser.add_argument("--report-dir", type=Path, default=root / "reports")
    args = parser.parse_args()
    reports = {}
    for timeframe in INTERVALS:
        path = args.data_dir / f"XAUUSD_{timeframe}.csv"
        result = analyze(path, timeframe)
        reports[timeframe] = render(result, path, timeframe)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    for timeframe, report in reports.items():
        destination = args.report_dir / f"XAUUSD_{timeframe}_validation.md"
        destination.write_text(report, encoding="utf-8")
        print(destination)


if __name__ == "__main__":
    main()

