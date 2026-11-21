"""Deterministic Phase 6.4 analytics for an offline Phase 6.3 ledger."""

import json
from collections import Counter
from decimal import Context, Decimal, DecimalException, localcontext

from goldbot.analysis.data_analysis import INTERVALS
from goldbot.backtesting.execution_simulator import EndOfData, ExitFill, Position, SimulationSpec
from goldbot.backtesting.portfolio_coordinator import LedgerEvent, PendingSignal, PortfolioResult, RiskSchedule
from goldbot.risk.risk_config import ILLUSTRATIVE_EQUITY
from goldbot.risk.trade_plan import TradePlan

ZERO = Decimal(0)


def _require(condition, index, reason):
    if not condition:
        raise ValueError(f"event {index}: {reason}")


def _finite(*values):
    return all(isinstance(value, Decimal) and value.is_finite() for value in values)


def _position_terms(position, spec, index):
    _require(isinstance(position, Position) and isinstance(position.plan, TradePlan),
             index, "invalid position")
    plan = position.plan
    _require(plan.side in ("BUY", "SELL")
             and _finite(plan.entry, plan.volume, plan.modeled_margin)
             and plan.entry > 0 and plan.volume > 0 and plan.modeled_margin > 0,
             index, "invalid position terms")
    direction = 1 if plan.side == "BUY" else -1
    return direction, plan.volume, (
        spec.round_trip_commission_per_lot * plan.volume
    )


