"""Offline prospective protocol and evidence gates. No collector or broker adapter."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import re
from typing import Callable, Mapping

from goldbot.backtesting.strategy_validation import FrozenManifest, sha256


CANDIDATES = ("M15", "H1")
MIN_TRADES = 100
MIN_PF = Fraction(13, 10)
MAX_DRAWDOWN = Fraction(1, 10)
REQUIRED_EVIDENCE = frozenset({
    "source-lineage", "utc-and-clock", "bid-ask", "sessions-and-exceptions",
    "heartbeat-and-gaps", "contract-and-tick-economics", "margin-and-fx",
    "commission", "funding", "risk-days", "fill-eligibility", "access-audit",
})
TRUST_VERIFIER = Callable[[str, str, bytes], datetime | None]


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError("an explicit UTC datetime is required")
    return value


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


@dataclass(frozen=True)
class Window:
    """Half-open UTC interval, including all warmup and entry/exit input."""

    start: datetime
    end: datetime

    def __post_init__(self):
        if _utc(self.start) >= _utc(self.end):
            raise ValueError("window must have positive duration")

    def record(self):
        return [point.isoformat() for point in (self.start, self.end)]

    def overlaps(self, other):
        return self.start < other.end and other.start < self.end


def registration_manifest(window, freeze, prior_sources):
    """Produce commitment bytes only. An independent receipt establishes time."""
    if not prior_sources or not all(_digest(digest) for digest in prior_sources.values()):
        raise ValueError("prior exposure inventory requires source digests")
    required = {"strategy", "evaluator", "environment", "execution-rules",
                "reference-inventory", "source-scope"}
    if set(freeze) != required or not all(_digest(digest) for digest in freeze.values()):
        raise ValueError("complete freeze digests required")
    return FrozenManifest.create({
        "schema": "goldbot.prospective-validation.v1",
        "window_utc": window.record(),
        "stop": "fixed-end-no-extensions",
        "freeze": freeze,
        "prior_sources": prior_sources,
        "candidates": {"M15": "XAUUSD Phase 6.6 independent USD 3000",
                       "H1": "XAUUSD Phase 6.6 independent USD 3000"},
        "required_intake_evidence": sorted(REQUIRED_EVIDENCE),
        "criteria": {
            "minimum_closed_trades": MIN_TRADES, "net_after_costs": ">0",
            "profit_factor": ">=1.3 with positive wins and zero losses treated as +infinity",
            "observed_drawdown": "<0.10",
            "violations": 0, "status": "provisional research choices",
        },
    })


@dataclass(frozen=True)
class Decision:
    state: str
    reason: str


def _receipt(verify, domain, digest, receipt):
    """Delegate trust policy to a separately configured independent verifier."""
    if not receipt:
        return None
    value = verify(domain, digest, receipt)
    return _utc(value) if value is not None else None


@dataclass(frozen=True)
class Intake:
    coverage: Window
    prior_utc: Mapping[str, Window]
    payload_sha256: str
    evidence: Mapping[str, str]

    def manifest(self, registration):
        return FrozenManifest.create({
            "registration": registration.sha256,
            "coverage": self.coverage.record(),
            "prior_utc": {key: value.record() for key, value in self.prior_utc.items()},
            "payload_sha256": self.payload_sha256,
            "evidence": self.evidence,
        })


def eligibility(window, freeze, current_freeze, prior_sources, registration_receipt,
                intake, intake_receipt, sealed_payload, *, now, verify: TRUST_VERIFIER):
    """Check precommit, freezes, nonoverlap and independently sealed intake."""
    now = _utc(now)
    registration = registration_manifest(window, freeze, prior_sources)
    registered_at = _receipt(verify, "registration", registration.sha256,
                             registration_receipt)
    if registered_at is None or registered_at >= window.start or registered_at > now:
        return Decision("blocked", "trusted pre-start registration required")
    if freeze != current_freeze:
        return Decision("fail", "frozen baseline or evaluation inputs changed")
    if now < window.end:
        return Decision("blocked", "fixed horizon has not elapsed")
    if intake is None or set(intake.prior_utc) != set(prior_sources):
        return Decision("inconclusive", "complete verified prior UTC coverage required")
    if (intake.coverage != window or not REQUIRED_EVIDENCE <= intake.evidence.keys()
            or not all(_digest(digest) for digest in intake.evidence.values())):
        return Decision("inconclusive", "complete fixed-window source and cost evidence required")
    if sealed_payload is None or sha256(sealed_payload) != intake.payload_sha256:
        return Decision("inconclusive", "sealed input bytes do not match intake")
    manifest = intake.manifest(registration)
    sealed_at = _receipt(verify, "intake", manifest.sha256, intake_receipt)
    if sealed_at is None or not window.end <= sealed_at <= now:
        return Decision("inconclusive", "independent post-horizon intake attestation required")
    if any(window.overlaps(prior) for prior in intake.prior_utc.values()):
        return Decision("fail", "prospective input overlaps prior inspected data")
    return Decision("eligible", "registered fixed window and sealed intake verified")


@dataclass(frozen=True)
class Ledger:
    closed_trade_net: tuple[Decimal, ...]
    observed_equity: tuple[Decimal, ...]
    unresolved_positions: int
    violations: tuple[str, ...]


def _score(ledger):
    if ledger.violations:
        return Decision("fail", "audit detected a risk, lookahead or protocol violation")
    if type(ledger.unresolved_positions) is not int or ledger.unresolved_positions != 0:
        return Decision("inconclusive", "terminal position unresolved")
    if len(ledger.closed_trade_net) < MIN_TRADES:
        return Decision("inconclusive", "fewer than 100 closed trades")
    if (not all(isinstance(value, Decimal) and value.is_finite()
                for value in (*ledger.closed_trade_net, *ledger.observed_equity))
            or len(ledger.observed_equity) < 2 or ledger.observed_equity[0] != 3000):
        return Decision("inconclusive", "complete finite equity and trade ledger required")
    trades = tuple(map(Fraction, ledger.closed_trade_net))
    equity = tuple(map(Fraction, ledger.observed_equity))
    net = sum(trades)
    if equity[-1] - equity[0] != net:
        return Decision("inconclusive", "flat terminal equity does not reconcile to net trades")
    wins = sum(value for value in trades if value > 0)
    losses = -sum(value for value in trades if value < 0)
    if net <= 0 or wins < MIN_PF * losses:
        return Decision("fail", "net P/L or after-cost profit factor missed the threshold")
    peak = equity[0]
    for value in equity:
        peak = max(peak, value)
        if peak - value >= MAX_DRAWDOWN * peak:
            return Decision("fail", "observed drawdown reached or exceeded 10%")
    return Decision("pass", "provisional research thresholds met")


def evaluate(window, freeze, current_freeze, prior_sources, registration_receipt,
             intake, intake_receipt, sealed_payload, *, now, verify, load_ledgers):
    """Ask for both ledgers only after eligibility. Bind the audit to intake."""
    gate = eligibility(window, freeze, current_freeze, prior_sources, registration_receipt,
                       intake, intake_receipt, sealed_payload, now=now, verify=verify)
    if gate.state != "eligible":
        return dict.fromkeys(CANDIDATES, gate)
    registration = registration_manifest(window, freeze, prior_sources)
    ledgers, receipt = load_ledgers(sealed_payload)
    if set(ledgers) != set(CANDIDATES):
        return dict.fromkeys(CANDIDATES, Decision("inconclusive", "both ledgers required"))
    audit = evaluation_manifest(intake.manifest(registration), ledgers)
    audited_at = _receipt(verify, "evaluation", audit.sha256, receipt)
    sealed_at = _receipt(verify, "intake", intake.manifest(registration).sha256,
                         intake_receipt)
    if audited_at is None or sealed_at is None or not sealed_at <= audited_at <= now:
        return dict.fromkeys(CANDIDATES, Decision("inconclusive", "independent ledger audit required"))
    return {candidate: _score(ledgers[candidate]) for candidate in CANDIDATES}


def evaluation_manifest(intake_manifest, ledgers):
    """Commit the audited outcomes for both candidates to sealed intake."""
    return FrozenManifest.create({
        "intake": intake_manifest.sha256,
        "ledgers": {candidate: {
            "closed_trade_net": [str(value) for value in ledger.closed_trade_net],
            "observed_equity": [str(value) for value in ledger.observed_equity],
            "unresolved_positions": ledger.unresolved_positions,
            "violations": ledger.violations,
        } for candidate, ledger in ledgers.items()},
    })
