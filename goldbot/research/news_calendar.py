"""Point-in-time US release blackout calendar (research only).

The calendar is a set of dated captures of official schedule pages: BLS
Employment Situation (NFP), BLS CPI and the Federal Reserve FOMC calendar.
For a decision at UTC time ``t``, only the latest capture of each source
taken at or before ``t`` is used, so a later revision to a schedule is never
visible early. New entries are blocked from 30 minutes before to 30 minutes
after each scheduled release, inclusive. Entries are also blocked, never
assumed safe, when a source has no capture yet, when its latest capture is
older than the freshness limit, or when ``t`` lies beyond the last release
that capture lists.

The same ``NewsCalendar.decide`` serves backtests and any future execution.
It only gates new entries; existing positions are untouched. It does not
change any frozen strategy, and it grants no trading authority.
"""

from __future__ import annotations

import gzip
import html as html_lib
import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")
NAIROBI = ZoneInfo("Africa/Nairobi")
BLACKOUT = timedelta(minutes=30)
MAX_CAPTURE_AGE = timedelta(days=35)
FOMC_STATEMENT_TIME_ET = time(14, 0)
SOURCES = {
    "BLS_EMPSIT": {"event": "NFP (Employment Situation)",
                   "url": "https://www.bls.gov/schedule/news_release/empsit.htm"},
    "BLS_CPI": {"event": "CPI",
                "url": "https://www.bls.gov/schedule/news_release/cpi.htm"},
    "FED_FOMC": {"event": "FOMC statement",
                 "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"},
}
MONTHS = {name[:3].lower(): number for number, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"), start=1)}


class CalendarError(ValueError):
    pass


def to_utc(day, clock):
    """US Eastern wall-clock time on ``day`` as an aware UTC datetime."""
    return datetime.combine(day, clock, ET).astimezone(timezone.utc)


def display_times(moment):
    """Presentation only: one UTC instant shown in UTC, New York and Kenya time.

    Calculations always use the UTC instant; these strings are never parsed back.
    """
    if moment.tzinfo is None:
        raise CalendarError("An aware datetime is required.")
    return {zone_name: f"{moment.astimezone(zone):%Y-%m-%d %H:%M} {moment.astimezone(zone).tzname()}"
            for zone_name, zone in (("utc", timezone.utc), ("new_york", ET), ("kenya", NAIROBI))}


def describe_event(event, blackout=BLACKOUT):
    """An event with its release time and blackout window in all three zones."""
    when = datetime.fromisoformat(event["scheduled_utc"])
    return {"event": event["event"], "reference": event.get("reference"),
            "release": display_times(when),
            "blackout_from": display_times(when - blackout),
            "blackout_until": display_times(when + blackout)}


def decode_page(raw):
    """Page bytes as text. Archived bodies are sometimes still gzip-encoded."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _text(fragment):
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _month(token):
    number = MONTHS.get(token.strip().rstrip(".")[:3].lower())
    if number is None:
        raise CalendarError(f"Unrecognized month {token!r}.")
    return number


def parse_bls(page):
    """Rows of a BLS 'Schedule of Releases' table as (reference, UTC datetime)."""
    table = re.search(r'<table class="release-list">(.*?)</table>', page, re.S)
    if not table:
        raise CalendarError("BLS release table not found.")
    body = re.search(r"<tbody>(.*?)</tbody>", table[1], re.S)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body[1] if body else "", re.S)
    events = []
    for row in rows:
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != 3:
            raise CalendarError(f"Unexpected BLS row {cells!r}.")
        reference, released, at = cells
        when = re.fullmatch(r"([A-Za-z]+)\.? (\d{1,2}), (\d{4})", released)
        clock = re.fullmatch(r"(\d{1,2}):(\d{2}) ([AP])M", at)
        if not when or not clock:
            raise CalendarError(f"Unparseable BLS release {released!r} {at!r}.")
        hour = int(clock[1]) % 12 + (12 if clock[3] == "P" else 0)
        day = date(int(when[3]), _month(when[1]), int(when[2]))
        events.append((reference, to_utc(day, time(hour, int(clock[2])))))
    if not events:
        raise CalendarError("BLS release table is empty.")
    return events


def parse_fomc(page):
    """Scheduled FOMC meetings as (label, statement UTC datetime, flags).

    Unscheduled meetings and notation votes are skipped; they cannot be
    known in advance. The statement is placed on the meeting's last day at
    FOMC_STATEMENT_TIME_ET.
    """
    headers = list(re.finditer(r"(\d{4}) FOMC Meetings", page))
    if not headers:
        raise CalendarError("FOMC year sections not found.")
    events, skipped = [], []
    for index, header in enumerate(headers):
        year = int(header[1])
        end = headers[index + 1].start() if index + 1 < len(headers) else len(page)
        section = page[header.end():end]
        rows = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>(.*?)</strong>\s*</div>\s*'
                          r'<div class="fomc-meeting__date[^"]*">(.*?)</div>', section, re.S)
        for month_text, date_text in rows:
            month_text, date_text = _text(month_text), _text(date_text)
            if re.search(r"(?i)unscheduled|notation|conference call", date_text + month_text):
                skipped.append(f"{year} {month_text} {date_text}")
                continue
            days = [int(d) for d in re.findall(r"\d+", date_text)]
            if not days:
                raise CalendarError(f"Unparseable FOMC date {month_text!r} {date_text!r}.")
            months = [_month(m) for m in month_text.split("/")]
            if len(months) == 1:
                month = months[0]
            elif len(months) == 2 and len(days) == 2 and days[1] < days[0]:
                month = months[1]  # e.g. "Apr/May 30-1": the last day falls in May
            else:
                raise CalendarError(f"Ambiguous FOMC date {month_text!r} {date_text!r}.")
            final = date(year, month, days[-1])
            label = f"{year} {month_text} {date_text}"
            events.append((label, to_utc(final, FOMC_STATEMENT_TIME_ET),
                           ["SEP"] if "*" in date_text else []))
    return events, skipped


def snapshot_events(source, page):
    name = SOURCES[source]["event"]
    if source == "FED_FOMC":
        parsed, skipped = parse_fomc(page)
        return ([{"event": name, "reference": label, "scheduled_utc": when.isoformat(), "flags": flags}
                 for label, when, flags in parsed], skipped)
    return ([{"event": name, "reference": ref, "scheduled_utc": when.isoformat(), "flags": []}
             for ref, when in parse_bls(page)], [])


def canonical_bytes(calendar):
    body = {k: v for k, v in calendar.items() if k != "calendar_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def seal(calendar):
    """Return the calendar with its own SHA-256 over every other field."""
    return dict(calendar, calendar_sha256=sha256(canonical_bytes(calendar)).hexdigest())


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    events: tuple
    coverage: tuple
    problems: tuple = ()

    def record(self):
        return {"allowed": self.allowed, "reason": self.reason, "events": list(self.events),
                "problems": [{"code": c, "source": s} for c, s in self.problems],
                "coverage": list(self.coverage)}


CONFLICT_WINDOW = timedelta(days=3)
METHODS = ("wayback", "operator_import")
PROBLEM_ORDER = ("CALENDAR_COVERAGE_MISSING", "CALENDAR_STALE", "CALENDAR_HORIZON_EXCEEDED",
                 "CALENDAR_CONFLICT")


class NewsCalendar:
    """Answer 'may a new entry be opened at this UTC instant?' point-in-time.

    Captures arrive by two routes: Wayback Machine captures (primary) and
    operator-imported official pages (fallback). For each source the newest
    capture at or before the decision is used, whichever route it came from.
    If the newest captures from the two routes are within CONFLICT_WINDOW of
    each other and disagree about any upcoming release, new entries are
    refused with CALENDAR_CONFLICT until the routes agree or one is clearly
    newer.
    """

    def __init__(self, calendar, *, blackout=BLACKOUT, max_capture_age=MAX_CAPTURE_AGE,
                 conflict_window=CONFLICT_WINDOW):
        if calendar.get("calendar_sha256") != sha256(canonical_bytes(calendar)).hexdigest():
            raise CalendarError("Calendar SHA-256 does not match its contents.")
        self.sha256 = calendar["calendar_sha256"]
        self.blackout, self.max_age, self.conflict_window = blackout, max_capture_age, conflict_window
        contents = calendar["contents"]
        self._captures, self._times = {}, {}
        for source in SOURCES:
            rows = sorted((datetime.fromisoformat(c["captured_utc"]), c.get("method", "wayback"),
                           c["content_sha256"], c.get("wayback") or c.get("url"))
                          for c in calendar["captures"] if c["source"] == source)
            for _, method, digest, _ in rows:
                if digest not in contents:
                    raise CalendarError(f"Capture refers to unknown content {digest[:12]}.")
                if method not in METHODS:
                    raise CalendarError(f"Unknown capture method {method!r}.")
            self._captures[source] = rows
            self._times[source] = [row[0] for row in rows]
        self._events = {digest: sorted(((datetime.fromisoformat(e["scheduled_utc"]), e)
                                        for e in body["events"]), key=lambda item: item[0])
                        for digest, body in contents.items()}

    def _latest(self, source, moment, method=None):
        index = bisect_right(self._times[source], moment)
        for row in reversed(self._captures[source][:index]):
            if method is None or row[1] == method:
                return row
        return None

    def _horizon(self, digest):
        events = self._events[digest]
        return events[-1][0] if events else None

    def latest_capture(self, source, moment):
        """(captured_utc, content_sha256, events) of the newest capture at or before
        ``moment``, or None. Read-only view used for display."""
        row = self._latest(source, moment)
        if row is None:
            return None
        captured, _, digest, _ = row
        return captured, digest, [event for _, event in self._events[digest]]

    def _conflict(self, source, moment, chosen):
        """Disagreement between the two routes' newest captures, if they are close in time."""
        captured, method, digest, _ = chosen
        other = self._latest(source, moment, next(m for m in METHODS if m != method))
        if other is None or captured - other[0] > self.conflict_window or moment - other[0] > self.max_age:
            return None
        horizons = [h for h in (self._horizon(digest), self._horizon(other[2])) if h is not None]
        until, since = min(horizons) if horizons else moment, moment - self.blackout

        def upcoming(content):
            return {e["reference"]: when.isoformat() for when, e in self._events[content]
                    if since <= when <= until}

        mine, theirs = upcoming(digest), upcoming(other[2])
        if mine == theirs:
            return None
        return {"source": source, "captures": [
            {"method": method, "captured_utc": captured.isoformat(), "upcoming": mine},
            {"method": other[1], "captured_utc": other[0].isoformat(), "upcoming": theirs}]}

    def coverage_report(self, moment):
        """Per source: the capture in use, and the exact UTC instants after which,
        without a new capture, entries would be refused as stale or out of range."""
        moment = moment.astimezone(timezone.utc)
        sources, limits = {}, []
        for source in SOURCES:
            row = self._latest(source, moment)
            if row is None:
                sources[source] = {"status": "CALENDAR_COVERAGE_MISSING"}
                continue
            captured, method, digest, location = row
            stale_after = captured + self.max_age
            horizon = self._horizon(digest)
            listed_until = horizon + self.blackout if horizon else captured
            limits.append(min(stale_after, listed_until))
            sources[source] = {"method": method, "captured_utc": captured.isoformat(),
                               "location": location, "stale_after_utc": stale_after.isoformat(),
                               "last_listed_release_utc": horizon.isoformat() if horizon else None,
                               "listed_until_utc": listed_until.isoformat()}
        return {"at_utc": moment.isoformat(), "sources": sources,
                "entries_refused_after_utc": min(limits).isoformat()
                if len(limits) == len(SOURCES) else None}

    def decide(self, moment):
        """Return a Decision for a new entry at the aware datetime ``moment``."""
        if moment.tzinfo is None:
            raise CalendarError("An aware UTC datetime is required.")
        moment = moment.astimezone(timezone.utc)
        problems, hits, coverage, conflicts = [], [], [], []
        for source in SOURCES:
            chosen = self._latest(source, moment)
            if chosen is None:
                problems.append(("CALENDAR_COVERAGE_MISSING", source))
                coverage.append({"source": source, "capture": None})
                continue
            captured, method, digest, location = chosen
            coverage.append({"source": source, "method": method, "captured_utc": captured.isoformat(),
                             "content_sha256": digest, "location": location})
            if moment - captured > self.max_age:
                problems.append(("CALENDAR_STALE", source))
                continue
            horizon = self._horizon(digest)
            if horizon is None or moment > horizon + self.blackout:
                problems.append(("CALENDAR_HORIZON_EXCEEDED", source))
                continue
            conflict = self._conflict(source, moment, chosen)
            if conflict is not None:
                problems.append(("CALENDAR_CONFLICT", source))
                conflicts.append(conflict)
            for when, event in self._events[digest]:
                if when - self.blackout <= moment <= when + self.blackout:
                    hits.append(dict(event, source=source, capture_utc=captured.isoformat(),
                                     capture_method=method, content_sha256=digest))
        coverage.extend({"conflict": c} for c in conflicts)
        for code in PROBLEM_ORDER:
            if any(p[0] == code for p in problems):
                return Decision(False, code, tuple(hits), tuple(coverage), tuple(problems))
        if hits:
            return Decision(False, "NEWS_BLACKOUT", tuple(hits), tuple(coverage))
        return Decision(True, "ALLOWED", (), tuple(coverage))
