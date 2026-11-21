from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from goldbot.backtesting.prospective_validation import Intake, REQUIRED_EVIDENCE, Window
from goldbot.reporting import readiness_61055 as phase


ROOT = Path(__file__).resolve().parents[1]


class ConsolidatedReadinessTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in phase.PINS.keys() | phase.legacy.PINS.keys():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def evaluate(self):
        reports = phase.build(self.root, phase.REVIEWED_ON)
        return (reports["readiness.json"],
                {item["id"]: item for item in reports["blocker-register.json"]["blockers"]})

    def test_baseline_preserves_distinct_gates_without_network(self):
        with patch("socket.socket", side_effect=AssertionError("network")):
            assessment, blockers = self.evaluate()
        decisions = assessment["assessments"]
        self.assertEqual(len(decisions), 6)
        self.assertEqual(decisions["offline_engineering_completeness"]["status"], "PASS")
        self.assertEqual(decisions[phase.RESEARCH]["scoped_legacy_ohlc"]["status"], "PASS")
        self.assertEqual(decisions[phase.RESEARCH]["status"], "BLOCKED")
        self.assertEqual(decisions[phase.PREP]["status"], "BLOCKED")
        self.assertTrue(decisions[phase.PREP]["draft_available"])
        for name in phase.EXECUTION:
            self.assertFalse(decisions[name]["authorized"])
        self.assertEqual(assessment["overall"], "NO-GO")
        self.assertEqual(blockers["monetary_precision_and_booked_pnl"]["verification_status"],
                         phase.STATUS.CONFLICTING)

    def test_missing_original_blocks_engineering_and_scoped_research(self):
        (self.root / phase.CSV[0]).unlink()
        decisions = self.evaluate()[0]["assessments"]
        self.assertEqual(decisions["offline_engineering_completeness"]["status"], "BLOCKED")
        self.assertEqual(decisions[phase.RESEARCH]["scoped_legacy_ohlc"]["status"], "BLOCKED")

    def test_stale_and_future_clock_evidence_does_not_authorize(self):
        assessment, blockers = self.evaluate()
        self.assertEqual(assessment["inherited_findings"]["exness_identity"], phase.STATUS.STALE)
        self.assertIn(phase.STATUS.STALE, blockers["broker_identity_and_product"]["unresolved_conditions"])
        early = phase.build(self.root, phase.REVIEWED_ON - timedelta(days=1))["readiness.json"]
        self.assertEqual(early["assessments"]["offline_engineering_completeness"]["status"], "BLOCKED")

    def test_changed_policy_and_unresolved_precision_fail_closed(self):
        (self.root / phase.SESSIONS).write_text('{"accepted_quote_intervals":[true]}', encoding="utf-8")
        (self.root / phase.LOSS).unlink()
        decision, blockers = self.evaluate()
        self.assertEqual(blockers["quote_trade_sessions_and_exceptions"]["verification_status"],
                         phase.STATUS.INVALID)
        self.assertEqual(blockers["monetary_precision_and_booked_pnl"]["verification_status"],
                         phase.STATUS.MISSING)
        self.assertFalse(decision["assessments"][phase.DEMO]["authorized"])

    def test_hash_matching_but_contradictory_gate_fails_engineering(self):
        raw = (self.root / phase.GATE).read_bytes()
        contradictory = raw.replace(b'"execution_authorized": false', b'"execution_authorized": true', 1)
        self.assertNotEqual(raw, contradictory)
        (self.root / phase.GATE).write_bytes(contradictory)
        with patch.dict(phase.PINS, {phase.GATE: sha256(contradictory).hexdigest()}):
            decision = self.evaluate()[0]["assessments"]
        self.assertTrue(decision["offline_engineering_completeness"]["archived_gate_conflict"])
        self.assertEqual(decision["offline_engineering_completeness"]["status"], "BLOCKED")
        self.assertFalse(decision[phase.LIVE]["authorized"])

    def test_incomplete_history_blocks_new_data_and_intake(self):
        decision, blockers = self.evaluate()
        history = blockers["historical_provenance_and_coverage"]
        self.assertTrue(history["blocks"][phase.RESEARCH])
        self.assertTrue(history["blocks"][phase.ADMIT])
        self.assertEqual(history["verification_status"], phase.STATUS.UNRESOLVED)
        self.assertEqual(decision["assessments"][phase.ADMIT]["technical_intake"]["state"], "blocked")

    def test_existing_intake_nonoverlap_and_attestation_are_required(self):
        start = datetime(2027, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        window = Window(start, end)
        prior = Window(start - timedelta(days=2), start - timedelta(days=1))
        digest = "a" * 64
        freeze = {key: digest for key in ("strategy", "evaluator", "environment",
                                         "execution-rules", "reference-inventory", "source-scope")}
        payload = b"synthetic"
        intake = Intake(window, {"archive": prior}, sha256(payload).hexdigest(),
                        {key: digest for key in REQUIRED_EVIDENCE})

        def verify(domain, digest, receipt):
            self.assertEqual(receipt, b"synthetic-trust-verifier-fixture")
            return prior.end if domain == "registration" else end

        options = dict(window=window, freeze=freeze, current_freeze=freeze,
                       prior_sources={"archive": digest},
                       registration_receipt=b"synthetic-trust-verifier-fixture",
                       intake_receipt=b"synthetic-trust-verifier-fixture",
                       intake=intake, sealed_payload=payload, now=end, verify=verify)
        self.assertEqual(phase.review_intake(options)["state"], "eligible")
        self.assertEqual(phase.review_intake(dict(options, intake=None))["state"], "inconclusive")
        overlap = replace(intake, prior_utc={"archive": window})
        self.assertEqual(phase.review_intake(dict(options, intake=overlap))["state"], "fail")
        self.assertEqual(phase.review_intake(dict(options, registration_receipt=None))["state"], "blocked")
        decisions = phase.build(self.root, phase.REVIEWED_ON, submission=options)["readiness.json"]["assessments"]
        self.assertFalse(decisions[phase.ADMIT]["authorized"])
