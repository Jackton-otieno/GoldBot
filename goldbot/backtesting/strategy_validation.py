"""Phase 6.6 retrospective partition audits and synthetic-only evaluation."""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from math import isnan
from pathlib import Path

from goldbot.analysis.data_analysis import EXPECTED_ROWS, INTERVALS
from goldbot.analysis.indicators import EMA_PERIODS, SMA_PERIODS
from goldbot.backtesting.historical_replay import (
    ORIGINAL_DIGESTS, ClosedEvent, OpenEvent, Replay, _indicator_columns, _validated_rows,
)
from goldbot.backtesting.portfolio_coordinator import RiskBoundary, RiskSchedule, run_portfolio
from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.risk import risk_config
from goldbot.strategy import strategy_config
from goldbot.strategy.signals import FIRST_VALID
from goldbot.strategy.strategy import Indicators, evaluate


ROOT = Path(__file__).resolve().parents[2]
PARTITIONS = ("development", "validation", "test")
BASELINE = "phase-6.6-synthetic-baseline"
POLICY = (
    "Each timeframe is evaluated independently in original row order.",
    "All earlier same-timeframe closes may seed indicators and previous-candle state only.",
    "Each partition starts with fresh account, risk, position and pending signal state.",
    "Synthetic risk schedule starts at the first partition open with no inferred resets.",
    "Final close signal expires unfilled. Open position is reported unresolved and discarded.",
    "No liquidation, carry, or later candle is used to resolve a partition boundary.",
)
SOURCE_FILES = (
    "analysis/data_analysis.py", "analysis/indicators.py",
    "backtesting/execution_simulator.py", "backtesting/historical_replay.py",
    "backtesting/portfolio_coordinator.py", "backtesting/sensitivity_analysis.py",
    "backtesting/strategy_validation.py",
    "risk/position_sizing.py", "risk/risk_config.py", "risk/risk_manager.py",
    "risk/trade_plan.py", "strategy/signals.py", "strategy/strategy.py",
    "strategy/strategy_config.py",
)
RISK_FIELDS = (
    "SYMBOL", "ILLUSTRATIVE_EQUITY", "RISK_PER_TRADE", "STOP_ATR_MULTIPLE",
    "TARGET_STOP_MULTIPLE", "MAX_POSITIONS", "MAX_DAILY_LOSS", "MAX_DRAWDOWN",
)


def _decimal_text(value):
    if not value.is_finite():
        raise ValueError("manifest decimals must be finite")
    if not value:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _json_default(value):
    if isinstance(value, Decimal):
        return _decimal_text(value)
    raise TypeError(f"unsupported manifest type: {type(value).__name__}")


