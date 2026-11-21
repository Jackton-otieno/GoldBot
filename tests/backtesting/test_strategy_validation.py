import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
from pathlib import Path
from unittest.mock import patch

from goldbot.analysis.data_analysis import FIELDS
from goldbot.backtesting import strategy_validation as validation
from goldbot.strategy.strategy import Signal


def fixture(prices, *, interval=900, start=1):
    lines = [",".join(FIELDS)]
    for index, close in enumerate(prices):
        lines.append(f"{start + index * interval},{close},{close + 1},{close - 1},{close},1,0,0")
    return ("\n".join(lines) + "\n").encode("ascii")


class StrategyValidationTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixture([2000] * 350)
        self.timeframe = "M15"
        strategy, _ = validation.frozen_strategy()
        self.strategy_digest = strategy.sha256

    def commitments(self, payload, timeframe):
        args = {
            "expected_sha256": validation.sha256(payload),
            "expected_strategy_sha256": self.strategy_digest,
        }
        boundaries = validation.synthetic_boundaries(payload, timeframe, **args)
        return dict(args, expected_boundaries_sha256=boundaries.sha256)

    def test_historical_audit_and_report(self):
        encoded = validation.audit_bytes()
        actual = json.loads(encoded)
        self.assertFalse(actual["historical_execution_performed"])
        manifest = actual["boundaries"]["manifest"]
        self.assertFalse(manifest["genuine_unseen_holdout"])
        for timeframe, source in manifest["sources"].items():
            self.assertIn("previously inspected", source["provenance"])
            self.assertEqual(source["sha256"], validation.ORIGINAL_DIGESTS[timeframe])
            groups = source["partitions"]
            self.assertEqual([p["count"] for p in groups], [6000, 2000, 2000])
            self.assertEqual([p["first_source_row"] for p in groups], [1, 6001, 8001])
            self.assertEqual([p["last_source_row"] for p in groups], [6000, 8000, 10000])
            self.assertEqual([p["preceding_close_warmup_rows"] for p in groups], [0, 6000, 8000])
            lines = (validation.ROOT / source["path"]).read_text().splitlines()
            for part in groups:
                for edge in ("first", "last"):
                    raw_label = int(lines[part[f"{edge}_source_row"]].split(",")[0])
                    self.assertEqual(part[f"{edge}_raw_server_clock_label"], raw_label)
            for previous, current in zip(groups, groups[1:]):
                self.assertLess(previous["last_raw_server_clock_label"],
                                current["first_raw_server_clock_label"])
        for key in ("strategy", "boundaries"):
            self.assertEqual(actual[key]["sha256"], validation.sha256(
                validation.canonical_bytes(actual[key]["manifest"])))
        self.assertEqual(encoded, validation.audit_bytes())
        report = validation.ROOT / "reports/validation_phase_6_6/validation.json"
        self.assertEqual(encoded, report.read_bytes())

    def test_prefix_invariance_and_warmup(self):
        prices = [2000 + (index % 29) / 10 for index in range(350)]
        for timeframe, interval in (("M15", 900), ("H1", 3600)):
            payload = fixture(prices, interval=interval)
            rows = validation._synthetic_fixture(payload, timeframe, validation.sha256(payload))
            part = validation.partitions(len(rows))[1]
            events = validation._events(rows, timeframe, part)
            partial = validation.Partition(part.name, part.start, part.start + 10)
            prefix = validation._events(rows, timeframe, partial)
            self.assertEqual(events[:20], prefix)
            self.assertIsNotNone(dict(events[1].indicators)["ema_200"])
            self.assertEqual(events[0].raw_server_clock_label, rows[part.start][0])
            self.assertIsNone(events[0].raw_label_delta)
            changed_history = fixture([2100] * part.start + prices[part.start:], interval=interval)
            altered = validation._synthetic_fixture(
                changed_history, timeframe, validation.sha256(changed_history))
            self.assertNotEqual(dict(events[1].indicators)["ema_200"], dict(
                validation._events(altered, timeframe, part)[1].indicators)["ema_200"])
            changed_future = fixture(prices[:partial.stop] + [2500] * (350 - partial.stop),
                                     interval=interval)
            altered = validation._synthetic_fixture(
                changed_future, timeframe, validation.sha256(changed_future))
            self.assertEqual(events[:20], validation._events(altered, timeframe, part)[:20])

    def test_account_boundaries_and_unresolved_position(self):
        args = self.commitments(self.payload, self.timeframe)
        hold = Signal("HOLD", ("FIXTURE",))
        buy = Signal("BUY", ("BUY_SETUP",))
        # Feed two close signals to exercise the simulator boundary paths.
        with patch.object(validation, "evaluate", side_effect=[hold] * 208 + [buy, buy]):
            result = validation.evaluate_synthetic(
                self.payload, self.timeframe, "development", **args)
        self.assertEqual(result.terminal.terminal_signal_row, 210)
        self.assertEqual(result.terminal.unresolved_position.entry_row, 210)
        self.assertIsNone(result.events[-1].exit)
        next_result = validation.evaluate_synthetic(
            self.payload, self.timeframe, "validation", **args)
        first = next_result.events[0]
        self.assertEqual(first.row, 1)
        self.assertEqual(first.raw_server_clock_label, 1 + 210 * 900)
        self.assertEqual(first.balance, Decimal("3000"))
        self.assertEqual(first.equity, first.balance)
        self.assertEqual(first.entry_status, "NO_PRIOR_SIGNAL")
        self.assertTrue(first.boundary)
        self.assertIsNone(first.attempted)
        self.assertIsNone(first.position)
        self.assertEqual(next_result, validation.evaluate_synthetic(
            self.payload, self.timeframe, "validation", **args))

    def test_frozen_manifest_and_commitments(self):
        original, _ = validation.frozen_strategy()
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(original, validation.frozen_strategy()[0])
        with self.assertRaises(FrozenInstanceError):
            original.canonical = b"{}"
        original.envelope()["manifest"]["risk"].clear()
        self.assertEqual(original, validation.frozen_strategy()[0])
        args = self.commitments(self.payload, self.timeframe)
        for name in args:
            changed = dict(args, **{name: "0" * 64})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                validation.evaluate_synthetic(self.payload, self.timeframe, "development", **changed)
        with self.assertRaisesRegex(ValueError, "input SHA-256 mismatch"):
            validation.evaluate_synthetic(self.payload + b"\n", self.timeframe, "test", **args)
        with patch.object(validation.risk_config, "MAX_POSITIONS", 2):
            with self.assertRaisesRegex(ValueError, "strategy manifest SHA-256 mismatch"):
                validation.evaluate_synthetic(self.payload, self.timeframe, "test", **args)

    def test_reject_contaminated_inputs(self):
        lines = self.payload.splitlines()
        for bad_lines in ([lines[0], lines[2], lines[1], *lines[3:]],
                          [lines[0], lines[1], lines[1], *lines[3:]]):
            bad = b"\n".join(bad_lines)
            with self.assertRaisesRegex(ValueError, "repeated, backward"):
                self.commitments(bad, self.timeframe)
        with self.assertRaisesRegex(ValueError, "off-grid"):
            self.commitments(self.payload, "H1")
        hourly = fixture([2000] * 350, interval=3600)
        hourly_args = self.commitments(hourly, "H1")
        with self.assertRaisesRegex(ValueError, "boundaries SHA-256 mismatch"):
            validation.evaluate_synthetic(hourly, "M15", "test", **hourly_args)
        historical = (validation.ROOT / "data/XAUUSD_H1.csv").read_bytes()
        with self.assertRaisesRegex(ValueError, "relative labels"):
            self.commitments(historical, "H1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/XAUUSD_M15.csv").write_bytes(self.payload)
            with self.assertRaisesRegex(ValueError, "input SHA-256 mismatch"):
                validation.retrospective_audit(root)
