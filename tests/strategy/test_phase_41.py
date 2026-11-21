import csv
from dataclasses import replace
from io import StringIO
import math
import unittest

from goldbot.strategy.signals import FIRST_VALID, PHASE_33_FIELDS, signal_rows
from goldbot.strategy.strategy import Indicators, evaluate
from goldbot.strategy.strategy_config import StrategyConfig


BUY = Indicators(3, 2, 4, 3, 60, 1, 1)
SELL = Indicators(1, 2, 3, 4, 40, -1, 1)
EQUAL = replace(BUY, ema_9=2)


def fixture(interval):
    rows = []
    label = 10000
    for number in range(1, 204):
        delta = interval * (2 if number == 200 else 1)
        label += delta
        current = {199: EQUAL, 201: SELL, 202: BUY}.get(number, BUY)
        row = dict.fromkeys(PHASE_33_FIELDS, "1")
        row.update(raw_server_clock_label=str(label),
                   raw_label_delta=str(delta) if number > 1 else "",
                   gap_before=str(delta > interval))
        for field, first in FIRST_VALID.items():
            row[field] = str(getattr(current, field)) if number >= first else "nan"
        rows.append(row)
    return rows


def run_rows(rows, timeframe="M15"):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, PHASE_33_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    stream.seek(0)
    return list(signal_rows(stream, timeframe))


class StrategyTests(unittest.TestCase):
    def test_both_directions_accept_previous_equality(self):
        self.assertEqual(evaluate(BUY, EQUAL).decision, "BUY")
        self.assertEqual(evaluate(SELL, EQUAL).decision, "SELL")
        self.assertEqual(evaluate(EQUAL, SELL).reasons, ("NO_CROSSOVER",))
        self.assertEqual(evaluate(BUY, BUY).reasons, ("NO_CROSSOVER",))

    def test_strict_rsi_boundaries_and_inner_values(self):
        for base, floor, ceiling, direction in ((BUY, 50, 70, "BUY"), (SELL, 30, 50, "SELL")):
            for boundary in (floor, ceiling):
                with self.subTest(direction=direction, boundary=boundary):
                    self.assertEqual(evaluate(replace(base, rsi_14=boundary), EQUAL).reasons,
                                     ("RSI_FILTER",))
            for inner in (math.nextafter(floor, ceiling), math.nextafter(ceiling, floor)):
                self.assertEqual(evaluate(replace(base, rsi_14=inner), EQUAL).decision, direction)

    def test_zero_and_wrong_sign_filters(self):
        for base in (BUY, SELL):
            for histogram in (0, -base.macd_histogram):
                current = replace(base, ema_50=base.ema_200, macd_histogram=histogram, atr_14=0)
                self.assertEqual(evaluate(current, EQUAL).reasons,
                                 ("TREND_FILTER", "MACD_FILTER", "ATR_FILTER"))
            wrong_trend = replace(base, ema_50=base.ema_200, ema_200=base.ema_50)
            self.assertEqual(evaluate(wrong_trend, EQUAL).reasons, ("TREND_FILTER",))

    def test_invalid_and_warmup(self):
        for change in ({"atr_14": -1}, {"atr_14": math.inf}, {"rsi_14": 101},
                       {"rsi_14": -1}, {"ema_9": "3"}, {"macd_histogram": -math.inf}):
            self.assertEqual(evaluate(replace(BUY, **change), EQUAL).reasons, ("INVALID_INPUT",))
        self.assertEqual(evaluate(BUY, None).reasons, ("WARMUP",))
        self.assertEqual(evaluate(replace(BUY, ema_200=math.nan), EQUAL).reasons, ("WARMUP",))
        self.assertEqual(evaluate(BUY, replace(EQUAL, ema_9=math.nan)).reasons, ("WARMUP",))

    def test_gap_policy_uses_only_current_gap_flag(self):
        self.assertEqual(evaluate(BUY, EQUAL, gap_before=True).reasons, ("GAP_CROSSOVER",))
        self.assertEqual(evaluate(SELL, EQUAL, gap_before=True).reasons, ("GAP_CROSSOVER",))
        self.assertEqual(evaluate(BUY, BUY, gap_before=True).reasons, ("NO_CROSSOVER",))
        config = StrategyConfig(hold_gap_crossovers=False)
        self.assertEqual(evaluate(BUY, EQUAL, gap_before=True, config=config).decision, "BUY")


class SignalRowTests(unittest.TestCase):
    def test_prefix_invariance_and_independent_timeframes(self):
        m15 = fixture(900)
        h1 = fixture(3600)
        full = run_rows(m15)
        h1[201]["macd_histogram"] = "0"
        self.assertEqual(run_rows(h1, "H1")[201]["reasons"], "MACD_FILTER")
        self.assertEqual(run_rows(m15), full)
        for length in (1, 199, 200, 201, 202):
            self.assertEqual(run_rows(m15[:length]), full[:length])
        self.assertEqual(full[198]["reasons"], "WARMUP")
        self.assertEqual(full[199]["reasons"], "GAP_CROSSOVER")
        self.assertEqual(full[200]["decision"], "SELL")
        self.assertEqual(full[201]["decision"], "BUY")
        self.assertEqual(full[202]["decision"], "HOLD")
        self.assertEqual(full[200]["source_row"], 201)
        self.assertEqual(full[200]["raw_server_clock_label"], m15[200]["raw_server_clock_label"])

    def test_reject_corrupted_strategy_inputs_and_gap_metadata(self):
        for field, value in (("ema_200", "nan"), ("rsi_14", "bogus"),
                             ("atr_14", "inf"), ("gap_before", "False"),
                             ("raw_label_delta", "900")):
            with self.subTest(field=field):
                rows = fixture(900)
                rows[199][field] = value
                with self.assertRaisesRegex(ValueError, "M15 source row 200"):
                    run_rows(rows)


if __name__ == "__main__":
    unittest.main()
