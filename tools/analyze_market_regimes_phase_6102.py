"""Causal offline annotations for the frozen Phase 6.10.1 research ledger."""

import argparse
from collections import Counter, defaultdict, deque
from decimal import Decimal
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from statistics import mean, median

from goldbot.backtesting.historical_replay import ORIGINAL_DIGESTS, load_replay
from tools.audit_research_phase_6101 import build as rebuild_audit, json_bytes, require

AUDIT = Path("reports/phase_6_10_1/audit.json")
REPORT = Path("reports/phase_6_10_2")
PERIOD = 14
EMA_PERIOD = 20
SLOPE_LAG = 5
AXES = ("direction", "strength", "volatility")
STATUS = ("directional_signals", "attempts", "filled", "rejected",
          "below_minimum_volume", "closed", "wins", "losses", "breakeven",
          "stops", "targets")


def wilder(previous, observation):
    return (previous * (PERIOD - 1) + observation) / PERIOD


def classify(candles):
    """Accept replay closes in source order and yield one annotation per close."""
    previous = None
    for bar in candles:
        if previous is None or bar.gap_before:
            seed = []
            dx_seed = []
            close_seed = []
            ema_history = deque(maxlen=SLOPE_LAG)
            natr_history = deque(maxlen=EMA_PERIOD)
            atr = plus_dm = minus_dm = adx = ema = None
        natr = ratio = slope = None
        baseline_ready = len(natr_history) == EMA_PERIOD
        if previous is not None and not bar.gap_before:
            up = bar.high - previous.high
            down = previous.low - bar.low
            movement = (
                max(bar.high - bar.low, abs(bar.high - previous.close),
                    abs(bar.low - previous.close)),
                up if up > max(0, down) else 0.0,
                down if down > max(0, up) else 0.0,
            )
            if atr is None:
                seed.append(movement)
                if len(seed) == PERIOD:
                    atr, plus_dm, minus_dm = map(mean, zip(*seed))
            else:
                atr, plus_dm, minus_dm = map(wilder, (atr, plus_dm, minus_dm), movement)
            if atr is not None:
                # The common ATR denominator in both DIs cancels in DX.
                movement_sum = plus_dm + minus_dm
                dx = 100 * abs(plus_dm - minus_dm) / movement_sum if movement_sum else 0.0
                if adx is None:
                    dx_seed.append(dx)
                    if len(dx_seed) == PERIOD:
                        adx = mean(dx_seed)
                else:
                    adx = wilder(adx, dx)
                natr = atr / bar.close
                if baseline_ready:
                    baseline = median(natr_history)
                    if baseline > 0:
                        ratio = natr / baseline
                    elif natr == 0:
                        ratio = 1.0
                    # With a zero baseline and nonzero NATR, the ratio is undefined.
                natr_history.append(natr)
        if ema is None:
            close_seed.append(bar.close)
            if len(close_seed) == EMA_PERIOD:
                ema = mean(close_seed)
        else:
            ema += 2 / (EMA_PERIOD + 1) * (bar.close - ema)
        if ema is not None:
            if len(ema_history) == SLOPE_LAG:
                slope = (ema - ema_history[0]) / SLOPE_LAG
            ema_history.append(ema)
        direction = "WARMUP"
        if slope is not None:
            direction = "UP" if slope > 0 else "DOWN" if slope < 0 else "FLAT"
        strength = "WARMUP"
        if adx is not None:
            strength = "WEAK" if adx < 20 else "STRONG" if adx >= 25 else "AMBIGUOUS"
        volatility = "WARMUP"
        if ratio is not None:
            volatility = "LOW" if ratio < 2 / 3 else "HIGH" if ratio > 1.5 else "TYPICAL"
        elif baseline_ready:
            volatility = "UNDEFINED"
        if bar.gap_before:
            direction = strength = volatility = "GAP"
        yield dict(direction=direction, strength=strength, volatility=volatility,
                   adx_14=adx, atr_14=atr, ema_20=ema, ema_slope=slope,
                   normalized_atr=natr, volatility_ratio=ratio)
        previous = bar


