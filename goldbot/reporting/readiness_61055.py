"""Consolidate reviewed evidence without changing the operational gates."""

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from goldbot.backtesting.prospective_validation import eligibility
from goldbot.reporting import readiness_696 as legacy


REVIEWED_ON = date(2026, 11, 21)
GATE = "reports/phase_6_9_6/assessment.json"
PRECISION = "reports/phase_6_10_5_1/precision-validation.json"
LOSS = "reports/phase_6_10_5_1/risk-impact.json"
TIME = "reports/phase_6_10_5_2/timestamp-verification.json"
SESSIONS = "reports/phase_6_10_5_2/session-evidence.json"
RISK_DAY = "reports/phase_6_10_5_2/risk-day-verification.json"
HISTORY = "reports/phase_6_10_5_3/historical-readiness.json"
QUALITY = "reports/phase_6_10_5_3/data-quality.json"
DATA_MANIFEST = "reports/phase_6_10_5_3/data-manifest.json"
CAPITAL = "reports/phase_6_10_5_4/capital-feasibility.json"
COSTS = "reports/phase_6_10_5_4/cost-evidence.md"
REJECTIONS = "reports/phase_6_10_5_4/rejection-analysis.json"
COMPARISON = "reports/phase_6_10_4/comparison.json"
CSV = ("data/XAUUSD_M15.csv", "data/XAUUSD_H1.csv")
RESEARCH = "retrospective_research_data_eligibility"
PREP = "prospective_validation_preparation"
ADMIT = "prospective_validation_admission"
DEMO = "automated_demo_trading_authorization"
LIVE = "live_trading_authorization"
TRADING = (DEMO, LIVE)
EXECUTION = (ADMIT, *TRADING)
STATUS = legacy.Status
LEGACY_KEYS = ("decision", "execution_authorized", "historical_execution_authorized",
               "prospective_authorized")


@dataclass(frozen=True)
class Blocker:
    key: str
    severity: str
    observed_status: STATUS
    finding: str
    resolution: str
    responsible: str
    impact: tuple[str, ...]
    paths: tuple[str, ...]
    required_values: tuple = ()
    legacy_keys: tuple[str, ...] = ()