def canonical_bytes(record):
    """Encode sorted compact UTF-8 JSON, with exact decimal strings and no NaNs."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=_json_default).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FrozenManifest:
    canonical: bytes

    @classmethod
    def create(cls, record):
        return cls(canonical_bytes(record))

    @property
    def sha256(self):
        return sha256(self.canonical)

    def envelope(self):
        return {"sha256": self.sha256, "manifest": json.loads(self.canonical)}


def frozen_strategy():
    costs = dict(SCENARIOS)["baseline"]
    spec = execution_spec(BASELINE, costs)
    manifest = FrozenManifest.create({
        "schema": "goldbot.strategy-validation.config.v1",
        "strategy": asdict(strategy_config.StrategyConfig()),
        "rsi_thresholds": [
            strategy_config.RSI_BEAR_FLOOR,
            strategy_config.RSI_MIDPOINT,
            strategy_config.RSI_BULL_CEILING,
        ],
        "indicator_ema_periods": EMA_PERIODS,
        "indicator_sma_periods": SMA_PERIODS,
        "indicator_first_valid_rows": FIRST_VALID,
        "risk": {field: getattr(risk_config, field) for field in RISK_FIELDS},
        "synthetic_execution": asdict(spec),
        "historical_execution": "disabled",
        "boundary_policy": POLICY,
        "package_source_sha256": {
            name: sha256((ROOT / "goldbot" / name).read_bytes()) for name in SOURCE_FILES
        },
    })
    return manifest, spec


@dataclass(frozen=True)
class Partition:
    name: str
    start: int  # Inclusive zero-based index.
    stop: int   # Exclusive zero-based index.


def partitions(count):
    """Use cumulative floor cuts at 60% and 80%, without sorting or shuffling."""
    if type(count) is not int or count < 5:
        raise ValueError("at least five candle rows are required")
    cuts = (0, count * 3 // 5, count * 4 // 5, count)
    return tuple(Partition(name, start, stop)
                 for name, start, stop in zip(PARTITIONS, cuts, cuts[1:]))


def _boundaries(rows):
    return [
        {
            "name": part.name,
            "count": part.stop - part.start,
            "first_source_row": part.start + 1,
            "last_source_row": part.stop,
            "first_raw_server_clock_label": rows[part.start][0],
            "last_raw_server_clock_label": rows[part.stop - 1][0],
            "preceding_close_warmup_rows": part.start,
        }
        for part in partitions(len(rows))
    ]


def _verified_rows(payload, timeframe, expected_sha256, expected_rows=None):
    if timeframe not in INTERVALS:
        raise ValueError("unsupported timeframe")
    if type(payload) is not bytes or sha256(payload) != expected_sha256:
        raise ValueError("input SHA-256 mismatch")
    return _validated_rows(payload, timeframe, expected_rows)


def retrospective_audit(root=ROOT):
    """Read only the two known exports and derive row and boundary metadata."""
    strategy, _ = frozen_strategy()
    sources = {}
    for timeframe, digest in ORIGINAL_DIGESTS.items():
        relative = f"data/XAUUSD_{timeframe}.csv"
        rows = _verified_rows((root / relative).read_bytes(), timeframe, digest, EXPECTED_ROWS)
        sources[timeframe] = {
            "path": relative,
            "sha256": digest,
            "row_count": len(rows),
            "provenance": "original GoldBot MT5 export; previously inspected",
            "partitions": _boundaries(rows),
        }
    boundaries = FrozenManifest.create({
        "schema": "goldbot.strategy-validation.boundaries.v1",
        "classification": "retrospective partitions of previously inspected data",
        "genuine_unseen_holdout": False,
        "split_method": "60/20/20 by original source row, independently for each timeframe",
        "timestamp_semantics": "raw server-clock labels with no timezone interpretation",
        "boundary_policy": POLICY,
        "sources": sources,
        "strategy_manifest_sha256": strategy.sha256,
    })
    return {
        "strategy": strategy.envelope(),
        "boundaries": boundaries.envelope(),
        "historical_execution_performed": False,
        "prospective_holdout_collected": False,
    }


def _events(rows, timeframe, part):
    # Only the partition and its earlier same-timeframe history reach the causal
    # indicator implementation. Warmup rows never enter the account simulator.
    columns = _indicator_columns(rows[:part.stop])
    events = []
    for index in range(part.start, part.stop):
        label, delta, gap, opening, *closed_fields = rows[index]
        elapsed = None if index == part.start else delta
        common = (timeframe, index - part.start + 1, label, elapsed,
                  elapsed is not None and gap, opening)
        current = Indicators(**{name: columns[name][index] for name in FIRST_VALID})
        previous = (Indicators(**{name: columns[name][index - 1] for name in FIRST_VALID})
                    if index else None)
        signal = evaluate(current, previous, gap_before=gap)
        values = tuple((name, None if isnan(series[index]) else series[index])
                       for name, series in columns.items())
        events.extend((OpenEvent(*common), ClosedEvent(*common, *closed_fields, values, signal)))
    return tuple(events)


def _synthetic_fixture(payload, timeframe, expected_sha256):
    rows = _verified_rows(payload, timeframe, expected_sha256)
    # Test coordinates are isolated from the raw server-label domain. The
    # caller must supply hand-authored or generated candles, never rebased exports.
    if rows[0][0] != 1 or rows[-1][0] >= 10_000_000:
        raise ValueError("synthetic fixture must use relative labels starting at 1")
    return rows


def _synthetic_manifest(rows, timeframe, input_digest, strategy_digest):
    return FrozenManifest.create({
        "schema": "goldbot.strategy-validation.synthetic-boundaries.v1",
        "classification": "synthetic fixture",
        "timeframe": timeframe,
        "input_sha256": input_digest,
        "strategy_manifest_sha256": strategy_digest,
        "partitions": _boundaries(rows),
    })


def synthetic_boundaries(payload, timeframe, *, expected_sha256, expected_strategy_sha256):
    """Build a commitment for one synthetic fixture before evaluation."""
    strategy, _ = frozen_strategy()
    if strategy.sha256 != expected_strategy_sha256:
        raise ValueError("strategy manifest SHA-256 mismatch")
    rows = _synthetic_fixture(payload, timeframe, expected_sha256)
    return _synthetic_manifest(rows, timeframe, expected_sha256, strategy.sha256)


def evaluate_synthetic(payload, timeframe, partition, *, expected_sha256,
                       expected_strategy_sha256, expected_boundaries_sha256):
    """Evaluate one committed synthetic partition in a fresh account.

    Ledger row numbers are partition-local. Add the number of preceding
    warmup rows from the boundary manifest to recover the fixture row number.
    The terminal record identifies any expired signal and unresolved position.
    """
    strategy, spec = frozen_strategy()
    if strategy.sha256 != expected_strategy_sha256:
        raise ValueError("strategy manifest SHA-256 mismatch")
    rows = _synthetic_fixture(payload, timeframe, expected_sha256)
    boundaries = _synthetic_manifest(rows, timeframe, expected_sha256, strategy.sha256)
    if boundaries.sha256 != expected_boundaries_sha256:
        raise ValueError("synthetic boundaries SHA-256 mismatch")
    if partition not in PARTITIONS:
        raise ValueError("unknown partition")
    part = partitions(len(rows))[PARTITIONS.index(partition)]
    replay = Replay(timeframe, "synthetic fixture", expected_sha256, True,
                    _events(rows, timeframe, part))
    schedule = RiskSchedule(timeframe, spec.evidence, (RiskBoundary(1, "synthetic-day"),))
    return run_portfolio(replay, spec=spec, schedule=schedule)


def audit_bytes(root=ROOT):
    return (json.dumps(retrospective_audit(root), sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="write to this path instead of stdout")
    args = parser.parse_args()
    data = audit_bytes()
    if args.report is None:
        sys.stdout.buffer.write(data)
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(data)


if __name__ == "__main__":
    main()
