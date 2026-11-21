"""Compute causal indicators from GoldBot's offline closed-candle exports."""

import argparse
import csv
from math import fsum, isfinite, nan
from pathlib import Path

from goldbot.analysis.data_analysis import EXPECTED_ROWS, INTERVALS, analyze

SMA_PERIODS = (20, 50, 200)
EMA_PERIODS = (9, 21, 50, 200)


def _validate(closes, period):
    if type(period) is not int or period < 1:
        raise ValueError("period must be a positive integer")
    closes = tuple(closes)
    if any(isinstance(close, bool) or not isinstance(close, (int, float))
           or not isfinite(close) or close <= 0 for close in closes):
        raise ValueError("closes must be finite positive numbers")
    return closes


def _mean(values, period):
    return fsum(value / period for value in values)


def sma(closes, period):
    """Return a trailing mean including the current close, with warm-up NaNs."""
    closes = _validate(closes, period)
    return [nan] * min(len(closes), period - 1) + [
        _mean(closes[end - period:end], period)
        for end in range(period, len(closes) + 1)
    ]


def ema(closes, period):
    """Seed with the first period's SMA, then apply alpha = 2 / (period + 1)."""
    closes = _validate(closes, period)
    return _smooth(closes, period, 2 / (period + 1))


def _smooth(samples, period, alpha):
    if len(samples) < period:
        return [nan] * len(samples)
    values = [nan] * (period - 1)
    values.append(_mean(samples[:period], period))
    for sample in samples[period:]:
        previous = values[-1]
        values.append(previous + alpha * (sample - previous))
    return values


def rsi(closes, period=14):
    """Wilder RSI, with a neutral value of 50 when both averages are zero."""
    closes = _validate(closes, period)
    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = _smooth([max(change, 0) for change in changes], period, 1 / period)
    losses = _smooth([max(-change, 0) for change in changes], period, 1 / period)
    values = [nan] * min(len(closes), period)
    for gain, loss in zip(gains[period - 1:], losses[period - 1:]):
        if loss == 0:
            values.append(50.0 if gain == 0 else 100.0)
        else:
            values.append(100 - 100 / (1 + gain / loss))
    return values


def macd(closes):
    """Return aligned MACD(12,26,9) line, signal and histogram lists."""
    closes = _validate(closes, 26)
    fast = _smooth(closes, 12, 2 / 13)
    slow = _smooth(closes, 26, 2 / 27)
    line = [short - long for short, long in zip(fast, slow)]
    signal = [nan] * min(len(closes), 25) + _smooth(line[25:], 9, 2 / 10)
    histogram = [value - average for value, average in zip(line, signal)]
    return line, signal, histogram


def atr(highs, lows, closes, period=14):
    """Wilder ATR seeded with the first N true ranges, including high-low at row one."""
    highs = _validate(highs, period)
    lows = _validate(lows, period)
    closes = _validate(closes, period)
    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs, lows and closes must have the same length")
    ranges = []
    for index, (high, low, close) in enumerate(zip(highs, lows, closes)):
        if not low <= close <= high:
            raise ValueError("each close must be between its low and high")
        if index == 0:
            ranges.append(high - low)
        else:
            previous_close = closes[index - 1]
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return _smooth(ranges, period, 1 / period)


def derive(path, timeframe, expected_rows=EXPECTED_ROWS, *, phase_3_3=False):
    """Validate the export and derive columns in original row order."""
    interval = INTERVALS[timeframe]
    result = analyze(path, timeframe)
    if (result["rows"] != expected_rows or expected_rows < 1
            or any(result[key] for key in ("malformed", "nonpositive", "inconsistent", "unchecked"))
            or any(result["issues"].values())
            or any(delta <= 0 or delta % interval for delta in result["deltas"])):
        raise ValueError(f"{path}: {timeframe} failed closed-candle export validation")
    labels = list(result["timestamps"])
    closes = result["prices"]["close"]
    deltas = [None] + [current - previous for previous, current in zip(labels, labels[1:])]
    columns = {
        "raw_server_clock_label": labels,
        "raw_label_delta": deltas,
        "gap_before": [delta is not None and delta > interval for delta in deltas],
        "close": closes,
    }
    columns.update({f"sma_{period}": sma(closes, period) for period in SMA_PERIODS})
    columns.update({f"ema_{period}": ema(closes, period) for period in EMA_PERIODS})
    if phase_3_3:
        line, signal, histogram = macd(closes)
        columns.update(
            rsi_14=rsi(closes),
            macd_12_26=line,
            macd_signal_9=signal,
            macd_histogram=histogram,
            atr_14=atr(result["prices"]["high"], result["prices"]["low"], closes),
        )
    return columns, result["sha256"]