BLOCKERS = (
    Blocker("broker_identity_and_product", "CRITICAL", STATUS.MISSING,
            "Earlier terminal identity is dated. The exact product variant is unverified.",
            "Recheck installation and exact account at attachment and obtain redacted product confirmation.",
            "Operator and Exness KE", EXECUTION, (GATE,),
            legacy_keys=("exness_identity", "exness_account_variant")),
    Blocker("monetary_precision_and_booked_pnl", "CRITICAL", STATUS.CONFLICTING,
            "216 independent calculator results fit the empirical model. Booked P/L remains unverified.",
            "Obtain authoritative calculator/booking rules and reconcile the discrepancy with the unchanged validator.",
            "Exness KE / MetaQuotes and independent reviewer", EXECUTION, (PRECISION, LOSS),
            ((PRECISION, ("broker_acceptance",), "BLOCKED"),
             (LOSS, ("booked_profit_loss",), "UNVERIFIED")),
            ("exness_monetary_precision",)),
    Blocker("utc_mapping_and_freshness", "CRITICAL", STATUS.UNRESOLVED,
            "The clock bracket supported conditional age estimates. No effective-dated production mapping exists.",
            "Obtain server-specific live and historical UTC semantics and verify full-bracket freshness and transition handling.",
            "Exness KE / MetaQuotes and time-evidence reviewer", EXECUTION, (TIME,),
            ((TIME, ("production_mapping",), "UNVERIFIED"),), ("production_utc_mapping",)),
    Blocker("quote_trade_sessions_and_exceptions", "CRITICAL", STATUS.UNRESOLVED,
            "The public DST schedule does not establish exact quote or trade intervals for this account.",
            "Verify dated quote, trade and close-only permissions, DST, holidays, maintenance and exceptional closures.",
            "Exness KE and session-evidence reviewer", EXECUTION, (SESSIONS,),
            ((SESSIONS, ("accepted_quote_intervals",), []),
             (SESSIONS, ("accepted_trade_intervals",), [])), ("dated_quote_and_trade_sessions",)),
    Blocker("risk_day_and_opening_equity", "CRITICAL", STATUS.MISSING,
            "No approved daily reset or independently attested opening equity was recorded.",
            "Approve an exact account-scoped policy boundary and attest opening equity at that UTC instant.",
            "GoldBot operator and independent account-evidence reviewer", EXECUTION, (RISK_DAY,),
            ((RISK_DAY, ("reset_authorized",), False),
             (RISK_DAY, ("verified_opening_equity",), None)), ("risk_day", "opening_equity")),
    Blocker("historical_provenance_and_coverage", "HIGH", STATUS.UNRESOLVED,
            "No new research dataset or execution-grade history passed. Archived ticks are diagnostic only.",
            "Verify original bytes, reuse rights, UTC mapping, bid/ask basis, dated coverage and gaps with the existing validator.",
            "Data provider, data custodian and independent reviewer", (RESEARCH, PREP, *EXECUTION),
            (HISTORY, QUALITY, DATA_MANIFEST),
            ((HISTORY, ("research_source_acceptance",), "BLOCKED"),
             (HISTORY, ("execution_grade_historical_acceptance",), "BLOCKED")),
            ("archive_coverage_and_quote_basis",)),
    Blocker("costs_margin_and_slippage", "CRITICAL", STATUS.UNRESOLVED,
            "Observed quotes and margin are point samples. Commission, swaps, funding, tariffs and fills are unverified.",
            "Obtain effective scoped spreads, commissions, swap/funding, margin tiers, slippage and fill evidence.",
            "Exness KE and independent execution reviewer", EXECUTION, (CAPITAL, COSTS),
            legacy_keys=("executable_costs_and_margin",)),
    Blocker("minimum_volume_feasibility", "HIGH", STATUS.UNRESOLVED,
            "The USD 3,000 reference frequently fails minimum-lot risk checks, especially on H1.",
            "Verify actual contract/cost inputs and feasible scoped entries at the unchanged budget.",
            "GoldBot risk reviewer and Exness KE", EXECUTION, (CAPITAL, REJECTIONS),
            ((CAPITAL, ("reference_equity_usd",), "3000"),
             (CAPITAL, ("reference_account_balance_changed",), False))),
    Blocker("profitability_not_demonstrated", "HIGH", STATUS.REJECTED,
            "Frozen retrospective outcomes do not demonstrate robust profitability.",
            "Obtain independently validated net-after-costs strategy results and risk compliance.",
            "Independent strategy reviewer", TRADING, (COMPARISON,),
            ((COMPARISON, ("readiness_decision",), "NO-GO"),), ("retrospective_strategy",)),
    Blocker("prospective_registration_and_exposure", "HIGH", STATUS.MISSING,
            "The protocol is a draft. No trusted registration, verified exposure inventory or sealed intake is configured.",
            "Approve scope and fixed dates, independently precommit, verify nonoverlap and admit sealed intake under the existing protocol.",
            "GoldBot operator, independent registrar and data custodian", (PREP, *EXECUTION),
            (legacy.DRAFT, legacy.PROTOCOL),
            legacy_keys=("prior_exposure", "prospective_protocol")),
)


def inspect(root, path, expected):
    """Validate bytes before interpreting any asserted status."""
    actual, payload = None, None
    try:
        source = root / path
        if source.resolve() != root.resolve() / path:
            raise ValueError("Source resolves outside the reviewed path.")
        content = source.read_bytes()
        actual = sha256(content).hexdigest()
        if actual != expected:
            raise ValueError("Source SHA-256 differs.")
        if path.endswith(".json"):
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("Expected an evidence object.")
    except FileNotFoundError:
        return legacy.Provenance(path, expected, None, STATUS.MISSING), None
    except (OSError, ValueError, RuntimeError):
        return legacy.Provenance(path, expected, actual, STATUS.INVALID), None
    return legacy.Provenance(path, expected, actual), payload


