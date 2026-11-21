import csv
import math
import tempfile
import unittest
from pathlib import Path

from goldbot.analysis.data_analysis import FIELDS
from goldbot.analysis.indicators import atr, derive, macd, rsi


class Phase33Tests(unittest.TestCase):
    def test_wilder_rsi_seed_and_update(self):
        values = rsi([10, 14, 12, 15, 11], 2)
        self.assertTrue(all(map(math.isnan, values[:2])))
        for value, expected in zip(values[2:], [200 / 3, 250 / 3, 500 / 14]):
            self.assertAlmostEqual(value, expected)

    def test_rsi_flat_rising_and_falling(self):
        for closes, expected in (([4] * 18, 50), (range(1, 19), 100), (range(18, 0, -1), 0)):
            with self.subTest(expected=expected):
                values = rsi(closes)
                self.assertTrue(all(map(math.isnan, values[:14])))
                self.assertEqual(values[14:], [expected] * 4)

    def test_atr_seed_and_gap_true_range(self):
        values = atr([12, 21, 20], [8, 19, 18], [10, 20, 19], 2)
        self.assertTrue(math.isnan(values[0]))
        self.assertEqual(values[1:], [7.5, 4.75])
        self.assertEqual(atr([12], [8], [10], 1), [4])

    def test_macd_alignment_and_signal_seed(self):
        # A linear ramp gives a 7-unit EMA spread. Shock the ninth valid MACD row.
        for direction in (1, -1):
            closes = [100 + direction * i for i in range(34)]
            closes[-1] += direction * 13
            line, signal, histogram = macd(closes)
            self.assertTrue(all(map(math.isnan, line[:25])))
            self.assertTrue(all(map(math.isnan, signal[:33] + histogram[:33])))
            shock = direction * 13 * (2 / 13 - 2 / 27)
            for value in line[25:33]:
                self.assertAlmostEqual(value, direction * 7)
            self.assertAlmostEqual(line[33], direction * 7 + shock)
            self.assertAlmostEqual(signal[33], direction * 7 + shock / 9)
            self.assertAlmostEqual(histogram[33], shock * 8 / 9)
        self.assertEqual([series[33:] for series in macd([8] * 35)], [[0, 0]] * 3)

    def test_warmups_and_prefix_invariance(self):
        closes = [2 + i * 17 % 31 for i in range(80)]

        def calculate(prices):
            return (rsi(prices), atr([p + 2 for p in prices], [p - 1 for p in prices], prices),
                    *macd(prices))

        full = calculate(closes)
        for cutoff in range(len(closes) + 1):
            for prefix, series, warmup in zip(calculate(closes[:cutoff]), full, (14, 13, 25, 33, 33)):
                self.assertEqual(len(prefix), cutoff)
                self.assertTrue(all(map(math.isnan, prefix[:warmup])))
                self.assertEqual(prefix[warmup:], series[warmup:cutoff])

    def test_invalid_inputs(self):
        for bad in (0, -1, True, "2", None, math.inf, math.nan):
            for calculate in (rsi, macd, lambda prices: atr(prices, [1], [1])):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    calculate([bad])
        for period in (0, -1, True, 2.0, "2"):
            with self.assertRaises(ValueError):
                rsi([2], period)
            with self.assertRaises(ValueError):
                atr([3], [1], [2], period)
        for highs, lows, closes in (([2], [], [1]), ([3], [2], [1]), ([1], [3], [2])):
            with self.assertRaises(ValueError):
                atr(highs, lows, closes)

    def test_exports_keep_gap_candle_and_timeframes_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            counts = 40
            paths = {}
            for timeframe, interval in (("M15", 900), ("H1", 3600)):
                path = paths[timeframe] = Path(directory) / f"{timeframe}.csv"
                with path.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(FIELDS)
                    for index in range(counts):
                        gap = timeframe == "M15" and index >= 34
                        close = 10 + 20 * gap if timeframe == "M15" else 100 - index
                        writer.writerow([interval * (index + 1 + gap), close, close, close, close, 0, 0, 0])
            m15, _ = derive(paths["M15"], "M15", counts, phase_3_3=True)
            h1, _ = derive(paths["H1"], "H1", counts, phase_3_3=True)
            self.assertEqual(m15["raw_server_clock_label"][34], 36 * 900)
            self.assertEqual(h1["raw_server_clock_label"][34], 35 * 3600)
            self.assertEqual(m15["gap_before"].count(True), 1)
            self.assertTrue(m15["gap_before"][34])
            self.assertFalse(any(h1["gap_before"]))
            self.assertEqual(m15["rsi_14"][33:35], [50, 100])
            self.assertEqual(h1["rsi_14"][33:35], [0, 0])
            self.assertAlmostEqual(m15["atr_14"][34], 20 / 14)
            self.assertAlmostEqual(h1["atr_14"][34], 1 - (13 / 14) ** 21 / 14)
            self.assertGreater(m15["macd_12_26"][34], 0)
            self.assertAlmostEqual(h1["macd_12_26"][34], -7)
