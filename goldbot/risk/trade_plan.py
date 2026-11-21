"""Indicative geometry and result types for Phase 5.1."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from goldbot.risk.risk_config import D, STOP_ATR_MULTIPLE, TARGET_STOP_MULTIPLE


def round_to_tick(price, tick, rounding):
    return (price / tick).to_integral_value(rounding=rounding) * tick


@dataclass(frozen=True)
class TradePlan:
    scenario_id: str
    risk_day_id: str
    symbol: str
    side: str
    entry: Decimal
    stop: Decimal
    target: Decimal
    stop_distance: Decimal
    spread: Decimal
    volume: Decimal
    loss_budget: Decimal
    modeled_stop_loss: Decimal
    modeled_margin: Decimal
    sources: tuple[str, ...]
    status: str = "INDICATIVE"
    caveat: str = "Gaps, spread changes and slippage can produce losses above the modeled amount."


@dataclass(frozen=True)
class RiskDecision:
    reason: str
    plan: TradePlan | None = None


def price_levels(side, atr, quote, specs):
    """Build levels from executable quote sides with adverse entry slippage."""
    buy = side == "BUY"
    direction = D(1) if buy else D(-1)
    reference = quote.ask if buy else quote.bid
    exit_quote = quote.bid if buy else quote.ask
    outward = ROUND_CEILING if buy else ROUND_FLOOR
    stop_rounding = ROUND_FLOOR if buy else ROUND_CEILING
    entry = round_to_tick(reference + direction * quote.entry_slippage,
                          specs.tick_size, outward)
    stop = round_to_tick(reference - direction * STOP_ATR_MULTIPLE * atr,
                         specs.tick_size, stop_rounding)
    distance = direction * (entry - stop)
    target = entry + direction * TARGET_STOP_MULTIPLE * distance
    minimum = specs.point * specs.stops_level_points
    if (min(entry, stop, target) <= 0 or distance <= 0
            or direction * (exit_quote - stop) <= 0
            or direction * (exit_quote - stop) < minimum
            or direction * (target - exit_quote) < minimum):
        return None
    return entry, stop, target, distance