def matches(payload, keys, expected):
    for key in keys:
        if not isinstance(payload, dict) or key not in payload:
            return False
        payload = payload[key]
    return type(payload) is type(expected) and payload == expected


def evaluate_blocker(item, provenance, payloads, legacy_findings):
    inherited = [legacy_findings[key] for key in item.legacy_keys]
    sources = {path: provenance[path] for path in item.paths}
    for finding in inherited:
        sources.update({source.path: source for source in finding.sources})
    issues = {source.issue for source in sources.values() if source.issue}
    issues.update(issue for finding in inherited for issue in finding.issues)
    issues.add(item.observed_status)
    inconsistent = any(not provenance[path].issue and not matches(payloads[path], keys, expected)
                       for path, keys, expected in item.required_values)
    if inconsistent:
        issues.add(STATUS.CONFLICTING)
    precedence = (STATUS.INVALID, STATUS.MISSING, STATUS.STALE, STATUS.CONFLICTING,
                  STATUS.REJECTED, STATUS.UNRESOLVED)
    ordered = [status for status in precedence if status in issues]
    return dict(id=item.key, severity=item.severity, verification_status=ordered[0],
                unresolved_conditions=ordered, unexpected_evidence=inconsistent, finding=item.finding,
                required_resolution=item.resolution, responsible_or_dependency=item.responsible,
                blocks={name: name in item.impact for name in (RESEARCH, PREP, ADMIT, DEMO, LIVE)},
                evidence=[asdict(sources[path]) for path in sorted(sources)])


def review_intake(submission=None):
    """Delegate technical eligibility. A result cannot grant authorization."""
    if submission is None:
        return {"state": "blocked", "reason": "No trusted registration and intake configured"}
    try:
        return asdict(eligibility(**submission))
    except Exception:
        return {"state": "blocked", "reason": "Invalid evidence or independent verifier failure"}


def build(root, as_of, *, submission=None):
    prior = legacy.assess(root, as_of)
    old_findings = {item.requirement.key: item for item in prior.findings}
    checked = {name: inspect(root, name, digest) for name, digest in PINS.items()}
    provenance = {name: result[0] for name, result in checked.items()}
    payloads = {name: result[1] for name, result in checked.items()}
    provenance.update({source.path: source for item in prior.findings for source in item.sources})
    expected_gate = (prior.decision, prior.execution_authorized,
                     prior.historical_execution_authorized, prior.prospective_authorized)
    gate_conflict = not provenance[GATE].issue and any(
        not matches(payloads[GATE], (key,), value)
        for key, value in zip(LEGACY_KEYS, expected_gate, strict=True)
    )
    register = [evaluate_blocker(item, provenance, payloads, old_findings) for item in BLOCKERS]
    invalid_sources = sorted(name for name, source in provenance.items() if source.issue)
    inconsistent = [item["id"] for item in register if item["unexpected_evidence"]]
    integrity_ok = not invalid_sources and not gate_conflict and not inconsistent and as_of >= REVIEWED_ON
    legacy_research_ok = (as_of >= REVIEWED_ON and not gate_conflict
                          and not any(provenance[path].issue for path in (*CSV, COMPARISON, GATE))
                          and matches(payloads[COMPARISON], ("readiness_decision",), "NO-GO"))
    decisions = {
        "offline_engineering_completeness": {
            "status": "PASS" if integrity_ok else "BLOCKED",
            "scope": "Reviewed offline work and pinned evidence integrity",
            "source_issues": invalid_sources, "archived_gate_conflict": gate_conflict,
            "unexpected_blocker_evidence": inconsistent,
            "assessment_predates_review": as_of < REVIEWED_ON,
        }
    }
    for name in (RESEARCH, PREP, ADMIT, DEMO, LIVE):
        decisions[name] = {"status": "BLOCKED", "blockers": [
            item["id"] for item in register if item["blocks"][name]
        ]}
    decisions[RESEARCH]["scoped_legacy_ohlc"] = {
        "status": "PASS" if legacy_research_ok else "BLOCKED",
        "scope": "Frozen exposed hypothetical OHLC research only",
        "execution_grade": False, "prospective_eligible": False,
    }
    decisions[PREP]["draft_available"] = not any(
        provenance[path].issue for path in (legacy.DRAFT, legacy.PROTOCOL))
    decisions[ADMIT]["technical_intake"] = review_intake(submission)
    for name in (ADMIT, DEMO, LIVE):
        decisions[name]["authorized"] = False
    common = {"as_of": as_of.isoformat(), "overall": prior.decision}
    return {
        "blocker-register.json": dict(common, blockers=register),
        "readiness.json": dict(common, assessments=decisions, phase_6_9_6=dict(
            zip(LEGACY_KEYS, expected_gate, strict=True)),
            inherited_findings={key: finding.status for key, finding in old_findings.items()}),
        "evidence-manifest.json": dict(common, review_completed_on=REVIEWED_ON.isoformat(),
                                       sources=[asdict(provenance[name]) for name in sorted(provenance)]),
    }