def group_keys(row):
    yield ("all", "ALL")
    for axis in AXES:
        yield (axis, row[axis])
    yield ("joint", "/".join(row[axis] for axis in AXES))


def metrics(rows, attempts, trades):
    signals = Counter(row["decision"] for row in rows)
    statuses = Counter(attempt["entry_status"] for attempt in attempts)
    exits = Counter(trade["exit_reason"] for trade in trades)
    nets = [Decimal(trade["net_pnl_usd"]) for trade in trades]
    wins = sum(net > 0 for net in nets)
    filled = statuses["FILLED"]
    return dict(
        candles=len(rows), signals=dict(signals),
        directional_signals=signals["BUY"] + signals["SELL"],
        attempts=len(attempts), filled=filled, rejected=len(attempts) - filled,
        below_minimum_volume=statuses["BELOW_MINIMUM_VOLUME"],
        attempt_statuses=dict(statuses), closed=len(trades), wins=wins,
        losses=sum(net < 0 for net in nets), breakeven=sum(net == 0 for net in nets),
        win_rate=wins / len(trades) if trades else None,
        net_pnl_usd=sum(nets, Decimal(0)), exit_reasons=dict(exits),
        stops=sum(count for reason, count in exits.items() if reason.endswith("STOP")),
        targets=sum(count for reason, count in exits.items() if reason.endswith("TARGET")),
    )


def summarize(candles, opens, rows, run):
    attempts = {item["signal_row"]: item for item in run["attempts"]}
    trades = {item["signal_row"]: item for item in run["closed_trades"]}
    directional = {row["row"] for row in rows if row["decision"] in ("BUY", "SELL")}
    require(len(attempts) == len(run["attempts"]) and attempts.keys() == directional
            and run["terminal_unattempted_signal_count"] == 0,
            "Attempts differ from frozen directional signals")
    require(len(trades) == len(run["closed_trades"]) and trades.keys() ==
            {key for key, item in attempts.items() if item["entry_status"] == "FILLED"},
            "Closed trades differ from frozen fills")
    for key, attempt in attempts.items():
        signal, successor = candles[key - 1], opens[key]
        require(attempt["side"] == signal.signal.decision
                and attempt["signal_rule_reasons"] == list(signal.signal.reasons)
                and attempt["signal_raw_label"] == signal.raw_server_clock_label
                and attempt["next_open_row"] == successor.source_row
                and attempt["next_open_raw_label"] == successor.raw_server_clock_label
                and attempt["open_has_raw_label_gap"] == successor.gap_before,
                f"Attempt provenance mismatch at signal row {key}")
        if key in trades:
            trade = trades[key]
            exit_open = opens[trade["exit_row"] - 1]
            require(trade["side"] == attempt["side"]
                    and trade["signal_raw_label"] == attempt["signal_raw_label"]
                    and trade["entry_row"] == successor.source_row <= exit_open.source_row
                    and trade["entry_raw_label"] == successor.raw_server_clock_label
                    and trade["exit_raw_label"] == exit_open.raw_server_clock_label
                    and trade["signal_atr"] == dict(signal.indicators)["atr_14"]
                    and Decimal(trade["gross_pnl_usd"]) - Decimal(trade["commission_usd"])
                    == Decimal(trade["net_pnl_usd"]),
                    f"Trade provenance mismatch at signal row {key}")
    groups = defaultdict(list)
    for row in rows:
        for key in group_keys(row):
            groups[key].append(row)
    summary = defaultdict(dict)
    for (axis, label), group in groups.items():
        keys = {row["row"] for row in group}
        summary[axis][label] = metrics(group, [attempts[key] for key in sorted(keys & attempts.keys())],
                                      [trades[key] for key in sorted(keys & trades.keys())])
    total = summary["all"]["ALL"]
    require(total["signals"] == run["signal_counts"]
            and total["attempt_statuses"] == run["attempt_status_counts"]
            and total["attempts"] == run["open_attempt_count"]
            and total["exit_reasons"] == run["exit_reasons"]
            and total["net_pnl_usd"] == Decimal(run["terminal_net_pnl_usd"])
            and total["stops"] + total["targets"] == total["closed"]
            and run["terminal_position"] is None and run["terminal_pending_signal"] is None,
            "Scenario totals differ from frozen audit")
    for axis in (*AXES, "joint"):
        for field in ("candles", *STATUS, "net_pnl_usd"):
            require(sum(group[field] for group in summary[axis].values()) == total[field],
                    f"{axis} does not reconcile for {field}")
        for field in ("signals", "attempt_statuses", "exit_reasons"):
            combined = Counter()
            for group in summary[axis].values():
                combined.update(group[field])
            require(combined == total[field], f"{axis} does not reconcile for {field}")
    return summary


