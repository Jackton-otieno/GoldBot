"""Standalone evidence gate for historical execution inputs. No replay or order calls."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import json

from goldbot.analysis.data_analysis import INTERVALS
from goldbot.backtesting.historical_replay import _validated_rows
from goldbot.core.time_manager import TimeManager
from goldbot.market_data.session_verification import Authority, SessionKind, SessionState, UTCInterval
from goldbot.market_data.tick_data import audit_ticks
from goldbot.risk.risk_day_verification import PolicyDay, RiskDayScope


SCHEDULES = ("contract_and_tick_economics", "commission", "swap",
             "margin", "account_currency_and_conversion")


@dataclass(frozen=True)
class DatasetEvidence:
    scope: RiskDayScope
    timeframe: str
    sha256: str
    quote_basis: str
    authority: Authority


@dataclass(frozen=True)
class TickCoverage:
    scope: RiskDayScope
    interval: UTCInterval
    rows_sha256: str
    authority: Authority
    # Attests all events and original order for this exact interval and digest.
    exhaustive: bool = False
    quote_basis: str = ""


@dataclass(frozen=True)
class EffectiveSchedule:
    scope: RiskDayScope
    interval: UTCInterval
    topic: str
    # Identifies the reviewed, applicable schedule with values, units and calculation rules.
    schedule_ref: str
    authority: Authority
    historical_applicability_attested: bool = False


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str


@dataclass(frozen=True)
class Readiness:
    findings: tuple[Finding, ...]

    @property
    def ready(self):
        return not self.findings


def rows_digest(rows):
    if not isinstance(rows, (list, tuple)) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Expected an ordered sequence of raw tick row mappings.")
    return sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("ascii")).hexdigest()


def _cover(interval, records):
    """Return in-scope intersecting records and exact gaps/overlaps."""
    intersecting = sorted(
        (item for item in records
         if item.interval.start < interval.end and interval.start < item.interval.end),
        key=lambda item: item.interval.start,
    )
    gaps, overlap = [], False
    cursor = interval.start
    for record in intersecting:
        start = max(interval.start, record.interval.start)
        end = min(interval.end, record.interval.end)
        if cursor > start:
            overlap = True
        if cursor < start:
            gaps.append(UTCInterval(cursor, start))
        cursor = max(cursor, end)
    if cursor < interval.end:
        gaps.append(UTCInterval(cursor, interval.end))
    return intersecting, gaps, overlap


@dataclass(frozen=True)
class _ClockSpan:
    interval: UTCInterval


def _clock(server, windows, interval):
    converter = TimeManager(server, windows)
    spans = [_ClockSpan(UTCInterval(w.valid_from, w.valid_until)) for w in converter.windows]
    _, gaps, _ = _cover(interval, spans)
    if gaps:
        raise ValueError("Offset evidence does not cover the requested UTC interval.")
    for window in converter.windows:
        start = max(interval.start, window.valid_from)
        end = min(interval.end, window.valid_until)
        if start >= end:
            continue
        if any(other is not window
               and start + window.shift < other.valid_until + other.shift
               and end + window.shift > other.valid_from + other.shift
               for other in converter.windows):
            raise ValueError("Offset windows produce ambiguous raw coordinates.")
    return converter


def verify_execution_data(
    scope: RiskDayScope, interval: UTCInterval, *, candle_bytes=None, dataset=None,
    batches=(), candle_offsets=(), tick_offsets=(), sessions=(), schedules=(), days=(),
    max_quote_silence=None,
):
    """Check caller-reviewed evidence for a complete half-open target interval.

    This checks scope, identity, coverage and consistency. Authorities and schedule
    references must be resolved and reviewed by the caller before use.
    Each batch is (TickCoverage, sequence of raw tick mappings).
    """
    findings = []

    def add(code, subject, detail):
        findings.append(Finding(code, subject, detail))

    def cover(subject, records):
        covered, gaps, overlap = _cover(interval, records)
        for gap in gaps:
            add("COVERAGE_HOLE", subject, f"{gap.start.isoformat()} to {gap.end.isoformat()}")
        if overlap:
            add("OVERLAPPING_EVIDENCE", subject, "Intersecting effective intervals.")
        return covered

    def clock(subject, windows):
        try:
            return _clock(scope.market.server, windows, interval)
        except (ValueError, OverflowError) as error:
            add("UTC_UNVERIFIED", subject, str(error))
            return None

    candle_gaps = []
    candle_clock = clock("candles", candle_offsets)
    tick_clock = clock("ticks", tick_offsets)
    if (not isinstance(dataset, DatasetEvidence) or dataset.scope != scope
            or not isinstance(dataset.authority, Authority) or not isinstance(candle_bytes, bytes)
            or sha256(candle_bytes).hexdigest() != dataset.sha256):
        add("PROVENANCE_UNVERIFIED", "candles", "Expected reviewed scope and exact CSV SHA-256.")
    else:
        if dataset.quote_basis not in ("bid", "ask", "last", "mid"):
            add("QUOTE_BASIS_UNVERIFIED", "candles", "Expected documented historical OHLC basis.")
        try:
            labels = _validated_rows(candle_bytes, dataset.timeframe, None)
            if candle_clock:
                step = timedelta(seconds=INTERVALS[dataset.timeframe])
                # Validate the full dataset, including labels near offset transitions.
                times = [candle_clock.decode(row[0]).utc for row in labels]
                if times[0] != interval.start or times[-1] + step != interval.end:
                    add("DATASET_RANGE_MISMATCH", "candles", "Target must span the full CSV including its final bar.")
                candle_gaps = [(left + step, right) for left, right in zip(times, times[1:])
                               if right - left > step]
                if any(right - left < step for left, right in zip(times, times[1:])):
                    add("INVALID_CANDLE_ORDER", "candles", "Decoded candles are out of order or overlap.")
        except (KeyError, ValueError, OverflowError) as error:
            add("CANDLE_DATA_UNVERIFIED", "candles", str(error))

    quote_sessions = []
    for kind in SessionKind:
        covered = cover(f"{kind.value}_sessions", (
            item for item in sessions if item.scope == scope.market and item.kind == kind
            and isinstance(item.authority, Authority)
        ))
        if kind == SessionKind.QUOTE:
            quote_sessions = covered
    for start, end in candle_gaps:
        if any(item.state == SessionState.OPEN
               and item.interval.start < end and item.interval.end > start
               for item in quote_sessions):
            add("CANDLE_GAP_DURING_OPEN_SESSION", "candles",
                f"{start.isoformat()} to {end.isoformat()}")
    for topic in SCHEDULES:
        cover(topic, (record for record in schedules if record.scope == scope
                      and record.topic == topic and record.historical_applicability_attested is True
                      and isinstance(record.schedule_ref, str) and record.schedule_ref.strip()
                      and isinstance(record.authority, Authority)))
    policy_days = cover("policy_risk_days", (day for day in days
                        if isinstance(day, PolicyDay) and day.scope == scope))
    if len({day.day_id for day in policy_days}) != len(policy_days):
        add("DUPLICATE_RISK_DAY", "policy_risk_days", "Risk-day identifiers must be distinct.")

    accepted, tick_times = [], []
    for index, (claim, rows) in enumerate(batches):
        subject = f"ticks[{index}]"
        if (not isinstance(claim, TickCoverage) or claim.scope != scope
                or not isinstance(claim.authority, Authority)):
            add("PROVENANCE_UNVERIFIED", subject, "Missing reviewed source scope or authority.")
            continue
        try:
            digest = rows_digest(rows)
        except (TypeError, ValueError):
            digest = None
        if digest is None or digest != claim.rows_sha256:
            add("PROVENANCE_UNVERIFIED", subject, "Tick content fails SHA-256 binding.")
            continue
        if claim.exhaustive is not True:
            add("SAMPLE_ONLY", subject, "Samples do not establish complete tick coverage.")
            continue
        if claim.quote_basis != "broker_bid_ask":
            add("QUOTE_BASIS_UNVERIFIED", subject, "Expected documented historical broker bid and ask.")
            continue
        audit = audit_ticks(rows)
        if audit.issues:
            for issue in audit.issues:
                add(issue.code, subject, f"Returned row index {issue.index}.")
            continue
        if not tick_clock:
            continue
        try:
            times = [tick_clock.decode(row["time"], row["time_msc"]).utc for row in rows]
        except (ValueError, OverflowError) as error:
            add("UTC_UNVERIFIED", subject, str(error))
            continue
        if any(not claim.interval.start <= time < claim.interval.end for time in times):
            add("TICK_OUTSIDE_COVERAGE", subject, "Decoded event falls outside the certified interval.")
            continue
        if any(right < left for left, right in zip(times, times[1:])):
            add("OUT_OF_ORDER", subject, "Decoded UTC order differs from source order.")
            continue
        accepted.append(claim)
        tick_times.extend(time for time in times if interval.start <= time < interval.end)
    cover("ticks", accepted)

    # Sort comparison coordinates across independent chunks only. Preserve each
    # source batch's original sequence, including events at the same millisecond.
    tick_times.sort()
    session_starts = [item.interval.start for item in quote_sessions]
    for time in tick_times:
        index = bisect_right(session_starts, time) - 1
        if (index < 0 or time >= quote_sessions[index].interval.end
                or quote_sessions[index].state != SessionState.OPEN):
            add("QUOTE_SESSION_UNVERIFIED_AT_TICK", "ticks",
                f"First quote outside verified open time is at {time.isoformat()}.")
            break

    if not isinstance(max_quote_silence, timedelta) or max_quote_silence <= timedelta(0):
        add("GAP_POLICY_UNVERIFIED", "ticks", "An approved positive open-session silence limit is required.")
    else:
        for session in quote_sessions:
            if session.state != SessionState.OPEN:
                continue
            start = max(interval.start, session.interval.start)
            end = min(interval.end, session.interval.end)
            within = tick_times[bisect_left(tick_times, start):bisect_left(tick_times, end)]
            if not within:
                add("NO_OPEN_SESSION_QUOTES", "ticks", f"{start.isoformat()} to {end.isoformat()}")
                continue
            edges = [start, *within, end]
            for left, right in zip(edges, edges[1:]):
                if right - left > max_quote_silence:
                    add("OPEN_SESSION_SILENCE", "ticks", f"{left.isoformat()} to {right.isoformat()}")
    if not tick_times:
        add("NO_VERIFIED_TICKS", "ticks", "No usable historical quotes in the target.")
    return Readiness(tuple(findings))
