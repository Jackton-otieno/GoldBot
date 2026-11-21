"""Replay validated XAUUSD exports offline, one timeframe at a time."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import asdict, dataclass
from math import isfinite, isnan
from pathlib import Path

from goldbot.analysis.data_analysis import EXPECTED_ROWS, FIELDS, INTERVALS, PRICES
from goldbot.analysis.indicators import EMA_PERIODS, SMA_PERIODS, atr, ema, macd, rsi, sma
from goldbot.strategy.signals import FIRST_VALID
from goldbot.strategy.strategy import Indicators, Signal, evaluate


ORIGINAL_DIGESTS = {
    "M15": "a8611beccee72e10e8774a299b2fd1752521d04c755543d87f187d36b9ab986e",
    "H1": "a0ec85476a9cf5b5186c69dfed2d65bb6ccd100e5a05044bf1c041d94ad32541",
}


@dataclass(frozen=True)
class CandleEvent:
    timeframe: str
    source_row: int
    raw_server_clock_label: int
    raw_label_delta: int | None
    gap_before: bool
    open: float


@dataclass(frozen=True)
class OpenEvent(CandleEvent):
    pass


@dataclass(frozen=True)
class ClosedEvent(CandleEvent):
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int
    indicators: tuple[tuple[str, float | None], ...]
    signal: Signal


@dataclass(frozen=True)
class Replay:
    timeframe: str
    source_name: str
    source_sha256: str
    source_hash_verified: bool
    events: tuple[OpenEvent | ClosedEvent, ...]


def _validated_rows(source, timeframe, expected_rows):
    interval = INTERVALS[timeframe]
    reader = csv.reader(io.StringIO(source.decode("utf-8-sig"), newline=""), strict=True)
    rows = []
    previous = None
    try:
        if tuple(next(reader, ())) != FIELDS:
            raise ValueError("unexpected CSV header")
        for record in reader:
            if len(record) != len(FIELDS):
                raise ValueError("unexpected field count")
            label = int(record[0])
            prices = tuple(map(float, record[1:1 + len(PRICES)]))
            opening, high, low, close = prices
            volumes = tuple(map(int, record[5:]))
            if label <= 0 or any(value < 0 for value in volumes):
                raise ValueError("invalid label, volume, or spread")
            if any(not isfinite(price) or price <= 0 for price in prices):
                raise ValueError("prices must be finite and positive")
            if not low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError("inconsistent OHLC")
            delta = None if previous is None else label - previous
            if delta is not None and (delta <= 0 or delta % interval):
                raise ValueError("repeated, backward, or off-grid label difference")
            gap = delta is not None and delta > interval
            rows.append((label, delta, gap, *prices, *volumes))
            previous = label
    except (ValueError, csv.Error) as error:
        raise ValueError(f"{timeframe} near CSV line {reader.line_num}: {error}") from error
    if not rows or (expected_rows is not None and len(rows) != expected_rows):
        raise ValueError(f"{timeframe}: unexpected candle count {len(rows)}")
    return rows


def _indicator_columns(rows):
    highs = [row[4] for row in rows]
    lows = [row[5] for row in rows]
    closes = [row[6] for row in rows]
    line, signal, histogram = macd(closes)
    columns = {f"sma_{period}": sma(closes, period) for period in SMA_PERIODS}
    columns.update({f"ema_{period}": ema(closes, period) for period in EMA_PERIODS})
    columns.update(
        rsi_14=rsi(closes), macd_12_26=line, macd_signal_9=signal,
        macd_histogram=histogram, atr_14=atr(highs, lows, closes),
    )
    return columns


def load_replay(path, timeframe, *, expected_sha256=None, expected_rows=None):
    """Validate and hash the same bytes used to produce immutable replay events."""
    if timeframe not in INTERVALS:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise ValueError(f"{timeframe}: source SHA-256 mismatch")
    rows = _validated_rows(source, timeframe, expected_rows)
    columns = _indicator_columns(rows)
    events = []
    previous = None
    for index, row in enumerate(rows):
        label, delta, gap, opening, *closed_fields = row
        common = (timeframe, index + 1, label, delta, gap, opening)
        events.append(OpenEvent(*common))
        current = Indicators(**{name: columns[name][index] for name in FIRST_VALID})
        signal = evaluate(current, previous, gap_before=gap)
        values = tuple((name, series[index]) for name, series in columns.items())
        if signal.reasons == ("INVALID_INPUT",) or any(
            not (isfinite(value) or isnan(value)) for _, value in values
        ):
            raise ValueError(f"{timeframe} source row {index + 1}: invalid derived indicator")
        visible = tuple((name, None if isnan(value) else value) for name, value in values)
        events.append(ClosedEvent(*common, *closed_fields, visible, signal))
        previous = current
    return Replay(timeframe, path.name, digest, expected_sha256 is not None, tuple(events))


def _event_record(event):
    record = asdict(event)
    if isinstance(event, ClosedEvent):
        return {"event": "closed", **record, "indicators": dict(event.indicators)}
    return {"event": "open", **record}


def render_audit(replay):
    opens = replay.events[::2]
    closes = replay.events[1::2]
    gaps = [event for event in opens if event.gap_before]
    decisions = Counter(event.signal.decision for event in closes)
    reasons = Counter(reason for event in closes for reason in event.signal.reasons)
    sample_rows = {1, len(closes)}
    if gaps:
        sample_rows.update((gaps[0].source_row - 1, gaps[0].source_row))
    for direction in ("BUY", "SELL"):
        first = next((event for event in closes if event.signal.decision == direction), None)
        if first is not None:
            sample_rows.add(first.source_row)
    audit = {
        "timeframe": replay.timeframe,
        "source": replay.source_name,
        "source_sha256": replay.source_sha256,
        "source_hash_verified": replay.source_hash_verified,
        "counts": {
            "source_rows": len(closes),
            "open_events": len(opens),
            "closed_events": len(closes),
            "raw_label_gaps": len(gaps),
            "decisions": {key: decisions[key] for key in ("BUY", "SELL", "HOLD")},
            "reasons": dict(reasons),
        },
        "final_closed_row": closes[-1].source_row,
        "final_closed_row_has_successor_open": False,
        "gap_open_events": [_event_record(event) for event in gaps],
        "sample_events": [
            _event_record(event) for event in replay.events if event.source_row in sample_rows
        ],
    }
    return json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    reports = {}
    for timeframe, digest in ORIGINAL_DIGESTS.items():
        source = args.root / "data" / f"XAUUSD_{timeframe}.csv"
        replay = load_replay(source, timeframe, expected_sha256=digest, expected_rows=EXPECTED_ROWS)
        reports[timeframe] = render_audit(replay)
    output = args.report_dir or args.root / "reports" / "replay_phase_6_1"
    output.mkdir(parents=True, exist_ok=True)
    for timeframe, report in reports.items():
        path = output / f"XAUUSD_{timeframe}_replay_audit.json"
        path.write_text(report, encoding="utf-8", newline="\n")
        print(path)


if __name__ == "__main__":
    main()
