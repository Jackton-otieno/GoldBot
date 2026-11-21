# Phase 6.9.6 integrated readiness

**NO-GO** · Assessed 2026-11-18 (Africa/Nairobi).

Execution, historical execution and prospective authorization are disabled.

## Diagnostics

- Phase 6.9.5 archive integrity: RECONCILED.
- The archived journal contains eight quote snapshots and zero admitted M15/H1 bar payloads. Between-poll tick coverage is unknown. The opening clock probe failed and the paired clock assessment was unavailable.
- Phase 6.9.6 boundary diagnostic: JOURNAL_VERIFIED.
- Collector completion status: COMPLETE_BOUNDED_DIAGNOSTIC.
- Observed 8 quote snapshots. Between-poll coverage is unknown.
- M15: 5 admitted bar observations, counting repeat reads, and 1 unique stored bar payloads. Observed close labels in raw seconds: 1795014000.
- H1: 5 admitted bar observations, counting repeat reads, and 1 unique stored bar payloads. Observed close labels in raw seconds: 1795014000.
- Clock bracket assessment: INDEPENDENT_TIME_UNAVAILABLE. The production UTC mapping is unverified.
- All diagnostic observations are exposed and ineligible for a prospective holdout.
- [reports/phase_6_9_6/boundary.sqlite3](boundary.sqlite3) · `1f7d42645c268a425669f9d6c0c00ae7a45c5e6f122156e356193b61c5db4884`
- [reports/phase_6_9_6/boundary-run.txt](boundary-run.txt) · `1b2b92d272227852cb952eddf73eed0b409376f7cb2a42bc864e880a41f83487`

## Blocker register

### Exness identity · OBSERVED

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Observed terminal diagnostics. Pinned connectivity passed on 18 November 2026. This is a historical identity snapshot.

Required evidence. Recheck exact identity using the independent local pin at every future attachment.

- [reports/phase_6_9_2/connectivity.json](../../reports/phase_6_9_2/connectivity.json) · SHA-256 `0c2d7c622624e72908216fce85a07151ffb68e227f07d8ac972f0b3eb5386ac3`

### Exness account variant · MISSING

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Required evidence absent. Terminal identity supplies no Personal Area Pro classification.

Required evidence. Record redacted independent evidence for the product variant of this exact demo.

Conditions recorded MISSING.

- [reports/phase_6_9_2/connectivity.json](../../reports/phase_6_9_2/connectivity.json) · SHA-256 `0c2d7c622624e72908216fce85a07151ffb68e227f07d8ac972f0b3eb5386ac3`

### Exness monetary precision · CONFLICTING

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Observed terminal diagnostics. The unchanged validator rejected four of 144 P/L probes; the earlier run rejected six. The notional-first rounding fit leaves calculator semantics and booked P/L unresolved.

Required evidence. Obtain authoritative rounding and accounting rules and independently reconcile them.

Conditions recorded CONFLICTING.

- [reports/phase_6_9_3/probes.json](../../reports/phase_6_9_3/probes.json) · SHA-256 `9b7a01e99829a12cbd0c18f809214d8ad9e2b6718cef21f3f006a9458f223b30`
- [reports/phase_6_9_3_1/probes.json](../../reports/phase_6_9_3_1/probes.json) · SHA-256 `75d55e303f010fbba3d1aa8a94dd475bfc2bf7dd72af8954c8ecaa545d534b26`
- [reports/phase_6_9_3_1/verification.md](../../reports/phase_6_9_3_1/verification.md) · SHA-256 `0f4684a44f0de45866f14309055f34ba389bd2cd8888beaa54135f000f8ee5ae`
- [reports/phase_6_9_3_1/notional-comparison.json](../../reports/phase_6_9_3_1/notional-comparison.json) · SHA-256 `e1cf52b2da259e32f117e95213734abd94af63a338ae1c541c083e46de3485fb`

### Metaquotes contract · REJECTED

Original MetaQuotes demo / XAUUSD. Observed terminal diagnostics. USD 0.10 tick metadata conflicts with USD 1.00 implied by calculator probes.

Required evidence. Keep original broker isolated and require its own contract reconciliation.

Conditions recorded REJECTED.

