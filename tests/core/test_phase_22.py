import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from goldbot.core import connection
from tools import verify_dst
from goldbot.core.time_manager import OffsetWindow, TimeManager


UTC = timezone.utc
START = datetime(2026, 11, 17, 20, tzinfo=UTC)
END = START + timedelta(hours=1)
SERVER = "MetaQuotes-Demo"
FIXTURE = OffsetWindow(SERVER, 7200, START, END, "Synthetic bounded test fixture")


class TimeManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = TimeManager(SERVER, [FIXTURE])
        self.now = START + timedelta(minutes=5)
        self.raw = int(self.now.timestamp()) + 7200

    def test_round_trip_and_raw_retention(self):
        east = timezone(timedelta(hours=3))
        self.assertEqual(
            self.manager.request_bounds(self.now.astimezone(east), self.now),
            (self.raw, self.raw),
        )
        stamp = self.manager.decode(self.raw, self.raw * 1000 + 123)
        self.assertEqual(stamp.utc, self.now + timedelta(milliseconds=123))
        self.assertIs(stamp.utc.tzinfo, UTC)
        self.assertEqual((stamp.raw_seconds, stamp.raw_milliseconds),
                         (self.raw, self.raw * 1000 + 123))
        self.assertEqual(self.manager.decode(self.raw, 0).utc, self.now)
        self.assertEqual(self.manager.decode(None, self.raw * 1000).utc, self.now)

    def test_freshness_boundaries(self):
        for age in (0, 60):
            self.manager.require_fresh(self.raw - age, None, self.now)
        with self.assertRaisesRegex(ValueError, "STALE"):
            self.manager.require_fresh(self.raw - 61, (self.raw - 60) * 1000 - 1, self.now)
        with self.assertRaisesRegex(ValueError, "FUTURE"):
            self.manager.require_fresh(self.raw, self.raw * 1000 + 1, self.now)

    def test_missing_and_disagreeing_timestamps(self):
        with self.assertRaisesRegex(ValueError, "Missing"):
            self.manager.require_fresh(None, 0, self.now)
        with self.assertRaisesRegex(ValueError, "disagree"):
            self.manager.decode(self.raw + 1, self.raw * 1000)

    def test_unknown_server_and_expiry(self):
        with self.assertRaisesRegex(ValueError, "No current"):
            TimeManager("Other-Demo", [FIXTURE]).require_fresh(self.raw, None, self.now)
        end_raw = int(END.timestamp()) + 7200
        with self.assertRaisesRegex(ValueError, "No current"):
            self.manager.require_fresh(end_raw - 1, None, END)
        with self.assertRaisesRegex(ValueError, "no unique"):
            self.manager.decode(end_raw)
        with self.assertRaisesRegex(ValueError, "one verified"):
            self.manager.request_bounds(END - timedelta(seconds=1), END)

    def test_fall_back_ambiguity_and_spring_gap(self):
        before = OffsetWindow(SERVER, 10800, START - timedelta(hours=2), START, "Test")
        fall = TimeManager(SERVER, [before, FIXTURE])
        with self.assertRaisesRegex(ValueError, "no unique"):
            fall.decode(self.raw)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            fall.request_bounds(self.now, self.now)

        after = OffsetWindow(SERVER, 10800, END, END + timedelta(hours=2), "Test")
        spring = TimeManager(SERVER, [FIXTURE, after])
        with self.assertRaisesRegex(ValueError, "no unique"):
            spring.decode(int(END.timestamp()) + 7200)
        with self.assertRaisesRegex(ValueError, "one verified"):
            spring.request_bounds(END - timedelta(seconds=1), END)

    def test_invalid_configuration_and_naive_bounds(self):
        with self.assertRaisesRegex(ValueError, "evidence"):
            OffsetWindow(SERVER, 0, START, END, " ")
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            TimeManager(SERVER, [FIXTURE, FIXTURE])
        with self.assertRaisesRegex(ValueError, "aware"):
            self.manager.request_bounds(self.now.replace(tzinfo=None), self.now)


class DemoAccessTests(unittest.TestCase):
    def test_history_requires_demo_and_expected_server(self):
        for mode, server, should_read in ((2, SERVER, False), (0, "Other-Demo", False),
                                          (0, SERVER, True)):
            with self.subTest(mode=mode, server=server), patch.object(connection, "mt5") as api, \
                    patch.object(verify_dst, "mt5", api), patch.object(sys, "argv", ["verify_dst"]), \
                    patch("builtins.print"):
                api.ACCOUNT_TRADE_MODE_DEMO = 0
                api.terminal_info.return_value.connected = True
                api.account_info.return_value = SimpleNamespace(trade_mode=mode, server=server)
                api.copy_rates_range.return_value = []
                self.assertEqual(verify_dst.main(), 1)
                self.assertEqual(api.copy_rates_range.called, should_read)
                api.shutdown.assert_called_once()
                api.order_send.assert_not_called()
                api.symbol_select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
