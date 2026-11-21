import csv
import math
import tempfile
import unittest
from pathlib import Path

from goldbot.analysis.data_analysis import FIELDS
from goldbot.analysis.indicators import EMA_PERIODS, SMA_PERIODS, derive, ema, sma, write_csv


class MovingAverageTests(unittest.TestCase):
    def test_known_sequences(self):
        closes = [2, 4, 9, 7, 11]
        self.assertEqual(sma(closes, 3)[2:], [5, 20 / 3, 9])
        self.assertEqual(ema(closes, 3)[2:], [5, 6, 8.5])

    def test_warmup_and_period_one(self):
        for calculate, periods in ((sma, SMA_PERIODS), (ema, EMA_PERIODS)):
            for period in periods:
                with self.subTest(calculate=calculate.__name__, period=period):
                    closes = [8.0] * (period + 1)
                    values = calculate(closes, period)
                    self.assertTrue(all(map(math.isnan, values[:period - 1])))
                    self.assertEqual(values[period - 1:], [8.0, 8.0])
                    self.assertTrue(all(map(math.isnan, calculate(closes[:period - 1], period))))
            self.assertEqual(calculate([], 1), [])
            self.assertEqual(calculate([2, 4], 1), [2, 4])

    def test_invalid_inputs(self):
        for calculate in (sma, ema):
            for period in (0, -1, True, 2.0, "2"):
                with self.subTest(period=period), self.assertRaises(ValueError):
                    calculate([1], period)
            for close in (None, "1", True, 0, -1, math.nan, math.inf, -math.inf):
                with self.subTest(close=close), self.assertRaises(ValueError):
                    calculate([8, close], 3)

    def test_prefix_invariance(self):
        closes = [1 + (i * 17 % 31) for i in range(270)]
        for calculate, periods in ((sma, SMA_PERIODS), (ema, EMA_PERIODS)):
            for period in periods:
                full = calculate(closes, period)
                for cutoff in (period - 1, period, period + 1, 240):
                    prefix = calculate(closes[:cutoff], period)
                    self.assertEqual(len(prefix), cutoff)
                    self.assertTrue(all(map(math.isnan, prefix[:period - 1])))
                    self.assertEqual(prefix[period - 1:], full[period - 1:cutoff])


class ExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def source(self, timeframe, labels, closes):
        path = self.root / f"{timeframe}.csv"
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            for label, close in zip(labels, closes):
                writer.writerow([label, close, close, close, close, 0, 0, 0])
        return path

    def test_gaps_and_independent_timeframes(self):
        labels = [900 * i for i in range(1, 10)] + [10800]
        m15 = self.source("M15", labels, list(range(1, 10)) + [15])
        h1 = self.source("H1", [3600 * i for i in range(1, 11)], [100] * 10)
        original = m15.read_bytes()
        m15_columns, _ = derive(m15, "M15", 10)
        h1_columns, _ = derive(h1, "H1", 10)
        self.assertEqual(m15_columns["raw_server_clock_label"], labels)
        self.assertEqual(m15_columns["raw_label_delta"], [None] + [900] * 8 + [2700])
        self.assertEqual(m15_columns["gap_before"], [False] * 9 + [True])
        self.assertEqual(h1_columns["gap_before"], [False] * 10)
        self.assertEqual(m15_columns["ema_9"][-2:], [5, 7])
        self.assertEqual(h1_columns["ema_9"][-2:], [100, 100])
        out = self.root / "derived.csv"
        write_csv(out, m15_columns)
        with out.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), len(labels))
        self.assertEqual(rows[0]["ema_9"], "nan")
        self.assertEqual(rows[-1]["gap_before"], "True")
        self.assertEqual(m15.read_bytes(), original)

    def test_rejects_invalid_exports(self):
        for labels, closes in (
            ([900, 900], [1, 1]), ([1800, 900], [1, 1]),
            ([900, 1801], [1, 1]), ([900, 1800], [1, math.nan]),
            ([900], [1]),
        ):
            with self.subTest(labels=labels, closes=closes), self.assertRaisesRegex(ValueError, "validation"):
                derive(self.source("M15", labels, closes), "M15", 2)


if __name__ == "__main__":
    unittest.main()