def write_csv(path, columns):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(zip(*columns.values()))


def write_chart(path, timeframe, columns, *, phase_3_3=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator, StrMethodFormatter

    labels = columns["raw_server_clock_label"]
    gaps = columns["gap_before"]
    # Insert plot breaks only. The calculations and CSV retain observed candles only.
    indices = [index for index, gap in enumerate(gaps) for _ in range(1 + gap)]
    breaks = [left == right for left, right in zip(indices, indices[1:])] + [False]
    x = [labels[index] for index in indices]
    if phase_3_3:
        panels = [
            ("RSI (0–100)", ["rsi_14"]),
            ("MACD (price units)", ["macd_12_26", "macd_signal_9", "macd_histogram"]),
            ("ATR (price units)", ["atr_14"]),
        ]
    else:
        panels = [
            ("XAUUSD price", ["close"] + [name for name in columns if name.startswith(prefix)])
            for prefix in ("sma_", "ema_")
        ]
    figure, axes = plt.subplots(len(panels), 1, sharex=True, figsize=(15, 8), layout="constrained")
    try:
        for axis, (unit, names) in zip(axes, panels):
            for name in names:
                series = columns[name]
                y = [nan if gap else series[index] for index, gap in zip(indices, breaks)]
                style = {"color": "#475569", "alpha": 0.6} if name == "close" else {}
                axis.plot(x, y, label=name.upper().replace("_", " "), linewidth=0.9, **style)
            axis.set_ylabel(unit)
            if unit.startswith("RSI"):
                axis.set_ylim(0, 100)
            axis.grid(alpha=0.2)
            axis.legend(ncol=len(names), loc="best")
        axes[-1].xaxis.set_major_locator(MaxNLocator(7, integer=True))
        axes[-1].xaxis.set_major_formatter(StrMethodFormatter("{x:.0f}"))
        axes[-1].set_xlabel("Raw server-clock label (mt5_time_epoch)")
        figure.suptitle(f"XAUUSD {timeframe} closed candles | {sum(gaps)} raw label gaps break the lines")
        figure.savefig(path, dpi=150)
    finally:
        plt.close(figure)


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--phase-3-3", action="store_true", help="include RSI, MACD and ATR")
    parser.add_argument("--charts", action="store_true", help="also generate offline PNGs using Matplotlib")
    args = parser.parse_args()
    output_dir = args.output_dir or root / "reports" / (
        "indicators_phase_3_3" if args.phase_3_3 else "indicators"
    )
    suffix = "indicators_phase_3_3" if args.phase_3_3 else "indicators"
    results = {
        timeframe: derive(args.data_dir / f"XAUUSD_{timeframe}.csv", timeframe,
                          phase_3_3=args.phase_3_3)
        for timeframe in INTERVALS
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for timeframe, (columns, digest) in results.items():
        destination = output_dir / f"XAUUSD_{timeframe}_{suffix}.csv"
        write_csv(destination, columns)
        print(f"{destination}: {len(columns['close'])} rows, {sum(columns['gap_before'])} gaps, source SHA-256 {digest}")
        if args.charts:
            chart = destination.with_suffix(".png")
            write_chart(chart, timeframe, columns, phase_3_3=args.phase_3_3)
            print(chart)


if __name__ == "__main__":
    main()
