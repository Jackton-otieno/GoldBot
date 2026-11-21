"""Deterministic USD sizing against an explicit stop and margin estimate."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from goldbot.risk.risk_config import decimal_at_least, positive


@dataclass(frozen=True)
class PositionSize:
    volume: Decimal
    modeled_loss: Decimal
    margin: Decimal


def size_position(*, stop_distance, budget, free_margin, specs, execution):
    # The distance already spans executable entry to the exit-side stop.
    if not positive(stop_distance):
        return None, "INVALID_STOP"
    if not all(positive(value) for value in (
        budget, specs.tick_size, specs.tick_value_loss, specs.volume_min,
        specs.volume_max, specs.volume_step, execution.margin_per_lot,
    )) or not all(decimal_at_least(value) for value in (
        free_margin, execution.stop_slippage, execution.commission_round_trip_per_lot,
    )):
        return None, "INVALID_SIZING_INPUT"
    if specs.volume_max < specs.volume_min or specs.volume_min % specs.volume_step:
        return None, "INVALID_VOLUME_GRID"

    loss_per_lot = (
        (stop_distance + execution.stop_slippage) / specs.tick_size
        * specs.tick_value_loss + execution.commission_round_trip_per_lot
    )
    # Cap at the broker maximum, then floor on the broker's volume grid.
    increment = specs.volume_step
    ceiling = min(specs.volume_max, budget / loss_per_lot)
    volume = (ceiling / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
    if volume < specs.volume_min:
        return None, "BELOW_MINIMUM_VOLUME"
    loss = volume * loss_per_lot
    if loss > budget:
        return None, "RISK_BUDGET_EXCEEDED"
    margin = volume * execution.margin_per_lot
    if margin > free_margin:
        return None, "INSUFFICIENT_MARGIN"
    return PositionSize(volume, loss, margin), "INDICATIVE"