def overlap(rows, runs):
    groups = defaultdict(set)
    for row in rows:
        if row["decision"] in ("BUY", "SELL"):
            for key in group_keys(row):
                groups[key].add(row["row"])
    fills = {name: {trade["signal_row"] for trade in run["closed_trades"]}
             for name, run in runs.items()}
    output = defaultdict(dict)
    for (axis, label), signals in groups.items():
        output[axis][label] = {
            "directional_signals_shared_by_all_scenarios": len(signals),
            "unique_closed_signal_rows": len(signals & set.union(*fills.values())),
            "closed_signal_rows_in_all_scenarios": len(signals & set.intersection(*fills.values())),
            "pairs": {
                f"{left}/{right}": dict(
                    shared=len(signals & fills[left] & fills[right]),
                    left_only=len(signals & (fills[left] - fills[right])),
                    right_only=len(signals & (fills[right] - fills[left])),
                )
                for left, right in combinations(sorted(fills), 2)
            },
        }
    return output


def build(root):
    audit_bytes = (root / AUDIT).read_bytes()
    require(json_bytes(rebuild_audit(root)) == audit_bytes,
            "Phase 6.10.1 audit does not reproduce byte for byte")
    audit = json.loads(audit_bytes)
    frames = {}
    for timeframe, digest in ORIGINAL_DIGESTS.items():
        source = Path("data") / f"XAUUSD_{timeframe}.csv"
        replay = load_replay(root / source, timeframe, expected_sha256=digest, expected_rows=10000)
        opens, candles = replay.events[::2], replay.events[1::2]
        rows = [
            dict(row=bar.source_row, raw_label=bar.raw_server_clock_label,
                 raw_label_delta=bar.raw_label_delta, gap_before=bar.gap_before,
                 decision=bar.signal.decision, reasons=bar.signal.reasons, **regime)
            for bar, regime in zip(candles, classify(candles), strict=True)
        ]
        runs = audit["timeframes"][timeframe]
        frames[timeframe] = dict(
            source=source.as_posix(), source_sha256=replay.source_sha256,
            scenarios={name: summarize(candles, opens, rows, run) for name, run in runs.items()},
            rows=rows,
            ledgers={name: {key: run[key] for key in ("attempts", "closed_trades")}
                     for name, run in runs.items()},
            overlap=overlap(rows, runs),
        )
    return dict(schema_version=1, mode="RESEARCH", readiness_decision=audit["readiness_decision"],
                source_sha256={**audit["source_sha256"], AUDIT.as_posix(): sha256(audit_bytes).hexdigest()},
                join_key=["timeframe", "one-based source signal row"], timeframes=frames)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build(args.root)
    output = args.output or args.root / REPORT / "market-regimes.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(json_bytes(report))


if __name__ == "__main__":
    main()

