"""Build the Phase 6.10.1 retrospective audit in an isolated GoldBot copy."""

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from goldbot.backtesting import research_phase_6_8_5 as frozen

ASSUMPTIONS = frozen.REPORT_DIR / "assumptions.json"
RESULTS = frozen.REPORT_DIR / "results.json"
READINESS = Path("reports/phase_6_9_6/assessment.json")


def json_bytes(report):
    return (json.dumps(report, default=str, sort_keys=True, indent=2, allow_nan=False)
            + "\n").encode("utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def excursions(position, exit_row, opens, closes, spread):
    """Lower magnitudes from observations while held, in USD per ounce."""
    plan = position.plan
    direction = 1 if plan.side == "BUY" else -1

    def move(midpoint):
        quote = Decimal(str(midpoint)) - direction * spread / 2
        return direction * (quote - plan.entry)

    points = [move(opens[row].open) for row in range(position.entry_row, exit_row + 1)]
    for row in range(position.entry_row, exit_row):
        points.extend((move(closes[row].low), move(closes[row].high)))
    return {
        "mae_lower_bound_usd_per_oz": -min(Decimal(0), *points),
        "mfe_lower_bound_usd_per_oz": max(Decimal(0), *points),
        "fully_held_bar_count": exit_row - position.entry_row,
    }


def analyze_ledger(replay, spec, result):
    opens = {bar.source_row: bar for bar in replay.events[::2]}
    closes = {bar.source_row: bar for bar in replay.events[1::2]}
    directions = Counter(bar.signal.decision for bar in closes.values())
    attempts, trades = [], []
    first_latch = None
    for event in result.events:
        if event.attempted is not None:
            signal = event.attempted
            attempts.append({
                "signal_row": signal.row,
                "signal_raw_label": closes[signal.row].raw_server_clock_label,
                "side": signal.side,
                "next_open_row": event.row,
                "next_open_raw_label": event.raw_server_clock_label,
                "open_has_raw_label_gap": opens[event.row].gap_before,
                "entry_status": event.entry_status,
                "signal_rule_reasons": closes[signal.row].signal.reasons,
            })
        if first_latch is None and "DAILY_LOSS_LIMIT" in event.flags:
            first_latch = {
                "row": event.row, "raw_label": event.raw_server_clock_label,
                "event": event.event, "equity": event.equity,
                "realized_losses": event.risk_day.loss_to_date,
                "loss_used": event.daily_loss_used,
            }
        fill = event.exit
        if fill is None:
            continue
        position = fill.position
        plan = position.plan
        signal = closes[position.signal_row]
        entry = opens[position.entry_row]
        exit_open = opens[fill.row]
        direction = 1 if plan.side == "BUY" else -1
        trades.append({
            "signal_row": signal.source_row,
            "entry_row": entry.source_row,
            "exit_row": fill.row,
            "signal_raw_label": signal.raw_server_clock_label,
            "entry_raw_label": entry.raw_server_clock_label,
            "exit_raw_label": exit_open.raw_server_clock_label,
            "signal_to_entry_row_delta": entry.source_row - signal.source_row,
            "signal_to_entry_raw_label_delta": entry.raw_label_delta,
            "holding_row_delta": fill.row - entry.source_row,
            "side": plan.side, "lots": plan.volume,
            "signal_atr": dict(signal.indicators)["atr_14"],
            "entry_midpoint": entry.open, "entry_fill": plan.entry,
            "stop": plan.stop, "target": plan.target, "exit_fill": fill.price,
            "exit_event": event.event, "exit_reason": fill.reason,
            "exit_row_has_raw_label_gap": exit_open.gap_before,
            "held_across_raw_label_gap": any(
                opens[row].gap_before for row in range(entry.source_row + 1, fill.row + 1)
            ),
            "both_stop_and_target_touched": fill.both_touched,
            "gross_pnl_usd": fill.gross_pnl, "commission_usd": fill.commission,
            "net_pnl_usd": fill.net_pnl, "entry_loss_budget_usd": plan.loss_budget,
            "modeled_stop_loss_usd": plan.modeled_stop_loss,
            "adverse_entry_vs_open_midpoint_usd_per_oz": direction * (
                plan.entry - Decimal(str(entry.open))
            ),
            "adverse_stop_fill_vs_stop_level_usd_per_oz": (
                direction * (plan.stop - fill.price) if fill.reason.endswith("STOP") else None
            ),
            **excursions(position, fill.row, opens, closes, spec.spread),
        })

    statuses = Counter(attempt["entry_status"] for attempt in attempts)
    terminal_signal = int(result.terminal.terminal_signal_row is not None)
    require(directions["BUY"] + directions["SELL"] == len(attempts) + terminal_signal,
            "Directional signal funnel does not balance")
    return {
        "signal_counts": dict(directions), "open_attempt_count": len(attempts),
        "terminal_unattempted_signal_count": terminal_signal,
        "attempt_status_counts": dict(statuses), "attempts": attempts,
        "first_synthetic_loss_latch": first_latch, "closed_trades": trades,
    }


def compare_to_ideal(runs):
    def index(run):
        return {(trade["signal_row"], trade["side"]): trade for trade in run["closed_trades"]}

    ideal = index(runs["ideal"])
    comparisons = {}
    for name, run in runs.items():
        if name == "ideal":
            continue
        scenario = index(run)
        common = ideal.keys() & scenario.keys()
        matched = sum((scenario[key]["net_pnl_usd"] - ideal[key]["net_pnl_usd"]
                       for key in common), Decimal(0))
        ideal_only = sorted(ideal.keys() - scenario.keys())
        scenario_only = sorted(scenario.keys() - ideal.keys())
        removed = sum((ideal[key]["net_pnl_usd"] for key in ideal_only), Decimal(0))
        added = sum((scenario[key]["net_pnl_usd"] for key in scenario_only), Decimal(0))
        total_delta = run["terminal_net_pnl_usd"] - runs["ideal"]["terminal_net_pnl_usd"]
        require(matched - removed + added == total_delta, f"{name}: P/L bridge does not balance")
        comparisons[name] = {
            "matched_signal_count": len(common), "matched_net_delta_usd": matched,
            "ideal_only_signal_keys": ideal_only, "ideal_only_net_usd": removed,
            "scenario_only_signal_keys": scenario_only, "scenario_only_net_usd": added,
            "total_net_delta_usd": total_delta,
        }
    return comparisons


def build(root):
    prior = {path: (root / path).read_bytes() for path in (ASSUMPTIONS, RESULTS, READINESS)}
    readiness = json.loads(prior[READINESS])
    require(readiness["decision"] == "NO-GO" and all(readiness[key] is False for key in (
        "execution_authorized", "historical_execution_authorized", "prospective_authorized",
    )), "Expected frozen Phase 6.9.6 NO-GO")

    breakdown = {}
    simulate = frozen._simulate

    def collect_ledger(replay, spec):
        result = simulate(replay, spec)
        breakdown[spec.evidence.scenario_id] = analyze_ledger(replay, spec, result)
        return result

    # Capture the transient ledger from the unchanged runner. Its main() writes
    # the frozen directory, so only call the in-memory builder.
    with patch.object(frozen, "_simulate", side_effect=collect_ledger):
        reports = frozen.build_reports(root)
    for path in (ASSUMPTIONS, RESULTS):
        require(json_bytes(reports[path.name]) == prior[path], f"Frozen bytes differ: {path}")

    timeframes = {}
    for timeframe, scenarios in reports["results.json"]["timeframes"].items():
        timeframes[timeframe] = runs = {}
        for scenario, original in scenarios.items():
            run = breakdown[original["scenario_id"]]
            statuses = run["attempt_status_counts"]
            rejections = {status: value for status, value in statuses.items() if status != "FILLED"}
            trades = run["closed_trades"]
            require(rejections == original["entry_rejections"]
                    and len(trades) == statuses.get("FILLED", 0) == original["entries"]
                    and len(trades) == original["trades"]["closed"]
                    and sum(trade["net_pnl_usd"] for trade in trades) == original["terminal_marked_pnl"],
                    f"{timeframe}/{scenario}: audit fails reconciliation")
            run.update(
                terminal_net_pnl_usd=original["terminal_marked_pnl"],
                realized_gross_pnl_usd=original["costs"]["realized_gross_pnl"],
                commission_paid_usd=original["costs"]["commission_paid"],
                observed_max_drawdown_usd=original["max_drawdown"]["drawdown"]["value"],
                exit_reasons=original["exit_reasons"],
                terminal_risk=original["risk"],
                terminal_position=original["unresolved_position"],
                terminal_pending_signal=original["terminal_pending_signal"],
            )
            runs[scenario] = run

    return {
        "schema_version": 1, **frozen.SCOPE, "readiness_decision": readiness["decision"],
        "source_sha256": {path.as_posix(): sha256(data).hexdigest() for path, data in prior.items()},
        "raw_csv_sha256": frozen.ORIGINAL_DIGESTS,
        "archive_reconciliation": "Both Phase 6.8.5 JSON files reproduced byte for byte",
        "raw_label_policy": "One-based source rows and unconverted raw server labels",
        "execution_cost_scope": "Hypothetical; spread, slippage and grid rounding embedded in fills",
        "excursion_scope": (
            "Lower magnitudes under the hypothetical exit-side quote model, relative to entry "
            "fill; includes held opens and full surviving bars; excludes exit-row high, low "
            "and close, gap interiors, and modeled exit fill, slippage and commission."
        ),
        "timeframes": timeframes,
        "comparison_to_ideal": {tf: compare_to_ideal(runs) for tf, runs in timeframes.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.scratch_root.resolve()
    require(root != Path(__file__).resolve().parents[1], "Use a separate copy of GoldBot")
    output = args.output.resolve()
    require(output.is_relative_to(root), "Write only inside the isolated copy")
    payload = json_bytes(build(root))
    with output.open("xb") as handle:
        handle.write(payload)


if __name__ == "__main__":
    main()
