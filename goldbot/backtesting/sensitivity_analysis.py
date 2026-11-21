"""Phase 6.5 offline execution-cost comparisons for one synthetic XAUUSD fixture."""

import json
from dataclasses import asdict, dataclass, replace
from decimal import Context, Decimal, localcontext
from fractions import Fraction

from goldbot.backtesting.execution_simulator import SimulationSpec
from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent, Replay
from goldbot.backtesting.performance_analysis import analyze_performance
from goldbot.backtesting.portfolio_coordinator import RiskBoundary, RiskSchedule, run_portfolio
from goldbot.risk.risk_config import BrokerSpecs, D, Evidence, decimal_at_least
from goldbot.strategy.strategy import Signal


@dataclass(frozen=True)
class CostInputs:
    spread_usd_per_oz: Decimal
    slippage_usd_per_oz: Decimal
    round_trip_commission_usd_per_lot: Decimal


SCENARIOS = (
    ("ideal", CostInputs(D("0"), D("0"), D("0"))),
    ("low", CostInputs(D("0.15"), D("0.05"), D("3"))),
    ("baseline", CostInputs(D("0.30"), D("0.10"), D("7"))),
    ("stress", CostInputs(D("1.00"), D("0.50"), D("15"))),
)

# Opening, high, low, close, signal at close, gap before open. The narrow
# first target touch, adverse gap and fresh risk day exercise diverging paths.
_ROWS = (
    (2000, 2000, 2000, 2000, "BUY", False),
    (2000, 2003.1, 2000, 2000, "SELL", False),
    (1989, 1989, 1989, 1989, "BUY", True),
    (1989, 1989, 1989, 1989, "SELL", False),
    (1989, 1989, 1989, 1989, "SELL", False),
    (1989, 1989, 1989, 1989, "SELL", False),
    (1989, 1989, 1985, 1987, "BUY", False),
    (1987, 1987.5, 1987, 1987.5, "HOLD", False),
)
_BOUNDARIES = (RiskBoundary(1, "synthetic-day-A"), RiskBoundary(6, "synthetic-day-B"))


def execution_spec(name: str, costs: CostInputs) -> SimulationSpec:
    """Map exact USD inputs to the simulator's price and per-lot cash fields."""
    if not isinstance(name, str) or not name.strip() or not isinstance(costs, CostInputs):
        raise ValueError("a named scenario and explicit cost inputs are required")
    spread, slippage, commission = (
        costs.spread_usd_per_oz, costs.slippage_usd_per_oz,
        costs.round_trip_commission_usd_per_lot,
    )
    if not all(decimal_at_least(value) for value in (spread, slippage, commission)):
        raise ValueError("costs must be finite nonnegative Decimal values")
    evidence = Evidence(f"phase-6.5/{name}", "hypothetical XAUUSD execution and broker inputs", True)
    tick = D("0.005")
    # The fixed-price legs must stay on-grid without hidden execution rounding.
    if ((Fraction(spread) / (2 * Fraction(tick))).denominator != 1
            or (Fraction(slippage) / Fraction(tick)).denominator != 1):
        raise ValueError("half-spread and slippage must lie on the hypothetical tick grid")
    broker = BrokerSpecs(
        evidence, "XAUUSD", "USD", "USD", tick, tick, D("0.50"), D("100"),
        D("0.01"), D("10"), D("0.01"), 0, "USD_LINEAR",
    )
    # XAUUSD quotes are USD per troy ounce. Price increments and per-lot USD
    # map 1:1; no conversion to points, ticks, or per-side commission applies.
    return SimulationSpec(evidence, broker, spread, slippage, slippage, commission, D("200"))


def _replay():
    events = []
    label = 10000
    for row, (opening, high, low, close, side, gap) in enumerate(_ROWS, 1):
        delta = None if row == 1 else (1800 if gap else 900)
        label += delta or 0
        common = ("M15", row, label, delta, gap, opening)
        reason = "NO_CROSSOVER" if side == "HOLD" else f"{side}_SETUP"
        events.extend((
            OpenEvent(*common),
            ClosedEvent(*common, high, low, close, 1, 0, 0, (("atr_14", 1.0),),
                        Signal(side, (reason,))),
        ))
    return Replay("M15", "phase-6.5 hand-authored OHLC and signal fixture", "", False, tuple(events))


