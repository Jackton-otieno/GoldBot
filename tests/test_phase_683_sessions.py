from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest

from goldbot.core.time_manager import OffsetWindow
from goldbot.market_data.session_verification import (
    Authority, MarketScope, SessionEvidence, SessionKind, SessionState, UTCInterval,
    VerifiedClock, require_session_quote, session_at,
)
from goldbot.risk.risk_day_verification import (
    BoundaryEquity, DailyState, PolicyDay, RiskDayScope, evaluate_boundary,
)


class SessionAndRiskDayTests(unittest.TestCase):
    def setUp(self):
        self.t = datetime(2026, 10, 25, tzinfo=timezone.utc)
        self.scope = MarketScope("fixture-demo", "XAUUSD")
        self.source = Authority("Synthetic broker", "fixture/session")
        self.policy = Authority("Synthetic policy owner", "fixture/policy-v1")
        self.windows = (OffsetWindow(self.scope.server, 7200, self.at(-24), self.at(48),
                                     "fixture/clock-conversion"),)
        self.quote = SessionEvidence(
            self.scope, SessionKind.QUOTE, UTCInterval(self.at(-2), self.at(2)),
            SessionState.OPEN, self.source,
        )
        self.risk = RiskDayScope(self.scope, "fixture-account", "policy-v1")
        self.old = PolicyDay(self.risk, "d1", UTCInterval(self.at(-20), self.at(4)), self.policy)
        self.new = PolicyDay(self.risk, "d2", UTCInterval(self.at(4), self.at(28)), self.policy)
        self.state = DailyState(self.old, Decimal("10000"), Decimal("400"), True)
        self.equity = BoundaryEquity(self.risk, self.at(4), Decimal("9600"), self.source)

    def at(self, hours):
        return self.t + timedelta(hours=hours)

    def clock(self, hours, latest=None):
        return VerifiedClock(self.scope, self.at(hours), self.at(hours if latest is None else latest),
                             Authority("Synthetic time source", "fixture/clock"))

    def reset(self, *, state=None, clock=None, windows=None, days=None, equity=None):
        return evaluate_boundary(
            self.state if state is None else state,
            clock=self.clock(4) if clock is None else clock,
            windows=self.windows if windows is None else windows,
            days=(self.old, self.new) if days is None else days, equity=equity,
        )

    def test_overnight_quote_and_trade_are_independent(self):
        trade = replace(self.quote, kind=SessionKind.TRADE, interval=UTCInterval(self.at(1), self.at(2)))
        for hours in (-1, 0.5):
            self.assertIs(session_at(self.scope, SessionKind.QUOTE, self.clock(hours),
                                     self.windows, (self.quote, trade)), self.quote)
            self.assertIsNone(session_at(self.scope, SessionKind.TRADE, self.clock(hours),
                                         self.windows, (self.quote, trade)))

    def test_holiday_closure_versus_uncovered_gap_and_overlap(self):
        closed = replace(self.quote, state=SessionState.CLOSED,
                         interval=UTCInterval(self.at(3), self.at(5)))
        for hours, expected in ((2, None), (3, closed), (5, None)):
            self.assertIs(session_at(self.scope, SessionKind.QUOTE, self.clock(hours),
                                     self.windows, (self.quote, closed)), expected)
        conflict = replace(closed, interval=UTCInterval(self.at(1), self.at(5)))
        self.assertIsNone(session_at(self.scope, SessionKind.QUOTE, self.clock(1),
                                     self.windows, (self.quote, conflict)))
        self.assertIsNone(session_at(self.scope, SessionKind.QUOTE, self.clock(1, 2),
                                     self.windows, (self.quote,)))
        self.assertIsNone(session_at(self.scope, SessionKind.QUOTE, self.clock(1), self.windows,
                                     (replace(self.quote, scope=MarketScope("other", "XAUUSD")),)))

    def test_quote_freshness_uses_worst_case_age_and_session_start(self):
        def tick(delta):
            raw = int((self.at(2) + timedelta(seconds=delta)).timestamp())
            return SimpleNamespace(time=raw, time_msc=raw * 1000, bid=10, ask=11)

        self.assertEqual(require_session_quote(self.scope, self.clock(0), self.windows,
                                               (self.quote,), tick(-60)).utc,
                         self.t - timedelta(seconds=60))
        with self.assertRaisesRegex(ValueError, "STALE"):
            require_session_quote(self.scope, self.clock(0, 1 / 3600), self.windows,
                                  (self.quote,), tick(-60))
        with self.assertRaisesRegex(ValueError, "future"):
            require_session_quote(self.scope, self.clock(0), self.windows, (self.quote,), tick(1))
        later_open = replace(self.quote, interval=UTCInterval(self.t, self.at(2)))
        with self.assertRaisesRegex(ValueError, "precedes"):
            require_session_quote(self.scope, self.clock(0), self.windows, (later_open,), tick(-1))

    def test_dst_fold_rejects_ambiguous_current_clock_and_tick(self):
        windows = (
            OffsetWindow(self.scope.server, 10800, self.at(-24), self.t, "fixture/pre-fold"),
            OffsetWindow(self.scope.server, 7200, self.t, self.at(48), "fixture/post-fold"),
        )
        self.assertIsNone(session_at(self.scope, SessionKind.QUOTE, self.clock(0.5),
                                     windows, (self.quote,)))
        raw = int(self.at(2.5).timestamp())
        tick = SimpleNamespace(time=raw, time_msc=raw * 1000, bid=10, ask=11)
        with self.assertRaisesRegex(ValueError, "unique"):
            require_session_quote(self.scope, self.clock(1.5), windows, (self.quote,), tick)

    def test_midnight_and_ambiguous_boundary_preserve_latch(self):
        for clock, status in ((self.clock(0), "SAME_DAY"),
                              (self.clock(3.99, 4), "UNVERIFIED_POLICY_DAY")):
            decision = self.reset(clock=clock, equity=self.equity)
            self.assertEqual(decision.status, status)
            self.assertIs(decision.state, self.state)

    def test_rejected_boundary_preserves_all_state(self):
        gap = replace(self.new, interval=UTCInterval(self.at(5), self.at(28)))
        overlap = replace(self.new, interval=UTCInterval(self.at(3), self.at(28)))
        for options, reason in (
            ({"days": ()}, "UNVERIFIED_POLICY_DAY"),
            ({"days": (self.old, overlap)}, "UNVERIFIED_POLICY_DAY"),
            ({"days": (self.old, gap), "clock": self.clock(5)}, "UNVERIFIED_SUCCESSOR"),
            ({"clock": self.clock(28)}, "UNVERIFIED_POLICY_DAY"),
            ({"windows": ()}, "UNVERIFIED_CLOCK"),
            ({}, "MISSING_BOUNDARY_EQUITY"),
            ({"equity": replace(self.equity, at=self.at(5))}, "MISSING_BOUNDARY_EQUITY"),
            ({"equity": replace(self.equity, scope=replace(self.risk, account_ref="other"))},
             "MISSING_BOUNDARY_EQUITY"),
        ):
            with self.subTest(reason=reason, options=options):
                decision = self.reset(**options)
                self.assertEqual(decision.status, reason)
                self.assertIs(decision.state, self.state)

    def test_reset_once_and_preserve_new_day_loss_and_latch_on_repeat(self):
        reset = self.reset(equity=self.equity)
        self.assertEqual(reset.status, "RESET")
        self.assertEqual(reset.state, DailyState(self.new, Decimal("9600"), Decimal(0), False))
        latched = replace(reset.state, loss_to_date=Decimal("500"), daily_latched=True)
        for clock, status in ((self.clock(4), "SAME_DAY"),
                              (self.clock(3), "UNVERIFIED_SUCCESSOR")):
            repeated = self.reset(state=latched, clock=clock, equity=self.equity)
            self.assertEqual(repeated.status, status)
            self.assertIs(repeated.state, latched)