- [reports/phase_6_8_1/current-demo.json](../../reports/phase_6_8_1/current-demo.json) · SHA-256 `a6097cae9c9094f2d4a3dc955c97f0b50187699c5a05f65cc6a527fc87bc9979`
- [reports/phase_6_9_1/demo-verification.md](../../reports/phase_6_9_1/demo-verification.md) · SHA-256 `9217ce47620aa983c9447408d3de3e9b58c195251f21c9cca192f81e76ec1c14`

### Production utc mapping · UNRESOLVED

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Observed terminal diagnostics. An earlier clock bracket was conditional. The smoke opening probe failed. Raw labels, archive request coordinates and effective UTC windows remain unverified.

Required evidence. Obtain scoped, independently reviewed effective-dated UTC mapping and transition checks.

Conditions recorded UNRESOLVED.

- [reports/phase_6_9_4/diagnostic.json](../../reports/phase_6_9_4/diagnostic.json) · SHA-256 `aa6b45cb882615293c8673a3893dfed24e2455049337d11c298d5d36d89a0fa2`
- [reports/phase_6_9_4_1/diagnostic.json](../../reports/phase_6_9_4_1/diagnostic.json) · SHA-256 `51105ca8252f0e773b81a4ec4e3d2e59968bde11a8b4e78c31155f74da811410`
- [reports/phase_6_9_5/live-summary.json](../../reports/phase_6_9_5/live-summary.json) · SHA-256 `c8f3c00b19cdd7c4a7fced6fff58134967ef0ded17f53206286001a4442da29a`

### Dated quote and trade sessions · UNRESOLVED

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Archived assessment. Current samples and general schedules leave account-specific sessions and exceptions open.

Required evidence. Document dated quote/trade intervals, close-only periods, holidays and maintenance.

Conditions recorded UNRESOLVED.

- [reports/phase_6_9_4/verification.md](../../reports/phase_6_9_4/verification.md) · SHA-256 `6674da483fd00dbdd4bcbbd2e3ac3efc99b1581fa49ea01c45e750bfa2b60564`
- [reports/phase_6_9_4_1/diagnostic.json](../../reports/phase_6_9_4_1/diagnostic.json) · SHA-256 `51105ca8252f0e773b81a4ec4e3d2e59968bde11a8b4e78c31155f74da811410`

### Archive coverage and quote basis · UNRESOLVED

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Observed terminal diagnostics. Sampled tick retrieval and one bid-derived M1 reconstruction do not establish archive coverage. The archived smoke recorded eight snapshots, zero admitted bars and unknown tick coverage.

Required evidence. Reconcile scoped bid/ask history, chart basis, continuity, gaps and corrections.

Conditions recorded UNRESOLVED.

- [reports/phase_6_9_4_1/diagnostic.json](../../reports/phase_6_9_4_1/diagnostic.json) · SHA-256 `51105ca8252f0e773b81a4ec4e3d2e59968bde11a8b4e78c31155f74da811410`
- [reports/phase_6_9_5/live-summary.json](../../reports/phase_6_9_5/live-summary.json) · SHA-256 `c8f3c00b19cdd7c4a7fced6fff58134967ef0ded17f53206286001a4442da29a`
- [reports/phase_6_9_5/diagnostic.sqlite3](../../reports/phase_6_9_5/diagnostic.sqlite3) · SHA-256 `edb4a74ad094bd6f02cc1773b5c2fc71bfacc73e863c9b3af8f366d055340578`
- [reports/phase_6_9_5/verified-manifest.json](../../reports/phase_6_9_5/verified-manifest.json) · SHA-256 `fb29fbfbea0b7050e020a726fad1f27ad0c8df414bf8052fc4c658e9955d03f9`

### Risk day · MISSING

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Required evidence absent. An approved account-scoped policy boundary is absent.

Required evidence. Approve the risk-day boundary and prove its effective UTC mapping.

Conditions recorded MISSING.

- [reports/phase_6_9_4_1/verification.md](../../reports/phase_6_9_4_1/verification.md) · SHA-256 `adb6cace34d8cc314605a462c2844384e982d2a62f9d198d57724156f4ffaeb2`

### Opening equity · MISSING

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Required evidence absent. The diagnostics collected no equity at the exact policy-day opening.