def _fixed_trades(spec):
    """Attribute costs for controlled midpoint-to-midpoint market executions."""
    trades = []
    volume = D("0.10")
    quantity = volume * spec.broker.contract_size
    half_spread = spec.spread / 2
    for side, direction, exit_midpoint in (("BUY", 1, D("2003")), ("SELL", -1, D("1997"))):
        entry_midpoint = D("2000")
        entry = entry_midpoint + direction * (half_spread + spec.entry_slippage)
        exit_price = exit_midpoint - direction * (half_spread + spec.stop_slippage)
        gross = direction * (exit_price - entry) * quantity
        commission = spec.round_trip_commission_per_lot * volume
        trades.append({
            "side": side, "volume_lots": volume, "entry_midpoint": entry_midpoint,
            "exit_midpoint": exit_midpoint, "entry_price": entry, "exit_price": exit_price,
            "midpoint_pnl_usd": direction * (exit_midpoint - entry_midpoint) * quantity,
            "spread_cost_usd": spec.spread * quantity,
            "slippage_cost_usd": (spec.entry_slippage + spec.stop_slippage) * quantity,
            "commission_usd": commission, "gross_pnl_usd": gross, "net_pnl_usd": gross - commission,
        })
    return {
        "trades": trades,
        "total_net_pnl_usd": sum(trade["net_pnl_usd"] for trade in trades),
    }


def analyze_sensitivity() -> dict:
    """Run the fixed trade comparison and four fresh dynamic portfolios."""
    replay = _replay()
    scenarios = {}
    with localcontext(Context(prec=40)):
        for name, costs in SCENARIOS:
            spec = execution_spec(name, costs)
            schedule = RiskSchedule(
                replay.timeframe, replace(spec.evidence, source="explicit synthetic row boundaries"),
                _BOUNDARIES,
            )
            result = run_portfolio(replay, spec=spec, schedule=schedule)
            performance = analyze_performance(result)
            path = []
            for event in result.events:
                if event.attempted or event.exit or event.boundary:
                    path.append({
                        "row": event.row, "event": event.event, "risk_day": event.risk_day.risk_day_id,
                        "risk_day_opening_equity": event.risk_day.opening_equity,
                        "risk_day_loss_to_date": event.risk_day.loss_to_date, "flags": event.flags,
                        "attempted": asdict(event.attempted) if event.attempted else None,
                        "entry_status": event.entry_status,
                        "entry": asdict(event.entry.plan) if event.entry else None,
                        "exit": asdict(event.exit) if event.exit else None,
                    })
            scenarios[name] = {
                "inputs": asdict(costs), "simulation_spec": asdict(spec),
                "fixed_trade_comparison": _fixed_trades(spec),
                "dynamic_portfolio": {
                    "performance": performance, "decision_path": path,
                    "entry_count": sum(event.entry is not None for event in result.events),
                    "rejection_count": sum(event.attempted is not None and event.entry is None
                                           for event in result.events),
                },
            }
    return {
        "schema_version": 1,
        "cost_input_source": "Phase 6.5 requested hypothetical scenarios",
        "fixed_trade_model": "Fixed midpoint references and lots; spread and adverse slippage on both market legs",
        "dynamic_replay": {
            "source": replay.source_name, "timeframe": replay.timeframe, "atr_14": D("1.0"),
            "rows": tuple(dict(zip(("open", "high", "low", "close", "signal", "gap_before"), row))
                          for row in _ROWS),
            "risk_day_boundaries": tuple(asdict(boundary) for boundary in _BOUNDARIES),
        },
        "scenario_order": tuple(name for name, _ in SCENARIOS),
        "scenarios": scenarios,
    }


def sensitivity_json() -> str:
    """Return deterministic strict JSON with Decimal values as strings."""
    return json.dumps(analyze_sensitivity(), default=str, allow_nan=False, sort_keys=True, indent=2) + "\n"


if __name__ == "__main__":
    print(sensitivity_json(), end="")
