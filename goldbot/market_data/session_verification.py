"""Evaluate explicitly attested UTC session intervals. No broker calendar is bundled."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import isfinite

from goldbot.core.config import MAX_QUOTE_AGE_SECONDS
from goldbot.core.time_manager import OffsetWindow, TimeManager, aware_utc


@dataclass(frozen=True)
class MarketScope:
    server: str
    symbol: str

    def __post_init__(self):
        if not self.server.strip() or not self.symbol.strip():
            raise ValueError("Exact server and symbol are required.")


@dataclass(frozen=True)
class Authority:
    """A caller-reviewed authority and traceable artifact reference."""

    issuer: str
    reference: str

    def __post_init__(self):
        if not self.issuer.strip() or not self.reference.strip():
            raise ValueError("An issuer and evidence reference are required.")


@dataclass(frozen=True)
class UTCInterval:
    start: datetime
    end: datetime

    def __post_init__(self):
        for field in ("start", "end"):
            object.__setattr__(self, field, aware_utc(getattr(self, field)))
        if self.start >= self.end:
            raise ValueError("Expected a positive-duration UTC interval.")


@dataclass(frozen=True)
class VerifiedClock:
    """Current UTC uncertainty bracket attested by the caller for this observation."""

    scope: MarketScope
    earliest: datetime
    latest: datetime
    authority: Authority

    def __post_init__(self):
        for field in ("earliest", "latest"):
            object.__setattr__(self, field, aware_utc(getattr(self, field)))
        if self.earliest > self.latest or not isinstance(self.authority, Authority):
            raise ValueError("Expected an ordered, independently attested UTC bracket.")

    def inside(self, interval):
        return interval.start <= self.earliest <= self.latest < interval.end


def verified_converter(clock, scope, windows):
    """Require a unique current offset across the entire clock bracket."""
    if not isinstance(clock, VerifiedClock) or clock.scope != scope:
        raise ValueError("No verified clock for this server and symbol.")
    converter = TimeManager(scope.server, windows)
    current = next((window for window in converter.windows
                    if window.contains(clock.earliest) and window.contains(clock.latest)), None)
    if not isinstance(current, OffsetWindow):
        raise ValueError("No single verified offset covers the clock bracket.")
    if any(other is not current
           and clock.earliest + current.shift < other.valid_until + other.shift
           and clock.latest + current.shift >= other.valid_from + other.shift
           for other in converter.windows):
        raise ValueError("Current server clock is ambiguous.")
    return converter


class SessionKind(Enum):
    QUOTE = "quote"
    TRADE = "trade"


class SessionState(Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class SessionEvidence:
    """A dated assertion including applicable exceptions, from the broker."""

    scope: MarketScope
    kind: SessionKind
    interval: UTCInterval
    state: SessionState
    authority: Authority

    def __post_init__(self):
        if (not isinstance(self.kind, SessionKind) or not isinstance(self.authority, Authority)
                or self.state not in (SessionState.OPEN, SessionState.CLOSED)):
            raise ValueError("Explicit open or closed broker session evidence is required.")


def unique_interval(records, clock):
    """Reject conflicting scoped evidence and require whole-bracket coverage."""
    ordered = sorted(records, key=lambda item: item.interval.start)
    if any(left.interval.end > right.interval.start for left, right in zip(ordered, ordered[1:])):
        return None
    return next((item for item in ordered if clock.inside(item.interval)), None)


def session_at(scope, kind, clock, windows, evidence):
    try:
        verified_converter(clock, scope, windows)
    except (ValueError, OverflowError):
        return None
    return unique_interval((item for item in evidence if item.scope == scope and item.kind == kind), clock)


def require_session_quote(scope, clock, windows, evidence, tick):
    """Accept a valid quote only inside the current verified quote interval."""
    converter = verified_converter(clock, scope, windows)
    session = unique_interval(
        (item for item in evidence if item.scope == scope and item.kind == SessionKind.QUOTE), clock,
    )
    if session is None or session.state != SessionState.OPEN:
        raise ValueError("Quote session is not verified open.")
    if (tick is None or not all(isfinite(price) for price in (tick.bid, tick.ask))
            or not 0 < tick.bid <= tick.ask):
        raise ValueError("Invalid quote prices.")
    timestamp = converter.decode(tick.time, tick.time_msc)
    if not session.interval.start <= timestamp.utc <= clock.earliest:
        raise ValueError("Quote precedes this session or may be in the future.")
    if clock.latest - timestamp.utc > timedelta(seconds=MAX_QUOTE_AGE_SECONDS):
        raise ValueError("STALE")
    return timestamp
