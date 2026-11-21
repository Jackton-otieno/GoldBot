"""Build the offline Phase 6.10.3 closed-candle research ledger."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import groupby
import json
from pathlib import Path
from statistics import fmean, pstdev
from typing import NamedTuple

from goldbot.analysis.data_analysis import EXPECTED_ROWS
from goldbot.analysis.indicators import ema, rsi
from goldbot.backtesting.historical_replay import ORIGINAL_DIGESTS, _validated_rows


REPORT = Path("reports/phase_6_10_3")
READINESS = Path("reports/phase_6_9_6/assessment.json")
WINDOW = 20
RSI_PERIOD = 14


class Candle(NamedTuple):
    label: int
    delta: int | None
    gap: bool
    high: float
    low: float
    close: float


def direction(buy, sell):
    return "BUY" if buy else "SELL" if sell else "HOLD"


def trend_pullback(candles):
    closes = [bar.close for bar in candles]
    averages = ema(closes, WINDOW)
    momentum = rsi(closes, RSI_PERIOD)
    for index, close in enumerate(closes):
        if index < WINDOW:
            yield "WARMUP"
            continue
        previous, current = averages[index - 1:index + 1]
        yield direction(
            current > previous and closes[index - 1] <= previous and close > current
            and momentum[index] > 50,
            current < previous and closes[index - 1] >= previous and close < current
            and momentum[index] < 50,
        )


def donchian_breakout(candles):
    for index, bar in enumerate(candles):
        if index < WINDOW:
            yield "WARMUP"
            continue
        prior = candles[index - WINDOW:index]
        yield direction(bar.close > max(item.high for item in prior),
                        bar.close < min(item.low for item in prior))


def bollinger_reversion(candles):
    closes = [bar.close for bar in candles]
    momentum = rsi(closes, RSI_PERIOD)
    for index, close in enumerate(closes):
        if index + 1 < max(WINDOW, RSI_PERIOD + 1):
            yield "WARMUP"
            continue
        window = closes[index + 1 - WINDOW:index + 1]
        center = fmean(window)
        deviation = pstdev(window)
        yield direction(close < center - 2 * deviation and momentum[index] <= 30,
                        close > center + 2 * deviation and momentum[index] >= 70)


CANDIDATES = {
    "trend_pullback_ema_rsi": trend_pullback,
    "breakout_donchian": donchian_breakout,
    "mean_reversion_bollinger_rsi": bollinger_reversion,
}


def score(candles):
    """Score validated candles in source order, resetting at each raw-label gap."""
    row = 0
    segment_id = 0

    def segment_key(bar):
        nonlocal segment_id
        if bar.gap:
            segment_id += 1
        return segment_id

    for _, group in groupby(candles, key=segment_key):
        segment = list(group)
        decisions = [candidate(segment) for candidate in CANDIDATES.values()]
        for bar, *statuses in zip(segment, *decisions, strict=True):
            row += 1
            if bar.gap:
                statuses = ["GAP"] * len(CANDIDATES)
            yield dict(
                row=row, raw_label=bar.label, raw_label_delta=bar.delta,
                gap_before=bar.gap, decisions=dict(zip(CANDIDATES, statuses, strict=True)),
            )


def build(root):
    readiness_bytes = (root / READINESS).read_bytes()
    readiness = json.loads(readiness_bytes)
    if readiness["decision"] != "NO-GO" or any(
        readiness[key] is not False
        for key in ("execution_authorized", "historical_execution_authorized",
                    "prospective_authorized")
    ):
        raise ValueError("Expected the archived Phase 6.9.6 NO-GO assessment")

    frames = {}
    for timeframe, expected_digest in ORIGINAL_DIGESTS.items():
        source = Path("data") / f"XAUUSD_{timeframe}.csv"
        source_bytes = (root / source).read_bytes()
        digest = sha256(source_bytes).hexdigest()
        if digest != expected_digest:
            raise ValueError(f"{source}: source SHA-256 mismatch")
        candles = [
            Candle(label, delta, gap, high, low, close)
            for label, delta, gap, _, high, low, close, *_ in
            _validated_rows(source_bytes, timeframe, EXPECTED_ROWS)
        ]
        rows = list(score(candles))
        counts = {}
        for name in CANDIDATES:
            seen = Counter(record["decisions"][name] for record in rows)
            counts[name] = {key: seen[key] for key in ("BUY", "SELL", "HOLD", "WARMUP", "GAP")}
        frames[timeframe] = dict(source=source.as_posix(), source_sha256=digest,
                                 counts=counts, rows=rows)

    return dict(schema_version=1, mode="RESEARCH", readiness_decision="NO-GO",
                readiness_source=READINESS.as_posix(),
                readiness_sha256=sha256(readiness_bytes).hexdigest(),
                join_key=["timeframe", "one-based source row"], timeframes=frames)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build(args.root)
    payload = json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"
    output = args.output or args.root / REPORT / "candidate-signals.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(payload.encode("utf-8"))


if __name__ == "__main__":
    main()
