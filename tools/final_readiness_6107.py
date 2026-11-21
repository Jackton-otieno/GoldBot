"""Generate the final offline readiness snapshot using the existing gates."""

import argparse
from datetime import date
from decimal import Decimal
from importlib import metadata
import json
from pathlib import Path
import platform
import struct

from goldbot.backtesting.strategy_validation import FrozenManifest
from goldbot.reporting import prospective_6106 as protocol
from goldbot.reporting import readiness_61055 as consolidated
from goldbot.reporting import readiness_696 as governing


DRAFT_DIR = "reports/phase_6_10_6"
DRAFT_MANIFEST = f"{DRAFT_DIR}/phase-artifacts.sha256"
DRAFT_MANIFEST_SHA256 = "f606daa02641cb28e5a6fa4b7ea4be7f7c70b756b535b601cf0e01677300038f"
PROVENANCE_TEST = "tests/reporting/test_consolidated.py"
RESEARCH_EVIDENCE = (
    "reports/phase_6_10_1/audit.json", "reports/phase_6_10_2/verification.md",
    "reports/phase_6_10_3/verification.md", protocol.COMPARISON,
)

# Explicit closure criteria complement the assigned owners and evidence paths
# in the existing consolidated blocker register.
RESOLUTION = {
    "broker_identity_and_product": (
        1, "Obtain a redacted product card and broker confirmation; independently verify the exact pinned installation at any later attachment.",
        "Dated Exness KE account-variant confirmation and matching masked server, account, symbol, mode and installation evidence.",
        "Independent reviewer confirms exact scope; current identity guard passes before any permitted diagnostic.",
    ),
    "monetary_precision_and_booked_pnl": (
        1, "Request the rounding sequence, tie rules, and documented calculator-to-booking treatment at both sides of a cent boundary.",
        "Authoritative formula and booked-P/L examples for gains/losses, minimum volume, commission and partial closes.",
        "Independent reconciliation passes the unchanged broker validator and resolves the known discrepancy without a larger tolerance.",
    ),
    "utc_mapping_and_freshness": (
        1, "Obtain effective-dated live and archive time semantics and capture independent clock brackets under existing diagnostic controls.",
        "Raw seconds/milliseconds, request/return semantics, transition samples, offset windows and independent UTC measurements.",
        "Unique mapping covers the whole bracket; existing freshness and close-boundary checks pass under the scoped clock evidence.",
    ),
    "quote_trade_sessions_and_exceptions": (
        1, "Obtain separate dated quote/trade calendars and a versioned exception feed for the exact product.",
        "UTC quote, open, close-only and restricted intervals, DST transitions, holidays, maintenance, closure and correction notices.",
        "Validator finds a unique applicable interval, with explicit exceptional coverage and no unresolved overlaps or gaps.",
    ),
    "risk_day_and_opening_equity": (
        2, "Approve an account-specific risk-day policy, then obtain a boundary equity observation independent of the collector.",
        "Exact UTC successor boundary, documented equity calculation and positive attested equity at that instant.",
        "Existing risk-day check admits only the verified successor, and missing or conflicting evidence leaves latches in force.",
    ),
    "historical_provenance_and_coverage": (
        2, "Obtain one bounded permitted sample first, independently review lineage and gaps, then check the target interval inventory.",
        "Source and account scope, rights, original hashes, bid/ask basis, UTC encoding, coverage and exception evidence.",
        "Existing historical validator admits the intended scope or explicitly limits it to research. All unexplained gaps remain outstanding.",
    ),
    "costs_margin_and_slippage": (
        1, "Obtain dated exact-product rates and documentation of ordinary and exceptional execution.",
        "Commission and rounding, spread data, swaps/funding, margin and HMR tiers, conversion, stop-out and fill/slippage evidence.",
        "Independent reviewer reconciles the approved evaluator assumptions to dated executable evidence over the entire intended scope.",
    ),
    "minimum_volume_feasibility": (
        3, "Recheck the USD 3,000 reference with verified dates, costs, contract economics and existing risk limits.",
        "Minimum/step, validated stop geometry, actual budget and margin inputs, rejection reconciliation.",
        "Every admitted test entry fits the unchanged planner and free margin; rejected cases remain rejected and accounted for.",
    ),
    "profitability_not_demonstrated": (
        5, "Use the separately approved evaluator once on a valid sealed intake, reporting all eight cohorts together.",
        "Independent audit of each complete after-cost ledger, drawdown, sample count, and protocol violations.",
        "A candidate meets the independently approved thresholds on eligible unseen data. This finding alone grants no trading authority.",
    ),
    "prospective_registration_and_exposure": (
        4, "Complete the exposure declaration; freeze the source, evaluator, environment, costs and dates; obtain independent receipts.",
        "Signed plan and prior UTC envelopes, pre-start registration, timely custody, full horizon and independently sealed intake.",
        "Phase 6.10.6 verifies strategy identity, scope, timing and nonoverlap, and the governing gate explicitly authorizes the permitted activity.",
    ),
}
ADDITIONAL = (
    {
        "id": "phase7_operational_controls", "responsible_or_dependency": "GoldBot operator and independent operations reviewer",
        "sequence": 6, "status": "BLOCKED",
        "action": "Specify and separately verify the Phase 7 demo-only operating envelope and incident response after prerequisite gates clear.",
        "evidence_required": "Pinned demo identity, risk and reconciliation drills, stop/kill and restart drills, logs, monitoring owner and rollback checklist.",
        "acceptance_criteria": "Independent dry-run evidence passes, all applicable blockers are closed, and Phase 6.9.6 explicitly authorizes demo execution.",
        "depends_on": ["broker_identity_and_product", "risk_day_and_opening_equity", "profitability_not_demonstrated",
                       "prospective_registration_and_exposure"],
        "evidence_paths": ["reports/phase_6_9_6/assessment.json", "reports/phase_6_10_6/readiness.json"],
        "blocks": {"automated_demo_trading_authorization": True},
    },
    {
        "id": "live_authorization", "responsible_or_dependency": "GoldBot operator, live broker and independent risk reviewer",
        "sequence": 7, "status": "BLOCKED",
        "action": "Treat any live deployment as a distinct decision using live-account evidence and explicit authorization.",
        "evidence_required": "Successful separately authorized demo evidence, independently verified live scope and signed live approval.",
        "acceptance_criteria": "Every live condition passes and Phase 6.9.6 grants explicit applicable execution authorization.",
        "depends_on": ["phase7_operational_controls", "costs_margin_and_slippage"],
        "evidence_paths": ["reports/phase_6_9_6/assessment.json", "reports/phase_6_10_5_5/readiness.json"],
        "blocks": {"live_trading_authorization": True},
    },
)


