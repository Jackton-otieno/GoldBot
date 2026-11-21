"""Generate deterministic Phase 4.1 reports from Phase 3.3 CSV exports."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from math import isnan
from pathlib import Path

from goldbot.analysis.data_analysis import INTERVALS
from goldbot.strategy.strategy import Indicators, evaluate

FIRST_VALID = {
    "ema_9": 9, "ema_21": 21, "ema_50": 50, "ema_200": 200,
    "rsi_14": 15, "macd_histogram": 34, "atr_14": 14,
}
PHASE_33_FIELDS = (
    "raw_server_clock_label", "raw_label_delta", "gap_before", "close",
    "sma_20", "sma_50", "sma_200", "ema_9", "ema_21", "ema_50", "ema_200",
    "rsi_14", "macd_12_26", "macd_signal_9", "macd_histogram", "atr_14",
)
REPORT_FIELDS = ("source_row", *PHASE_33_FIELDS, "decision", "reasons")


def signal_rows(source, timeframe):
    """Yield results in source order, with one-based candle row numbers."""
    interval = INTERVALS[timeframe]
    reader = csv.DictReader(source, strict=True)
    if tuple(reader.fieldnames or ()) != PHASE_33_FIELDS:
        raise ValueError("Unexpected Phase 3.3 CSV header")

    previous = None
    previous_label = None
    for number, row in enumerate(reader, 1):
        try:
            if None in row or None in row.values():
                raise ValueError("unexpected number of columns")
            label = int(row["raw_server_clock_label"])
            delta = None if previous_label is None else label - previous_label
            expected_delta = "" if delta is None else str(delta)
            gap = delta is not None and delta > interval
            if (
                label <= 0 or row["raw_label_delta"] != expected_delta
                or (delta is not None and (delta <= 0 or delta % interval))
                or row["gap_before"] != str(gap)
            ):
                raise ValueError("inconsistent raw label, delta, or gap flag")

            inputs = {field: float(row[field]) for field in FIRST_VALID}
            if any(isnan(inputs[field]) != (number < first)
                   for field, first in FIRST_VALID.items()):
                raise ValueError("unexpected indicator warm-up value")
            current = Indicators(**inputs)
            signal = evaluate(current, previous, gap_before=gap)
            if signal.reasons == ("INVALID_INPUT",):
                raise ValueError("invalid strategy indicator")
        except ValueError as error:
            raise ValueError(f"{timeframe} source row {number}: {error}") from error

        yield dict(source_row=number, **row, decision=signal.decision,
                   reasons="|".join(signal.reasons))
        previous = current
        previous_label = label


def generate_report(source, output, timeframe):
    raw = source.read_bytes()
    rows = list(signal_rows(io.StringIO(raw.decode("utf-8-sig"), newline=""), timeframe))
    if not rows:
        raise ValueError(f"{source}: no candle rows")

    decisions = Counter(row["decision"] for row in rows)
    reasons = Counter(reason for row in rows for reason in row["reasons"].split("|"))
    summary = {
        "timeframe": timeframe,
        "source": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows),
        "raw_label_gaps": sum(row["gap_before"] == "True" for row in rows),
        "decisions": {key: decisions[key] for key in ("BUY", "SELL", "HOLD")},
        "reasons": dict(reasons),
    }
    output.mkdir(parents=True, exist_ok=True)
    stem = f"XAUUSD_{timeframe}_signals_phase_4_1"
    with (output / f"{stem}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, REPORT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with (output / f"{stem}_counts.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reports = args.root / "reports"
    output = args.output or reports / "signals_phase_4_1"
    for timeframe in INTERVALS:
        source = reports / "indicators_phase_3_3" / f"XAUUSD_{timeframe}_indicators_phase_3_3.csv"
        summary = generate_report(source, output, timeframe)
        print(f"{timeframe}: {summary['rows']} rows, {summary['decisions']}")


if __name__ == "__main__":
    main()
