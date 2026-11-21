"""Prepare and review a sealed research protocol without granting authorization."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import file_digest
import json
from pathlib import Path
import re

from goldbot.backtesting.historical_replay import ORIGINAL_DIGESTS
from goldbot.backtesting.prospective_validation import REQUIRED_EVIDENCE, Window
from goldbot.backtesting.sensitivity_analysis import SCENARIOS, execution_spec
from goldbot.backtesting.strategy_validation import FrozenManifest, sha256
from goldbot.reporting.readiness_696 import assess
from goldbot.reporting.readiness_61055 import build as assess_readiness


UTC = timezone.utc
PROPOSED_WINDOW = Window(datetime(2027, 2, 1, tzinfo=UTC), datetime(2028, 2, 1, tzinfo=UTC))
BASELINE = "reports/validation_phase_6_6/validation.json"
ALTERNATIVES = "tools/research_strategies_phase_6103.py"
COMPARISON = "reports/phase_6_10_4/comparison.json"
FIXED = {
    BASELINE: "ada9c5d23978a2e97a0754ab37397318b786b086a9478553ecbf39432170a123",
    ALTERNATIVES: "a7292bb9c47673efed29909d15b326cec8b0c4aa6a41e2295c81708466cb75fb",
    COMPARISON: "4829ae1bb824ac289a3328b92ad2bccb99c78d2b883a548fb24d9e08064dc5df",
}
COMPONENTS = frozenset({"source_scope", "evaluator", "environment", "execution_cost_rules"})
INTAKE_EVIDENCE = REQUIRED_EVIDENCE | {"fixed-selection-and-exposure"}
PROPOSAL = {
    "version": "phase-6.10.6-draft-1",
    "window_utc": PROPOSED_WINDOW.record(),
    "window_includes_warmup": True,
    "minimum_closed_trades_per_cohort": 100,
    "net_after_all_costs_usd": ">0",
    "profit_factor": ">=1.3; positive wins with zero losses are +infinity",
    "maximum_observed_drawdown_fraction": "<0.10",
    "allowed_protocol_violations": 0,
    "maximum_chunk_duration_hours": 24,
    "maximum_custody_attestation_delay_hours": 24,
    "thresholds_status": "PROPOSED_REQUIRES_INDEPENDENT_APPROVAL",
    "horizon_policy": "Fixed end; no peeks, extensions, early success, or replacements",
    "violations": [
        "lookahead, premature evaluation access, or retrospective sampling",
        "unapproved code, data, costs, risk, dates, or configuration changes",
        "unknown source identity, unexplained coverage, or unverified timestamps",
        "missing/contradictory receipts, lineage, cost evidence, or risk records",
        "unsupported fill or sizing, risk-limit breach, or unresolved terminal exposure",
    ],
}
ENTRYPOINTS = {
    "baseline": "evaluate", "trend_pullback_ema_rsi": "trend_pullback",
    "breakout_donchian": "donchian_breakout",
    "mean_reversion_bollinger_rsi": "bollinger_reversion",
}

# Grouped references cover known inspected raw feeds and diagnostics. Derived
# output inherits exposure and supplies no extra independent period.
EXPOSURES = {
    "legacy_M15": ("data/XAUUSD_M15.csv",),
    "legacy_H1": ("data/XAUUSD_H1.csv",),
    "metaquotes_diagnostics": (
        "reports/phase_5_2_broker_diagnostic.json", "reports/phase_6_8_1/current-demo.json",
        "reports/phase_6_8_2/initial-demo.json", "reports/phase_6_8_2/repeat-demo.json",
        "reports/phase_6_8_2/current-demo.json", "reports/phase_6_8_2/dst-2025.json",
        "reports/phase_6_8_2/dst-2026.json", "reports/phase_6_8_3/demo-session-metadata.json",
        "reports/phase_6_8_4/demo-tick-samples.json",
    ),
    "exness_broker_diagnostics": (
        "reports/phase_6_9_2/connectivity.json", "reports/phase_6_9_3/initial-probes.json",
        "reports/phase_6_9_3/probes.json", "reports/phase_6_9_3_1/probes.json",
        "reports/phase_6_9_4/diagnostic.json", "reports/phase_6_9_4_1/diagnostic.json",
        "reports/phase_6_10_5_1/precision-validation.json",
    ),
    "exness_read_only_journals": (
        "reports/phase_6_9_5/diagnostic.sqlite3", "reports/phase_6_9_6/boundary.sqlite3",
    ),
    "exness_timestamp_and_history_pilots": (
        "reports/phase_6_10_5_2/timestamp-verification.json",
        "reports/phase_6_10_5_3/data-manifest.json",
        "historical_data/phase_6_10_5_3/exness-mt5/xauusd-raw-ticks.json",
    ),
}
RAW_LABELS = {"legacy_M15": [1781128800, 1794930300], "legacy_H1": [1740704400, 1794927600]}


def file_hash(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def checked_json(root, path):
    content = (root / path).read_bytes()
    if sha256(content) != FIXED[path]:
        raise ValueError(f"Pinned reference differs: {path}")
    return json.loads(content)


def candidate_registry(root):
    archived = checked_json(root, BASELINE)["strategy"]
    baseline = archived["manifest"]
    if FrozenManifest.create(baseline).sha256 != archived["sha256"]:
        raise ValueError("Invalid Phase 6.6 freeze.")
    code = {f"goldbot/{name}": digest for name, digest in baseline["package_source_sha256"].items()}
    code[ALTERNATIVES] = FIXED[ALTERNATIVES]
    if any(file_hash(root / name) != digest for name, digest in code.items()):
        raise ValueError("Frozen strategy or shared implementation bytes changed.")
    parameters = {
        "baseline": dict(
            version="Phase 6.6 frozen baseline", ema=[9, 21, 50, 200], macd=[12, 26, 9],
            rsi_period=14, rsi_bounds=baseline["rsi_thresholds"], atr_period=14,
            gap_crossovers="HOLD", entry="EMA 9/21 cross with EMA 50/200 trend, RSI band and MACD sign",
            rules=baseline["strategy"], first_valid_rows=baseline["indicator_first_valid_rows"],
        ),
        "trend_pullback_ema_rsi": dict(version="Phase 6.10.3", ema_period=20, rsi_period=14,
                                      rsi_midpoint=50, first_segment_bar=21,
                                      entry="EMA slope, close reclaims EMA and RSI confirms"),
        "breakout_donchian": dict(version="Phase 6.10.3", prior_candles=20, first_segment_bar=21,
                                 entry="Strict close above prior highs or below prior lows"),
        "mean_reversion_bollinger_rsi": dict(version="Phase 6.10.3", bollinger_period=20,
                                            population_stddev_multiple=2, rsi_period=14,
                                            rsi_bounds=[30, 70], first_segment_bar=20,
                                            entry="Strict band excursion and inclusive RSI extreme"),
    }
    compared = checked_json(root, COMPARISON)["timeframes"]
    if set(compared) != {"M15", "H1"} or any(set(records) != set(parameters) for records in compared.values()):
        raise ValueError("Candidate set differs from Phase 6.10.4.")
    reference_costs = {}
    for name, cost in SCENARIOS:
        spec = execution_spec(name, cost)
        reference_costs[name] = {
            "spread_usd_per_oz": spec.spread, "entry_slippage_usd_per_oz": spec.entry_slippage,
            "stop_slippage_usd_per_oz": spec.stop_slippage,
            "round_trip_commission_usd_per_lot": spec.round_trip_commission_per_lot,
            "fixed_margin_usd_per_lot": spec.margin_per_lot, "price_grid": spec.broker.tick_size,
            "minimum_lot": spec.broker.volume_min, "lot_step": spec.broker.volume_step,
            "funding_modeled": False,
        }
    return FrozenManifest.create({
        "schema": "goldbot.prospective.candidates.v2", "symbol": "XAUUSD",
        "source_sha256": code, "baseline_freeze_sha256": archived["sha256"],
        "comparison_sha256": FIXED[COMPARISON], "risk": baseline["risk"],
        "candidate_parameters": parameters,
        "cohorts": [{"strategy": name, "timeframe": frame,
                     "implementation": "goldbot/strategy/strategy.py" if name == "baseline" else ALTERNATIVES,
                     "entrypoint": ENTRYPOINTS[name],
                     "risk_atr_period": 14, "isolated_reference_equity_usd": "3000"}
                    for name in parameters for frame in ("M15", "H1")],
        "retrospective_cost_references_only": reference_costs,
        "prospective_cost_rules": "UNVERIFIED_MUST_FREEZE_BEFORE_APPROVAL",
        "alternative_signal_gap_policy": "Restart in each contiguous segment",
        "winner_selected": False,
    })


def exposure_map(root):
    records = {}
    for group, paths in EXPOSURES.items():
        sources = {name: file_hash(root / name) for name in paths}
        if group.startswith("legacy_") and sources[paths[0]] != ORIGINAL_DIGESTS[group.split("_")[1]]:
            raise ValueError("Original exposed candle bytes changed.")
        records[group] = {"sources": sources, "raw_label_endpoints": RAW_LABELS.get(group),
                          "verified_utc": None, "prospective_eligible": False}
    return FrozenManifest.create({
        "groups": records, "known_inventory_only": True, "outside_repository_attested": False,
        "derived_results": "All prior partitions, strategy comparisons and analyses inherit source exposure.",
        "raw_boundary_policy": "Supply attested coverage including final bar span and every diagnostic interval.",
    })


def digest_bytes(data):
    if type(data) is not bytes or not data:
        raise ValueError("Nonempty evidence bytes are required.")
    return sha256(data)


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def prepare_registration(root, components, exposure_windows, additional_sources):
    """Build the exact candidate, rules, scope and exposure commitment."""
    registry = candidate_registry(root)
    known = exposure_map(root)
    if set(components) != COMPONENTS:
        raise ValueError("Incomplete evaluator, environment, cost rules or source scope.")
    if (set(known.envelope()["manifest"]["groups"]) & additional_sources.keys()
            or any(not key.strip() or not valid_digest(value) for key, value in additional_sources.items())):
        raise ValueError("Invalid additional exposure inventory.")
    if set(exposure_windows) != EXPOSURES.keys() | additional_sources.keys():
        raise ValueError("Complete independently mapped prior UTC coverage is required.")
    for prior in exposure_windows.values():
        if not isinstance(prior, Window) or prior.end > PROPOSED_WINDOW.start:
            raise ValueError("Prior exposure overlaps the proposed period or is unverifiable.")
    return FrozenManifest.create({
        "schema": "goldbot.prospective-registration.v2",
        "proposal": dict(PROPOSAL, window_utc=PROPOSED_WINDOW.record()),
        "candidate_registry_sha256": registry.sha256, "known_exposure_sha256": known.sha256,
        "additional_exposure_sources": additional_sources,
        "prior_exposure_utc": {name: window.record() for name, window in exposure_windows.items()},
        "freeze": {name: digest_bytes(data) for name, data in components.items()},
        "required_intake_evidence": sorted(INTAKE_EVIDENCE),
    })


@dataclass(frozen=True)
class Attestation:
    signer: str
    at: datetime


def receipt(verify, role, manifest, proof):
    if not isinstance(proof, bytes) or not proof:
        raise ValueError(f"Missing {role} receipt.")
    result = verify(role, manifest.sha256, proof)
    if (not isinstance(result, Attestation) or not isinstance(result.signer, str)
            or not result.signer or result.signer != result.signer.strip()
            or not isinstance(result.at, datetime)
            or result.at.utcoffset() != timedelta(0)):
        raise ValueError(f"Unverifiable {role} attestation.")
    return result


def _verify_registration(committed, current, approval_proof, registration_proof, *, now, verify):
    if not isinstance(now, datetime) or now.utcoffset() != timedelta(0):
        raise ValueError("Assessment time must be explicit UTC.")
    if (not isinstance(committed, FrozenManifest) or not isinstance(current, FrozenManifest)
            or committed.canonical != current.canonical):
        raise ValueError("Registration conflicts with current strategy, scope, evidence or rules.")
    approved = receipt(verify, "approval", committed, approval_proof)
    registered = receipt(verify, "registration", committed, registration_proof)
    if (approved.signer == registered.signer or not approved.at <= registered.at <= now
            or registered.at >= PROPOSED_WINDOW.start):
        raise ValueError("Independent approval and registration must precede the start.")
    return approved, registered


def review_registration(root, *, committed, components, exposure_windows, additional_sources,
                        approval_proof, registration_proof, now, verify):
    """Check the pre-start commitment and independent receipts against current bytes."""
    try:
        current = prepare_registration(root, components, exposure_windows, additional_sources)
        _verify_registration(committed, current, approval_proof, registration_proof,
                             now=now, verify=verify)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return {"status": "BLOCKED", "reason": str(error)}
    except Exception:
        return {"status": "BLOCKED", "reason": "Independent verifier failed"}
    return {"status": "REGISTRATION_VERIFIED", "registration_sha256": current.sha256}


@dataclass(frozen=True)
class Chunk:
    interval: Window
    path: Path
    sha256: str
    source_scope_sha256: str
    previously_exposed: bool
    selection: str
    custody_proof: bytes

    def manifest(self):
        return FrozenManifest.create({
            "utc": self.interval.record(), "sha256": self.sha256,
            "source_scope_sha256": self.source_scope_sha256,
            "previously_exposed": self.previously_exposed, "selection": self.selection,
        })


def review_intake(root, *, committed, components, exposure_windows, additional_sources,
                  approval_proof, registration_proof, chunks, evidence, intake_proof, now, verify):
    """Evaluate technical eligibility only. Never use receipt data as trading authority."""
    try:
        current = prepare_registration(root, components, exposure_windows, additional_sources)
        approval, registration = _verify_registration(
            committed, current, approval_proof, registration_proof, now=now, verify=verify)
        if now < PROPOSED_WINDOW.end or not INTAKE_EVIDENCE <= evidence.keys():
            raise ValueError("Fixed horizon or mandatory provenance evidence is incomplete.")
        already_exposed = {digest for row in exposure_map(root).envelope()["manifest"]["groups"].values()
                           for digest in row["sources"].values()} | set(additional_sources.values())
        cursor = PROPOSED_WINDOW.start
        chunk_hashes, custodians, seen = [], set(), set()
        scope = digest_bytes(components["source_scope"])
        for chunk in chunks:
            if (chunk.interval.start != cursor or chunk.interval.end > PROPOSED_WINDOW.end
                    or chunk.interval.end - cursor > timedelta(hours=24)):
                raise ValueError("Chunk coverage is unordered, overlapping, incomplete or out of bounds.")
            if (chunk.previously_exposed is not False or chunk.selection != "fixed-window-capture"
                    or not valid_digest(chunk.sha256) or chunk.sha256 in already_exposed | seen
                    or chunk.source_scope_sha256 != scope):
                raise ValueError("Exposed, duplicate, retrospectively selected or unverified source chunk.")
            chunk_manifest = chunk.manifest()
            custody = receipt(verify, "custody", chunk_manifest, chunk.custody_proof)
            if not chunk.interval.end <= custody.at <= min(now, chunk.interval.end + timedelta(hours=24)):
                raise ValueError("Chunk lacks timely independent UTC custody evidence.")
            if file_hash(chunk.path) != chunk.sha256:
                raise ValueError("Chunk bytes differ from the immutable manifest.")
            cursor = chunk.interval.end
            seen.add(chunk.sha256)
            custodians.add(custody.signer)
            chunk_hashes.append(chunk_manifest.sha256)
        if cursor != PROPOSED_WINDOW.end:
            raise ValueError("Complete fixed-window chunk coverage is required.")
        manifest = FrozenManifest.create({
            "registration_sha256": committed.sha256, "chunk_manifest_sha256": chunk_hashes,
            "evidence_sha256": {name: digest_bytes(data) for name, data in evidence.items()},
        })
        reviewer = receipt(verify, "intake", manifest, intake_proof)
        if (len({approval.signer, registration.signer, reviewer.signer}) != 3
                or custodians & {approval.signer, registration.signer, reviewer.signer}
                or not PROPOSED_WINDOW.end <= reviewer.at <= now):
            raise ValueError("Independent post-horizon review and separated roles are required.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return {"status": "BLOCKED", "reason": str(error)}
    except Exception:
        return {"status": "BLOCKED", "reason": "Independent verifier failed"}
    return {"status": "ELIGIBLE_FOR_RESEARCH_REVIEW", "intake_manifest": manifest.envelope()}


def readiness(root, as_of):
    gate = assess(root, as_of)
    inherited = assess_readiness(root, as_of)["readiness.json"]["assessments"]
    engineering = inherited["offline_engineering_completeness"]["status"]
    try:
        candidate_registry(root)
        exposure_map(root)
    except (OSError, ValueError, KeyError):
        engineering = "BLOCKED"
    return {
        "as_of": as_of.isoformat(), "overall": gate.decision,
        "engineering_completion": engineering,
        "protocol_preparation": {"status": "DRAFT_READY" if engineering == "PASS" else "BLOCKED",
                                 "registration_ready": False,
                                 "missing": sorted(COMPONENTS | {"attested_complete_prior_exposure"})},
        "protocol_approval": {"status": "BLOCKED", "reason": "Independent approval and registration absent"},
        "prospective_data_intake_admission": {
            "status": "BLOCKED", "authorized": gate.prospective_authorized,
            "reason": "Unapproved protocol; no trusted receipt, verified source or sealed prospective payload",
            "inherited_blockers": inherited["prospective_validation_admission"]["blockers"],
        },
        "automated_demo_authorization": {"status": "BLOCKED", "authorized": gate.execution_authorized},
        "live_trading_authorization": {"status": "BLOCKED", "authorized": gate.execution_authorized},
    }
