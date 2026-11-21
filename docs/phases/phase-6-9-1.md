# GoldBot Phase 6.9.1 — alternative MT5 broker selection

Research reviewed on 18 November 2026 (Africa/Nairobi). Recommend **Exness KE MT5 Pro demo** for manual approval and **IC Markets (KE) MT5 Standard demo** as the fallback. Both are conditional on written confirmation of Kenyan routing, demo-only access and the exact gold symbol. All five entities below appear in the CMA register. Demo behavior remains untested.

| Rank | Candidate | Reason |
| --- | --- | --- |
| 1 | Exness KE | Kenyan MT5 demo offering, published gold contract and UTC server policy, and an indicative public bid/ask archive. The Pro symbol is published without a suffix and the account advertises zero commission. |
| 2 | IC Markets (KE) | Kenyan MT5 demo offering, local metals sheet and published DST convention. The metals sheet describes MT4 and the demo inactivity policy could affect continuity. |
| 3 | Pepperstone Markets Kenya | Strong local evidence for MT5 Spot Gold on Standard and Razor. Exact demo contract, expiry and history need confirmation. |
| 4 | HFM Investments | Kenyan demo terms and group gold specifications exist. Exact Kenyan MT5 product mapping is unresolved, and the local agreement gives Premium demo a 60-day life. |
| 5 | FXTM / Exinity Capital East Africa | Kenyan Advantage offering lists MT5 and demo. Entity-specific contract economics, clock and coverage were less well evidenced. |

## GoldBot acceptance gates

- 6.8.1 rejected the existing demo: USD 0.10 for each tick-value field versus USD 1.00 implied by 144 calculator probes. A replacement needs agreement across raw metadata, the calculation-mode formula and terminal calculations for both gains and losses.
- 6.8.2 observed a static quote and could not establish broker clock or exact DST mapping. 6.8.3 also left dated quote/trade sessions and the account-scoped risk day unresolved. GoldBot needs a uniquely mapped quote inside a verified open interval, no more than 60 seconds old across the UTC uncertainty bracket.
- 6.8.4 recovered zero archived tick rows. The replacement needs actual bounded bid/ask retrieval, verified chart basis and coverage, and effective-dated specification, FX, commission, swap, margin and execution-model inputs.
- 6.8.5 used hypothetical costs on previously inspected candles. 6.8.6 requires a complete prior-exposure inventory with independently verified UTC bounds, fixed M15/H1 candidates, approved exact UTC dates and rules, an independent pre-start receipt and audited intake/ledgers. The 12-month dates remain unset. Technical smoke tests become prior exposure and must precede any authorized study window.

KES 1,000–5,000 is future context only. Demo ranking is independent of live funding, minimum deposit and live affordability. Live minimum volume, stops, margin and costs would need separate evidence before any future assessment.

- [Source evidence and unresolved terms](../../reports/phase_6_9_1/source-evidence.md)
- [Phase 6.9.2–4 checklist and unsent questions](../../reports/phase_6_9_1/demo-verification.md)
- [Offline verification](../../reports/phase_6_9_1/verification.md)

Await manual broker approval before any migration. Phase 7, historical execution, and prospective collection and evaluation remain blocked.
