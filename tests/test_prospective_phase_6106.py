from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from goldbot.backtesting.prospective_validation import Window
from goldbot.backtesting.strategy_validation import FrozenManifest, sha256
from goldbot.reporting import prospective_6106 as phase


ROOT = Path(__file__).resolve().parents[1]


class ProspectiveProtocolTests(TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        start = datetime(2027, 2, 1, tzinfo=timezone.utc)
        day = timedelta(days=1)
        self.window = Window(start, start + 2 * day)
        window_patch = patch.object(phase, "PROPOSED_WINDOW", self.window)
        window_patch.start()
        self.addCleanup(window_patch.stop)
        self.components = {name: f"fixture:{name}".encode() for name in phase.COMPONENTS}
        self.prior = {group: Window(start - 3 * day, start - day) for group in phase.EXPOSURES}
        self.committed = phase.prepare_registration(ROOT, self.components, self.prior, {})
        self.evidence = {name: f"fixture:{name}".encode() for name in phase.INTAKE_EVIDENCE}
        chunks = []
        self.proofs = {
            "approval": {b"approval": (self.committed.sha256, "approver", start - 2 * day)},
            "registration": {b"registration": (self.committed.sha256, "registrar", start - day)},
            "custody": {},
        }
        for index in range(2):
            data = f"tick-fixture-{index}".encode()
            path = self.scratch / f"chunk-{index}"
            path.write_bytes(data)
            proof = bytes([index])
            chunk = phase.Chunk(Window(start + index * day, start + (index + 1) * day),
                                path, sha256(data), sha256(self.components["source_scope"]),
                                False, "fixed-window-capture", proof)
            self.proofs["custody"][proof] = (chunk.manifest().sha256, "custodian", chunk.interval.end)
            chunks.append(chunk)
        self.chunks = chunks
        manifest = FrozenManifest.create({
            "registration_sha256": self.committed.sha256,
            "chunk_manifest_sha256": [chunk.manifest().sha256 for chunk in chunks],
            "evidence_sha256": {name: sha256(data) for name, data in self.evidence.items()},
        })
        self.proofs["intake"] = {b"intake": (manifest.sha256, "reviewer", self.window.end)}

    def verify(self, role, digest, proof):
        expected, signer, at = self.proofs[role].get(proof, ("", "", None))
        return phase.Attestation(signer, at) if digest == expected else None

    def run_gate(self, **changes):
        options = dict(committed=self.committed, components=self.components,
                       exposure_windows=self.prior, additional_sources={}, approval_proof=b"approval",
                       registration_proof=b"registration", chunks=self.chunks, evidence=self.evidence,
                       intake_proof=b"intake", now=self.window.end, verify=self.verify)
        return phase.review_intake(ROOT, **(options | changes))

    def test_full_synthetic_lineage_eligible_only_for_research_review(self):
        with patch("socket.socket", side_effect=AssertionError("network")):
            result = self.run_gate()
        self.assertEqual(result["status"], "ELIGIBLE_FOR_RESEARCH_REVIEW")
        self.assertNotIn("authorized", result)
        status = phase.readiness(ROOT, self.window.start.date())
        self.assertEqual(status["overall"], "NO-GO")
        self.assertFalse(status["automated_demo_authorization"]["authorized"])
        self.assertFalse(status["live_trading_authorization"]["authorized"])
        self.assertFalse(status["prospective_data_intake_admission"]["authorized"])

    def test_missing_approval_and_registration_receipts_fail_closed(self):
        self.assertIn("Missing approval", self.run_gate(approval_proof=None)["reason"])
        self.assertIn("Missing registration", self.run_gate(registration_proof=b"")["reason"])
        registration = phase.review_registration(
            ROOT, committed=self.committed, components=self.components, exposure_windows=self.prior,
            additional_sources={}, approval_proof=b"approval", registration_proof=b"registration",
            now=self.window.start - timedelta(hours=1), verify=self.verify)
        self.assertEqual(registration["status"], "REGISTRATION_VERIFIED")

    def test_modified_strategy_bytes_block_registration(self):
        files = phase.candidate_registry(ROOT).envelope()["manifest"]["source_sha256"]
        for name in (*files, phase.BASELINE):
            target = self.scratch / name
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(ROOT / name, target)
        path = self.scratch / phase.ALTERNATIVES
        path.write_bytes(path.read_bytes() + b"\n# synthetic modification\n")
        with self.assertRaisesRegex(ValueError, "implementation bytes changed"):
            phase.candidate_registry(self.scratch)

    def test_conflicting_rules_and_shared_signers_are_blocked(self):
        changed = self.components | {"execution_cost_rules": b"conflicting"}
        self.assertIn("conflicts", self.run_gate(components=changed)["reason"])
        digest, _, at = self.proofs["registration"][b"registration"]
        self.proofs["registration"][b"registration"] = (digest, "approver", at)
        self.assertIn("Independent approval", self.run_gate()["reason"])

    def test_overlap_and_incomplete_prior_mapping_are_blocked(self):
        self.assertIn("overlaps", self.run_gate(
            exposure_windows=self.prior | {"legacy_M15": self.window})["reason"])
        self.assertIn("Complete", self.run_gate(exposure_windows={})["reason"])
        self.assertIn("overlapping", self.run_gate(chunks=[self.chunks[0]] * 2)["reason"])

    def test_retroselected_and_exposed_data_are_blocked(self):
        first, second = self.chunks
        for changed in (replace(first, previously_exposed=True),
                        replace(first, selection="best-historical-month"),
                        replace(first, sha256=phase.ORIGINAL_DIGESTS["M15"])):
            self.assertIn("Exposed", self.run_gate(chunks=[changed, second])["reason"])

    def test_invalid_source_and_unverifiable_bytes_are_blocked(self):
        first, second = self.chunks
        invalid = replace(first, source_scope_sha256="0" * 64)
        self.assertIn("unverified source", self.run_gate(chunks=[invalid, second])["reason"])
        self.assertIn("mandatory provenance", self.run_gate(evidence={})["reason"])
        first.path.write_bytes(b"tampered")
        self.assertIn("immutable manifest", self.run_gate()["reason"])

    def test_missing_custody_and_intake_provenance_are_blocked(self):
        first, second = self.chunks
        self.assertIn("Missing custody", self.run_gate(
            chunks=[replace(first, custody_proof=b""), second])["reason"])
        self.assertIn("Missing intake", self.run_gate(intake_proof=b"")["reason"])
        self.assertIn("Assessment time", self.run_gate(now=self.window.end.replace(tzinfo=None))["reason"])
