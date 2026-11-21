"""Inspect raw MT5 tick records without sorting, deduplication or time conversion."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from numbers import Integral, Real


BID_FLAG, ASK_FLAG = 2, 4


def _integer(value):
    return isinstance(value, Integral) and not isinstance(value, bool)


def _price(value):
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(value)


def spread(row):
    """Return raw ask minus bid in price units for usable two-sided quotes."""
    bid, ask = row.get("bid"), row.get("ask")
    if _price(bid) and _price(ask) and 0 < bid <= ask:
        return str(Decimal(str(ask)) - Decimal(str(bid)))
    return None


@dataclass(frozen=True)
class TickIssue:
    index: int
    code: str


@dataclass(frozen=True)
class TickAudit:
    issues: tuple[TickIssue, ...]
    observations: dict[str, int]
    largest_raw_spacing_ms: int | None


def audit_ticks(rows, *, bounds=None):
    """Bounds are optional inclusive raw milliseconds, never assumed UTC."""
    issues = []
    notes = Counter()
    previous_ms = previous_quote = None
    largest = None
    for index, row in enumerate(rows):
        seconds, ms, flags = (row.get(key) for key in ("time", "time_msc", "flags"))
        bid, ask = row.get("bid"), row.get("ask")
        codes = []
        if any(value is None for value in (seconds, ms, flags, bid, ask)):
            codes.append("MISSING_FIELD")
        if not (_integer(seconds) and _integer(ms) and seconds > 0 and ms > 0
                and ms // 1000 == seconds):
            codes.append("INVALID_TIMESTAMP")
        else:
            if bounds is not None and not bounds[0] <= ms <= bounds[1]:
                codes.append("OUTSIDE_REQUEST_BOUNDS")
            if previous_ms is not None:
                delta = ms - previous_ms
                if delta < 0:
                    codes.append("OUT_OF_ORDER")
                else:
                    largest = max(largest or 0, delta)
                    if delta == 0:
                        notes["same_millisecond"] += 1
            previous_ms = ms
        if not _integer(flags) or flags < 0:
            codes.append("INVALID_FLAGS")
        elif flags & ~(2 | 4 | 8 | 16 | 32 | 64):
            notes["other_flag_bits"] += 1
        if bid is None or ask is None:
            previous_quote = None
        elif not (_price(bid) and _price(ask) and bid > 0 and ask > 0):
            codes.append("INVALID_BID_ASK")
            previous_quote = None
        elif ask < bid:
            codes.append("CROSSED_QUOTE")
            previous_quote = None
        else:
            if bid == ask:
                notes["zero_spread"] += 1
            if previous_quote is not None:
                for side, price, old, flag in zip(
                    ("bid", "ask"), (bid, ask), previous_quote, (BID_FLAG, ASK_FLAG),
                ):
                    if price == old:
                        notes[f"unchanged_{side}"] += 1
                    elif _integer(flags) and flags >= 0 and not flags & flag:
                        notes[f"{side}_change_without_flag"] += 1
            previous_quote = (bid, ask)
        issues.extend(TickIssue(index, code) for code in codes)
    return TickAudit(tuple(issues), dict(notes), largest)
