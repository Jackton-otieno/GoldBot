# Exness XAUUSD cost evidence

Reviewed 21 November 2026, Africa/Nairobi. Scope is XAUUSD on the Exness
(KE) Limited USD MT5 demo ending 9498 on ExnessKE-MT5Trial9.

## Archived observations

- Eight Phase 6.9.3.1 minimum-lot margin probes, four prices per side, returned USD 37.50–38.26. The sample matches approximately 1% of USD notional around the observed prices. The terminal reported 1:100 leverage, a 100-ounce contract, 0.001 price tick, USD 0.10 tick value per lot, 0.01-lot minimum and step, and a 200-lot maximum. The sampled margin convention and point-in-time stop-level metadata establish no dated maintenance, stop-out, HMR, tier or intraday schedule. [Contract probe](../phase_6_9_3_1/probes.json)
- The 14 quote snapshots in the Phase 6.9.4.1 capture and the successful Phase 6.10.5.2 capture each had USD 0.168/oz quoted spread. That equals USD 0.168 for 0.01 lot at 100 ounces per lot. The count includes repeated observations. These short captures do not cover news, rollover or execution. [Earlier quote capture](../phase_6_9_4_1/diagnostic.json) · [Later clock and quote capture](../phase_6_10_5_2/timestamp-verification.json)
- The product variant, applicable commission, effective swap-free status, dated directional swap rates, additional funding charges, and realized slippage are unresolved for the account. No new terminal diagnostics or transactions were needed. [Readiness blocker register](../phase_6_9_6/readiness.md)

## Published policy

- Exness lists the 100 troy ounce XAUUSD contract and 0.01-lot minimum. Group product documentation lists Raw Spread at USD 3.50 and Zero at USD 5.50 per lot per side. At 0.01 lot those imply unrounded round-trip commissions of USD 0.07 and USD 0.11 if applicable. Kenya's key facts statement says applicable two-sided commission is collected at entry. An exact charge, any minimum or cent rounding, and the demo's account type need separate confirmation. [Exness commodity specifications](https://get.exness.help/hc/en-us/articles/17854173039388-Commodities) · [Kenya key facts statement](https://www.exness.ke/cdn/media/tadenex/tadenex_key_facts_statement.pdf)
- Exness describes changes in spread around liquidity, news and session boundaries. It documents dynamic pending-order slippage thresholds and possible slippage on market orders. These references supply no fill-price distribution or guaranteed bound for the tested account. [Exness spread policy](https://get.exness.help/hc/en-us/articles/360014690880-About-spread) · [Pending-order slippage rule](https://get.exness.help/hc/en-us/articles/18054855363484-Slippage-rule)
- Exness describes an ordinary Wednesday triple swap for metals and notes holiday changes, directional rates and account-dependent swap-free status. This leaves applicable charges, credits, any additional funding terms, and effective accrual dates unverified. Kenya's fees page and agreement describe method-dependent payment or third-party fees. Such cash-flow costs are distinct from trading spread, commission and rollover. [Swap policy](https://get.exness.help/hc/en-us/articles/360014709151-About-swap) · [Swap-free eligibility](https://get.exness.help/hc/en-us/articles/4402341895570-Swap-free-status) · [Kenya fees](https://www.exness.ke/fees/) · [Kenya client agreement](https://www.exness.ke/cdn/media/tadenex/tadenex_client_agreement.pdf)
- Group HMR documentation lists XAUUSD rates of 0.1%–0.5% with event windows. The Kenya agreement specifies a 1:400 leverage ceiling. Neither establishes the exact demo's applicable tiers or resolves their relationship to the earlier point-in-time 1:100 observation. [Exness HMR](https://get.exness.help/hc/en-us/articles/20618327917596-Higher-Margin-Requirements-HMR) · [Kenya client agreement](https://www.exness.ke/cdn/media/tadenex/tadenex_client_agreement.pdf)

## Hypothetical costs used in the analysis

| Scenario | Spread, USD/oz | Adverse slip on each leg, USD/oz | Round trip commission, USD/lot | Immediate flat-midpoint cost at 0.01 lot |
| --- | ---: | ---: | ---: | ---: |
| Ideal | 0 | 0 | 0 | $0.00 |
| Low | 0.15 | 0.05 | 3 | $0.28 |
| Baseline | 0.30 | 0.10 | 7 | $0.57 |
| Stress | 1.00 | 0.50 | 15 | $2.15 |

The four scenarios retain the historical research model's fictional USD
0.005 tick grid and exclude actual financing. The USD 1 carry and one-cent
rounding cases are separate sensitivity calculations. The Phase 6.10.5.1
calculator observations leave booked monetary precision unresolved.
No sampled broker value or public policy has been applied as verified
historical conditions.
[Frozen assumptions](../research_phase_6_8_5/assumptions.json) ·
[Precision risk analysis](../phase_6_10_5_1/risk-impact.json)
