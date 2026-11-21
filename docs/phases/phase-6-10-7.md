# Phase 6.10.7 final readiness assessment

**Offline engineering PASS. GoldBot remains NO-GO for prospective intake,
automated demo execution and live trading.** Assessed 21 November 2026,
Africa/Nairobi. Phase 6.9.6 retains authorization authority.
[Final readiness](../../reports/phase_6_10_7/final-readiness.json)

| Decision | Result |
| --- | --- |
| Offline engineering | PASS for the verified checkout and recorded runtime |
| Retrospective research | The original exposed candles retain scoped eligibility for frozen hypothetical research. New research-data admission remains blocked. |
| Protocol approval | BLOCKED. The draft is frozen locally and remains unapproved and unregistered externally. |
| Prospective data intake | BLOCKED. Source scope, full prior exposure, cost and UTC evidence, and independent receipts remain outstanding. |
| Phase 7 automated demo | BLOCKED by Phase 6.9.6. No Phase 7 operating approval or eligible prospective results are present. |
| Live trading | BLOCKED by Phase 6.9.6. Live-account evidence and separate authorization are absent. |

## Evidence reviewed

Phase 6.10.1 reconciled the earlier hypothetical baseline. Phase 6.10.2
described market regimes, with uneven indicator warmup and coverage in the
gap-affected data. Phase 6.10.3 recorded three alternative strategy rules.
Phase 6.10.4 compared all four strategies on M15 and H1. Across 32 runs,
each closed four to nine trades, and no cohort was positive across all
four cost scenarios. Higher theoretical capital can change minimum-lot
feasibility. The retrospective results supply no new profitability evidence.
[Trade audit](phase-6-10-1.md) · [Market regime analysis](phase-6-10-2.md) ·
[Alternative rules](phase-6-10-3.md) · [Controlled comparison](phase-6-10-4.md)

The Phase 6.10.5 investigations left the following dependencies unresolved.

- **Broker and account.** Exact product variant, monetary precision and
  booked P/L, historical UTC mapping, live quote freshness, and dated quote
  and trade sessions and exceptions. The calculator fit and conditional
  clock bracket are observations with limited scope.
- **Risk and costs.** Approved daily reset and attested opening equity,
  executable fees and funding, slippage and margin tiers, and verified
  minimum-lot feasibility at the unchanged risk budget.
- **Data and validation.** No new research dataset or execution-grade history
  passed admission. Prior exposure and external sources need independent
  UTC attestation. A verified evaluator, pre-start receipt and sealed
  post-horizon intake are absent.

[Consolidated blockers](../../reports/phase_6_10_5_5/blocker-register.json) ·
[External resolution register](../../reports/phase_6_10_7/external-dependencies.json)

## Frozen observation proposal

The assessment rehashed the Phase 6.10.6 artifact inventory and regenerated
the cohort registry and exposure map from the actual files. All eight
cohorts match the local draft, including strategy parameters, implementation
hashes, hypothetical cost references, and unchanged risk settings.
The proposed window is **[1 February 2027 00:00 UTC, 1 February 2028 00:00
UTC)**, equivalent to 03:00 Nairobi time on both dates. Its 365 days include
warmup. It was still in the future at assessment. No approved start, source,
independent precommitment or collection exists. If prerequisite approvals
miss the start, this proposal cannot qualify retroactively. A successor
proposal requires fresh review and precommitment before exposure to its
data.
[Frozen draft](../../reports/phase_6_10_6/proposed-protocol.md)

| Outcome | Treatment under the proposed protocol |
| --- | --- |
| Fewer than 100 closed trades per cohort | INCONCLUSIVE. Keep the fixed end and publish the observed count. |
| Unavailable or unverifiable data, incomplete custody, or missing approval | Block intake. If an independently reviewed study was underway, report the affected cohort as INCONCLUSIVE where eligibility or results cannot be established. |
| Confirmed protocol violation | FAIL the affected cohort. Record the violation and scope. Confirmed unresolved exposure at the end is a violation under this draft. If available records cannot establish whether the account is flat, treat the evidence as INCONCLUSIVE. |
| Complete, compliant results miss an economic threshold | FAIL that cohort. The proposed thresholds remain strictly positive net P/L after costs, profit factor at least 1.3, and drawdown below 10%. |
| All proposed criteria met | A cohort can pass only under a separately approved protocol with independent verification. Publish all eight outcomes together. No automatic promotion, rerun or trading authorization follows. |

No threshold reductions, early success stops, substitutions, performance
peeks, or retrospective extensions. A documented safety stop may leave
a cohort inconclusive. These rules describe the frozen proposal and do not
alter the earlier two-cohort offline scorer or supply an approved evaluator
for the eight-cohort protocol.

## Controlled engineering baseline

The baseline records the exact source, test, configuration and input
hashes, observed runtime and distribution versions, and the archived
evidence digests. The verified environment is 64-bit CPython 3.11.9 on
Windows with MetaTrader5 5.0.6231. The complete observed distribution
inventory is in the baseline. It records the installed environment rather
than a portable dependency lock or any future deployment approval.

Use a new output directory, both thread settings equal to 1 and the
recorded environment. Compare canonical JSON outputs, run all offline
tests, verify the 13 dashboard outputs and reconcile preservation hashes.
For any later change, record the reason, affected files and hashes, and
expected impact. Preserve the prior baseline and all exposed data.
Independently review changes to strategy, risk, source scope, thresholds,
evaluator, cost rules, dates or runtime before sealing a successor baseline.
If a registered input changes, invalidate that registration and follow
the existing independent precommitment and exposure process.
[Engineering baseline](../../reports/phase_6_10_7/engineering-baseline.json)

~~~powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m tools.final_readiness_6107 --as-of 2026-11-21 --output <fresh-directory>
& .\.venv\Scripts\python.exe -B -m unittest discover -v
~~~

## Resolution order

Obtain written, effective-dated broker evidence first. Independently
reconcile the account scope, time and session mapping, economics and risk
boundary, then qualify a bounded data sample. Once minimum-lot risk and
source coverage can be verified, complete the exposure map and freeze the
approved protocol and evaluator. Obtain external pre-start receipts before
any authorized observation. Review sealed intake and score all cohorts
after the fixed end. Phase 7 then needs its own demo-only operating controls
and explicit Phase 6.9.6 authorization. Live trading remains a separate
decision requiring live-account evidence and approval.
[Unsent broker inquiry](../../reports/phase_6_10_7/consolidated-broker-inquiry.md) ·
[Phase 7 checklist](../../reports/phase_6_10_7/phase-7-entry-checklist.md) ·
[Verification](../../reports/phase_6_10_7/verification.md)
