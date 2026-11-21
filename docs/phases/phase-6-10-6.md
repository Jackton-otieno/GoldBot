# Phase 6.10.6 prospective validation protocol

**Engineering complete. Protocol approval and intake blocked.
GoldBot remains NO-GO.** The existing Phase 6.9.6 gate governs authorization.
[Readiness decisions](../../reports/phase_6_10_6/readiness.json)

The registry preserves the Phase 6.6 baseline and all three Phase 6.10.3
alternatives evaluated in Phase 6.10.4. Each has separate M15 and H1 cohorts.
It pins implementation hashes, exact entry parameters, the shared risk
configuration, and the former synthetic cost scenarios. The phase selected
no winner. The old cost scenarios are comparison references. An actual
prospective evaluator, source, configuration, environment and effective cost
rules need to be frozen before approval.
[Registry](../../reports/phase_6_10_6/candidate-registry.json) ·
[Earlier comparison](phase-6-10-4.md)

| Decision | Status |
| --- | --- |
| Offline engineering | PASS |
| Protocol preparation | DRAFT READY. Registration preparation still needs source, evaluator, cost and exposure evidence. |
| Protocol approval and registration | BLOCKED. No independent approval or pre-start registration receipt. |
| Prospective data intake | BLOCKED. Exact source and UTC coverage remain unverified, and no prospective capture is sealed. |
| Automated demo authorization | BLOCKED under Phase 6.9.6. |
| Live trading authorization | BLOCKED under Phase 6.9.6. |

## Offline registration and eligibility

The draft proposes 1 February 2027 at 00:00 UTC through 1 February 2028
at 00:00 UTC, end exclusive, including warmup. The protocol sets out the
proposed scoring, stopping, violation and independence rules.
[Proposed protocol](../../reports/phase_6_10_6/proposed-protocol.md)

The offline library exposes three operations.

1. `prepare_registration` builds a canonical commitment from the exact
   strategies and risk definitions, original exposure inventory, verified
   prior UTC envelopes, additional exposed-source digests, evaluator,
   environment, source scope, execution/cost rules and scoring policy.
   It refuses an incomplete prior map or an interval extending into the
   proposed period.
2. `review_registration` recomputes that commitment from current input
   bytes, then verifies independent approval and registration receipts
   strictly before the proposed start. The verifier must bind canonical
   signer identity, role, digest, and verified UTC time to each receipt.
3. `review_intake` checks the pre-start commitment again, requires the
   finished horizon and contiguous bounded chunks, checks source scope,
   exclusion of previously exposed and retrospectively selected data,
   rehashes payload bytes, and checks timely UTC custody receipts. An
   independent post-horizon reviewer must attest the combined intake
   manifest and provenance. The technical result is eligibility for
   research review. The authorization result remains separate.

A caller must configure an independent verifier and supply the actual
component and evidence bytes. The verifier is responsible for trust roots,
canonical signer identity and roles, exact UTC time provenance, and
checking external attestations. This checkout has no live trust adapter,
approval, timestamp receipt, or sealed prospective payload. Local hashes
establish integrity of the reviewed bytes. Independent receipts establish
who attested those bytes and when.

The exposure map records six known groups, with source digests and raw
label endpoints where available. The archived candles, broker diagnostics,
journals and derived results were already inspected. Production UTC mapping
and independent attestation of complete prior exposure, including material
outside this checkout, remain unresolved. Exness monetary precision,
sessions, account-specific economics, historical-data eligibility, and
risk-day boundaries remain blockers under the consolidated assessment.
[Exposure map](../../reports/phase_6_10_6/exposure-map.json) ·
[Consolidated blockers](../../reports/phase_6_10_5_5/blocker-register.json)

## Reproduce

Use a new empty output directory from the GoldBot root.

~~~powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m tools.prepare_prospective_6106 --as-of 2026-11-21 --output <directory>
& .\.venv\Scripts\python.exe -B -m unittest discover -v
~~~

[Verification](../../reports/phase_6_10_6/verification.md)