# Fixed digests from the reviewed checkout. Updating evidence requires review.
PINS = {
    'data/XAUUSD_H1.csv': 'a0ec85476a9cf5b5186c69dfed2d65bb6ccd100e5a05044bf1c041d94ad32541',
    'data/XAUUSD_M15.csv': 'a8611beccee72e10e8774a299b2fd1752521d04c755543d87f187d36b9ab986e',
    'docs/phases/phase-6-10-4.md': '2dce7da8f77f4f63f86b384f6506933682b744eb5d1648b6f1a3bc8f01fabb92',
    'docs/phases/phase-6-10-5-1.md': 'aab7dab5ffccdcc0de4b16f58e712b7043ffb66a8841754ac0c016e992d22b7f',
    'docs/phases/phase-6-10-5-2.md': '25fa9e38887821314fc0949b485c5f78468f32e5acadfd534a83941fc41894ea',
    'docs/phases/phase-6-10-5-3.md': '02c0e39c6df7f2a9688053465a409d1972c6343691231bba0807ce07c84e2e0e',
    'docs/phases/phase-6-10-5-4.md': '01d9ef4a63e730a01c88a04d9c3108b1cb3c5a3dac3bfbc136c0a6b0770237bb',
    'goldbot/backtesting/execution_data_validator.py': 'ee66aca18a4a51fc078d6c48ed239151b099a03697d5f8e1f7810a0b2317baaf',
    'goldbot/backtesting/prospective_validation.py': '01f85a3d1a704e0dd1ce6463da89eb4ced55a6c72266a7892f2aec1a08acc23b',
    'goldbot/reporting/readiness_696.py': '2c6aee6da5da70502a1fcc05687dcb947e85e7575ef78d3cbe3516665bcc5057',
    'historical_data/phase_6_10_5_3/exness-mt5/xauusd-raw-ticks.json': 'ccfd69fdd76854f32e1f4cfe3a4206cf6430fc28d0c9e0e4670fac03d54b0dd2',
    'reports/phase_6_10_4/comparison.json': '4829ae1bb824ac289a3328b92ad2bccb99c78d2b883a548fb24d9e08064dc5df',
    'reports/phase_6_10_4/offline-regression.txt': 'e6b35621084075b5591bba50de64fd584abf01e50d4b1abd0dce47135bed8832',
    'reports/phase_6_10_5_1/broker-support-inquiry.md': 'bb8dc4d2c6368e3dde4efb86c0776117b3da6ecf4c46c87965630fc428f1e6f1',
    'reports/phase_6_10_5_1/offline-regression.txt': '0ab3a8996425ff788b4807a52ac3b30679d266196bd3d4d451801110f37b5762',
    'reports/phase_6_10_5_1/phase-artifacts.sha256': '57a5976bd6bd408c6913faa52a9b64dcffbf880c95eb81bbc0ca6c39a153bf99',
    'reports/phase_6_10_5_1/precision-validation.json': '8946c573024c626328b3248f42873ed1b16dd65247487c5442c14b14412e255b',
    'reports/phase_6_10_5_1/preserved-after.sha256': 'ebb9f40d23bd267fddfcdb3838717de20807b0f9cb679165dfcb2c8b9e681524',
    'reports/phase_6_10_5_1/preserved-before.sha256': 'ebb9f40d23bd267fddfcdb3838717de20807b0f9cb679165dfcb2c8b9e681524',
    'reports/phase_6_10_5_1/risk-impact.json': 'fad993feb56e1f58d51ea2fbffba7fd0d8860d9be9a4bc780d9f0f12f040abea',
    'reports/phase_6_10_5_1/verification.md': 'a3de18c0cf4009921ee1e1f2608a2e8d5990b705ff41c7268313274849f4920b',
    'reports/phase_6_10_5_2/broker-support-inquiry.md': 'ae52d77c0110fc449268243a10c3307dfe1750b39772e4bece088c9ede59c032',
    'reports/phase_6_10_5_2/offline-regression.txt': '5e241c58e18ff01e9348629d9eea534f5f6b7511b854ce93a901837440ded786',
    'reports/phase_6_10_5_2/phase-artifacts.sha256': '04b36d2911f199be63ac1eb041a47ad895b2fed373f9693d3ef38d9eef80b263',
    'reports/phase_6_10_5_2/preserved-after.sha256': 'f5da6d492842fa0cf70a5248802adae947b0246a4ffa60f5f9848977bde28e67',
    'reports/phase_6_10_5_2/preserved-before.sha256': 'f5da6d492842fa0cf70a5248802adae947b0246a4ffa60f5f9848977bde28e67',
    'reports/phase_6_10_5_2/risk-day-verification.json': '88f05bf80e4a720b769ef508b5ff481d2550bda44d21859cc73a24ca89363848',
    'reports/phase_6_10_5_2/session-evidence.json': 'f8f71d1023d21b003861be8dc4b2d8c1264e6fbc2dcad176a4f32719f29e3469',
    'reports/phase_6_10_5_2/timestamp-verification.json': '0e8ccb596a0dbc000b3a097060e9a1af1afc66f06a01a260f36b80bf21770166',
    'reports/phase_6_10_5_2/verification.md': 'de1f59b53ad83bc37dca4f34183f7e1370070a273f65e79bb6c467f8c122f493',
    'reports/phase_6_10_5_3/data-manifest.json': '965f9f2bdc21f2c276ec1fa417fd8b84c630390d4704f564c1c205517a01f3c1',
    'reports/phase_6_10_5_3/data-quality.json': '370e43e7d5380e6f678e1e2d5303a9e4b3f7e0701d9d3a9319704ecd46f3613c',
    'reports/phase_6_10_5_3/historical-readiness.json': '5a7430eadafbbf5e07ac2fa20c87df27b0e1e839dfd7e8378beef01d72053401',
    'reports/phase_6_10_5_3/offline-regression.txt': '8e0fcfb4c6f468eb92f0d6742a19e8a6749bf853f5e6490057eca60089d86d0e',
    'reports/phase_6_10_5_3/phase-artifacts.sha256': '119711cd528b24174e99c504c60aec69617482299d8f87ba203f4c6a77db22c6',
    'reports/phase_6_10_5_3/preserved-after.sha256': '2da1cfb58558fb5e83509395f43c0688280a8cffd1475e1e3fa0cb8b6dfa2734',
    'reports/phase_6_10_5_3/preserved-before.sha256': '2da1cfb58558fb5e83509395f43c0688280a8cffd1475e1e3fa0cb8b6dfa2734',
    'reports/phase_6_10_5_3/source-comparison.md': '5c4bf08703f562e5127aa84e5380f29f91a649f60297d26e6891afd547314b26',
    'reports/phase_6_10_5_3/source-evidence.md': '383d1a51d7707c767ed6ad7af5c988af1ddd3662ea60bab9ecc5e70afefd6447',
    'reports/phase_6_10_5_3/verification.md': '7b9c8def7c899e95a158b86ae07dd2da98008d59c4477d7336f223cb2e562ef9',
    'reports/phase_6_10_5_4/broker-support-inquiry.md': 'bf7147ddf5e1ef2dd16f54463a501da32b20b7c862fa23af100e41cf2780c362',
    'reports/phase_6_10_5_4/capital-feasibility.json': '8024bc7f31306af38d36229dc3a11b5a0397eb253b80f9bb53401d91e86febf1',
    'reports/phase_6_10_5_4/cost-evidence.md': 'c83c8da1a74cff842f34835baf4ffc9793365174daecab411785a1e8b85daffb',
    'reports/phase_6_10_5_4/offline-regression.txt': '929dea2bab89b5b6c2412c0321232dbe2d62076ceeea7cf570f75d71696e3530',
    'reports/phase_6_10_5_4/phase-artifacts.sha256': 'd6a97d4d8ab2667f52c8dd46f33f953078bc8b2e5a8532f96c0d440249ac6d56',
    'reports/phase_6_10_5_4/preserved-after.sha256': '13505cc5c34b46cffd08ef83a4393306a72f81e476987b3bf4fa50e29a1bbc39',
    'reports/phase_6_10_5_4/preserved-before.sha256': '13505cc5c34b46cffd08ef83a4393306a72f81e476987b3bf4fa50e29a1bbc39',
    'reports/phase_6_10_5_4/rejection-analysis.json': 'b8ac6223f88fabc471dbb41bbb993926b8c3405c4dc3bfa5b5fc8ca8312fd218',
    'reports/phase_6_10_5_4/verification.md': '91f2459e78e6300c514b58f13261e3eb57faf51d11d8bc3b46e743b87bb43ec7',
    'reports/phase_6_10_5_4/volatility-analysis.json': '6450528dec27bf0471bc0bf9c5a43bd6c5e5fad869579275663a5ba9f58b7446',
    'reports/phase_6_9_6/assessment.json': '2fe1c592f86cc84cbb722dab14b5c3d853b6e863c91aaad28e4317c45a2b8adb',
    'tests/test_capital_feasibility_phase_61054.py': '492bcf68c4aa6cd878e4ab1a33ca34c0b7afe1f00721a4ea913dde7911a21965',
    'tests/test_exness_precision_phase_61051.py': 'cbdf7574a08879434073fb54757546999ed9bc51335983eb54d3b2e05b450595',
    'tests/test_exness_time_phase_61052.py': '7f6c044146d94c3ce7ef04f7c2373ff07eef4dbec74daa637fa372283a6fb316',
    'tests/test_historical_sources_phase_61053.py': '754576634e1a9da57459b855ddefaecd0b5b14cb9ac519dffa871f7b9711b607',
    'tools/capital_feasibility_phase_61054.py': '1c83be50d2bb97da022a22b51b55622ba3702fbe58fa24c27241ad03f2ef410c',
    'tools/compare_strategies_phase_6104.py': '86ea05cab69f687f2e8e0ccfcaec376f0a62841ce1b21847b9de2d47484c49f2',
    'tools/dukascopy_sample.py': '25ccd60b8d87f4745d507e8503e98ed5d3f54278e8ed72ea6fa331fb610918c7',
    'tools/histdata_sample.py': 'e427b36c82915d94d2a04f9d7a2c64c76f252ea25f678f440941abe4102e5ef4',
    'tools/sample_exness_history_phase_61053.py': '921af92b0563f7e6842e9f0ed7cce07f54118bc60b479f9d772d56e6c9eb0bc3',
    'tools/verify_exness_precision_phase_61051.py': '029b19816219daccee627bc479ec333a97b84f8c3e489acdee7874c8c095dd75',
    'tools/verify_exness_time_phase_61052.py': 'a68d68a131da7fc248181a60c867031eb783cddfd27fc6d521d14487ce8ce97d',
}
