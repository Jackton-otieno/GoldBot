"""Regression tests for read-only clock and raw timestamp evidence."""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from goldbot.core import connection
from goldbot.core.time_manager import OffsetWindow, TimeManager
from tools import diagnose_time, verify_dst


UTC = timezone.utc
AT = datetime(2026, 11, 18, tzinfo=UTC)
RAW = int(AT.timestamp())
SERVER = "MetaQuotes-Demo"


def mark(seconds, wall_shift=0):
    return {"monotonic": seconds, "wall_utc": (
        AT + timedelta(seconds=seconds + wall_shift)).isoformat()}


def sample(raw_ms, bid=100, up=True):
    return {"connected_before": up, "connected_after": up,
            "tick": {"raw_s": raw_ms // 1000, "raw_ms": raw_ms,
                     "bid": bid, "ask": 101, "flags": 6}}


class EvidenceTests(unittest.TestCase):
    def test_static_quote_remains_static_at_apparently_current_raw_time(self):
        ticks = [sample(RAW * 1000)] * 16
        self.assertEqual(diagnose_time.quote_state(ticks), "STATIC_TIMESTAMP")
        self.assertEqual(diagnose_time.quote_state([ticks[0], sample(RAW * 1000, up=False)]),
                         "DISCONNECTED_OR_UNAVAILABLE")

    def test_changes_are_not_proof_of_freshness(self):
        one, two = sample(RAW * 1000), sample(RAW * 1000 + 1000, bid=99)
        self.assertEqual(diagnose_time.quote_state([one, two]),
                         "TIMESTAMP_AND_PRICES_ADVANCED_FRESHNESS_UNVERIFIED")
        self.assertEqual(diagnose_time.quote_state([two, one]), "RAW_TIME_REGRESSED")

    def test_clock_bracket_includes_transport_and_source_allowance(self):
        line = "61362 26-11-18 00:00:00 00 0 0 50.0 UTC(NIST) *"
        mjd = (AT - datetime(1858, 11, 17, tzinfo=UTC)).days
        line = f"{mjd} " + line.split(" ", 1)[1]
        lower, upper = diagnose_time.clock_bounds(line, mark(-0.25), mark(0.25))
        self.assertAlmostEqual(lower, -1.4)
        self.assertAlmostEqual(upper, 1.3)
        with self.assertRaises(ValueError):
            diagnose_time.clock_bounds(line.replace("0 0 50", "0 1 50"),
                                       mark(-0.25), mark(0.25))

    def test_uncertain_disagreeing_and_stepped_clocks_fail_closed(self):
        first = dict(before=mark(0), after=mark(1), correction_bounds_s=[-1, 1])
        last = dict(before=mark(3), after=mark(4), correction_bounds_s=[-1, 1])
        self.assertEqual(diagnose_time.assess_clock(first, last, [])["status"],
                         "UTC_WITHIN_TOLERANCE")
        for change, expected in (
            ({"correction_bounds_s": [-3, 1]}, "CLOCK_ERROR_OR_UNCERTAINTY_TOO_LARGE"),
            ({"correction_bounds_s": [2, 3]}, "INDEPENDENT_TIME_DISAGREES"),
            ({"correction_bounds_s": None}, "INDEPENDENT_TIME_UNAVAILABLE"),
            ({"after": mark(4, 1)}, "WALL_CLOCK_DISCONTINUITY"),
        ):
            self.assertEqual(diagnose_time.assess_clock(first, dict(last, **change), [])
                             ["status"], expected)

    def test_history_comparison_uses_raw_coordinates_and_capped_calls(self):
        tick = sample(RAW * 1000)["tick"]
        row = dict(time=RAW, time_msc=RAW * 1000, bid=100, ask=101, flags=6)
        with patch.object(diagnose_time, "mt5") as api:
            api.terminal_info.return_value.connected = True
            api.copy_ticks_from.return_value = [dict(row, ask=102), row]
            api.copy_rates_from_pos.return_value = [{"time": RAW - 60}, {"time": RAW}]
            report = diagnose_time.history_evidence(tick)
            api.copy_ticks_from.assert_called_once_with("XAUUSD", RAW, 128, api.COPY_TICKS_ALL)
            api.copy_rates_from_pos.assert_called_once_with("XAUUSD", api.TIMEFRAME_M1, 0, 16)
            self.assertEqual(report["exact_tick_matches"], [tick])
            self.assertEqual(report["matching_raw_minute_bar_opens"], [RAW])

    def test_dst_proxy_alone_has_no_authority_and_one_state_cannot_fit(self):
        records = [dict(status="PROXY_SAMPLE", us_dst_hours=1, eu_dst_hours=0,
                        raw_minus_cme_proxy_s=10800)]
        self.assertFalse(verify_dst.compare(records, "us")["proxy_pattern_matches"])
        records.append(dict(status="PROXY_SAMPLE", us_dst_hours=0, eu_dst_hours=0,
                            raw_minus_cme_proxy_s=7200))
        self.assertTrue(verify_dst.compare(records, "us")["proxy_pattern_matches"])
        self.assertFalse(verify_dst.compare(records, "eu")["proxy_pattern_matches"])
        self.assertEqual(list(verify_dst.weeks(2026, datetime(2026, 1, 1, tzinfo=UTC))), [])

    def test_bounded_window_is_server_specific_and_stale_age_rejected(self):
        window = OffsetWindow(SERVER, 0, AT - timedelta(hours=1),
                              AT + timedelta(seconds=1), "Synthetic fixture")
        with self.assertRaisesRegex(ValueError, "STALE"):
            TimeManager(SERVER, [window]).require_fresh(RAW - 61, None, AT)
        with self.assertRaisesRegex(ValueError, "No current"):
            TimeManager(SERVER, [window]).require_fresh(RAW, None, window.valid_until)
        with self.assertRaisesRegex(ValueError, "No current"):
            TimeManager("Unknown-Demo", [window]).require_fresh(RAW, None, AT)

    def test_quote_cli_checks_demo_and_expected_server_before_market_reads(self):
        for mode, server in ((2, SERVER), (0, "Unexpected-Demo")):
            with self.subTest(mode=mode, server=server), patch.object(connection, "mt5") as api,                     patch.object(diagnose_time, "mt5", api),                     patch.object(sys, "argv", ["diagnose_time"]),                     patch.object(diagnose_time, "clock_probe", return_value={}),                     patch("builtins.print") as output:
                api.ACCOUNT_TRADE_MODE_DEMO = 0
                api.terminal_info.return_value.connected = True
                api.account_info.return_value = SimpleNamespace(trade_mode=mode, server=server)
                self.assertEqual(diagnose_time.main(), 1)
                report = json.loads(output.call_args.args[0])
                self.assertEqual(report["status"], "REJECTED")
                self.assertEqual(report["samples"], [])
                self.assertNotIn("Unexpected-Demo", output.call_args.args[0])
                api.symbol_info_tick.assert_not_called()
                api.copy_ticks_from.assert_not_called()
                api.order_send.assert_not_called()
                api.symbol_select.assert_not_called()
                api.shutdown.assert_called_once()