def reviewed_draft(root):
    if protocol.file_hash(root / DRAFT_MANIFEST) != DRAFT_MANIFEST_SHA256:
        raise ValueError("Phase 6.10.6 manifest differs from the reviewed archive.")
    pins = dict(line.split("  ", 1)[::-1] for line in (root / DRAFT_MANIFEST).read_text().splitlines())
    for name, expected in pins.items():
        # This one later-phase discovery-list update is intentional.
        if name != PROVENANCE_TEST and protocol.file_hash(root / name) != expected:
            raise ValueError(f"Phase 6.10.6 artifact differs: {name}")
    registry = protocol.candidate_registry(root)
    if registry.envelope() != json.loads((root / DRAFT_DIR / "candidate-registry.json").read_bytes()):
        raise ValueError("Current candidate registry differs from the frozen draft.")
    if protocol.exposure_map(root).envelope() != json.loads((root / DRAFT_DIR / "exposure-map.json").read_bytes()):
        raise ValueError("Current known exposure map differs from the draft.")
    proposal = json.loads((root / DRAFT_DIR / "proposed-protocol.json").read_bytes())
    if proposal != protocol.PROPOSAL:
        raise ValueError("Current protocol differs from the frozen draft.")
    return registry, proposal, pins


def inventory(root, directories, files=()):
    paths = {root / path for path in files}
    for directory in directories:
        paths.update(path for path in (root / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    return {path.relative_to(root).as_posix(): protocol.file_hash(path) for path in sorted(paths)}


def comparison_summary(root):
    data = protocol.checked_json(root, protocol.COMPARISON)
    scenarios = [list(candidate["scenarios"].values()) for frame in data["timeframes"].values()
                 for candidate in frame.values()]
    runs = [run for cohort in scenarios for run in cohort]
    closures = [len(run["closed_trades"]) for run in runs]
    return dict(source_sha256=protocol.FIXED[protocol.COMPARISON], runs=len(runs),
                closed_trades_per_run_range=[min(closures), max(closures)],
                cohorts_positive_across_all_costs=sum(
                    all(Decimal(run["terminal_marked_pnl"]) > 0 for run in cohort)
                    for cohort in scenarios))


def external_dependencies(register):
    if {item["id"] for item in register} != RESOLUTION.keys():
        raise ValueError("Consolidated blocker set changed; review closure criteria.")
    entries = []
    for item in register:
        order, action, evidence, acceptance = RESOLUTION[item["id"]]
        entries.append(dict(item, sequence=order, action=action, evidence_required=evidence,
                            acceptance_criteria=acceptance))
    return sorted([*entries, *ADDITIONAL], key=lambda item: (item["sequence"], item["id"]))


def build(root, as_of):
    legacy = governing.assess(root, as_of)
    earlier = consolidated.build(root, as_of)
    inherited = earlier["readiness.json"]["assessments"]
    registry, proposal, draft_files = reviewed_draft(root)
    reference = registry.envelope()["manifest"]
    requirement = (root / "requirements.txt").read_text().strip()
    installed = {item.metadata["Name"]: item.version for item in metadata.distributions()}
    mt5 = metadata.version("MetaTrader5")
    runtime_matches = requirement == f"MetaTrader5=={mt5}"
    engineering = runtime_matches and inherited["offline_engineering_completeness"]["status"] == "PASS"
    common = {"as_of": as_of.isoformat(), "overall": legacy.decision}
    baseline = FrozenManifest.create({
        "schema": "goldbot.engineering-baseline.v1",
        "code_config_and_tests_sha256": inventory(
            root, ("goldbot", "tools", "tests"), ("main.py", "requirements.txt", "README.md", ".gitignore")),
        "data_files_sha256": inventory(root, ("data", "historical_data")),
        "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                    "platform": platform.system(), "architecture_bits": struct.calcsize("P") * 8,
                    "declared_requirements": [requirement], "observed_distributions": installed,
                    "requirements_match": runtime_matches},
        "regression_environment": {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        "reproducibility": {
            "commands": ["python -B -m tools.final_readiness_6107 --as-of 2026-11-21 --output <fresh-directory>",
                         "python -B -m unittest discover -v"],
            "dashboard_expected_count": 13, "require_byte_identical_reports": True,
            "requires_review_for_changes": ["strategy", "risk", "runtime", "source", "execution rules",
                                            "scope", "dates", "thresholds", "evaluator"],
        },
        "risk_configuration": reference["risk"],
        "candidate_registry_sha256": registry.sha256,
        "draft_artifacts_sha256": draft_files,
        "historical_data_manifest_sha256": protocol.file_hash(
            root / "reports/phase_6_10_5_3/data-manifest.json"),
        "research_evidence_sha256": inventory(root, (), RESEARCH_EVIDENCE),
        "prior_readiness_source_sha256": {
            row["path"]: row["expected_sha256"] for row in earlier["evidence-manifest.json"]["sources"]
        },
    })
    decisions = {
        "offline_engineering": {"status": "PASS" if engineering else "BLOCKED",
                                "inherited_integrity": inherited["offline_engineering_completeness"]},
        "retrospective_research": inherited[consolidated.RESEARCH],
        "protocol_approval": {"status": "BLOCKED", "approved": False,
                              "reason": "No verified independent approval or registration receipt"},
        "prospective_data_intake": dict(inherited[consolidated.ADMIT], authorized=legacy.prospective_authorized),
        "automated_demo_trading": {"status": "BLOCKED", "authorized": legacy.execution_authorized},
        "live_trading": {"status": "BLOCKED", "authorized": legacy.execution_authorized},
    }
    return {
        "final-readiness.json": dict(common, decisions=decisions, cohorts=reference["cohorts"],
                                    frozen_draft_verified=True, external_registration_verified=False,
                                    candidate_registry_sha256=registry.sha256,
                                    phase_6_9_6=earlier["readiness.json"]["phase_6_9_6"],
                                    comparison=comparison_summary(root), observation_period={
                                        "proposal": proposal, "approved": False,
                                        "calendar_days": (protocol.PROPOSED_WINDOW.end - protocol.PROPOSED_WINDOW.start).days,
                                        "assessment_calendar_day_precedes_start": as_of < protocol.PROPOSED_WINDOW.start.date(),
                                    }),
        "engineering-baseline.json": dict(common, **baseline.envelope()),
        "external-dependencies.json": dict(common, dependencies=external_dependencies(
            earlier["blocker-register.json"]["blockers"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for name, content in build(root, args.as_of).items():
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as output:
            json.dump(content, output, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
            output.write("\n")


if __name__ == "__main__":
    main()
