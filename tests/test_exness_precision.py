from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from tools.verify_exness_precision import grid, predictions, summarize


class ExnessPrecisionTests(unittest.TestCase):
    def test_ties_floors_and_nonzero_minimum(self):
        for amount in (D(".001"), D("-.001")):
            result = predictions(amount)
            self.assertEqual(result["nearest_half_even"], 0)
            self.assertEqual(result["minimum_cent_nearest_half_even"], D(".01").copy_sign(amount))
        self.assertEqual(predictions(D("-.005"))["nearest_half_positive"], 0)
        self.assertEqual(predictions(D("-.005"))["nearest_half_negative"], D("-.01"))
        self.assertEqual(predictions(D(".025"))["nearest_half_even"], D(".02"))
        self.assertEqual(predictions(D(".025"))["nearest_half_away"], D(".03"))
        self.assertEqual(predictions(D(".011"))["away_from_zero"], D(".02"))
        self.assertTrue(all(value == 0 for value in predictions(D("0")).values()))

    def test_grid_uses_exact_cash_and_market_steps(self):
        specs = SimpleNamespace(volume_min=D(".01"), volume_max=D("200"),
                                volume_step=D(".01"), contract_size=D("100"), tick_size=D(".001"))
        cases, unsupported = grid(specs, SimpleNamespace(volume_limit=.02), [D("3800.001")])
        self.assertIn(("BUY", D(".01"), D("3800.001"), D("3800.006"), D(".005")), cases)
        self.assertIn(("SELL", D(".01"), D("3800.001"), D("3799.996"), D(".005")), cases)
        self.assertTrue(any(row["lots"] == "0.02" and row["target_usd"] == "0.005"
                            for row in unsupported))
        for side, volume, entry, exit_price, cash in cases:
            self.assertLessEqual(volume, D(".02"))
            self.assertEqual(exit_price % specs.tick_size, 0)
            direction = 1 if side == "BUY" else -1
            self.assertEqual((exit_price - entry) * direction * volume * specs.contract_size, cash)

    def test_summary_detects_sign_asymmetry_and_repeat_changes(self):
        base = {"side": "BUY", "lots": "0.01", "entry": "3800.005"}
        rows = [
            {**base, "repeat": 1, "formula_usd": ".005", "exit": "3800.010", "observed_usd": ".01"},
            {**base, "repeat": 1, "formula_usd": "-.005", "exit": "3800.000", "observed_usd": "0"},
            {**base, "repeat": 2, "formula_usd": ".005", "exit": "3800.010", "observed_usd": ".01"},
            {**base, "repeat": 2, "formula_usd": "-.005", "exit": "3800.000", "observed_usd": "-.01"},
            {**base, "repeat": 1, "formula_usd": ".006", "error": "PROFIT_UNAVAILABLE"},
        ]
        result = summarize(rows)
        self.assertEqual(result["sign_pairs_compared"], 2)
        self.assertEqual(len(result["sign_asymmetries"]), 1)
        self.assertEqual(len(result["changed_between_repeats"]), 1)
        self.assertEqual(result["unsupported_observations"], 1)
        self.assertEqual(result["policy_counts"]["all"]["observations"], 4)

    def test_notional_rounding_compares_prices_before_subtraction(self):
        row = {"side": "BUY", "lots": "0.01", "entry": "3788.548", "exit": "3788.554",
               "repeat": 1, "formula_usd": ".006", "observed_usd": "0"}
        result = summarize([row], D("100"))
        self.assertEqual(result["notional_policy_matches"]["ROUND_HALF_UP"], 1)
        self.assertNotIn("nearest_half_even", row["matching_policies"])