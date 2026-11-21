from collections import Counter
from decimal import Decimal as D
from unittest import TestCase

from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.risk.position_sizing import size_position
from goldbot.risk.risk_config import ExecutionAssumptions, RISK_PER_TRADE
from goldbot.risk.trade_plan import price_levels
from tools import capital_feasibility_phase_61054 as phase


class MinimumCapitalTests(TestCase):
    def setUp(self):
        self.spec = execution_spec("baseline", dict(SCENARIOS)["baseline"])

    def test_min_lot_boundary_matches_unchanged_sizer_on_both_sides(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                spec = self.spec
                quote = ExecutionAssumptions(
                    spec.evidence, "XAUUSD", side, D("3799.85"), D("3800.15"),
                    spec.entry_slippage, spec.stop_slippage,
                    spec.round_trip_commission_per_lot, spec.margin_per_lot,
                )
                levels = price_levels(side, D("8.001"), quote, spec.broker)
                loss = phase.minimum_loss(D("8.001"), spec, side, phase.MIDPOINT)
                sized, _ = size_position(stop_distance=levels[-1], budget=loss,
                                         free_margin=D(10), specs=spec.broker, execution=quote)
                self.assertEqual(sized.volume, D(".01"))
                self.assertEqual(sized.modeled_loss, loss)
                _, status = size_position(stop_distance=levels[-1], budget=loss - D(".00001"),
                                          free_margin=D(10), specs=spec.broker, execution=quote)
                self.assertEqual(status, "BELOW_MINIMUM_VOLUME")
                self.assertLess((phase.minimum_equity(loss) - D(".01")) * RISK_PER_TRADE, loss)
                self.assertGreaterEqual(phase.minimum_equity(loss) * RISK_PER_TRADE, loss)

    def test_spread_consumes_stop_geometry_and_cannot_be_cured_by_capital(self):
        self.assertIsNone(phase.minimum_loss(D(".10"), self.spec, "BUY", phase.MIDPOINT))
        result = phase.feasibility([D(".10"), D("4")], self.spec)
        self.assertEqual(result["invalid_geometry_either_side"], 1)
        self.assertEqual(result["equity_levels"]["10000"]["cases_passing_risk_by_sensitivity"]["planner"], 1)

    def test_precision_and_carry_hurdles_do_not_mutate_base_risk(self):
        result = phase.feasibility([D("8")], self.spec)
        thresholds = result["risk_minimum_equity_usd"]
        base = thresholds["planner"]["p50"]
        self.assertEqual(thresholds["precision_cent_sensitivity"]["p50"] - base, D(2))
        self.assertEqual(thresholds["carry_usd_1_sensitivity"]["p50"] - base, D(200))
        self.assertEqual(result["equity_levels"]["3000"]["per_trade_budget_usd"], D("15"))

    def test_margin_is_independent_of_risk_and_quantiles_are_nearest_rank(self):
        rows = phase.margin_cases(D(".01"), D(100), D(3800), D(2))
        self.assertEqual([row["required_free_margin_usd"] for row in rows],
                         [D(2), D("9.50"), D(38), D(190)])
        self.assertFalse(rows[-1]["feasible_if_free_margin_equals_equity"]["100"])
        self.assertTrue(rows[-1]["feasible_if_free_margin_equals_equity"]["500"])
        self.assertEqual(phase.distribution([D(3), D(1), D(2)])["p50"], D(2))
