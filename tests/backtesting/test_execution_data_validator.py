"""Synthetic verification fixtures only. No terminal connection."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest
from unittest.mock import patch

import numpy as np

from goldbot.backtesting.execution_data_validator import (
    DatasetEvidence, EffectiveSchedule, SCHEDULES, TickCoverage, rows_digest,
    verify_execution_data,
)
from goldbot.core.time_manager import OffsetWindow
from goldbot.market_data.session_verification import (
    Authority, MarketScope, SessionEvidence, SessionKind, SessionState, UTCInterval,
)
from goldbot.market_data.tick_data import audit_ticks, spread
from goldbot.risk.risk_day_verification import PolicyDay, RiskDayScope
from tools.diagnose_execution_data import CHUNK_SECONDS, ROOT, sample, sample_plan


def tick(ms, bid=100, ask=101, flags=6):
    return {"time": ms // 1000, "time_msc": ms, "flags": flags, "bid": bid, "ask": ask}


class TickTests(unittest.TestCase):
    def test_same_timestamp_and_unchanged_side_are_preserved(self):
        rows = [tick(10001), tick(10001, ask=102, flags=4), tick(10002, ask=102, flags=8)]
        audit = audit_ticks(rows)
        self.assertEqual(audit.issues, ())
        self.assertEqual(audit.observations["same_millisecond"], 1)
        self.assertEqual(audit.observations["unchanged_bid"], 2)
        self.assertEqual(audit.observations["unchanged_ask"], 1)
        self.assertEqual(spread(rows[1]), "2")

    def test_corruption_is_reported_without_reordering(self):
        rows = [tick(10020), tick(10010, ask=99), tick(10030, bid=0),
                tick(10040, ask=None), dict(tick(10050), time=9, flags=None)]
        audit = audit_ticks(rows, bounds=(10015, 10049))
        self.assertEqual({(issue.index, issue.code) for issue in audit.issues}, {
            (1, "OUT_OF_ORDER"), (1, "CROSSED_QUOTE"), (1, "OUTSIDE_REQUEST_BOUNDS"),
            (2, "INVALID_BID_ASK"), (3, "MISSING_FIELD"), (4, "MISSING_FIELD"),
            (4, "INVALID_TIMESTAMP"), (4, "INVALID_FLAGS"),
        })

    def test_diagnostic_keeps_return_order_and_raw_flags(self):
        raw = np.array(
            [(10, 10001, 100.0, 101.0, 6), (10, 10001, 100.0, 102.0, 1028)],
            dtype=[("time", "i8"), ("time_msc", "i8"), ("bid", "f8"),
                   ("ask", "f8"), ("flags", "u4")],
        )
        with (patch("tools.diagnose_execution_data.mt5.copy_ticks_range", return_value=raw) as get,
              patch("tools.diagnose_execution_data.mt5.last_error", return_value=(1, "success"))):
            result = sample(10, ["fixture"])
        self.assertEqual(get.call_args.args[1:3], (10, 10 + CHUNK_SECONDS - 1))
        self.assertEqual([row["flags"] for row in result["raw_rows"]], [6, 1028])
        self.assertEqual(result["spread_price_units_by_index"], ["1.0", "2.0"])
        self.assertEqual(result["rows_sha256"], rows_digest(result["raw_rows"]))

    def test_diagnostic_plan_covers_dataset_anchors_and_gap_probes(self):
        inventory, anchors = sample_plan(ROOT)
        self.assertLessEqual(len(anchors), 18)
        self.assertEqual(len({start for start, _ in anchors}), len(anchors))
        reasons = {reason for _, labels in anchors for reason in labels}
        for frame, facts in inventory.items():
            self.assertIn((facts["first_raw_label"], f"{frame}:first"),
                          {(start, reason) for start, labels in anchors for reason in labels})
            self.assertIn(f"{frame}:last", reasons)
            self.assertIn(f"{frame}:midpoint_row", reasons)
            for gap in ("shortest", "longest"):
                for position in ("before", "inside", "after"):
                    self.assertIn(f"{frame}:{gap}_gap:{position}", reasons)


class ExecutionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=15)
        self.interval = UTCInterval(self.start, self.end)
        market = MarketScope("synthetic-server", "XAUUSD")
        self.scope = RiskDayScope(market, "synthetic-account", "test-policy")
        self.authority = Authority("synthetic", "fixture://review")
        self.offset = OffsetWindow(market.server, 7200, self.start, self.end, "fixture clock")
        self.raw = int(self.start.timestamp()) + 7200
        self.csv = (
            "mt5_time_epoch,open,high,low,close,tick_volume,spread,real_volume\n"
            f"{self.raw},100,101,99,100,1,1,0\n"
        ).encode("ascii")
        self.dataset = DatasetEvidence(self.scope, "M15", sha256(self.csv).hexdigest(),
                                       "bid", self.authority)
        self.rows = [tick((self.raw + elapsed) * 1000) for elapsed in (0, 300, 600)]
        self.claim = TickCoverage(self.scope, self.interval, rows_digest(self.rows),
                                  self.authority, exhaustive=True, quote_basis="broker_bid_ask")
        self.sessions = [SessionEvidence(market, kind, self.interval, SessionState.OPEN,
                                         self.authority) for kind in SessionKind]
        self.schedules = [EffectiveSchedule(self.scope, self.interval, topic,
                                            f"fixture://{topic}", self.authority,
                                            historical_applicability_attested=True)
                          for topic in SCHEDULES]
        self.day = PolicyDay(self.scope, "day-1", self.interval, self.authority)

    def verify(self, **changes):
        arguments = dict(candle_bytes=self.csv, dataset=self.dataset,
                         batches=[(self.claim, self.rows)], candle_offsets=[self.offset],
                         tick_offsets=[self.offset], sessions=self.sessions,
                         schedules=self.schedules, days=[self.day],
                         max_quote_silence=timedelta(minutes=5))
        return verify_execution_data(self.scope, self.interval, **(arguments | changes))

    def test_fully_attested_synthetic_fixture(self):
        self.assertTrue(self.verify().ready)

    def test_sample_or_tampered_rows_cannot_certify_coverage(self):
        sample = replace(self.claim, exhaustive=False)
        result = self.verify(batches=[(sample, self.rows), (self.claim, self.rows[::-1])])
        self.assertFalse(result.ready)
        self.assertTrue({"SAMPLE_ONLY", "PROVENANCE_UNVERIFIED", "COVERAGE_HOLE"} <=
                        {finding.code for finding in result.findings})
        self.assertFalse(self.verify(candle_bytes=self.csv + b"\n").ready)

    def test_missing_quote_interval_distinct_from_closed(self):
        result = self.verify(sessions=self.sessions[1:])
        self.assertIn(("COVERAGE_HOLE", "quote_sessions"),
                      {(finding.code, finding.subject) for finding in result.findings})
        closed = [replace(self.sessions[0], state=SessionState.CLOSED), self.sessions[1]]
        self.assertIn("QUOTE_SESSION_UNVERIFIED_AT_TICK",
                      {finding.code for finding in self.verify(sessions=closed).findings})

    def test_missing_tick_chunk_and_open_session_silence(self):
        start = self.start + timedelta(minutes=5)
        subset = self.rows[1:2]
        claim = replace(self.claim, interval=UTCInterval(start, self.end),
                        rows_sha256=rows_digest(subset))
        findings = self.verify(batches=[(claim, subset)]).findings
        self.assertIn(("COVERAGE_HOLE", "ticks"), {(f.code, f.subject) for f in findings})
        self.assertIn("OPEN_SESSION_SILENCE", {f.code for f in findings})

    def test_overlapping_specs_expired_costs_and_account_mismatch(self):
        contract, commission, swap, margin, conversion = self.schedules
        expired = UTCInterval(self.start - timedelta(days=1), self.start)
        findings = self.verify(schedules=[
            contract, contract, replace(commission, interval=expired),
            replace(swap, schedule_ref=""),
            replace(margin, historical_applicability_attested=False),
            replace(conversion, scope=replace(self.scope, account_ref="other")),
        ]).findings
        pairs = {(finding.code, finding.subject) for finding in findings}
        self.assertIn(("OVERLAPPING_EVIDENCE", contract.topic), pairs)
        for record in (commission, swap, margin, conversion):
            self.assertIn(("COVERAGE_HOLE", record.topic), pairs)

    def test_unknown_and_ambiguous_utc(self):
        overlap = OffsetWindow(self.scope.market.server, 6300, self.end,
                               self.end + timedelta(minutes=15), "fixture fold")
        for offsets in ([], [self.offset, overlap]):
            findings = self.verify(tick_offsets=offsets).findings
            self.assertIn(("UTC_UNVERIFIED", "ticks"),
                          {(finding.code, finding.subject) for finding in findings})

    def test_unknown_basis_and_risk_day(self):
        result = self.verify(dataset=replace(self.dataset, quote_basis=""), days=[])
        pairs = {(finding.code, finding.subject) for finding in result.findings}
        self.assertIn(("QUOTE_BASIS_UNVERIFIED", "candles"), pairs)
        self.assertIn(("COVERAGE_HOLE", "policy_risk_days"), pairs)

    def test_candle_gap_requires_closed_quote_session(self):
        middle = self.end + timedelta(minutes=15)
        end = middle + timedelta(minutes=15)
        interval = UTCInterval(self.start, end)
        payload = self.csv + f"{self.raw + 1800},100,101,99,100,1,1,0\n".encode()
        rows = [self.rows[0], tick((self.raw + 1800) * 1000)]
        offsets = [replace(self.offset, valid_until=end)]
        quotes = [
            replace(self.sessions[0], interval=UTCInterval(self.end, middle),
                    state=SessionState.CLOSED),
            self.sessions[0],
            replace(self.sessions[0], interval=UTCInterval(middle, end)),
        ]
        inputs = dict(
            candle_bytes=payload, dataset=replace(self.dataset, sha256=sha256(payload).hexdigest()),
            candle_offsets=offsets, tick_offsets=offsets,
            batches=[(replace(self.claim, interval=interval, rows_sha256=rows_digest(rows)), rows)],
            schedules=[replace(item, interval=interval) for item in self.schedules],
            days=[replace(self.day, interval=interval)], max_quote_silence=timedelta(minutes=15),
        )
        trade = replace(self.sessions[1], interval=interval)
        self.assertTrue(verify_execution_data(
            self.scope, interval, sessions=[*quotes, trade], **inputs,
        ).ready)
        findings = verify_execution_data(
            self.scope, interval, sessions=[replace(trade, kind=SessionKind.QUOTE), trade], **inputs,
        ).findings
        self.assertIn("CANDLE_GAP_DURING_OPEN_SESSION", {finding.code for finding in findings})
