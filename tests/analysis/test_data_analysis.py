import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from goldbot.analysis.data_analysis import FIELDS, analyze, render


class DataAnalysisTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "candles.csv"

    def write_rows(self, rows, header=FIELDS):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def test_checks_original_order_and_separates_gap_returns(self):
        labels = (100, 1000, 2900, 2900, 1000, 1450, 2350)
        closes = (100, 110, 121, 99, 100, 110, 99)
        self.write_rows((label, close, close, close, close, 1, 0, 0)
                        for label, close in zip(labels, closes))
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        result = analyze(self.path, "M15")
        self.assertEqual(result["rows"], 7)
        self.assertEqual(result["deltas"], {900: 2, 1900: 1, 0: 1, -1900: 1, 450: 1})
        self.assertEqual(result["timestamps"][1000], 2)
        self.assertEqual(result["gaps"], [(1900, 2, 1000, 2900)])
        self.assertAlmostEqual(result["returns"]["Nominal-interval pairs"][0], 10)
        self.assertAlmostEqual(result["returns"]["Nominal-interval pairs"][1], -10)
        self.assertAlmostEqual(result["returns"]["Longer-interval pairs"][0], 10)
        self.assertIn("raw server-clock labels", render(result, self.path, "M15"))
        self.assertEqual(result["sha256"], before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_bad_values_and_ohlc_do_not_create_bridged_returns(self):
        self.write_rows([
            (100, 10, 11, 9, 10, 1, 0, 0),
            ("NaN", 10, "inf", "", "bad", -1, 0),
            (1900, 10, 8, 9, 10, 1, 0, 0),
            (2800, 10, 11, -1, 0, 1, 0, 0),
        ])
        result = analyze(self.path, "M15")
        self.assertEqual(result["malformed"], 1)
        self.assertEqual(result["issues"]["Missing"], {"low": 1, "real_volume": 1})
        self.assertEqual(result["issues"]["Nonfinite"], {"mt5_time_epoch": 1, "high": 1})
        self.assertEqual(result["issues"]["Invalid"], {"close": 1, "tick_volume": 1})
        self.assertEqual(result["inconsistent"], 1)
        self.assertEqual(result["unchecked"], 1)
        self.assertEqual(result["nonpositive"], 1)
        self.assertEqual(result["deltas"], {900: 1})
        self.assertFalse(any(result["returns"].values()))

    def test_h1_nominal_and_header_only_series(self):
        self.write_rows([])
        result = analyze(self.path, "H1")
        self.assertEqual(result["rows"], 0)
        self.assertIn("unavailable", render(result, self.path, "H1"))
        self.write_rows([(1, 1, 1, 1, 1, 0, 0, 0), (3601, 1, 1, 1, 1, 0, 0, 0)])
        self.assertEqual(analyze(self.path, "H1")["returns"]["Nominal-interval pairs"], [0])

    def test_rejects_unexpected_header(self):
        self.write_rows([], header=FIELDS[::-1])
        with self.assertRaisesRegex(ValueError, "unexpected CSV header"):
            analyze(self.path, "H1")


if __name__ == "__main__":
    unittest.main()
