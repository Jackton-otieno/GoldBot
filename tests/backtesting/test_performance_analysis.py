"""Synthetic offline checks for Phase 6.4."""

import json
import unittest
from dataclasses import replace
from decimal import localcontext

from goldbot.backtesting.performance_analysis import analyze_performance, performance_json
from goldbot.risk.risk_config import D
from tests.backtesting import test_portfolio_coordinator as fixtures
from tests.backtesting.test_execution_simulator import candle


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PortfolioTests()
        self.fixture.setUp()

    def run_rows(self, *rows, **kwargs):
        return self.fixture.run_rows(rows, **kwargs)

    def test_multi_trade_recovery_and_reconciliation(self):
        result = self.run_rows(
            candle(1, decision="BUY"), candle(2, high=104, decision="BUY"),
            candle(3, low=98, decision="BUY"), candle(4, low=98, decision="BUY"),
            candle(5, high=104, decision="BUY"), candle(6, high=104),
        )
        report = analyze_performance(result)
        account = report["account"]
        trades = report["trades"]
        self.assertEqual(account["final_balance"], D("3047.60"))
        self.assertEqual(account["final_equity"], D("3047.60"))
        self.assertEqual(account["realized_net_pnl"], D("47.60"))
        self.assertAlmostEqual(account["marked_return"], D("0.01586666666666666667"))
        self.assertEqual(account["marked_return"], account["realized_return"])
        self.assertEqual(trades["counts"], {"win": 3, "loss": 2, "breakeven": 0})
        self.assertEqual(trades["longest_streaks"], {"win": 2, "loss": 2, "breakeven": 0})
        self.assertEqual(trades["ending_streak"], {"outcome": "win", "length": 2})
        self.assertEqual(trades["mean_win"], D("25.20"))
        self.assertEqual(trades["mean_loss"], D("-14"))
        self.assertEqual(trades["expectancy"], D("9.52"))
        self.assertEqual(trades["profit_factor"], {"value": D("2.7"), "status": "finite", "reason": None})
        self.assertEqual(report["costs"]["realized_gross_pnl"], D("49.60"))
        self.assertEqual(report["costs"]["commission_paid"], D("2"))
        self.assertIsNone(report["costs"]["spread_cost"]["value"])
        drawdown = report["max_drawdown"]["drawdown"]
        self.assertEqual(drawdown, {
            "value": D("30.40"), "peak_event_index": 4, "trough_event_index": 9,
            "recovery_event_index": 12, "peak_to_recovery_intervals": 8, "status": "recovered",
        })
        self.assertAlmostEqual(report["max_drawdown"]["drawdown_fraction"]["value"], D("30.4") / D("3025.2"), places=25)
        self.assertEqual(report["exposure"]["observed_intervals"], 11)
        self.assertEqual(report["exposure"]["intervals_with_position"], 5)
        with localcontext() as context:
            context.prec = 4
            encoded = performance_json(result)
        self.assertEqual(encoded, performance_json(result))
        self.assertEqual(D(json.loads(encoded)["account"]["final_equity"]), D("3047.60"))

    def test_flat_and_empty(self):
        result = self.run_rows(candle(1), candle(2))
        report = analyze_performance(result)
        self.assertEqual(report["account"]["final_balance"], D(3000))
        self.assertEqual(report["trades"]["closed"], 0)
        self.assertEqual(report["trades"]["profit_factor"]["status"], "undefined")
        self.assertIsNone(report["trades"]["expectancy"])
        self.assertEqual(report["max_drawdown"]["drawdown"]["status"], "none")
        self.assertEqual(report["exposure"]["intervals_with_position"], 0)
        self.assertEqual(report["entry_rejections"], {})
        with self.assertRaisesRegex(ValueError, "non-empty"):
            analyze_performance(replace(result, events=()))

    def test_no_losses_no_wins_and_breakeven(self):
        first = candle(1, decision="BUY")
        win = self.run_rows(first, candle(2, high=104))
        loss = self.run_rows(first, candle(2, low=98))
        scratch = self.run_rows(first, candle(2, high=104), spec=replace(
            self.fixture.spec, round_trip_commission_per_lot=D("32")
        ))
        self.assertEqual(json.loads(performance_json(win))["trades"]["profit_factor"], {
            "value": None, "status": "infinite", "reason": "no_net_losses",
        })
        loss_trades = analyze_performance(loss)["trades"]
        self.assertEqual(loss_trades["profit_factor"]["value"], D(0))
        self.assertIsNone(loss_trades["mean_win"])
        scratch_trades = analyze_performance(scratch)["trades"]
        self.assertEqual(scratch_trades["counts"], {"win": 0, "loss": 0, "breakeven": 1})
        self.assertEqual(scratch_trades["profit_factor"]["status"], "undefined")
        self.assertEqual(scratch_trades["expectancy"], D(0))

    def test_unresolved_position_and_marked_return(self):
        opening, close = candle(2, high=103, decision="SELL")
        result = self.run_rows(candle(1, decision="BUY"), (opening, replace(close, close=101)))
        report = analyze_performance(result)
        self.assertEqual(report["trades"]["closed"], 0)
        self.assertEqual(report["account"]["realized_net_pnl"], D(0))
        self.assertEqual(report["account"]["unrealized_pnl"], D("5.6"))
        self.assertEqual(report["account"]["final_equity"], D("3005.6"))
        self.assertGreater(report["account"]["marked_return"], D(0))
        self.assertEqual(report["unresolved_position"]["commission_due_on_exit"], D(".4"))
        self.assertEqual(report["terminal_signal_row"], 2)
        self.assertEqual(report["exposure"]["intervals_with_position"], 1)
        self.assertEqual(report["max_drawdown"]["drawdown"]["recovery_event_index"], 4)
        self.assertTrue(all(metric["value"] is None for metric in report["unavailable"].values()))

    def test_rejection_counts_and_insolvency(self):
        result = self.run_rows(
            candle(1, decision="SELL"), candle(2, decision="BUY"),
            candle(3, opening=500, gap=True, decision="SELL"), candle(4),
            boundaries=(1, 4),
        )
        report = analyze_performance(result)
        self.assertEqual(report["entry_rejections"], {"POSITION_LIMIT": 1, "INSOLVENT": 1})
        self.assertEqual(report["account"]["final_balance"], D("-203.60"))
        self.assertEqual(report["account"]["first_insolvent_event_index"], 5)
        drawdown = report["max_drawdown"]["drawdown_fraction"]
        self.assertGreater(drawdown["value"], D(1))
        self.assertEqual(drawdown["status"], "unrecovered")
        self.assertIsNone(drawdown["recovery_event_index"])

    def test_reject_tampered_ledger(self):
        result = self.run_rows(candle(1, decision="BUY"), candle(2, high=104))
        last = result.events[-1]
        for mutation in (
            {"balance": last.balance + 1}, {"equity": D("NaN")},
            {"commission_paid": D("Infinity")}, {"unrealized_pnl": D(1)},
            {"drawdown": D(1)}, {"exit": replace(last.exit, net_pnl=D(0))},
            {"exit": None}, {"row": 5},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                analyze_performance(replace(result, events=(*result.events[:-1], replace(last, **mutation))))
        with self.assertRaisesRegex(ValueError, "terminal"):
            analyze_performance(replace(result, terminal=replace(result.terminal, terminal_signal_row=2)))
