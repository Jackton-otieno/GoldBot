import csv
import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from goldbot.analysis.data_analysis import FIELDS, INTERVALS
from goldbot.backtesting.historical_replay import ClosedEvent, OpenEvent, load_replay, render_audit


class HistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "candles.csv"

    def rows(self, timeframe, count=300):
        interval = INTERVALS[timeframe]
        for index in range(count):
            label = 10000 + (index + 3 * (index >= 210)) * interval
            price = 100 + index % 31
            yield [label, price, price + 3, price - 2, price + 1, 10, 3, 0]

    def write(self, rows, fields=FIELDS):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_prefix_invariance_in_both_timeframes(self):
        for timeframe in INTERVALS:
            rows = list(self.rows(timeframe))
            self.write(rows)
            complete = load_replay(self.path, timeframe).events
            for length in (1, 14, 15, 33, 34, 199, 200, 210, 211, 250):
                with self.subTest(timeframe=timeframe, length=length):
                    self.write(rows[:length])
                    prefix = load_replay(self.path, timeframe).events
                    self.assertEqual(prefix, complete[:2 * length])

    def test_open_visibility_with_changed_current_close(self):
        rows = list(self.rows("M15"))
        self.write(rows)
        first = load_replay(self.path, "M15").events
        rows[-1][4] -= 2
        rows[-1][5] += 20
        self.write(rows)
        second = load_replay(self.path, "M15").events
        self.assertEqual(first[:-1], second[:-1])
        self.assertNotEqual(first[-1], second[-1])
        self.assertEqual(set(asdict(first[-2])), {
            "timeframe", "source_row", "raw_server_clock_label", "raw_label_delta",
            "gap_before", "open",
        })
        self.assertIsInstance(first[-2], OpenEvent)
        self.assertIsInstance(first[-1], ClosedEvent)
        self.assertNotIsInstance(first[-1], OpenEvent)

    def test_gap_and_terminal_event(self):
        for timeframe, interval in INTERVALS.items():
            with self.subTest(timeframe=timeframe):
                rows = list(self.rows(timeframe, 211))
                self.write(rows)
                replay = load_replay(self.path, timeframe)
                self.assertEqual(len(replay.events), 2 * len(rows))
                self.assertEqual([event.raw_server_clock_label for event in replay.events[::2]],
                                 [row[0] for row in rows])
                terminal_open, terminal_close = replay.events[-2:]
                self.assertTrue(terminal_open.gap_before)
                self.assertTrue(terminal_close.gap_before)
                self.assertEqual(terminal_open.raw_label_delta, 4 * interval)
                self.assertIsInstance(terminal_close, ClosedEvent)
                audit = json.loads(render_audit(replay))
                self.assertEqual(audit["counts"]["raw_label_gaps"], 1)
                self.assertFalse(audit["final_closed_row_has_successor_open"])
                self.assertEqual(audit["gap_open_events"][0]["source_row"], 211)

    def test_malformed_values_and_order(self):
        for column, value in ((0, 10000), (0, 9999), (0, 10901), (0, 0), (0, 10000.5),
                              (1, "nan"), (2, "inf"), (3, 0), (4, 200), (4, ""),
                              (5, "-1"), (6, "0.5"), (7, "bad")):
            with self.subTest(column=column, value=value):
                rows = list(self.rows("M15", 2))
                rows[1][column] = value
                self.write(rows)
                with self.assertRaisesRegex(ValueError, "CSV line 3"):
                    load_replay(self.path, "M15")

    def test_malformed_shapes(self):
        row = next(self.rows("M15"))
        for rows, fields in (([row], FIELDS[:-1]), ([row[:-1]], FIELDS),
                             ([row + [0]], FIELDS), ([], FIELDS)):
            with self.subTest(rows=rows, fields=fields):
                self.write(rows, fields)
                with self.assertRaises(ValueError):
                    load_replay(self.path, "M15")
        self.path.write_bytes((",".join(FIELDS) + '\n"broken').encode())
        with self.assertRaises(ValueError):
            load_replay(self.path, "M15")

    def test_provenance_and_expected_count(self):
        self.write(self.rows("M15", 2))
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertFalse(load_replay(self.path, "M15").source_hash_verified)
        replay = load_replay(self.path, "M15", expected_sha256=digest, expected_rows=2)
        self.assertTrue(replay.source_hash_verified)
        self.assertEqual(replay.source_sha256, digest)
        with self.assertRaisesRegex(ValueError, "candle count"):
            load_replay(self.path, "M15", expected_rows=3)
        with self.assertRaisesRegex(ValueError, "unsupported timeframe"):
            load_replay(self.path, "M5")
        self.write(self.rows("M15", 3))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            load_replay(self.path, "M15", expected_sha256=digest)

    def test_deterministic_one_candle_audit(self):
        self.write(self.rows("H1", 1))
        first = load_replay(self.path, "H1")
        second = load_replay(self.path, "H1")
        self.assertEqual(first, second)
        self.assertEqual(render_audit(first), render_audit(second))
        audit = json.loads(render_audit(first))
        self.assertEqual([event["event"] for event in audit["sample_events"]], ["open", "closed"])
        self.assertIsNone(audit["sample_events"][1]["indicators"]["ema_9"])
        self.assertEqual(audit["sample_events"][1]["signal"]["reasons"], ["WARMUP"])
        self.assertFalse(audit["final_closed_row_has_successor_open"])
