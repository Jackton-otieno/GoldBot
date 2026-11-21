# Phase 6.8.6 readiness

**Blocked for prospective collection and evaluation.** The prospective
window is unset and the protocol is a draft. No external timestamp,
independent approval record, prospective market payload or evaluation
exists. Phase 7 automated demo and verified historical execution remain
blocked.

## Existing evidence

- The current strategy and risk code reproduces the Phase 6.6 freeze,
  which also matches Phase 6.8.5. The reference manifest records the
  exact hashes. Both original CSVs were fully inspected. The eight
  research simulations closed six to eight trades each and all had
  negative net P/L under their hypothetical inputs. They supply no
  independent evidence for the prospective thresholds.
- The current XAUUSD demo tick metadata reports USD 0.10 against
  USD 1.00 implied by the Phase 6.8.1 calculator probes. The prior
  checks also found stale quotes and unverified clock/DST, session,
  historical quote-basis and risk-day semantics.
- Phase 6.8.4 recovered zero ticks. Source and UTC coverage,
  gap and heartbeat policy, effective contract economics, account
  margin and FX, commission, swap and fill eligibility remain unresolved.
  The prior-exposure UTC mapping and completeness attestation are pending.

## Decisions requiring explicit approval

1. Choose the broker, account and source scope, including any backup
   source. Seek broker evidence on the tick-value discrepancy, clock,
   session and execution terms first. If unresolved, evaluate a different
   demo broker with the same checks. A licensed independent bid/ask
   archive or feed may support a research-only protocol if separately
   verified and explicitly scoped. It cannot establish execution
   readiness for the original broker.
2. Confirm the complete prior-exposure declaration and independent UTC
   mapping, including any datasets viewed outside the repository.
3. Approve both fixed candidates, exact start and end UTC, provisional
   thresholds, final execution and cost rules, evaluator, environment,
   missing-data policy and independent registrar/custodian/auditor.
4. Verify the external precommit receipt before the approved start. Only
   then authorize the read-only collector. Keep outcomes sealed until
   the fixed horizon is complete and intake is independently verified.

The local reference hashes support byte comparison. Independently
verified evidence and externally timestamped commitments remain
requirements for a genuine prospective study.

## Offline verification

All 165 tests passed in GoldBot's existing .venv, including 10 new
synthetic gate tests. The initial run hit an OpenBLAS memory allocation
failure. The full retry passed with OPENBLAS_NUM_THREADS and
OMP_NUM_THREADS set to 1 for the test process. The Phase 6.7 test
regenerated the HTML, JSON and 11 SVGs and compared their bytes with the
saved reports. Both original CSVs and all 52 earlier report files matched
the pre-change SHA-256 inventory after the suite.
