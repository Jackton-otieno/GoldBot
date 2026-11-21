"""Measured server-label offset for the Exness MT5 demo (Phase 6.11).

Archive-versus-MT5 matching found server label = UTC+2 in winter and UTC+3
in summer, switching between 27 and 29 March 2026 and between 23 and 25
October 2026. Both changes are consistent with the EU rule: summer time runs
from 01:00 UTC on the last Sunday of March to 01:00 UTC on the last Sunday of
October. This is a measured rule for research use, not a broker statement.
Dates outside the measured transitions are extrapolated.
"""

from datetime import datetime, timedelta, timezone


MEASURED_TRANSITIONS_UTC_DATES = ("2026-03-29", "2026-10-25")
RULE = "EU daylight saving, measured for the 2026 transitions"


def _last_sunday_0100(year, month):
    day = datetime(year, month + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    return day - timedelta(days=(day.weekday() - 6) % 7)


def offset_hours(moment):
    """Server label minus UTC, in hours, for an aware datetime."""
    if moment.tzinfo is None:
        raise ValueError("an explicit UTC offset is required")
    moment = moment.astimezone(timezone.utc)
    summer = _last_sunday_0100(moment.year, 3) <= moment < _last_sunday_0100(moment.year, 10)
    return 3 if summer else 2
