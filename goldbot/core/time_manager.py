"""Convert MT5 timestamps using independently verified, server-specific windows."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from numbers import Integral

from goldbot.core.config import MAX_QUOTE_AGE_SECONDS


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def aware_utc(value):
    if value.utcoffset() is None:
        raise ValueError("An aware datetime is required.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class OffsetWindow:
    """Caller-attested evidence must cover [valid_from, valid_until) in UTC."""

    server: str
    offset_seconds: int
    valid_from: datetime
    valid_until: datetime
    evidence: str

    def __post_init__(self):
        if not self.server.strip() or not self.evidence.strip():
            raise ValueError("Server and independent evidence are required.")
        if type(self.offset_seconds) is not int or abs(self.offset_seconds) >= 86400:
            raise ValueError("Offset must be an integer number of seconds within one day.")
        object.__setattr__(self, "valid_from", aware_utc(self.valid_from))
        object.__setattr__(self, "valid_until", aware_utc(self.valid_until))
        if self.valid_from >= self.valid_until:
            raise ValueError("Offset validity window must have positive duration.")

    @property
    def shift(self):
        return timedelta(seconds=self.offset_seconds)

    def contains(self, utc):
        return self.valid_from <= utc < self.valid_until


@dataclass(frozen=True)
class Timestamp:
    raw_seconds: int | None
    raw_milliseconds: int | None
    utc: datetime


class TimeManager:
    def __init__(self, server, windows):
        self.windows = tuple(sorted(
            (window for window in windows if window.server == server),
            key=lambda window: window.valid_from,
        ))
        for previous, current in zip(self.windows, self.windows[1:]):
            if previous.valid_until > current.valid_from:
                raise ValueError("Overlapping UTC offset windows for this server.")

    def decode(self, raw_seconds, raw_milliseconds=None):
        for raw in (raw_seconds, raw_milliseconds):
            if raw is not None and (
                isinstance(raw, bool) or not isinstance(raw, Integral) or raw < 0
            ):
                raise ValueError("Invalid raw timestamp.")
        if raw_milliseconds:
            seconds, milliseconds = divmod(int(raw_milliseconds), 1000)
            if raw_seconds and raw_seconds != seconds:
                raise ValueError("Raw timestamp fields disagree.")
        elif raw_seconds:
            seconds, milliseconds = int(raw_seconds), 0
        else:
            raise ValueError("Missing timestamp.")
        raw = EPOCH + timedelta(seconds=seconds, milliseconds=milliseconds)
        matches = []
        for window in self.windows:
            utc = raw - window.shift
            if window.contains(utc):
                matches.append(utc)
        if len(matches) != 1:
            raise ValueError("Timestamp has no unique verified UTC mapping.")
        return Timestamp(raw_seconds, raw_milliseconds, matches[0])

    def request_bounds(self, utc_from, utc_to):
        """Return inclusive MT5 integer bounds for a whole-second UTC range."""
        start, end = aware_utc(utc_from), aware_utc(utc_to)
        if start > end or start.microsecond or end.microsecond:
            raise ValueError("Expected ordered whole-second request bounds.")
        for window in self.windows:
            if window.contains(start) and window.contains(end):
                raw_start, raw_end = start + window.shift, end + window.shift
                for other in self.windows:
                    if other is window:
                        continue
                    if (raw_start < other.valid_until + other.shift
                            and raw_end >= other.valid_from + other.shift):
                        raise ValueError("Request intersects an ambiguous raw timestamp range.")
                first, last = (int((raw - EPOCH).total_seconds()) for raw in (raw_start, raw_end))
                if first <= 0:
                    raise ValueError("Request bounds must encode positive timestamps.")
                return first, last
        raise ValueError("Request must fit inside one verified offset window.")

    def require_fresh(self, raw_seconds, raw_milliseconds, now):
        """Return the timestamp only if its mapping is known and its age is 0–60s."""
        now = aware_utc(now)
        if not any(window.contains(now) for window in self.windows):
            raise ValueError("No current verified offset for this server.")
        timestamp = self.decode(raw_seconds, raw_milliseconds)
        age = now - timestamp.utc
        if age < timedelta(0):
            raise ValueError("FUTURE TIMESTAMP")
        if age > timedelta(seconds=MAX_QUOTE_AGE_SECONDS):
            raise ValueError("STALE")
        return timestamp
