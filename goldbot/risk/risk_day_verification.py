"""Evaluate a policy-defined daily reset without mutating existing risk state."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from goldbot.core.time_manager import aware_utc
from goldbot.market_data.session_verification import (
    Authority, MarketScope, UTCInterval, unique_interval, verified_converter,
)
from goldbot.risk.risk_config import positive


@dataclass(frozen=True)
class RiskDayScope:
    market: MarketScope
    account_ref: str
    policy_ref: str

    def __post_init__(self):
        if not self.account_ref.strip() or not self.policy_ref.strip():
            raise ValueError("An account and policy reference are required.")


@dataclass(frozen=True)
class PolicyDay:
    scope: RiskDayScope
    day_id: str
    interval: UTCInterval
    authority: Authority

    def __post_init__(self):
        if not self.day_id.strip() or not isinstance(self.authority, Authority):
            raise ValueError("A day ID and policy authority are required.")


@dataclass(frozen=True)
class BoundaryEquity:
    scope: RiskDayScope
    at: datetime
    equity: Decimal
    authority: Authority

    def __post_init__(self):
        object.__setattr__(self, "at", aware_utc(self.at))
        if not positive(self.equity) or not isinstance(self.authority, Authority):
            raise ValueError("Verified positive boundary equity is required.")


@dataclass(frozen=True)
class DailyState:
    day: PolicyDay
    opening_equity: Decimal
    loss_to_date: Decimal
    daily_latched: bool


@dataclass(frozen=True)
class BoundaryDecision:
    status: str
    state: DailyState


def evaluate_boundary(state, *, clock, windows, days, equity=None):
    """Accept only one direct, verified successor with equity at its boundary.

    The caller must persist the returned state atomically with its own ledger.
    This function handles established state and does not initialize a ledger.
    """
    scope = state.day.scope
    try:
        verified_converter(clock, scope.market, windows)
    except (ValueError, OverflowError):
        return BoundaryDecision("UNVERIFIED_CLOCK", state)
    scoped = tuple(day for day in days if day.scope == scope)
    current = unique_interval(scoped, clock)
    if (current is None or state.day not in scoped
            or len({day.day_id for day in scoped}) != len(scoped)):
        return BoundaryDecision("UNVERIFIED_POLICY_DAY", state)
    if current == state.day:
        return BoundaryDecision("SAME_DAY", state)
    if current.interval.start != state.day.interval.end:
        return BoundaryDecision("UNVERIFIED_SUCCESSOR", state)
    if (not isinstance(equity, BoundaryEquity) or equity.scope != scope
            or equity.at != current.interval.start):
        return BoundaryDecision("MISSING_BOUNDARY_EQUITY", state)
    return BoundaryDecision("RESET", replace(
        state, day=current, opening_equity=equity.equity, loss_to_date=Decimal(0),
        daily_latched=False,
    ))
