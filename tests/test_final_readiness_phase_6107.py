from datetime import date
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tools import final_readiness_6107 as phase


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 21)


class FinalReadinessTests(TestCase):
    def test_snapshot_preserves_eight_cohorts_and_unapproved_window(self):
        with patch("socket.socket", side_effect=AssertionError("network")):
            report = phase.build(ROOT, AS_OF)["final-readiness.json"]
        self.assertEqual(len(report["cohorts"]), 8)
        self.assertEqual(len({(row["strategy"], row["timeframe"]) for row in report["cohorts"]}), 8)
        self.assertEqual(report["comparison"]["runs"], 32)
        self.assertFalse(report["observation_period"]["approved"])
        self.assertEqual(report["observation_period"]["calendar_days"], 365)
        self.assertFalse(report["external_registration_verified"])
        self.assertEqual(report["overall"], "NO-GO")
        for key in ("prospective_data_intake", "automated_demo_trading", "live_trading"):
            self.assertFalse(report["decisions"][key]["authorized"])

    def test_draft_digest_drift_stops_assessment(self):
        original = phase.protocol.file_hash

        def altered(path):
            return "0" * 64 if path.name == "candidate-registry.json" else original(path)

        with patch.object(phase.protocol, "file_hash", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "artifact differs"):
                phase.reviewed_draft(ROOT)

    def test_dependency_actions_cover_every_inherited_blocker(self):
        reports = phase.build(ROOT, AS_OF)
        entries = reports["external-dependencies.json"]["dependencies"]
        ids = {entry["id"] for entry in entries}
        self.assertEqual(ids, phase.RESOLUTION.keys() | {"phase7_operational_controls", "live_authorization"})
        for entry in entries:
            self.assertTrue(entry["action"] and entry["evidence_required"] and entry["acceptance_criteria"])
        with self.assertRaisesRegex(ValueError, "blocker set changed"):
            phase.external_dependencies([])

    def test_runtime_mismatch_blocks_engineering_without_changing_authorization(self):
        with patch.object(phase.metadata, "version", return_value="wrong-version"):
            result = phase.build(ROOT, AS_OF)["final-readiness.json"]
        self.assertEqual(result["decisions"]["offline_engineering"]["status"], "BLOCKED")
        self.assertEqual(result["overall"], "NO-GO")
