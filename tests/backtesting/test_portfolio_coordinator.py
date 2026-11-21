"""Synthetic account and event regressions for Phase 6.3."""
import unittest
from dataclasses import replace
from decimal import localcontext

from goldbot.backtesting.execution_simulator import SimulationSpec
from goldbot.backtesting.historical_replay import Replay
from goldbot.backtesting.portfolio_coordinator import PortfolioCoordinator, RiskBoundary, RiskSchedule, run_portfolio
from goldbot.risk.risk_config import BrokerSpecs, D, Evidence
from tests.backtesting.test_execution_simulator import candle


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        evidence = Evidence("phase63-fixture", "explicit synthetic pricing fixture", True)
        broker = BrokerSpecs(evidence, "XAUUSD", "USD", "USD", D(".01"), D(".1"),
                             D("1"), D("10"), D(".1"), D("10"), D(".1"), 0, "USD_LINEAR")
        self.spec = SimulationSpec(evidence, broker, D(".2"), D(".03"), D(".04"),
                                   D(".5"), D("200"))
        self.schedule_evidence = Evidence(evidence.scenario_id, "explicit synthetic row boundaries", True)

    def run_rows(self, rows, *, boundaries=(1,), timeframe="M15", spec=None):
        schedule = RiskSchedule(timeframe, self.schedule_evidence, tuple(
            RiskBoundary(row, f"bucket-{row}") for row in boundaries
        ))
        interval = 900 if timeframe == "M15" else 3600
        label = 10000
        events = []
        for opening, closed in rows:
            delta = None if not events else interval * (2 if opening.gap_before else 1)
            label += delta or 0
            events.extend(replace(event, timeframe=timeframe, raw_label_delta=delta,
                                  raw_server_clock_label=label) for event in (opening, closed))
        return run_portfolio(Replay(timeframe, "fixture", "", False, tuple(events)),
                             spec=spec or self.spec, schedule=schedule)

    def test_accounting_and_commission_for_both_directions(self):
        for side, trigger, quote in (("BUY", {"high": 104}, "99.9"),
                                     ("SELL", {"low": 96}, "100.1")):
            with self.subTest(side=side):
                result = self.run_rows([candle(1, decision=side), candle(2, **trigger)])
                first_close, opened, closed = result.events[1:]
                self.assertIsNone(first_close.position)
                self.assertEqual(first_close.pending.side, side)
                self.assertEqual(opened.attempted, first_close.pending)
                self.assertEqual(opened.balance, D(3000))
                self.assertEqual(opened.liquidation_quote, D(quote))
                self.assertEqual(opened.unrealized_pnl, D("-2.4"))
                self.assertEqual(opened.used_margin, D(160))
                self.assertEqual(opened.commission_paid, D(0))
                self.assertEqual(opened.commission_due_on_exit, D(".4"))
                self.assertEqual(closed.balance, D("3025.20"))
                self.assertEqual(closed.exit.gross_pnl, D("25.60"))
                self.assertEqual(closed.commission_paid, D(".4"))
                self.assertEqual(closed.commission_due_on_exit, D(0))
                self.assertEqual(closed.used_margin, D(0))
                for record in result.events:
                    self.assertEqual(record.equity, record.balance + record.unrealized_pnl)
                    self.assertEqual(record.free_margin, record.equity - record.used_margin)

    def test_intrabar_extremes_do_not_set_peak_and_terminal_stays_open(self):
        opening, closed = candle(2, high=103, low=99, decision="SELL")
        closed = replace(closed, close=101)
        result = self.run_rows([candle(1, decision="BUY"), (opening, closed)])
        last = result.events[-1]
        self.assertEqual(last.equity, D("3005.6"))
        self.assertEqual(last.peak_equity, last.equity)
        self.assertEqual(last.balance, D(3000))
        self.assertEqual(last.commission_paid, D(0))
        self.assertEqual(result.terminal.unresolved_position, last.position)
        self.assertEqual(result.terminal.terminal_signal_row, last.pending.row)

    def test_compounding_uses_current_realized_equity(self):
        rows = [candle(1, decision="BUY")]
        rows.extend(candle(row, high=104, decision="BUY") for row in range(2, 10))
        result = self.run_rows(rows)
        entries = [record.entry.plan for record in result.events if record.entry]
        self.assertEqual(entries[0].loss_budget, D(15))
        self.assertEqual(entries[1].loss_budget, D("15.126"))
        self.assertEqual(entries[-1].volume, D(".9"))

    def test_margin_before_and_after_mark_and_existing_deficit(self):
        rows = [candle(1, decision="BUY"), candle(2, low=99)]
        for margin, reason in (("3751", "INSUFFICIENT_MARGIN"),
                               ("3749", "INSUFFICIENT_MARKED_MARGIN")):
            with self.subTest(reason=reason):
                result = self.run_rows(rows, spec=replace(self.spec, margin_per_lot=D(margin)))
                self.assertEqual(result.events[2].entry_status, reason)
                self.assertIsNone(result.terminal.unresolved_position)
        opening, closed = rows[1]
        rows[-1] = (opening, replace(closed, close=99))
        result = self.run_rows(rows, spec=replace(self.spec, margin_per_lot=D("3747")))
        self.assertEqual(result.events[2].free_margin, D(0))
        self.assertEqual(result.events[-1].free_margin, D(-8))
        self.assertIn("MARGIN_DEFICIT", result.events[-1].flags)
        self.assertIsNotNone(result.terminal.unresolved_position)

    def test_daily_gap_overshoot_and_explicit_reset(self):
        rows = [candle(1, decision="BUY"), candle(2, decision="SELL"),
                candle(3, opening=90, gap=True, decision="BUY"),
                candle(4, decision="BUY"), candle(5)]
        result = self.run_rows(rows, boundaries=(1, 5))
        gap_exit, blocked, reset = result.events[4], result.events[6], result.events[8]
        self.assertEqual(gap_exit.entry_status, "POSITION_LIMIT")
        self.assertEqual(gap_exit.exit.reason, "OPEN_STOP")
        self.assertGreater(-gap_exit.exit.net_pnl, D(60))
        self.assertIn("DAILY_LOSS_LIMIT", gap_exit.flags)
        self.assertEqual(blocked.entry_status, "DAILY_LOSS_LIMIT")
        self.assertEqual(reset.risk_day.opening_equity, gap_exit.balance)
        self.assertEqual(reset.risk_day.loss_to_date, D(0))
        self.assertEqual(reset.entry_status, "FILLED")

    def test_carried_position_uses_previous_close_equity_at_boundary(self):
        rows = [candle(1, decision="BUY"), candle(2), candle(3, opening=90, gap=True)]
        result = self.run_rows(rows, boundaries=(1, 3))
        previous, opening = result.events[3:5]
        self.assertEqual(opening.risk_day.opening_equity, previous.equity)
        self.assertEqual(opening.risk_day.loss_to_date, -opening.exit.net_pnl)
        self.assertEqual(opening.risk_day.risk_day_id, "bucket-3")
        self.assertIn("DAILY_LOSS_LIMIT", opening.flags)

    def test_threshold_equality_latches(self):
        spec = replace(self.spec, round_trip_commission_per_lot=D(1))
        for price, amount, flag in (
            (93, D(60), "DAILY_LOSS_LIMIT"),
            (63, D(300), "DRAWDOWN_LIMIT"),
        ):
            with self.subTest(flag=flag):
                result = self.run_rows([candle(1, decision="BUY"), candle(2),
                                        candle(3, opening=price)], spec=spec)
                record = result.events[4]
                self.assertEqual(record.exit.net_pnl, -amount)
                self.assertIn(flag, record.flags)

    def test_drawdown_and_insolvency_stay_latched_across_boundary(self):
        for midpoint, reason in ((150, "DRAWDOWN_LIMIT"), (500, "INSOLVENT")):
            rows = [candle(1, decision="SELL"), candle(2),
                    candle(3, opening=midpoint), candle(4, decision="SELL"), candle(5)]
            result = self.run_rows(rows, boundaries=(1, 5))
            self.assertEqual(result.events[4].exit.reason, "OPEN_STOP")
            self.assertEqual(result.events[-2].entry_status, reason)
            self.assertIn("DRAWDOWN_LIMIT", result.events[-1].flags)
            if reason == "INSOLVENT":
                self.assertLess(result.events[-1].equity, 0)
                self.assertGreater(result.events[-1].drawdown_fraction, 1)

    def test_schedule_is_required_and_scenario_and_timeframe_must_match(self):
        for boundaries in ((), (RiskBoundary(2, "a"),),
                           (RiskBoundary(1, "a"), RiskBoundary(2, "a"))):
            with self.assertRaises(ValueError):
                RiskSchedule("M15", self.schedule_evidence, boundaries)
        schedule = RiskSchedule("H1", self.schedule_evidence, (RiskBoundary(1, "test"),))
        with self.assertRaises(ValueError):
            PortfolioCoordinator(self.spec, None)
        with self.assertRaises(ValueError):
            PortfolioCoordinator(self.spec, replace(schedule, evidence=replace(
                self.schedule_evidence, scenario_id="unrelated")))
        with self.assertRaises(ValueError):
            PortfolioCoordinator(self.spec, schedule).on_open(candle(1)[0])

    def test_independent_timeframes_and_event_prefix_causality(self):
        first = candle(1, decision="BUY")
        baseline = self.run_rows([first, candle(2, low=98)])
        with localcontext() as context:
            context.prec = 4
            self.assertEqual(baseline, self.run_rows([first, candle(2, low=98)]))
        changed = self.run_rows([first, candle(2, high=104)], boundaries=(1, 3))
        self.assertEqual(baseline.events[:3], changed.events[:3])
        self.assertNotEqual(baseline.events[-1].equity, changed.events[-1].equity)
        other = self.run_rows([first, candle(2, low=98)], timeframe="H1")
        self.assertEqual(other.events[0].balance, D(3000))
        self.assertEqual(other.events[2].entry.plan.volume, baseline.events[2].entry.plan.volume)
        self.assertNotEqual(other.events[0].risk_day.account_ref, baseline.events[0].risk_day.account_ref)

    def test_open_position_blocks_following_open_even_when_exit_fills(self):
        result = self.run_rows([candle(1, decision="BUY"), candle(2, decision="SELL"),
                                candle(3, opening=104)])
        opening = result.events[4]
        self.assertEqual(opening.entry_status, "POSITION_LIMIT")
        self.assertEqual(opening.attempted.side, "SELL")
        self.assertEqual(opening.exit.reason, "OPEN_TARGET")
        self.assertIsNone(opening.entry)
        self.assertIsNone(result.terminal.unresolved_position)
