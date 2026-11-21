import io
import json
import os
import struct
import unittest
from unittest.mock import patch

from goldbot.core.exness_demo import VerificationError
from tools import verify_exness_phase_6941 as phase


class Phase6941Tests(unittest.TestCase):
    def test_profile_requires_local_input_even_when_legacy_environment_is_set(self):
        with patch.dict(os.environ, {"GOLDBOT_DEMO_PROFILE": "exness-ke-mt5-pro-demo"}):
            with self.assertRaises(VerificationError):
                phase.local_profile(io.StringIO(""))

    @unittest.skipUnless(os.name == "nt", "Windows terminal paths")
    def test_profile_requires_pinned_server_and_suffix(self):
        profile = {
            "terminal": "C:/Test/terminal64.exe",
            "server": phase.SERVER,
            "login": "1239498",
        }
        self.assertEqual(phase.local_profile(io.StringIO(json.dumps(profile))).login, 1239498)
        for field, value in (("server", "ExnessKE-MT5Trial1"), ("login", "1230000")):
            with self.subTest(field=field), self.assertRaises(VerificationError):
                phase.local_profile(io.StringIO(json.dumps({**profile, field: value})))

    def test_ntp_bracket_checks_origin_and_server_health(self):
        before = {"wall_utc": "2026-11-18T12:00:00+00:00", "monotonic": 1}
        after = {"wall_utc": "2026-11-18T12:00:00.080000+00:00", "monotonic": 1.08}
        stamp = phase.clock.wall(before).timestamp() + phase.NTP_EPOCH
        sent, receive, transmit = [
            struct.pack("!Q", int((stamp + offset) * phase.NTP_SCALE))
            for offset in (0, 0.025, 0.030)
        ]
        reply = b"\x24\x02" + bytes(22) + sent + receive + transmit
        bounds, delay = phase.ntp_bounds(reply, sent, before, after)
        self.assertAlmostEqual(delay, 0.075, places=5)
        self.assertLess(bounds[0], 0)
        self.assertGreater(bounds[1], 0)
        with self.assertRaises(ValueError):
            phase.ntp_bounds(reply, bytes(8), before, after)
        with self.assertRaises(ValueError):
            phase.ntp_bounds(b"\xe4" + reply[1:], sent, before, after)
