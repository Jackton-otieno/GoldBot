import unittest
from dataclasses import dataclass, replace

from tools.analyze_market_regimes_phase_6102 import classify, metrics, overlap


@dataclass(frozen=True)
class Bar:
    high: float
    low: float
    close: float
    gap_before: bool = False


def rising(count):
    return [Bar(value + 1, value - 1, value) for value in range(100, 100 + count)]


class MarketRegimeTests(unittest.TestCase):
    def test_seeds_and_trend(self):
        rows = list(classify(rising(40)))
        self.assertIsNone(rows[13]["atr_14"])
        self.assertEqual(rows[14]["atr_14"], 2)
        self.assertEqual(rows[19]["ema_20"], 109.5)
        self.assertEqual(rows[23]["direction"], "WARMUP")
        self.assertEqual(rows[24]["ema_slope"], 1)
        self.assertEqual(rows[24]["direction"], "UP")
        self.assertIsNone(rows[26]["adx_14"])
        self.assertEqual(rows[27]["adx_14"], 100)
        self.assertEqual(rows[27]["strength"], "STRONG")
        self.assertIsNone(rows[33]["volatility_ratio"])
        self.assertAlmostEqual(rows[34]["normalized_atr"], 2 / 134)
        self.assertAlmostEqual(rows[34]["volatility_ratio"], (2 / 134) / ((2 / 123 + 2 / 124) / 2))

    def test_wilder_recurrence_and_directional_movement_tie(self):
        bars = rising(28) + [Bar(131, 122, 127)]
        row = list(classify(bars))[-1]
        # Prior high/low are 128/126. This outside bar has -DM=4 and +DM=0.
        self.assertAlmostEqual(row["atr_14"], (13 * 2 + 9) / 14)
        self.assertAlmostEqual(row["adx_14"], (1300 + 100 * 9 / 17) / 14)
        tied = list(classify(rising(28) + [Bar(132, 122, 127)]))[-1]
        self.assertEqual(tied["adx_14"], 100)

    def test_flat_series_and_unavailable_ratio(self):
        bars = [Bar(100, 100, 100)] * 36
        row = list(classify(bars))[-1]
        self.assertEqual((row["direction"], row["strength"], row["volatility"]),
                         ("FLAT", "WEAK", "TYPICAL"))
        changed = list(classify(bars + [Bar(110, 100, 105)]))[-1]
        self.assertEqual(changed["volatility"], "UNDEFINED")

    def test_gap_restart_prefix_invariance_and_future_perturbation(self):
        bars = rising(80)
        bars[40] = replace(bars[40], gap_before=True)
        full = list(classify(bars))
        self.assertEqual(full[40]["direction"], "GAP")
        restarted = list(classify([replace(bars[40], gap_before=False), *bars[41:]]))
        self.assertEqual(full[41:], restarted[1:])
        for end in (1, 14, 25, 28, 35, 40, 41, 55, 77):
            self.assertEqual(list(classify(bars[:end])), full[:end])
        changed = [*bars[:42], *[Bar(501, 499, 500)] * 38]
        self.assertEqual(list(classify(changed))[:42], full[:42])

    def test_funnel_and_overlap(self):
        rows = [dict(row=1, decision="BUY", direction="UP", strength="WEAK", volatility="LOW"),
                dict(row=2, decision="SELL", direction="DOWN", strength="WEAK", volatility="LOW")]
        trade = dict(signal_row=1, net_pnl_usd="-1.25", exit_reason="STOP")
        result = metrics(rows, [dict(entry_status="FILLED"),
                                dict(entry_status="BELOW_MINIMUM_VOLUME")], [trade])
        self.assertEqual((result["attempts"], result["filled"], result["rejected"],
                          result["below_minimum_volume"], result["stops"]), (2, 1, 1, 1, 1))
        self.assertEqual(result["win_rate"], 0)
        self.assertIsNone(metrics(rows, [], [])["win_rate"])
        runs = dict(a=dict(closed_trades=[trade]), b=dict(closed_trades=[trade,
                                                                         dict(trade, signal_row=2)]))
        total = overlap(rows, runs)["all"]["ALL"]
        self.assertEqual(total["closed_signal_rows_in_all_scenarios"], 1)
        self.assertEqual(total["unique_closed_signal_rows"], 2)
        self.assertEqual(total["pairs"]["a/b"], dict(shared=1, left_only=0, right_only=1))
