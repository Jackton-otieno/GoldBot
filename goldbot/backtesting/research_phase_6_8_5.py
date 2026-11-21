"""Phase 6.8.5 RESEARCH-only OHLC simulation with hypothetical execution inputs."""

import json
from collections import Counter
from dataclasses import asdict, replace
from decimal import Context, localcontext
from pathlib import Path

from goldbot.analysis.data_analysis import EXPECTED_ROWS
from goldbot.backtesting.historical_replay import ORIGINAL_DIGESTS, load_replay
from goldbot.backtesting.performance_analysis import analyze_performance
from goldbot.backtesting.portfolio_coordinator import RiskBoundary, RiskSchedule, run_portfolio
from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.backtesting.strategy_validation import FrozenManifest, frozen_strategy, sha256
from goldbot.risk.risk_config import Evidence

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = Path("reports/research_phase_6_8_5")
VALIDATION = Path("reports/validation_phase_6_6/validation.json")
READINESS = Path("reports/phase_6_8_4/historical-readiness.json")
SCOPE = {
    "mode": "RESEARCH",
    "verified_historical_execution": False,
    "verified_broker_attestation": False,
    "trading_readiness_established": False,
    "genuine_unseen_holdout": False,
}


def _spec(name, timeframe):
    spec = execution_spec(name, dict(SCENARIOS)[name])
    # Evidence.matches checks internal provenance in the legacy offline planner.
    # This is a scenario assertion only and has no broker authority or UTC scope.
    evidence = Evidence(
        f"research-phase-6.8.5/{timeframe}/{name}",
        "RESEARCH-only hypothetical scenario inputs and synthetic account state",
        True,
    )
    return replace(spec, evidence=evidence, broker=replace(spec.broker, evidence=evidence))


def _simulate(replay, spec):
    schedule = RiskSchedule(
        replay.timeframe, spec.evidence, (RiskBoundary(1, "research-full-run"),),
    )
    return run_portfolio(replay, spec=spec, schedule=schedule)


def _summary(result):
    summary = analyze_performance(result)
    del summary["event_series"]
    final = result.events[-1]
    summary["terminal_pending_signal"] = (
        asdict(final.pending) if final.pending is not None else None
    )
    with localcontext(Context(prec=40)):
        summary["terminal_marked_pnl"] = final.equity - summary["account"]["starting_equity"]
    summary["entries"] = sum(event.entry is not None for event in result.events)
    summary["closed_trades"] = [
        asdict(event.exit) for event in result.events if event.exit is not None
    ]
    summary["exit_reasons"] = dict(Counter(fill["reason"] for fill in summary["closed_trades"]))
    summary["risk"] = {
        "boundary_open_rows": [boundary.open_row for boundary in result.schedule.boundaries],
        "terminal_flags": final.flags,
        "terminal_loss_budget_used_usd": final.daily_loss_used,
        "cumulative_realized_losses_usd": final.risk_day.loss_to_date,
        "first_latch_events": {
            flag: next(
                ({"row": event.row, "event": event.event}
                 for event in result.events if flag in event.flags), None,
            )
            for flag in ("DAILY_LOSS_LIMIT", "DRAWDOWN_LIMIT", "INSOLVENT", "MARGIN_DEFICIT")
        },
    }
    return summary


