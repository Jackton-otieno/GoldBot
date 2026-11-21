"""Baseline thresholds and offline gap policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    hold_gap_crossovers: bool = True


RSI_BEAR_FLOOR = 30
RSI_MIDPOINT = 50
RSI_BULL_CEILING = 70
