from pathlib import Path
import unittest

from tools.research_strategies_phase_6103 import (
    Candle, bollinger_reversion, build, donchian_breakout, score, trend_pullback,
)


def candles(prices, gaps=()):
    return [
        Candle(index, None if index == 1 else 1800 if index in gaps else 900,
               index in gaps, price + 1, price - 1, price)
        for index, price in enumerate(prices, 1)
    ]


class AlternativeStrategyTests(unittest.TestCase):
    def test_pullback_requires_an_ema_reclaim_in_the_trend_direction(self):
        for previous, last, expected in ((90, 110, "BUY"), (110, 90, "SELL")):
            with self.subTest(expected=expected):
                self.assertEqual(list(trend_pullback(candles([100] * 19 + [previous, last]))),
                                 ["WARMUP"] * 20 + [expected])
        self.assertEqual(list(trend_pullback(candles(range(100, 121))))[-1], "HOLD")

    def test_breakout_excludes_current_range_and_rejects_equality(self):
        for last, expected in ((102, "BUY"), (98, "SELL"), (101, "HOLD"), (99, "HOLD")):
            with self.subTest(last=last):
                self.assertEqual(list(donchian_breakout(candles([100] * 20 + [last]))),
                                 ["WARMUP"] * 20 + [expected])

    def test_reversion_requires_both_extreme_close_and_momentum(self):
        for last, expected in ((90, "BUY"), (110, "SELL"), (100, "HOLD")):
            with self.subTest(last=last):
                self.assertEqual(list(bollinger_reversion(candles([100] * 19 + [last]))),
                                 ["WARMUP"] * 19 + [expected])
        mixed = [90, 110] * 9 + [100, 131]
        self.assertEqual(list(bollinger_reversion(candles(mixed)))[-1], "HOLD")

    def test_gap_row_seeds_fresh_warmup_and_restarts_all_candidates(self):
        prices = [200] * 22 + [100] * 20 + [90]
        rows = list(score(candles(prices, gaps=(23,))))
        self.assertEqual(set(rows[22]["decisions"].values()), {"GAP"})
        suffix = list(score(candles(prices[22:])))
        self.assertEqual([row["decisions"] for row in rows[23:]],
                         [row["decisions"] for row in suffix[1:]])
        self.assertEqual(set(rows[40]["decisions"].values()), {"WARMUP"})
        self.assertEqual(rows[41]["decisions"]["mean_reversion_bollinger_rsi"], "HOLD")
        self.assertEqual(rows[42]["decisions"]["breakout_donchian"], "SELL")

    def test_every_prefix_and_future_perturbations(self):
        series = candles([100, 97, 105, 104, 103, 96, 110, 100, 99, 101] * 10,
                         gaps=(25, 56, 79))
        full = list(score(series))
        for end in range(len(series) + 1):
            tail = [bar._replace(high=901, low=899, close=900) for bar in series[end:]]
            with self.subTest(end=end):
                self.assertEqual(list(score(series[:end])), full[:end])
                self.assertEqual(list(score(series[:end] + tail))[:end], full[:end])

    def test_original_inputs_reconcile_and_retain_no_go(self):
        report = build(Path(__file__).resolve().parents[1])
        self.assertEqual(report["readiness_decision"], "NO-GO")
        for frame in report["timeframes"].values():
            rows = frame["rows"]
            self.assertEqual([row["row"] for row in rows], list(range(1, 10001)))
            for candidate, counts in frame["counts"].items():
                self.assertEqual(sum(counts.values()), len(rows))
                self.assertEqual(counts["GAP"], sum(row["gap_before"] for row in rows))
                for status, count in counts.items():
                    self.assertEqual(count, sum(row["decisions"][candidate] == status
                                                for row in rows))
