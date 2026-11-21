"""Regression coverage for the Phase 6.8.1 read-only evidence."""
from unittest import TestCase
from types import SimpleNamespace

from tests.risk import test_phase_52


class BrokerSpecificationEvidenceTests(TestCase):
    def setUp(self):
        self.fixture = test_phase_52.BrokerValidationTests()
        self.fixture.setUp()
        self.symbol = self.fixture.symbol
        self.symbol.currency_base = "XAU"
        self.symbol.custom = False
        self.symbol.margin_initial = 0.0
        self.symbol.margin_maintenance = 0.0
        self.symbol.margin_hedged = 25.0
        self.symbol.margin_hedged_use_leg = False

    def test_scale_difference_does_not_override_metadata(self):
        self.symbol.trade_tick_value = 0.05
        self.symbol.trade_tick_value_profit = 0.05
        self.symbol.trade_tick_value_loss = 0.05
        report = self.fixture.assert_rejected("INCONSISTENT_TICK_VALUE_METADATA")
        field = report["tick_value_comparison"]["fields"]["loss"]
        self.assertEqual(field["formula_tick_per_lot_to_reported_ratio"], "10")
        self.assertEqual(field["implied_lots_if_value_is_usd_per_tick"], "0.1")
        self.assertFalse(field["matches_point_per_lot_exactly"])
        self.assertFalse(field["matches_tick_at_minimum_volume_exactly"])
        self.assertNotIn("PROFIT_FORMULA_MISMATCH", report["probe_counts"]["profit_errors"])
        self.assertTrue(report["final_metadata_recheck_passed"])
        self.assertEqual(report["currencies"]["base"], "XAU")
        self.assertEqual(report["margin_metadata"]["margin_hedged"], 25.0)
        self.assertEqual(report["historical_applicability"], "UNVERIFIED")

    def test_asymmetric_fields_in_same_currency_model(self):
        self.symbol.trade_tick_value_loss = 0.25
        report = self.fixture.assert_rejected("INCONSISTENT_TICK_VALUE_METADATA")
        mismatches = [row for row in report["profit"] if "PROFIT_METADATA_MISMATCH" in row["errors"]]
        self.assertEqual({row["outcome"] for row in mismatches}, {"LOSS"})
        self.assertEqual({row["side"] for row in mismatches}, {"BUY", "SELL"})

    def test_generic_alone_can_reject_even_with_clean_directional_probes(self):
        self.symbol.trade_tick_value = 0.25
        report = self.fixture.assert_rejected("INCONSISTENT_TICK_VALUE_METADATA")
        self.assertFalse(report["probe_counts"]["profit_errors"])
        self.assertTrue(report["tick_value_comparison"]["fields"]["generic"]
                        ["matches_point_per_lot_exactly"])

    def test_nonfinite_tick_value_rejected(self):
        self.symbol.trade_tick_value_profit = float("inf")
        report = self.fixture.assert_rejected("INVALID_TICK_VALUES")
        self.assertIsNone(report["raw_numeric_fields"]["trade_tick_value_profit"])
        self.fixture.mt5.order_calc_profit.assert_not_called()

    def test_missing_generic_tick_value_rejected(self):
        del self.symbol.trade_tick_value
        self.fixture.assert_rejected("INVALID_OR_MISSING_DATA")
        self.fixture.mt5.order_calc_profit.assert_not_called()

    def test_invalid_margin_metadata_rejected(self):
        self.symbol.margin_maintenance = -1
        self.fixture.assert_rejected("INVALID_MARGIN_METADATA")
        self.fixture.mt5.order_calc_profit.assert_not_called()

    def test_custom_symbol_rejected(self):
        self.symbol.custom = True
        self.fixture.assert_rejected("CUSTOM_SYMBOL")
        self.fixture.mt5.order_calc_profit.assert_not_called()

    def test_initial_real_account_rejected_before_terminal_queries(self):
        initial = SimpleNamespace(**vars(self.fixture.account))
        initial.trade_mode = 2
        report = self.fixture.run_validation(initial)
        self.assertEqual(report["errors"][0]["reason"], "DEMO_REQUIRED")
        self.fixture.mt5.terminal_info.assert_not_called()
        self.fixture.mt5.order_calc_profit.assert_not_called()

    def test_cash_outside_rounding_tolerance_rejected(self):
        from goldbot.risk.risk_config import D

        self.fixture.mt5.order_calc_profit.side_effect = (
            lambda *args: self.fixture.profit(*args) + D("0.0051")
        )
        report = self.fixture.assert_rejected("PROFIT_PROBE_FAILED")
        self.assertEqual(report["probe_counts"]["profit_errors"]["PROFIT_FORMULA_MISMATCH"],
                         report["probe_counts"]["profit"])