def build_reports(root=ROOT):
    strategy, _ = frozen_strategy()
    validation_bytes = (root / VALIDATION).read_bytes()
    validation = json.loads(validation_bytes)
    if validation["strategy"] != strategy.envelope():
        raise ValueError("current strategy differs from the saved Phase 6.6 freeze")
    readiness_bytes = (root / READINESS).read_bytes()
    readiness = json.loads(readiness_bytes)
    assumptions = {
        **SCOPE,
        "phase_6_8_4_readiness_snapshot": {
            "path": READINESS.as_posix(), "sha256": sha256(readiness_bytes),
            "ready": readiness["historical_execution_ready"],
            "findings": readiness["findings"],
        },
        "strategy_freeze": strategy.envelope(),
        "phase_6_6_validation_sha256": sha256(validation_bytes),
        "prior_partitions": validation["boundaries"],
        "data_exposure": (
            "Previously inspected exports. Full original stream per timeframe, including "
            "all three retrospective 60/20/20 partitions. No partition resets or tuning."
        ),
        "quote_basis": "Assume OHLC midpoint. Ignore the CSV spread field for execution.",
        "timestamp_policy": (
            "Original integer labels and source row order only. Recognize missing intervals "
            "from label gaps. Do not synthesize bars, map UTC or align timeframes."
        ),
        "execution_policy": (
            "Use only the previous close signal and ATR at the next observed open. Skip "
            "entry on raw-label gaps and while occupied at the open. Existing positions "
            "check the open before intrabar extremes. Adverse opening stops use the open "
            "with adverse slippage, targets receive the target price, and ambiguous "
            "intrabar touches resolve stop-first. Prices round on the hypothetical grid."
        ),
        "risk_policy": (
            "Independent USD 3000 portfolios for each timeframe and cost scenario. "
            "One run-long synthetic loss budget of USD 60 with no automatic reset. "
            "Usage is the maximum of cumulative net realized losses and loss from "
            "opening equity. Preserve the per-trade budget, drawdown latch, position "
            "limit and margin admission checks. No calendar-day compliance claim."
        ),
        "margin_policy": (
            "Flat USD 200 per lot reserved; admission also tests marked free margin. "
            "Record later deficits without modeling broker liquidation or margin calls."
        ),
        "funding_policy": "Swap, financing and rollover charges are omitted in all scenarios.",
        "mark_policy": (
            "Mark at the hypothetical bid for longs and ask for shorts at observed "
            "open and close only. Unpaid exit commission is shown separately. No forced "
            "liquidation or fill for a terminal signal without a successor open."
        ),
        "limitations": (
            "OHLC cannot resolve tick order, fill availability, sessions, or intrabar "
            "drawdown. Results provide no profitability, holdout or trading-readiness evidence."
        ),
        "research_runner_sha256": sha256(Path(__file__).read_bytes()),
        "performance_module_sha256": sha256(Path(__file__).with_name(
            "performance_analysis.py"
        ).read_bytes()),
        "sources": {},
        "scenario_inputs": {},
    }
    results = {}
    for timeframe, digest in ORIGINAL_DIGESTS.items():
        source = Path("data") / f"XAUUSD_{timeframe}.csv"
        replay = load_replay(root / source, timeframe, expected_sha256=digest,
                             expected_rows=EXPECTED_ROWS)
        assumptions["sources"][timeframe] = {
            "path": source.as_posix(), "sha256": replay.source_sha256,
            "rows": EXPECTED_ROWS,
            "raw_label_gaps": sum(event.gap_before for event in replay.events[::2]),
        }
        results[timeframe] = {}
        assumptions["scenario_inputs"][timeframe] = {}
        for name, _ in SCENARIOS:
            spec = _spec(name, timeframe)
            inputs = asdict(spec)
            del inputs["evidence"]
            del inputs["broker"]["evidence"]
            assumptions["scenario_inputs"][timeframe][name] = inputs
            results[timeframe][name] = _summary(_simulate(replay, spec))
    manifest = FrozenManifest.create(assumptions)
    return {
        "assumptions.json": {**SCOPE, **manifest.envelope()},
        "results.json": {**SCOPE, "assumptions_sha256": manifest.sha256, "timeframes": results},
    }


def main():
    reports = build_reports()
    output = ROOT / REPORT_DIR
    output.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        path = output / name
        payload = json.dumps(report, default=str, sort_keys=True, indent=2, allow_nan=False)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(payload + "\n", encoding="utf-8", newline="\n")
        temporary.replace(path)
        print(path)


if __name__ == "__main__":
    main()