def _validate(result):
    if (not isinstance(result, PortfolioResult)
            or not isinstance(result.specification, SimulationSpec)
            or not isinstance(result.schedule, RiskSchedule)
            or result.timeframe != result.schedule.timeframe
            or not isinstance(result.events, tuple) or not result.events
            or len(result.events) % 2 or not isinstance(result.terminal, EndOfData)):
        raise ValueError("expected a non-empty, complete Phase 6.3 portfolio result")
    spec = result.specification
    if not result.schedule.evidence.matches(spec.evidence.scenario_id):
        raise ValueError("portfolio scenario and schedule disagree")

    start = ILLUSTRATIVE_EQUITY
    balance = peak = start
    paid = gross = ZERO
    position = pending = None
    previous_label = 0
    net_trades = []
    rejections = Counter()
    series = [{"event_index": 0, "equity": start, "drawdown": ZERO,
               "drawdown_fraction": ZERO, "position_open": False}]

    for index, event in enumerate(result.events, 1):
        opening = index % 2 == 1
        row = (index + 1) // 2
        _require(isinstance(event, LedgerEvent) and event.timeframe == result.timeframe
                 and type(event.row) is int and event.row == row
                 and event.event == ("open" if opening else "closed")
                 and type(event.raw_server_clock_label) is int
                 and (event.raw_server_clock_label > previous_label
                      and (row == 1 or (event.raw_server_clock_label - previous_label)
                           % INTERVALS[result.timeframe] == 0) if opening
                      else event.raw_server_clock_label == previous_label),
                 index, "invalid event sequence")
        previous_label = event.raw_server_clock_label
        _require(_finite(event.balance, event.unrealized_pnl, event.equity, event.midpoint,
                         event.commission_paid, event.commission_due_on_exit,
                         event.used_margin, event.free_margin, event.peak_equity,
                         event.drawdown, event.drawdown_fraction)
                 and event.midpoint > spec.spread / 2, index, "invalid ledger numbers")

        if opening:
            status = event.entry_status
            _require(event.attempted == pending and event.pending is None
                     and isinstance(status, str) and bool(status.strip())
                     and (status == "FILLED") == (event.entry is not None)
                     and (pending is not None or status in
                          (("POSITION_LIMIT",) if position is not None else
                           ("NO_PRIOR_SIGNAL",) if row == 1 else ("HOLD_SIGNAL",)))
                     and (pending is None or status not in ("NO_PRIOR_SIGNAL", "HOLD_SIGNAL"))
                     and (status == "POSITION_LIMIT") == (position is not None),
                     index, "invalid entry status or signal transition")
            if pending is not None and status != "FILLED":
                rejections[status] += 1
        else:
            _require(event.entry is None and event.entry_status is None and event.attempted is None
                     and (event.pending is None or (
                         isinstance(event.pending, PendingSignal)
                         and event.pending.row == row and event.pending.side in ("BUY", "SELL")
                     )), index, "invalid close signal transition")
        if event.entry is not None:
            _position_terms(event.entry, spec, index)
            _require(position is None and pending is not None and event.exit is None
                     and event.entry.entry_row == row and event.entry.signal_row == pending.row
                     and event.entry.plan.side == pending.side, index, "invalid entry transition")
            position = event.entry
        pending = event.pending

        fill = event.exit
        if fill is not None:
            _require(isinstance(fill, ExitFill) and position is not None
                     and fill.position == position and fill.row == row
                     and fill.reason in (("OPEN_STOP", "OPEN_TARGET") if opening else ("STOP", "TARGET"))
                     and _finite(fill.price, fill.gross_pnl, fill.commission, fill.net_pnl)
                     and fill.price > 0, index, "invalid exit transition")
            direction, volume, commission = _position_terms(position, spec, index)
            entry = position.plan.entry
            _require(fill.gross_pnl == direction * (fill.price - entry) * spec.broker.contract_size * volume
                     and fill.commission == commission
                     and fill.net_pnl == fill.gross_pnl - commission,
                     index, "exit P/L or commission does not reconcile")
            balance += fill.net_pnl
            paid += commission
            gross += fill.gross_pnl
            net_trades.append(fill.net_pnl)
            position = None

        quote = None
        unrealized = margin = due = ZERO
        if position is not None:
            direction, volume, due = _position_terms(position, spec, index)
            quote = event.midpoint - direction * spec.spread / 2
            unrealized = direction * (quote - position.plan.entry) * spec.broker.contract_size * volume
            margin = position.plan.modeled_margin
        equity = balance + unrealized
        peak = max(peak, equity)
        drawdown = peak - equity
        fraction = drawdown / peak
        _require((event.liquidation_quote is None if quote is None else
                  _finite(event.liquidation_quote) and event.liquidation_quote == quote)
                 and event.position == position
                 and (event.balance, event.unrealized_pnl, event.equity,
                      event.used_margin, event.free_margin, event.commission_paid,
                      event.commission_due_on_exit, event.peak_equity, event.drawdown,
                      event.drawdown_fraction) ==
                 (balance, unrealized, equity, margin, equity - margin, paid, due,
                  peak, drawdown, fraction), index, "ledger accounting does not reconcile")
        series.append({"event_index": index, "row": row, "event": event.event,
                       "equity": equity, "drawdown": drawdown,
                       "drawdown_fraction": fraction, "position_open": position is not None})

    _require(result.terminal == EndOfData(pending.row if pending else None, position),
             len(result.events), "terminal state does not reconcile")
    return series, net_trades, gross, dict(sorted(rejections.items()))


def _trades(net):
    counts = dict.fromkeys(("win", "loss", "breakeven"), 0)
    longest = counts.copy()
    totals = dict.fromkeys(counts, ZERO)
    last = None
    streak = 0
    for pnl in net:
        outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
        counts[outcome] += 1
        totals[outcome] += pnl
        streak = streak + 1 if last == outcome else 1
        longest[outcome] = max(longest[outcome], streak)
        last = outcome
    wins, losses = totals["win"], totals["loss"]
    if losses:
        factor = {"value": wins / -losses, "status": "finite", "reason": None}
    elif wins:
        factor = {"value": None, "status": "infinite", "reason": "no_net_losses"}
    else:
        factor = {"value": None, "status": "undefined", "reason": "no_net_wins_or_losses"}
    return {
        "closed": len(net), "counts": counts, "profit_factor": factor,
        "net_win_total": wins, "net_loss_total": losses,
        "expectancy": sum(net, ZERO) / len(net) if net else None,
        "mean_win": wins / counts["win"] if counts["win"] else None,
        "mean_loss": losses / counts["loss"] if counts["loss"] else None,
        "longest_streaks": longest, "ending_streak": {"outcome": last, "length": streak},
    }


