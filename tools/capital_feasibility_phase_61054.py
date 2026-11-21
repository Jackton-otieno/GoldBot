"""Offline minimum-lot feasibility using the frozen research inputs."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from decimal import Decimal as D, ROUND_CEILING, localcontext
from hashlib import sha256
import json
from pathlib import Path

from goldbot.backtesting.historical_replay import ORIGINAL_DIGESTS, load_replay
from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.risk.risk_config import (
    ExecutionAssumptions, ILLUSTRATIVE_EQUITY, MAX_DAILY_LOSS, MAX_DRAWDOWN,
    RISK_PER_TRADE, STOP_ATR_MULTIPLE, TARGET_STOP_MULTIPLE,
)
from goldbot.risk.trade_plan import price_levels
from tools.analyze_market_regimes_phase_6102 import classify


ROOT = Path(__file__).resolve().parents[1]
EQUITIES = tuple(map(D, (100, 500, 1000, 3000, 5000, 10000)))
MIDPOINT = D("3800")
CENT = D(".01")
CARRY_STRESS = D("1")
MARGIN_RATES = tuple(map(D, (".0025", ".01", ".05")))
PERCENTILES = (10, 25, 50, 75, 90, 95, 99)
AUDIT = "reports/phase_6_10_1/audit.json"
COMPARISON = "reports/phase_6_10_4/comparison.json"
PROBES = "reports/phase_6_9_3_1/probes.json"
PRECISION = "reports/phase_6_10_5_1/risk-impact.json"
CLOCK = "reports/phase_6_10_5_2/timestamp-verification.json"
QUOTE = "reports/phase_6_9_4_1/diagnostic.json"
READINESS = "reports/phase_6_9_6/assessment.json"


def distribution(values):
    ordered = sorted(values)
    result = {"count": len(ordered)}
    if ordered:
        result.update(min=ordered[0], max=ordered[-1])
        result.update({f"p{p}": ordered[(len(ordered) * p + 99) // 100 - 1]
                       for p in PERCENTILES})
    return result


def minimum_equity(loss):
    return (loss / RISK_PER_TRADE).quantize(CENT, rounding=ROUND_CEILING)


def minimum_loss(atr, spec, side, midpoint):
    half = spec.spread / 2
    execution = ExecutionAssumptions(
        spec.evidence, spec.broker.symbol, side, midpoint - half, midpoint + half,
        spec.entry_slippage, spec.stop_slippage, spec.round_trip_commission_per_lot,
        spec.margin_per_lot,
    )
    levels = price_levels(side, atr, execution, spec.broker)
    if levels is None:
        return None
    _, stop, _, distance = levels
    if side == "BUY" and stop <= execution.stop_slippage:
        return None
    return spec.broker.volume_min * (
        (distance + execution.stop_slippage) / spec.broker.tick_size
        * spec.broker.tick_value_loss + execution.commission_round_trip_per_lot
    )


def margin_cases(minimum_lots, contract_size, midpoint, legacy_margin):
    legacy = {"model": "frozen_replay_flat_per_lot", "required_free_margin_usd": legacy_margin}
    notional = minimum_lots * contract_size * midpoint
    rates = [{"model": "illustrative_notional_rate", "rate": rate,
              "required_free_margin_usd": notional * rate} for rate in MARGIN_RATES]
    return [dict(row, feasible_if_free_margin_equals_equity={
        str(equity): equity >= row["required_free_margin_usd"] for equity in EQUITIES
    }) for row in (legacy, *rates)]


def feasibility(values, spec):
    losses = []
    for value in values:
        sides = [minimum_loss(value, spec, side, MIDPOINT) for side in ("BUY", "SELL")]
        if all(loss is not None for loss in sides):
            losses.append(max(sides))
    additions = {"planner": D(0), "precision_cent_sensitivity": CENT,
                 "carry_usd_1_sensitivity": CARRY_STRESS}
    return dict(
        atr_rows=len(values),
        invalid_geometry_either_side=len(values) - len(losses),
        minimum_lot_stop_loss_usd=distribution(losses),
        risk_minimum_equity_usd={
            name: distribution(minimum_equity(loss + extra) for loss in losses)
            for name, extra in additions.items()
        },
        equity_levels={
            str(equity): dict(
                per_trade_budget_usd=equity * RISK_PER_TRADE,
                daily_limit_usd=equity * MAX_DAILY_LOSS,
                drawdown_limit_usd=equity * MAX_DRAWDOWN,
                cases_passing_risk_by_sensitivity={
                    name: sum(loss + extra <= equity * RISK_PER_TRADE for loss in losses)
                    for name, extra in additions.items()
                },
            ) for equity in EQUITIES
        },
    )


def rejection_breakdown(run, closes, opens, spec):
    groups = defaultdict(list)
    fresh_budget = Counter()
    for attempt in run["attempts"]:
        signal = closes[attempt["signal_row"] - 1]
        opening = opens[attempt["next_open_row"] - 1]
        if (signal.raw_server_clock_label != attempt["signal_raw_label"]
                or opening.raw_server_clock_label != attempt["next_open_raw_label"]
                or attempt["side"] != signal.signal.decision):
            raise ValueError("Frozen attempt does not reconcile to replay.")
        atr = D(str(dict(signal.indicators)["atr_14"]))
        status = attempt["entry_status"]
        groups[status].append(atr)
        if status == "BELOW_MINIMUM_VOLUME":
            loss = minimum_loss(atr, spec, attempt["side"], D(str(opening.open)))
            if loss is None:
                raise ValueError("Archived minimum-volume rejection has invalid geometry.")
            label = ("fits_fresh_budget" if loss <= ILLUSTRATIVE_EQUITY * RISK_PER_TRADE
                     else "exceeds_fresh_budget")
            fresh_budget[label] += 1
    counts = {key: len(values) for key, values in groups.items()}
    if counts != run["attempt_status_counts"] or sum(counts.values()) != run["open_attempt_count"]:
        raise ValueError("Frozen rejection counts do not reconcile.")
    return dict(attempts=run["open_attempt_count"], first_status_counts=counts,
                minimum_volume_vs_fresh_3000_budget=dict(fresh_budget),
                atr_usd_per_oz_by_status={key: distribution(values) for key, values in groups.items()})


def build(root):
    loaded, digests = {}, {}
    for name in (AUDIT, COMPARISON, PROBES, PRECISION, CLOCK, QUOTE, READINESS):
        raw = (root / name).read_bytes()
        loaded[name], digests[name] = json.loads(raw), sha256(raw).hexdigest()
    if loaded[READINESS]["decision"] != "NO-GO" or loaded[PRECISION]["booked_profit_loss"] != "UNVERIFIED":
        raise ValueError("Expected original NO-GO and unresolved precision evidence.")
    contract = loaded[PROBES]["contract"]
    archived_min_margin = [D(probe["observed_usd"]) for probe in contract["margin"]
                           if D(probe["lots"]) == D(".01")]
    spread_samples = [sample["tick"] for path in (CLOCK, QUOTE) for sample in loaded[path]["samples"]]
    snapshot_spreads = [D(str(tick["ask"])) - D(str(tick["bid"])) for tick in spread_samples]
    capital = dict(
        reference_equity_usd=ILLUSTRATIVE_EQUITY, equity_levels_usd=EQUITIES,
        reference_account_balance_changed=False,
        policy=dict(risk=RISK_PER_TRADE, daily_loss=MAX_DAILY_LOSS, drawdown=MAX_DRAWDOWN,
                    stop_atr=STOP_ATR_MULTIPLE, reward_risk=TARGET_STOP_MULTIPLE),
        midpoint_usd_per_oz=MIDPOINT, fresh_unencumbered_budget=True,
        stop_model="Existing executable-side price_levels, including grid rounding and admission.",
        friction_model="Immediate flat-midpoint round trip. Includes full spread, both slips and commission. Separate from modeled stop distance.",
        margin_model="Minimum lot only. Static entry margin, assumes all equity is free margin for the comparison.",
        precision=dict(archived=loaded[PRECISION]["independent_calculator"],
                       booked_profit_loss="UNVERIFIED", additive_sensitivity_usd=CENT),
        observed_sample=dict(minimum_lot_margin_usd=distribution(archived_min_margin),
                             quote_spread_usd_per_oz=distribution(snapshot_spreads),
                             scope="Previously observed demo snapshots, no historical applicability"),
        scenarios={}, timeframes={},
    )
    volatility = dict(timeframes={})
    rejections = dict(archived_baseline={}, frozen_comparison={})
    for scenario, costs in SCENARIOS:
        spec = execution_spec(scenario, costs)
        broker = spec.broker
        quantity = broker.volume_min * broker.contract_size
        capital["scenarios"][scenario] = dict(
            **asdict(costs), minimum_lots=broker.volume_min, price_tick=broker.tick_size,
            immediate_round_trip_friction_usd=quantity * (spec.spread + spec.entry_slippage + spec.stop_slippage)
            + broker.volume_min * spec.round_trip_commission_per_lot,
            margin=margin_cases(broker.volume_min, broker.contract_size, MIDPOINT,
                                spec.margin_per_lot * broker.volume_min),
        )
    for frame, digest in ORIGINAL_DIGESTS.items():
        replay = load_replay(root / "data" / f"XAUUSD_{frame}.csv", frame,
                             expected_sha256=digest, expected_rows=10000)
        closes, opens = replay.events[1::2], replay.events[::2]
        continuous = [(D(str(atr)), D(str(bar.close))) for bar in closes
                      if (atr := dict(bar.indicators)["atr_14"]) is not None]
        segmented = [D(str(row["atr_14"])) for row in classify(closes) if row["atr_14"] is not None]
        values = [atr for atr, _ in continuous if atr > 0]
        volatility["timeframes"][frame] = dict(
            source_rows=len(closes), raw_label_gaps=sum(bar.gap_before for bar in closes),
            replay_atr_14_usd_per_oz=distribution(atr for atr, _ in continuous),
            replay_atr_14_percent_of_close=distribution(100 * atr / close for atr, close in continuous),
            segment_reset_atr_14_usd_per_oz=distribution(segmented),
        )
        capital["timeframes"][frame] = {}
        rejections["archived_baseline"][frame] = {}
        for scenario, costs in SCENARIOS:
            spec = execution_spec(scenario, costs)
            capital["timeframes"][frame][scenario] = feasibility(values, spec)
            rejections["archived_baseline"][frame][scenario] = rejection_breakdown(
                loaded[AUDIT]["timeframes"][frame][scenario], closes, opens, spec
            )
        rejections["frozen_comparison"][frame] = {
            strategy: {name: dict(
                attempts=run["entries"] + sum(run["entry_rejections"].values()),
                entries=run["entries"], first_rejections=run["entry_rejections"],
                terminal_marked_pnl_usd=run["terminal_marked_pnl"],
            ) for name, run in record["scenarios"].items()}
            for strategy, record in loaded[COMPARISON]["timeframes"][frame].items()
        }
    for report in capital, volatility, rejections:
        report.update(readiness="NO-GO", mode="OFFLINE_RESEARCH",
                      inputs_sha256=digests, raw_csv_sha256=ORIGINAL_DIGESTS)
    return {"capital-feasibility.json": capital, "volatility-analysis.json": volatility,
            "rejection-analysis.json": rejections}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with localcontext() as context:
        context.prec = 40
        for name, report in build(ROOT).items():
            with (args.output / name).open("x", encoding="utf-8", newline="\n") as output:
                json.dump(report, output, sort_keys=True, indent=2, allow_nan=False, default=str)
                output.write("\n")


if __name__ == "__main__":
    main()
