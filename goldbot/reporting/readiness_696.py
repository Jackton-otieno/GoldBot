"""Offline Phase 6.9.6 assessment of a fixed, hash-pinned evidence baseline."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from hashlib import sha256
from pathlib import Path


class Status(str, Enum):
    OBSERVED = "OBSERVED"
    UNRESOLVED = "UNRESOLVED"
    MISSING = "MISSING"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    REJECTED = "REJECTED"
    INVALID = "INVALID"


class Scope(str, Enum):
    EXNESS = "Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD"
    METAQUOTES = "Original MetaQuotes demo / XAUUSD"
    STUDY = "Strategy evidence / M15 and H1"


class Kind(str, Enum):
    TERMINAL = "Observed terminal diagnostics"
    ARCHIVE = "Archived assessment"
    RESEARCH = "Observed historical inputs, simulated outcomes"
    DRAFT = "Draft protocol"
    NONE = "Required evidence absent"


@dataclass(frozen=True)
class Requirement:
    key: str
    scope: Scope
    kind: Kind
    finding: Status
    detail: str
    next_evidence: str
    paths: tuple
    observed_on: date = None


@dataclass(frozen=True)
class Provenance:
    path: str
    expected_sha256: str
    actual_sha256: str
    issue: Status = None


@dataclass(frozen=True)
class Finding:
    requirement: Requirement
    status: Status
    issues: tuple
    sources: tuple


@dataclass(frozen=True)
class Assessment:
    as_of: date
    findings: tuple

    @property
    def decision(self):
        return "NO-GO"

    @property
    def execution_authorized(self):
        return False

    @property
    def historical_execution_authorized(self):
        return False

    @property
    def prospective_authorized(self):
        return False


DAY = date(2026, 11, 18)
CONNECT = "reports/phase_6_9_2/connectivity.json"
PRECISION = "reports/phase_6_9_3_1/probes.json"
PRECISION_REVIEW = "reports/phase_6_9_3_1/verification.md"
CONTRACT = "reports/phase_6_9_3/probes.json"
TIME = "reports/phase_6_9_4/diagnostic.json"
SAMPLE = "reports/phase_6_9_4_1/diagnostic.json"
SMOKE = "reports/phase_6_9_5/live-summary.json"
JOURNAL = "reports/phase_6_9_5/diagnostic.sqlite3"
CHAIN = "reports/phase_6_9_5/verified-manifest.json"
PROTOCOL = "reports/validation_phase_6_8_6/readiness.md"
DRAFT = "reports/validation_phase_6_8_6/draft-protocol.md"
RESEARCH = "reports/research_phase_6_8_5/results.json"

REQUIREMENTS = (
    Requirement("exness_identity", Scope.EXNESS, Kind.TERMINAL, Status.OBSERVED,
                "Pinned connectivity passed on 18 November 2026. This is a historical identity snapshot.",
                "Recheck exact identity using the independent local pin at every future attachment.",
                (CONNECT,), DAY),
    Requirement("exness_account_variant", Scope.EXNESS, Kind.NONE, Status.MISSING,
                "Terminal identity supplies no Personal Area Pro classification.",
                "Record redacted independent evidence for the product variant of this exact demo.",
                (CONNECT,)),
    Requirement("exness_monetary_precision", Scope.EXNESS, Kind.TERMINAL, Status.CONFLICTING,
                "The unchanged validator rejected four of 144 P/L probes; the earlier run rejected six. "
                "The notional-first rounding fit leaves calculator semantics and booked P/L unresolved.",
                "Obtain authoritative rounding and accounting rules and independently reconcile them.",
                (CONTRACT, PRECISION, PRECISION_REVIEW,
                 "reports/phase_6_9_3_1/notional-comparison.json")),
    Requirement("metaquotes_contract", Scope.METAQUOTES, Kind.TERMINAL, Status.REJECTED,
                "USD 0.10 tick metadata conflicts with USD 1.00 implied by calculator probes.",
                "Keep original broker isolated and require its own contract reconciliation.",
                ("reports/phase_6_8_1/current-demo.json", "reports/phase_6_9_1/demo-verification.md")),
    Requirement("production_utc_mapping", Scope.EXNESS, Kind.TERMINAL, Status.UNRESOLVED,
                "An earlier clock bracket was conditional. The smoke opening probe failed. "
                "Raw labels, archive request coordinates and effective UTC windows remain unverified.",
                "Obtain scoped, independently reviewed effective-dated UTC mapping and transition checks.",
                (TIME, SAMPLE, SMOKE)),
    Requirement("dated_quote_and_trade_sessions", Scope.EXNESS, Kind.ARCHIVE, Status.UNRESOLVED,
                "Current samples and general schedules leave account-specific sessions and exceptions open.",
                "Document dated quote/trade intervals, close-only periods, holidays and maintenance.",
                ("reports/phase_6_9_4/verification.md", SAMPLE)),
    Requirement("archive_coverage_and_quote_basis", Scope.EXNESS, Kind.TERMINAL, Status.UNRESOLVED,
                "Sampled tick retrieval and one bid-derived M1 reconstruction do not establish archive coverage. "
                "The archived smoke recorded eight snapshots, zero admitted bars and unknown tick coverage.",
                "Reconcile scoped bid/ask history, chart basis, continuity, gaps and corrections.",
                (SAMPLE, SMOKE, JOURNAL, CHAIN)),
    Requirement("risk_day", Scope.EXNESS, Kind.NONE, Status.MISSING,
                "An approved account-scoped policy boundary is absent.",
                "Approve the risk-day boundary and prove its effective UTC mapping.",
                ("reports/phase_6_9_4_1/verification.md",)),
    Requirement("opening_equity", Scope.EXNESS, Kind.NONE, Status.MISSING,
                "The diagnostics collected no equity at the exact policy-day opening.",
                "Attest positive opening equity at the effective boundary for this exact account.",
                ("reports/phase_6_9_4_1/verification.md",)),
    Requirement("executable_costs_and_margin", Scope.EXNESS, Kind.ARCHIVE, Status.UNRESOLVED,
                "The sampled margin results leave effective-dated rates, fees, swap, FX and fill costs open.",
                "Obtain broker-scoped effective schedules and execution eligibility evidence.",
                (PRECISION_REVIEW, "reports/phase_6_9_4/verification.md")),
    Requirement("retrospective_strategy", Scope.STUDY, Kind.RESEARCH, Status.REJECTED,
                "All eight Phase 6.8.5 hypothetical simulations had negative realized net P/L, including ideal costs.",
                "Carry the adverse result into independent protocol review.",
                (RESEARCH, "reports/research_phase_6_8_5/assumptions.json")),
    Requirement("prior_exposure", Scope.STUDY, Kind.DRAFT, Status.UNRESOLVED,
                "Historical candles and diagnostics are exposed. The complete independently mapped exposure inventory is pending.",
                "Attest all viewed datasets and diagnostics with independently verified UTC bounds.",
                (PROTOCOL, DRAFT, CHAIN)),
    Requirement("prospective_protocol", Scope.STUDY, Kind.DRAFT, Status.MISSING,
                "Exact UTC dates, independent approval, external pre-start receipt and audited intake are absent.",
                "Approve the frozen M15/H1 protocol and verify an external pre-start receipt before any separate authorization.",
                (PROTOCOL, DRAFT, "reports/validation_phase_6_8_6/reference-freeze.json")),
)


def inspect_source(root: Path, relative: str) -> Provenance:
    expected = PINS[relative]
    path = root / relative
    try:
        if path.resolve() != root.resolve() / relative:
            return Provenance(relative, expected, None, Status.INVALID)
        actual = sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return Provenance(relative, expected, None, Status.MISSING)
    except (OSError, RuntimeError):
        return Provenance(relative, expected, None, Status.INVALID)
    return Provenance(relative, expected, actual, None if actual == expected else Status.INVALID)


def assess(root: Path, as_of: date) -> Assessment:
    """Evaluate the fixed baseline. The caller supplies a root and explicit assessment date only."""
    evidence = {path: inspect_source(root, path) for path in sorted(PINS)}
    findings = []
    for requirement in REQUIREMENTS:
        sources = tuple(evidence[path] for path in requirement.paths)
        issues = {source.issue for source in sources if source.issue}
        if requirement.finding is not Status.OBSERVED:
            issues.add(requirement.finding)
        if requirement.observed_on:
            if as_of < requirement.observed_on:
                issues.add(Status.INVALID)
            elif as_of > requirement.observed_on:
                issues.add(Status.STALE)
        precedence = (Status.INVALID, Status.MISSING, Status.STALE, Status.CONFLICTING,
                      Status.REJECTED, Status.UNRESOLVED)
        ordered = tuple(status for status in precedence if status in issues)
        findings.append(Finding(requirement, ordered[0] if ordered else Status.OBSERVED,
                                ordered, sources))
    return Assessment(as_of, tuple(findings))


# Baseline digests committed from the pre-change inventory of the actual GoldBot files.
PINS = {
    "reports/phase_6_8_1/current-demo.json": "a6097cae9c9094f2d4a3dc955c97f0b50187699c5a05f65cc6a527fc87bc9979",
    "reports/phase_6_9_1/demo-verification.md": "9217ce47620aa983c9447408d3de3e9b58c195251f21c9cca192f81e76ec1c14",
    "reports/phase_6_9_2/connectivity.json": "0c2d7c622624e72908216fce85a07151ffb68e227f07d8ac972f0b3eb5386ac3",
    "reports/phase_6_9_3/probes.json": "9b7a01e99829a12cbd0c18f809214d8ad9e2b6718cef21f3f006a9458f223b30",
    "reports/phase_6_9_3_1/notional-comparison.json": "e1cf52b2da259e32f117e95213734abd94af63a338ae1c541c083e46de3485fb",
    "reports/phase_6_9_3_1/probes.json": "75d55e303f010fbba3d1aa8a94dd475bfc2bf7dd72af8954c8ecaa545d534b26",
    "reports/phase_6_9_3_1/verification.md": "0f4684a44f0de45866f14309055f34ba389bd2cd8888beaa54135f000f8ee5ae",
    "reports/phase_6_9_4/diagnostic.json": "aa6b45cb882615293c8673a3893dfed24e2455049337d11c298d5d36d89a0fa2",
    "reports/phase_6_9_4/verification.md": "6674da483fd00dbdd4bcbbd2e3ac3efc99b1581fa49ea01c45e750bfa2b60564",
    "reports/phase_6_9_4_1/diagnostic.json": "51105ca8252f0e773b81a4ec4e3d2e59968bde11a8b4e78c31155f74da811410",
    "reports/phase_6_9_4_1/verification.md": "adb6cace34d8cc314605a462c2844384e982d2a62f9d198d57724156f4ffaeb2",
    "reports/phase_6_9_5/diagnostic.sqlite3": "edb4a74ad094bd6f02cc1773b5c2fc71bfacc73e863c9b3af8f366d055340578",
    "reports/phase_6_9_5/live-summary.json": "c8f3c00b19cdd7c4a7fced6fff58134967ef0ded17f53206286001a4442da29a",
    "reports/phase_6_9_5/verified-manifest.json": "fb29fbfbea0b7050e020a726fad1f27ad0c8df414bf8052fc4c658e9955d03f9",
    "reports/research_phase_6_8_5/assumptions.json": "6791cf8423af99e65756fc6a2356e8b5db0cee2ab26f2c61b24a2483a643177e",
    "reports/research_phase_6_8_5/results.json": "b708a00c10fa4e79e82307a5dbb1589e7752eb8e4531083e7b485db064c197a3",
    "reports/validation_phase_6_8_6/draft-protocol.md": "d2e28c78ab4472e78350c8e3cb40936000c92975df354d0cfc63cdeb776397fb",
    "reports/validation_phase_6_8_6/readiness.md": "4228b43a606f52ba131271ab36b7b2fcfed5f9d624bd524b405cb68c48eb4e8a",
    "reports/validation_phase_6_8_6/reference-freeze.json": "aeb45b7a94fe43934541b0129e95b1d7a0e2ee5f1c58bf8b876b993867775544",
}