Required evidence. Attest positive opening equity at the effective boundary for this exact account.

Conditions recorded MISSING.

- [reports/phase_6_9_4_1/verification.md](../../reports/phase_6_9_4_1/verification.md) · SHA-256 `adb6cace34d8cc314605a462c2844384e982d2a62f9d198d57724156f4ffaeb2`

### Executable costs and margin · UNRESOLVED

Exness (KE) Limited / ExnessKE-MT5Trial9 / USD demo …9498 / XAUUSD. Archived assessment. The sampled margin results leave effective-dated rates, fees, swap, FX and fill costs open.

Required evidence. Obtain broker-scoped effective schedules and execution eligibility evidence.

Conditions recorded UNRESOLVED.

- [reports/phase_6_9_3_1/verification.md](../../reports/phase_6_9_3_1/verification.md) · SHA-256 `0f4684a44f0de45866f14309055f34ba389bd2cd8888beaa54135f000f8ee5ae`
- [reports/phase_6_9_4/verification.md](../../reports/phase_6_9_4/verification.md) · SHA-256 `6674da483fd00dbdd4bcbbd2e3ac3efc99b1581fa49ea01c45e750bfa2b60564`

### Retrospective strategy · REJECTED

Strategy evidence / M15 and H1. Observed historical inputs, simulated outcomes. All eight Phase 6.8.5 hypothetical simulations had negative realized net P/L, including ideal costs.

Required evidence. Carry the adverse result into independent protocol review.

Conditions recorded REJECTED.

- [reports/research_phase_6_8_5/results.json](../../reports/research_phase_6_8_5/results.json) · SHA-256 `b708a00c10fa4e79e82307a5dbb1589e7752eb8e4531083e7b485db064c197a3`
- [reports/research_phase_6_8_5/assumptions.json](../../reports/research_phase_6_8_5/assumptions.json) · SHA-256 `6791cf8423af99e65756fc6a2356e8b5db0cee2ab26f2c61b24a2483a643177e`

### Prior exposure · UNRESOLVED

Strategy evidence / M15 and H1. Draft protocol. Historical candles and diagnostics are exposed. The complete independently mapped exposure inventory is pending.

Required evidence. Attest all viewed datasets and diagnostics with independently verified UTC bounds.

Conditions recorded UNRESOLVED.

- [reports/validation_phase_6_8_6/readiness.md](../../reports/validation_phase_6_8_6/readiness.md) · SHA-256 `4228b43a606f52ba131271ab36b7b2fcfed5f9d624bd524b405cb68c48eb4e8a`
- [reports/validation_phase_6_8_6/draft-protocol.md](../../reports/validation_phase_6_8_6/draft-protocol.md) · SHA-256 `d2e28c78ab4472e78350c8e3cb40936000c92975df354d0cfc63cdeb776397fb`
- [reports/phase_6_9_5/verified-manifest.json](../../reports/phase_6_9_5/verified-manifest.json) · SHA-256 `fb29fbfbea0b7050e020a726fad1f27ad0c8df414bf8052fc4c658e9955d03f9`

### Prospective protocol · MISSING

Strategy evidence / M15 and H1. Draft protocol. Exact UTC dates, independent approval, external pre-start receipt and audited intake are absent.

Required evidence. Approve the frozen M15/H1 protocol and verify an external pre-start receipt before any separate authorization.

Conditions recorded MISSING.

- [reports/validation_phase_6_8_6/readiness.md](../../reports/validation_phase_6_8_6/readiness.md) · SHA-256 `4228b43a606f52ba131271ab36b7b2fcfed5f9d624bd524b405cb68c48eb4e8a`
- [reports/validation_phase_6_8_6/draft-protocol.md](../../reports/validation_phase_6_8_6/draft-protocol.md) · SHA-256 `d2e28c78ab4472e78350c8e3cb40936000c92975df354d0cfc63cdeb776397fb`
- [reports/validation_phase_6_8_6/reference-freeze.json](../../reports/validation_phase_6_8_6/reference-freeze.json) · SHA-256 `aeb45b7a94fe43934541b0129e95b1d7a0e2ee5f1c58bf8b876b993867775544`
