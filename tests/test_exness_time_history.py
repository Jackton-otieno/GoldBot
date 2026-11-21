import unittest

from tools.verify_exness_time_history import bars_evidence, quote_basis


class ExnessTimeHistoryTests(unittest.TestCase):
    def test_bar_gaps_and_relative_close(self):
        rows = [
            {"time": label, "open": 10, "high": 12, "low": 9, "close": 11}
            for label in (900, 2700)
        ]
        result = bars_evidence(rows, 900, 3500)
        self.assertEqual(result["gap_seconds"], {1800: 1})
        self.assertTrue(result["ordered"] and result["aligned"] and result["ohlc_valid"])
        self.assertFalse(result["relative_close"])
        self.assertFalse(bars_evidence(rows[::-1], 900, 3600)["ordered"])

    def test_basis_requires_usable_ordered_unsaturated_ticks(self):
        bar = {"raw_open": 60, "open": 10, "high": 11, "low": 10, "close": 11}
        rows = [
            {"raw_s": 60, "raw_ms": 60001, "bid": 10, "ask": 12},
            {"raw_s": 119, "raw_ms": 119999, "bid": 11, "ask": 13},
        ]
        self.assertEqual(quote_basis(rows, bar, False), ["bid"])
        self.assertEqual(quote_basis(rows, bar, True), [])
        self.assertEqual(quote_basis(rows[::-1], bar, False), [])
