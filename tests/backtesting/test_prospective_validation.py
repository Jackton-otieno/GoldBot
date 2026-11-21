from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from goldbot.backtesting.prospective_validation import (
    Intake, Ledger, REQUIRED_EVIDENCE, Window, evaluate, evaluation_manifest,
    registration_manifest, sha256,
)


class ProspectiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=365)
        self.window = Window(self.start, self.end)
        self.early = self.start - timedelta(days=1)
        self.payload = b"synthetic sealed fixture"
        self.prior = {"both-timeframes-covered": sha256(b"prior")}
        self.freeze = {key: sha256(key.encode()) for key in (
            "strategy", "evaluator", "environment", "execution-rules",
            "reference-inventory", "source-scope",
        )}
        self.registration = registration_manifest(self.window, self.freeze, self.prior)
        self.intake = Intake(
            self.window, {next(iter(self.prior)): Window(self.early, self.start)},
            sha256(self.payload), {key: sha256(key.encode()) for key in REQUIRED_EVIDENCE},
        )
        self.good = Ledger((D(13), D(-10)) * 50, (D(3000), D(3150)), 0, ())
        self.ledgers = dict.fromkeys(("M15", "H1"), self.good)
        self.loads = 0

    def run_gate(self, *, now=None, registered=None, intake=None, current=None,
                 payload=None, no_intake_receipt=False, no_audit=False, window=None):
        intake = self.intake if intake is None else intake
        manifest = intake.manifest(self.registration)
        receipts = {
            ("registration", self.registration.sha256, b"reg"): registered or self.early,
            ("intake", manifest.sha256, b"intake"): self.end,
            ("evaluation", evaluation_manifest(manifest, self.ledgers).sha256, b"audit"):
                self.end,
        }

        def load(data):
            self.assertEqual(data, self.payload)
            self.loads += 1
            return self.ledgers, None if no_audit else b"audit"

        results = evaluate(
            window or self.window, self.freeze, current or self.freeze, self.prior, b"reg",
            intake, None if no_intake_receipt else b"intake",
            self.payload if payload is None else payload, now=now or self.end,
            verify=lambda *args: receipts.get(args), load_ledgers=load,
        )
        return tuple(result.state for result in results.values())

    def test_pass_at_fixed_end_and_pf_boundary(self):
        self.assertEqual(self.run_gate(), ("pass", "pass"))

    def test_before_end_and_extension_never_load(self):
        self.assertEqual(self.run_gate(now=self.end - timedelta(seconds=1)), ("blocked",) * 2)
        longer = Window(self.start, self.end + timedelta(days=1))
        self.assertEqual(self.run_gate(window=longer, now=longer.end), ("blocked",) * 2)
        self.assertEqual(self.loads, 0)

    def test_late_or_at_start_registration(self):
        for registered in (self.start, self.start + timedelta(seconds=1)):
            self.assertEqual(self.run_gate(registered=registered), ("blocked",) * 2)
        self.assertEqual(self.loads, 0)

    def test_changed_freeze(self):
        current = {**self.freeze, "strategy": sha256(b"changed config")}
        self.assertEqual(self.run_gate(current=current), ("fail",) * 2)
        self.assertEqual(self.loads, 0)

    def test_overlap_and_missing_prior(self):
        prior = {next(iter(self.prior)): Window(self.early, self.start + timedelta(seconds=1))}
        self.assertEqual(self.run_gate(intake=replace(self.intake, prior_utc=prior)), ("fail",) * 2)
        self.assertEqual(self.run_gate(intake=replace(self.intake, prior_utc={})),
                         ("inconclusive",) * 2)
        self.assertEqual(self.loads, 0)

    def test_missing_cost_coverage_receipt_or_payload_integrity(self):
        evidence = dict(self.intake.evidence)
        del evidence["funding"]
        for kwargs in (
            {"intake": replace(self.intake, evidence=evidence)},
            {"intake": replace(self.intake, coverage=Window(self.start, self.end - timedelta(days=1)))},
            {"no_intake_receipt": True},
            {"payload": b"tampered bytes"},
        ):
            self.assertEqual(self.run_gate(**kwargs), ("inconclusive",) * 2)
        self.assertEqual(self.loads, 0)
        self.assertEqual(self.run_gate(no_audit=True), ("inconclusive",) * 2)

    def test_independent_fail_and_insufficient(self):
        self.ledgers["M15"] = replace(self.good, violations=("lookahead",))
        self.ledgers["H1"] = replace(self.good, closed_trade_net=(D(1),) * 99)
        self.assertEqual(self.run_gate(), ("fail", "inconclusive"))

    def test_unresolved_and_exact_drawdown_limit(self):
        self.ledgers["M15"] = replace(self.good, unresolved_positions=1)
        self.ledgers["H1"] = replace(self.good, observed_equity=(D(3000), D(2700), D(3150)))
        self.assertEqual(self.run_gate(), ("inconclusive", "fail"))

    def test_zero_loss_pf_and_flat_ledger(self):
        self.ledgers["M15"] = Ledger((D(1),) * 100, (D(3000), D(3100)), 0, ())
        self.ledgers["H1"] = Ledger((D(0),) * 100, (D(3000), D(3000)), 0, ())
        self.assertEqual(self.run_gate(), ("pass", "fail"))

    def test_positive_net_below_pf_threshold_and_unreconciled_equity(self):
        self.ledgers["M15"] = Ledger((D(12), D(-10)) * 50, (D(3000), D(3100)), 0, ())
        self.ledgers["H1"] = replace(self.good, observed_equity=(D(3000), D(3151)))
        self.assertEqual(self.run_gate(), ("fail", "inconclusive"))