def _drawdowns(series):
    """Select first maximum troughs, using the last peak at or before each decline."""
    peak = 0
    worst = {"drawdown": (0, 0), "drawdown_fraction": (0, 0)}
    for index, point in enumerate(series):
        if point["drawdown"] == ZERO:
            peak = index
        for metric, (_, trough) in worst.items():
            if point[metric] > series[trough][metric]:
                worst[metric] = (peak, index)

    report = {}
    for metric, (peak, trough) in worst.items():
        recovery = None
        if trough:
            recovery = next((i for i in range(trough + 1, len(series))
                             if series[i]["equity"] >= series[peak]["equity"]), None)
        report[metric] = {
            "value": series[trough][metric],
            "peak_event_index": peak if trough else None,
            "trough_event_index": trough if trough else None,
            "recovery_event_index": recovery,
            "peak_to_recovery_intervals": recovery - peak if recovery is not None else None,
            "status": "recovered" if recovery is not None else "unrecovered" if trough else "none",
        }
    return report


def analyze_performance(result: PortfolioResult) -> dict:
    """Validate the accounting ledger and report one hypothetical timeframe in USD."""
    try:
        with localcontext(Context(prec=40)):
            series, net, gross, rejections = _validate(result)
            final = result.events[-1]
            start = ILLUSTRATIVE_EQUITY
            realized = final.balance - start
            _require(realized == sum(net, ZERO) == gross - final.commission_paid,
                     len(result.events), "aggregate P/L does not reconcile")
            position = final.position
            unresolved = None if position is None else {
                "side": position.plan.side, "volume_lots": position.plan.volume,
                "signal_row": position.signal_row, "entry_row": position.entry_row,
                "entry_price": position.plan.entry, "liquidation_quote": final.liquidation_quote,
                "unrealized_pnl": final.unrealized_pnl, "used_margin": final.used_margin,
                "commission_due_on_exit": final.commission_due_on_exit,
            }
            intervals = len(result.events) - 1
            exposed = sum(point["position_open"] for point in series[1:-1])
            return {
                "schema_version": 1, "scenario_id": result.specification.evidence.scenario_id,
                "timeframe": result.timeframe, "currency": "USD",
                "account": {
                    "starting_balance": start, "final_balance": final.balance,
                    "starting_equity": start, "final_equity": final.equity,
                    "realized_net_pnl": realized, "unrealized_pnl": final.unrealized_pnl,
                    "realized_return": realized / start,
                    "marked_return": (final.equity - start) / start,
                    "first_insolvent_event_index": next(
                        (point["event_index"] for point in series if point["equity"] <= ZERO), None
                    ),
                },
                "trades": _trades(net), "max_drawdown": _drawdowns(series),
                "costs": {
                    "realized_gross_pnl": gross, "commission_paid": final.commission_paid,
                    "commission_due_on_exit": final.commission_due_on_exit,
                    **{name: {"value": None, "reason": "no_separate_cost_ledger"}
                       for name in ("spread_cost", "slippage_cost")},
                },
                "entry_rejections": rejections,
                "unresolved_position": unresolved,
                "terminal_signal_row": result.terminal.terminal_signal_row,
                "exposure": {
                    "observed_intervals": intervals, "intervals_with_position": exposed,
                    "observed_interval_fraction": Decimal(exposed) / intervals,
                },
                "unavailable": {
                    name: {"value": None, "reason": "unverified_time_or_sampling_boundaries"}
                    for name in ("annualized_sharpe", "calendar_returns", "elapsed_exposure", "day_metrics")
                },
                "event_series": series,
            }
    except DecimalException as exc:
        raise ValueError("invalid portfolio decimal arithmetic") from exc


def performance_json(result: PortfolioResult) -> str:
    """Serialize decimals as strings to preserve precision, using strict JSON."""
    return json.dumps(analyze_performance(result), default=str, allow_nan=False,
                      sort_keys=True, indent=2) + "\n"
