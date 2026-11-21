"""Evaluate a closed candle against its preceding observed candle."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, isnan

from goldbot.strategy.strategy_config import (
    RSI_BEAR_FLOOR, RSI_BULL_CEILING, RSI_MIDPOINT, StrategyConfig,
)


@dataclass(frozen=True)
class Indicators:
    ema_9: float
    ema_21: float
    ema_50: float
    ema_200: float
    rsi_14: float
    macd_histogram: float
    atr_14: float


@dataclass(frozen=True)
class Signal:
    decision: str
    reasons: tuple[str, ...]


def evaluate(current: Indicators, previous: Indicators | None, *,
             gap_before: bool = False, config: StrategyConfig = StrategyConfig()) -> Signal:
    values = (
        current.ema_9, current.ema_21, current.ema_50, current.ema_200,
        current.rsi_14, current.macd_histogram, current.atr_14,
    )
    if previous is not None:
        values += (previous.ema_9, previous.ema_21)
    if (
        any(type(value) not in (int, float) or not (isfinite(value) or isnan(value))
            for value in values)
        or not isinstance(gap_before, bool)
    ):
        return Signal("HOLD", ("INVALID_INPUT",))
    if current.rsi_14 < 0 or current.rsi_14 > 100 or current.atr_14 < 0:
        return Signal("HOLD", ("INVALID_INPUT",))
    if previous is None or any(isnan(value) for value in values):
        return Signal("HOLD", ("WARMUP",))

    crosses_up = previous.ema_9 <= previous.ema_21 and current.ema_9 > current.ema_21
    crosses_down = previous.ema_9 >= previous.ema_21 and current.ema_9 < current.ema_21
    if not (crosses_up or crosses_down):
        return Signal("HOLD", ("NO_CROSSOVER",))

    reasons = []
    if gap_before and config.hold_gap_crossovers:
        reasons.append("GAP_CROSSOVER")
    if crosses_up:
        direction = "BUY"
        trend_ok = current.ema_50 > current.ema_200
        rsi_ok = RSI_MIDPOINT < current.rsi_14 < RSI_BULL_CEILING
        macd_ok = current.macd_histogram > 0
    else:
        direction = "SELL"
        trend_ok = current.ema_50 < current.ema_200
        rsi_ok = RSI_BEAR_FLOOR < current.rsi_14 < RSI_MIDPOINT
        macd_ok = current.macd_histogram < 0

    if not trend_ok:
        reasons.append("TREND_FILTER")
    if not rsi_ok:
        reasons.append("RSI_FILTER")
    if not macd_ok:
        reasons.append("MACD_FILTER")
    if current.atr_14 == 0:
        reasons.append("ATR_FILTER")
    if reasons:
        return Signal("HOLD", tuple(reasons))
    return Signal(direction, (f"{direction}_SETUP",))

