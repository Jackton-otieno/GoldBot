"""Evaluate one Phase 4.1 signal row against a verified offline scenario."""
from collections.abc import Mapping
from decimal import DecimalException, localcontext, Context

from goldbot.risk.position_sizing import size_position
from goldbot.risk.risk_config import (
    AccountState, BrokerSpecs, D, Evidence, ExecutionAssumptions, RiskDayState,
    MAX_DAILY_LOSS, MAX_DRAWDOWN, MAX_POSITIONS, RISK_PER_TRADE, SYMBOL,
    decimal_at_least, positive, verified,
)
from goldbot.risk.trade_plan import RiskDecision, TradePlan, price_levels


def evaluate_risk(row, *, scenario_id, risk_day_id, signal_evidence=None,
                  account=None, risk_day=None, specs=None, execution=None):
    """Return an indicative plan or a stable rejection reason."""
    if not isinstance(row, Mapping):
        return RiskDecision("INVALID_SIGNAL")
    side = row.get("decision")
    if side == "HOLD":
        return RiskDecision("HOLD_SIGNAL")
    if side not in ("BUY", "SELL") or row.get("reasons") != f"{side}_SETUP":
        return RiskDecision("INVALID_SIGNAL")
    if row.get("gap_before") != "False":
        return RiskDecision("UNVERIFIED_SIGNAL_INTERVAL")
    if not isinstance(signal_evidence, Evidence) or not signal_evidence.matches(scenario_id):
        return RiskDecision("UNVERIFIED_SIGNAL")
    try:
        with localcontext(Context(prec=40)):
            atr = D(str(row.get("atr_14")))
            if not positive(atr):
                return RiskDecision("INVALID_ATR")
            return _plan(side, atr, scenario_id, risk_day_id, signal_evidence,
                         account, risk_day, specs, execution)
    except DecimalException:
        return RiskDecision("INVALID_NUMERIC_INPUT")


def _plan(side, atr, scenario_id, risk_day_id, signal_evidence,
          account, day, specs, execution):
    if not isinstance(account, AccountState) or not verified(account, scenario_id):
        return RiskDecision("UNVERIFIED_ACCOUNT")
    if (not isinstance(day, RiskDayState) or not verified(day, scenario_id)
            or not isinstance(risk_day_id, str) or not risk_day_id.strip()
            or day.risk_day_id != risk_day_id or day.account_ref != account.account_ref):
        return RiskDecision("UNVERIFIED_RISK_DAY")
    if (not isinstance(account.account_ref, str) or not account.account_ref.strip()
            or not all(positive(value) for value in (
                account.equity, account.peak_equity, day.opening_equity,
            ))
            or account.peak_equity < max(account.equity, day.opening_equity)
            or not decimal_at_least(account.free_margin)
            or not decimal_at_least(day.loss_to_date)
            or type(account.open_positions) is not int or account.open_positions < 0):
        return RiskDecision("INVALID_STATE")
    if account.currency != "USD":
        return RiskDecision("UNSUPPORTED_CURRENCY")
    if account.open_positions >= MAX_POSITIONS:
        return RiskDecision("POSITION_LIMIT")

    daily_used = max(day.loss_to_date, day.opening_equity - account.equity)
    daily_remaining = day.opening_equity * MAX_DAILY_LOSS - daily_used
    if daily_remaining <= 0:
        return RiskDecision("DAILY_LOSS_LIMIT")
    drawdown_remaining = account.equity - account.peak_equity * (1 - MAX_DRAWDOWN)
    if drawdown_remaining <= 0:
        return RiskDecision("DRAWDOWN_LIMIT")
    budget = min(account.equity * RISK_PER_TRADE, daily_remaining, drawdown_remaining)

    if not isinstance(specs, BrokerSpecs) or not verified(specs, scenario_id):
        return RiskDecision("UNVERIFIED_BROKER_SPECS")
    if (not isinstance(execution, ExecutionAssumptions)
            or not verified(execution, scenario_id)):
        return RiskDecision("UNVERIFIED_EXECUTION")
    if specs.symbol != SYMBOL or execution.symbol != SYMBOL or execution.side != side:
        return RiskDecision("EXECUTION_MISMATCH")
    if specs.profit_currency != "USD" or specs.margin_currency != "USD":
        return RiskDecision("UNSUPPORTED_CURRENCY")
    if specs.loss_model != "USD_LINEAR":
        return RiskDecision("UNSUPPORTED_LOSS_MODEL")
    if (not all(positive(value) for value in (
            specs.point, specs.tick_size, specs.contract_size, specs.tick_value_loss,
            execution.bid, execution.ask,
        ))
            or execution.ask < execution.bid
            or not all(decimal_at_least(value) for value in (
                execution.entry_slippage, execution.stop_slippage,
            ))
            or type(specs.stops_level_points) is not int or specs.stops_level_points < 0):
        return RiskDecision("INVALID_MARKET_INPUT")
    if specs.tick_value_loss != specs.tick_size * specs.contract_size:
        return RiskDecision("INCONSISTENT_TICK_VALUE")

    levels = price_levels(side, atr, execution, specs)
    if levels is None:
        return RiskDecision("INVALID_STOP_OR_TARGET")
    entry, stop, target, distance = levels
    if side == "BUY" and stop <= execution.stop_slippage:
        return RiskDecision("INVALID_STOP_OR_TARGET")
    size, reason = size_position(stop_distance=distance, budget=budget,
                                 free_margin=account.free_margin, specs=specs,
                                 execution=execution)
    if size is None:
        return RiskDecision(reason)
    return RiskDecision(reason, TradePlan(
        scenario_id=scenario_id, risk_day_id=risk_day_id, symbol=SYMBOL, side=side,
        entry=entry, stop=stop, target=target, stop_distance=distance,
        spread=execution.ask - execution.bid, volume=size.volume, loss_budget=budget,
        modeled_stop_loss=size.modeled_loss, modeled_margin=size.margin,
        sources=tuple(value.source for value in (
            signal_evidence, account.evidence, day.evidence, specs.evidence, execution.evidence,
        )),
    ))
