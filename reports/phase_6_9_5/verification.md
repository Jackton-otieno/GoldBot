# Phase 6.9.5 verification

**The bounded read-only smoke completed on 18 November 2026.** The exact profile and installation matched the independent Phase 6.9.2 journal recovery. The active terminal reported Exness (KE) Limited, USD demo ending 9498 on ExnessKE-MT5Trial9, build 6324 and disabled Algo Trading. One attachment sufficed. [Smoke command and limits](../../docs/phases/phase-6-9-5.md) · [Prior identity evidence](../phase_6_9_2/connectivity-verification.md)

- Eight XAUUSD polling snapshots had eight distinct payloads. Host receipt brackets spanned approximately 17:38:48 to 17:39:00 EAT. Between-poll tick coverage is unknown.
- Eight reads per timeframe returned 16 M15 and 16 H1 rows, counting repeats. All had raw close labels at or before the first raw quote and were excluded. The smoke stored zero bar payloads. Bar admission, raw gaps, and revision and reversion preservation were exercised with synthetic inputs.
- The opening Cloudflare NTP observation failed timing validation. The closing observation supplied a conditional host correction range of approximately −0.170 to +0.176 seconds. An independent clock bracket is unavailable. Production UTC mapping remains unverified.
- The read-only storage check matched the smoke manifest at 30 events and eight unique payloads. It found no unfinished run. The data is exposed and ineligible for a holdout. [Live summary](live-summary.json) · [Verified chain manifest](verified-manifest.json)

The Exness monetary-precision rejection and MetaQuotes rejection remain in force. Account-scoped sessions, archive continuity, risk-day boundaries and costs remain unverified. The run made no order calls, account changes or strategy evaluations. [Exness precision evidence](../phase_6_9_3_1/verification.md) · [MetaQuotes evaluation](../phase_6_9_1/demo-verification.md)

## Offline regression and preservation

All 190 tests passed with `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1`, including five synthetic tests for Phase 6.9.5. The consolidated-report regression regenerated all 13 Phase 6.7 files in an isolated copy and matched the installed outputs byte-for-byte. All 84 prior report files and both raw CSVs matched their pre-change hashes. [Regression log](offline-regression.txt) · [Before hashes](preserved-before.sha256) · [After hashes](preserved-after.sha256) · [Phase artifact hashes](phase-artifacts.sha256)
