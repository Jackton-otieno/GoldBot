from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from goldbot.core.exness_demo import VerificationError
from tools.verify_exness_time_phase_61052 import SERVER, capture, finish, head_evidence


def bar(label):
    return dict(time=label, open=2, high=3, low=1, close=2)


class TimePhaseTests(TestCase):
    def test_closed_and_current_roles_are_distinct_with_a_gap(self):
        result = head_evidence([bar(60), bar(180)], 60, 184, 192)
        self.assertTrue(result["closed_by_first_quote"])
        self.assertTrue(result["current_contains_both_quotes"])
        self.assertEqual(result["closed_nominal_raw"], 120)
        self.assertEqual(result["raw_label_gap_seconds"], 60)

    def test_boundary_straddle_and_invalid_labels_do_not_confirm_current_bar(self):
        self.assertFalse(head_evidence([bar(60), bar(120)], 60, 179, 180)
                         ["current_contains_both_quotes"])
        self.assertEqual(head_evidence([bar(60), bar(121)], 60, 121, 122)["status"],
                         "INVALID_RAW_BARS")
        self.assertEqual(head_evidence([bar(60)], 60, 121, 122)["status"], "INSUFFICIENT_BARS")

    def test_missing_external_bracket_never_assigns_quote_age(self):
        sample = dict(tick=dict(raw_s=60, raw_ms=60000, bid=1, ask=2),
                      connected_before=True, connected_after=True)
        report = finish({"samples": [sample]}, {}, {})
        self.assertEqual(report["clock"]["status"], "INDEPENDENT_TIME_UNAVAILABLE")
        self.assertNotIn("age_s_if_raw_utc", sample)

    def test_installation_gate_runs_before_attach(self):
        reader = Mock()
        profile = SimpleNamespace(server=SERVER, login=19498, terminal=Path("other/terminal64.exe"))
        with self.assertRaises(VerificationError):
            capture(reader, profile, {})
        self.assertEqual(reader.mock_calls, [])
