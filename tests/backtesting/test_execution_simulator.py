import unittest
from dataclasses import replace
from decimal import localcontext

from goldbot.backtesting.execution_simulator import EntryState, ExecutionSimulator, SimulationSpec
from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent
from goldbot.risk.risk_config import AccountState, BrokerSpecs, D, Evidence, RiskDayState
from goldbot.strategy.strategy import Signal


def candle(row, *, opening=100, low=None, high=None, decision="HOLD", gap=False):
    delta = None if row == 1 else (1800 if gap else 900)
    label = 10000 + (row - 1) * 900 + (900 if gap else 0)
    common = ("M15", row, label, delta, gap, opening)
    low = opening if low is None else low
    high = opening if high is None else high
    reason = "NO_CROSSOVER" if decision == "HOLD" else f"{decision}_SETUP"
    return OpenEvent(*common), ClosedEvent(
        *common, high, low, opening, 1, 999, 0, (("atr_14", 1.0),),
        Signal(decision, (reason,)),
    )


class ExecutionSimulatorTests(unittest.TestCase):
    def setUp(self):
        evidence = Evidence("synthetic-example", "hypothetical fixture", True)
        broker = BrokerSpecs(evidence, "XAUUSD", "USD", "USD", D(".01"), D(".1"),
                             D("1"), D("10"), D(".1"), D("10"), D(".1"), 0, "USD_LINEAR")
        self.spec = SimulationSpec(evidence, broker, D(".2"), D(".03"), D(".04"),
                                   D(".5"), D("200"))
        self.state = EntryState(
            "supplied-risk-day",
            AccountState(evidence, "synthetic-account", "USD", D("3000"), D("3000"), D("1000"), 0),
            RiskDayState(evidence, "synthetic-account", "supplied-risk-day", D("3000"), D(0)),
        )

    def armed(self, side="BUY"):
        simulator = ExecutionSimulator(self.spec)
        opening, closed = candle(1, decision=side)
        self.assertEqual(simulator.on_open(opening, state=self.state).entry_status, "NO_PRIOR_SIGNAL")
        self.assertIsNone(simulator.on_closed(closed))
        return simulator

    def enter(self, simulator, **kwargs):
        opening, closed = candle(2, **kwargs)
        result = simulator.on_open(opening, state=self.state)
        self.assertEqual(result.entry_status, "FILLED")
        self.assertEqual((result.entry.signal_row, result.entry.entry_row), (1, 2))
        return result.entry.plan, closed

    def test_symmetric_targets_rounding_and_net_costs(self):
        for side, low, high, entry, stop, target in (
            ("BUY", 100, 103.5, "100.2", "98.6", "103.4"),
            ("SELL", 96.5, 100, "99.8", "101.4", "96.6"),
        ):
            with self.subTest(side=side):
                simulator = self.armed(side)
                plan, closed = self.enter(simulator, low=low, high=high)
                self.assertEqual((plan.entry, plan.stop, plan.target), tuple(map(D, (entry, stop, target))))
                self.assertEqual(plan.volume, D(".8"))
                self.assertEqual(plan.modeled_margin, D("160"))
                self.assertEqual(plan.modeled_stop_loss, D("14"))
                fill = simulator.on_closed(closed)
                self.assertEqual((fill.reason, fill.price), ("TARGET", D(target)))
                self.assertEqual((fill.gross_pnl, fill.commission, fill.net_pnl),
                                 (D("25.6"), D(".4"), D("25.2")))

    def test_intrabar_stops_use_executable_side_and_slippage(self):
        for side, low, high, price in (
            ("BUY", 98.7, 100, "98.5"),
            ("SELL", 100, 101.3, "101.5"),
        ):
            with self.subTest(side=side):
                simulator = self.armed(side)
                plan, closed = self.enter(simulator, low=low, high=high)
                fill = simulator.on_closed(closed)
                self.assertEqual((fill.reason, fill.price, fill.net_pnl),
                                 ("STOP", D(price), -plan.modeled_stop_loss))
                self.assertFalse(fill.both_touched)

    def test_midpoint_target_touch_alone_does_not_fill(self):
        for side, low, high in (("BUY", 100, 103.4), ("SELL", 96.6, 100)):
            with self.subTest(side=side):
                simulator = self.armed(side)
                _, closed = self.enter(simulator, low=low, high=high)
                self.assertIsNone(simulator.on_closed(closed))
                self.assertIsNotNone(simulator.finish().unresolved_position)

    def test_entry_candle_both_touched_is_stop_first(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                simulator = self.armed(side)
                _, closed = self.enter(simulator, low=96, high=104)
                fill = simulator.on_closed(closed)
                self.assertEqual(fill.reason, "STOP")
                self.assertTrue(fill.both_touched)
                self.assertEqual(fill.net_pnl, D("-14"))

    def test_flagged_gap_consumes_entry_opportunity(self):
        simulator = self.armed()
        opening, closed = candle(2, gap=True)
        self.assertEqual(simulator.on_open(opening, state=self.state).entry_status, "GAP_ENTRY")
        simulator.on_closed(closed)
        opening, _ = candle(3)
        opening = replace(opening, raw_server_clock_label=closed.raw_server_clock_label + 900)
        self.assertEqual(simulator.on_open(opening, state=self.state).entry_status, "HOLD_SIGNAL")

    def test_gap_stop_uses_adverse_open_and_blocks_same_open_entry(self):
        for side, opening_price, fill_price in (
            ("BUY", 96.98, "96.8"), ("SELL", 103.02, "103.2"),
        ):
            with self.subTest(side=side):
                simulator = self.armed(side)
                _, closed = self.enter(simulator, decision=side)
                self.assertIsNone(simulator.on_closed(closed))
                opening, closed = candle(3, opening=opening_price, low=96, high=104, gap=True)
                result = simulator.on_open(opening, state=self.state)
                self.assertEqual(result.entry_status, "POSITION_LIMIT")
                self.assertIsNone(result.entry)
                self.assertEqual((result.exit.reason, result.exit.price, result.exit.net_pnl),
                                 ("OPEN_STOP", D(fill_price), D("-27.6")))
                self.assertIsNone(simulator.on_closed(closed))

    def test_open_target_never_improves_limit_or_reenters(self):
        for side, opening_price, target in (("BUY", 105, "103.4"), ("SELL", 95, "96.6")):
            with self.subTest(side=side):
                simulator = self.armed(side)
                _, closed = self.enter(simulator, decision=side)
                simulator.on_closed(closed)
                result = simulator.on_open(candle(3, opening=opening_price)[0], state=self.state)
                self.assertEqual(result.entry_status, "POSITION_LIMIT")
                self.assertEqual((result.exit.reason, result.exit.price, result.exit.net_pnl),
                                 ("OPEN_TARGET", D(target), D("25.2")))

    def test_terminal_signal_and_open_position_are_explicit(self):
        simulator = self.armed()
        self.assertEqual(simulator.finish().terminal_signal_row, 1)
        self.assertIsNone(simulator.finish().unresolved_position)
        with self.assertRaises(ValueError):
            simulator.on_open(candle(2)[0], state=self.state)

        simulator = self.armed()
        plan, closed = self.enter(simulator, decision="SELL")
        self.assertIsNone(simulator.on_closed(closed))
        end = simulator.finish()
        self.assertEqual(end.terminal_signal_row, 2)
        self.assertEqual(end.unresolved_position.plan, plan)

    def test_missing_invalid_and_rejected_risk_state(self):
        account = self.state.account
        day = self.state.risk_day
        for state, reason in (
            (None, "UNAVAILABLE_STATE"),
            (replace(self.state, account=None), "UNVERIFIED_ACCOUNT"),
            (replace(self.state, risk_day=None), "UNVERIFIED_RISK_DAY"),
            (replace(self.state, risk_day_id="wrong"), "UNVERIFIED_RISK_DAY"),
            (replace(self.state, account=replace(account, equity=D("NaN"))), "INVALID_STATE"),
            (replace(self.state, account=replace(account, open_positions=1)), "POSITION_LIMIT"),
            (replace(self.state, risk_day=replace(day, loss_to_date=D("60"))), "DAILY_LOSS_LIMIT"),
            (replace(self.state, account=replace(account, peak_equity=D("3400"))), "DRAWDOWN_LIMIT"),
        ):
            with self.subTest(reason=reason):
                result = self.armed().on_open(candle(2)[0], state=state)
                self.assertEqual(result.entry_status, reason)
                self.assertIsNone(result.entry)

    def test_insufficient_margin_rejects_risk_sized_trade(self):
        account = replace(self.state.account, free_margin=D("159.99"))
        state = replace(self.state, account=account)
        self.assertEqual(self.armed().on_open(candle(2)[0], state=state).entry_status,
                         "INSUFFICIENT_MARGIN")
        state = replace(state, account=replace(account, free_margin=D("160")))
        self.assertEqual(self.armed().on_open(candle(2)[0], state=state).entry_status, "FILLED")

    def test_invalid_specs_fail_closed(self):
        for changes in (
            {"spread": D("-1")}, {"entry_slippage": D("NaN")}, {"margin_per_lot": D(0)},
            {"broker": replace(self.spec.broker, tick_value_loss=D(".1"))},
            {"broker": replace(self.spec.broker, volume_min=D(".15"))},
            {"broker": replace(self.spec.broker, volume_max=D("10.05"))},
            {"evidence": replace(self.spec.evidence, verified=False)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.spec, **changes)

    def test_duplicate_stale_missing_and_mismatched_events_are_rejected(self):
        simulator = self.armed()
        for row in (1, 3):
            with self.assertRaises(ValueError):
                simulator.on_open(candle(row)[0], state=self.state)
        opening, closed = candle(2)
        simulator.on_open(opening, state=self.state)
        with self.assertRaises(ValueError):
            simulator.on_open(opening, state=self.state)
        with self.assertRaises(ValueError):
            simulator.on_closed(replace(closed, open=101))
        simulator.on_closed(closed)
        with self.assertRaises(ValueError):
            simulator.on_closed(closed)
        with self.assertRaises(ValueError):
            simulator.on_open(opening, state=self.state)
        self.assertEqual(simulator.on_open(candle(3)[0], state=self.state).entry_status, "POSITION_LIMIT")

    def test_open_prefix_invariance_and_reproducibility(self):
        def run(future_low, *, stop_after_open=False):
            first = candle(1, decision="BUY")
            simulator = ExecutionSimulator(self.spec)
            prefix = [simulator.on_open(first[0]), simulator.on_closed(first[1])]
            second = candle(2, low=future_low)
            prefix.append(simulator.on_open(second[0], state=self.state))
            if stop_after_open:
                return prefix
            return prefix + [simulator.on_closed(second[1]), simulator.finish()]

        winning_prefix = run(100, stop_after_open=True)
        stopped = run(98)
        self.assertEqual(stopped[:3], winning_prefix)
        self.assertEqual(run(100)[:3], winning_prefix)
        self.assertEqual(stopped[3].reason, "STOP")
        self.assertIsNone(run(100)[3])
        with localcontext() as context:
            context.prec = 5
            self.assertEqual(run(98), stopped)


if __name__ == "__main__":
    unittest.main()
