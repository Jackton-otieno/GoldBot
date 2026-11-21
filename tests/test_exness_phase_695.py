import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from goldbot.core.exness_demo import DemoProfile, KE_COMPANY, VerificationError
from tools import collect_exness_phase_695 as phase


def clock_unavailable():
    return {"error": "synthetic_no_external_clock"}


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60

    def __init__(self, pin):
        self.pin = pin
        self.calls = 0
        self.attaches = 0
        self.shutdowns = 0
        self.fail_poll = 0
        self.switch_on_retry = False
        self.switch_during_quote = False
        self.switched = False

    def initialize(self, path, *, timeout):
        assert path == str(self.pin.terminal) and timeout == 5000
        self.attaches += 1
        self.switched |= self.switch_on_retry and self.attaches > 1
        return True

    def shutdown(self):
        self.shutdowns += 1

    def terminal_info(self):
        return SimpleNamespace(connected=True, path=str(self.pin.terminal.parent),
                               trade_allowed=False, build=1)

    def account_info(self):
        login = self.pin.login + 10000 if self.switched else self.pin.login
        return SimpleNamespace(login=login, currency="USD", trade_mode=0,
                               company=KE_COMPANY, server=self.pin.server)

    def symbol_info(self, name):
        return SimpleNamespace(name=name, custom=False)

    def last_error(self):
        return -10000, "synthetic"

    def symbol_info_tick(self, name):
        assert name == "XAUUSD"
        self.calls += 1
        if self.calls == self.fail_poll:
            return None
        label = 3599 if self.calls == 1 else 5400
        self.switched |= self.switch_during_quote
        bid = 2601.0 if self.calls == 3 else 2600.0
        return SimpleNamespace(time=label, time_msc=label * 1000, bid=bid, ask=2602.0,
                               last=0.0, volume=0, flags=6, volume_real=0.0)

    def copy_rates_from_pos(self, name, frame, position, count):
        assert name == "XAUUSD" and position == 1 and count == 2
        if frame == self.TIMEFRAME_H1:
            return []
        labels = [1800] if self.calls == 1 else [2700, 4500]
        return [dict(time=label, open=2600, high=2602, low=2599,
                     close=2601 if self.calls == 3 else 2600,
                     tick_volume=7, spread=12, real_volume=0) for label in labels]


class CollectorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        self.path = path / "synthetic.sqlite3"
        terminal = path / "terminal64.exe"
        terminal.touch()
        self.pin = DemoProfile(terminal, phase.SERVER, 19498)
        self.api = FakeMT5(self.pin)

    def run_collection(self):
        with closing(sqlite3.connect(self.path)) as db:
            reader = phase.Reader(self.api, self.pin, lambda: [str(self.pin.terminal)])
            status = phase.collect(phase.Journal(db), reader, clock_unavailable, lambda _: None)
            journal = phase.Journal(db)
            events = [json.loads(body) for body, in db.execute("SELECT body FROM events ORDER BY seq")]
            return status, journal.manifest(), events

    def test_snapshots_preserve_distinct_same_label_and_bar_revisions(self):
        status, manifest, events = self.run_collection()
        self.assertEqual(status, "COMPLETE_BOUNDED_DIAGNOSTIC")
        self.assertFalse(manifest["scope"]["holdout_eligible"])
        quotes = [event["data"] for event in events if event["kind"] == "quote_snapshot"]
        self.assertEqual(len(quotes), phase.POLLS)
        second, third, fourth = [quote["objects"][0] for quote in quotes[1:4]]
        self.assertNotEqual(second["sha256"], third["sha256"])
        self.assertEqual(second["sha256"], fourth["sha256"])
        self.assertNotIn("raw", fourth)
        self.assertLessEqual(quotes[1]["before"]["monotonic_after_ns"],
                             quotes[1]["after"]["monotonic_before_ns"])
        bars = [event["data"] for event in events if
                event["kind"] == "bars" and event["data"]["frame"] == "M15"]
        self.assertEqual(bars[0]["objects"], [])
        self.assertEqual(bars[1]["raw_missing_open_ranges_half_open"], [[3600, 4500]])
        objects = [bar["objects"][0] for bar in bars[1:4]]
        self.assertNotEqual(objects[0]["sha256"], objects[1]["sha256"])
        self.assertEqual(objects[0]["sha256"], objects[2]["sha256"])
        self.assertEqual(events[-1]["data"]["host_clock_assessment"]["status"],
                         "INDEPENDENT_TIME_UNAVAILABLE")

    def test_transient_failure_reconnects_without_backfilling(self):
        self.api.fail_poll = 2
        status, _, events = self.run_collection()
        self.assertEqual(status, "COMPLETE_BOUNDED_DIAGNOSTIC")
        self.assertEqual(self.api.attaches, 2)
        self.assertEqual(self.api.shutdowns, 2)
        self.assertTrue(any(event["kind"] == "coverage_gap" for event in events))
        self.assertFalse(any(event["data"]["objects"] for event in events if event["kind"] == "bars"))

    def test_wrong_account_on_reconnect_and_mid_request_stop(self):
        self.api.fail_poll = 2
        self.api.switch_on_retry = True
        status, _, events = self.run_collection()
        self.assertEqual(status, "FAILED_CLOSED")
        self.assertEqual(self.api.calls, 2)
        self.assertEqual(sum(event["kind"] == "quote_snapshot" for event in events), 1)
        self.api = FakeMT5(self.pin)
        self.api.switch_during_quote = True
        start = len(events)
        status, _, events = self.run_collection()
        self.assertEqual(status, "FAILED_CLOSED")
        self.assertEqual(self.api.attaches, 1)
        self.assertFalse(any(event["kind"] == "quote_snapshot" for event in events[start:]))

    def test_rollback_recovery_and_manifest_integrity(self):
        with closing(sqlite3.connect(self.path)) as db:
            journal = phase.Journal(db)
            journal.append("stopped", "start", {})
            db.execute("INSERT INTO events VALUES (2, 'uncommitted', 'uncommitted')")
        status, manifest, events = self.run_collection()
        self.assertEqual(status, "COMPLETE_BOUNDED_DIAGNOSTIC")
        self.assertEqual(events[1]["kind"], "interrupted")
        self.assertFalse(manifest["interrupted_run_pending"])
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE events SET sha256 = 'corrupt' WHERE seq = 2")
            with self.assertRaises(VerificationError):
                phase.Journal(db, read_only=True)

    def test_exclusive_writer_and_unclosed_bar_rejected(self):
        with phase.exclusive(self.path), self.assertRaises(OSError):
            with phase.exclusive(self.path):
                self.fail("Duplicate writer acquired lock")
        row = self.api.copy_rates_from_pos("XAUUSD", 15, 1, 2)
        with self.assertRaises(VerificationError):
            phase.closed_bars(row, 900, 2699)
