"""Phase 6.9.6 offline tests. Temporary mutations and market fixtures are synthetic."""

import shutil
import sqlite3
import unittest
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from goldbot.reporting.readiness_696 import (
    CHAIN, CONNECT, DAY, PINS, PRECISION, Scope, Status, assess,
)
from goldbot.core.exness_demo import DemoProfile
from tests.test_exness_phase_695 import FakeMT5, clock_unavailable
from tools import collect_exness_phase_695 as collector
from tools.assess_readiness_696 import generate
from tools.collect_exness_phase_696 import PHASE_SCOPE
from tools.summarize_exness_phase_696 import summarize

ROOT = Path(__file__).resolve().parents[1]


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for source in PINS:
            target = self.root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target)

    def evaluate(self, as_of=DAY):
        assessment = assess(self.root, as_of)
        self.assertEqual(assessment.decision, "NO-GO")
        self.assertFalse(assessment.execution_authorized)
        self.assertFalse(assessment.historical_execution_authorized)
        self.assertFalse(assessment.prospective_authorized)
        return {finding.requirement.key: finding for finding in assessment.findings}

    def test_pinned_baseline_and_broker_isolation(self):
        entries = self.evaluate()
        self.assertIs(entries["exness_identity"].status, Status.OBSERVED)
        self.assertIs(entries["exness_monetary_precision"].status, Status.CONFLICTING)
        self.assertIs(entries["exness_monetary_precision"].requirement.scope, Scope.EXNESS)
        self.assertIs(entries["metaquotes_contract"].status, Status.REJECTED)
        self.assertIs(entries["metaquotes_contract"].requirement.scope, Scope.METAQUOTES)
        (self.root / PRECISION).unlink()
        entries = self.evaluate()
        self.assertIs(entries["exness_monetary_precision"].status, Status.MISSING)
        self.assertIn(Status.CONFLICTING, entries["exness_monetary_precision"].issues)
        self.assertIs(entries["metaquotes_contract"].status, Status.REJECTED)

    def test_unseen_input_and_forged_approval_cannot_bypass(self):
        path = self.root / CONNECT
        path.write_text('{"authorization": true, "prospective_authorized": true}', encoding="utf-8")
        (self.root / "approval.json").write_text('{"approved": true}', encoding="utf-8")
        entries = self.evaluate()
        self.assertIs(entries["exness_identity"].status, Status.INVALID)
        self.assertIs(entries["prospective_protocol"].status, Status.MISSING)
        assessment = assess(self.root, DAY)
        with self.assertRaises(AttributeError):
            assessment.execution_authorized = True

    def test_missing_stale_and_future_identity(self):
        self.assertIs(self.evaluate(DAY + timedelta(days=1))["exness_identity"].status, Status.STALE)
        self.assertIs(self.evaluate(DAY - timedelta(days=1))["exness_identity"].status, Status.INVALID)
        (self.root / CONNECT).unlink()
        self.assertIs(self.evaluate()["exness_identity"].status, Status.MISSING)

    def test_archived_smoke_and_report_are_offline_and_deterministic(self):
        with patch("socket.socket", side_effect=AssertionError("network")), patch.dict(
            "sys.modules", {"MetaTrader5": None}
        ):
            output = generate(self.root, DAY)
            first = {path.name: path.read_bytes() for path in output.iterdir()}
            self.assertEqual(len(first), 3)
            self.assertIn(b"RECONCILED", first["assessment.json"])
            self.assertIn(b"zero admitted M15/H1", first["readiness.md"])
            self.assertEqual(generate(self.root, DAY), output)
            self.assertEqual(first, {path.name: path.read_bytes() for path in output.iterdir()})
        (self.root / CHAIN).unlink()
        generate(self.root, DAY)
        self.assertIn(b"SOURCE_INTEGRITY_FAILURE", (output / "assessment.json").read_bytes())

    def test_synthetic_boundary_is_diagnostic_and_never_prospective(self):
        terminal = self.root / "terminal64.exe"
        terminal.touch()
        profile = DemoProfile(terminal, collector.SERVER, 19498)
        api = FakeMT5(profile)
        reader = collector.Reader(api, profile, lambda: [str(terminal)])
        output = self.root / "reports/phase_6_9_6"
        output.mkdir()
        path = output / "boundary.sqlite3"
        delays = []
        with closing(sqlite3.connect(path)) as db:
            collector.collect(collector.Journal(db, scope=PHASE_SCOPE), reader,
                              clock_unavailable, delays.append, poll_interval=6)
        self.assertEqual(delays, [6] * 7)
        report = summarize(path, PHASE_SCOPE)
        self.assertEqual(report["bars"]["M15"]["raw_boundaries"], [3600, 5400])
        self.assertEqual(report["bars"]["H1"]["raw_boundaries"], [])
        self.assertFalse(report["manifest"]["scope"]["holdout_eligible"])
        self.assertTrue(report["manifest"]["scope"]["exposed"])
        self.assertIs(self.evaluate()["prospective_protocol"].status, Status.MISSING)
        self.assertIs(self.evaluate()["archive_coverage_and_quote_basis"].status, Status.UNRESOLVED)
        with self.assertRaises(collector.VerificationError):
            summarize(path, collector.SCOPE)
