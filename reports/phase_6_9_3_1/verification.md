# Phase 6.9.3.1 Exness monetary precision

**Broker specification acceptance remains blocked.** The unchanged validator rejected four of 144 P/L probes on 18 November 2026 at 16:51 EAT. All 24 margin probes passed under the existing XAU-to-USD conversion check, with a maximum absolute residual of USD 0.00496. The existing USD 0.00500001 tolerance, loss guards, and MetaQuotes rejection remain in force.

The read-only attachment matched the exact running installation and full account reference from the local journal in memory, then checked Exness (KE) Limited, ExnessKE-MT5Trial9, USD demo ending 9498, 1:100 leverage, disabled Algo Trading, and the exact non-custom XAUUSD. MT5 build 6324 with Python package 5.0.6231 returned account currency precision of two digits. Both archived Phase 6.9.3 runs also recorded this precision and six failures apiece. The four fresh failures were 0.02-lot one-tick cases at entries 3788.548 and 3826.433. BUY losses and SELL profits returned USD −0.01 and +0.01 against exact expectations of −0.002 and +0.002. The archived failures included one-tick USD 0.001 cases at other prices. Calculator calls used the connected session without credentials, account changes or orders.

## Precision grid

Two consecutive passes within one terminal attachment returned 840 rows each. The grid used four quote-relative entries (3750.496, 3788.380, 3788.548 and 3826.433), five volumes (0.01, 0.02, 0.03, 0.05 and 0.10 lots), both sides and both signs, including 80 zero-movement controls. Prices, volumes and baseline arithmetic are exact decimals until the calculator call. All zero controls returned zero. Fifty-five volume/target combinations could not be expressed as integer ticks and are listed in the JSON. All 1,680 submitted cases returned finite values. The two passes agreed on every exact input. Reproducibility across recalculated entry anchors, terminal builds, independent sessions or other accounts remains untested for the expanded grid.

Of 800 opposite-movement pairs at fixed side, entry and volume, 304 had unequal absolute outputs. Individual final-P/L rules fit different rows. Each of the five nearest-cent tie variants matched 1,376 of 1,680 rows. Their minimum-nonzero-cent versions each matched 1,296. Away-from-zero matched 1,232, truncation 1,168, and ceiling and floor 1,200 each. Each row matches at least one of these candidates, but no single final-P/L rule accounts for the grid. A universal minimum cent fails because some nonzero P/L estimates returned zero, including all sampled USD 0.001 magnitudes. A tie policy alone cannot explain non-tie discrepancies.

A separate observational model rounds each positive USD notional (price × lots × 100) to cents before subtraction and applies the BUY or SELL direction afterward. Round-half-up in that model matched **1,680 of 1,680** observations, compared with 1,492 for half-even, 1,380 for half-down, and 1,020 for truncation. For example, at 0.01 lots, BUY from 3788.548 to 3788.554 returned zero on exact price-move P/L of USD 0.006, while BUY from 3788.548 to 3788.542 returned −0.01 for exact P/L of −0.006. The model rounds the three notionals to 3788.55, 3788.55 and 3788.54 respectively. This fit was identified from the same observations and leaves the calculator implementation and realized-deal accounting unresolved. The fit gives no basis to certify a risk scenario or accept a reduced loss estimate.

[Sanitized calculator rows](probes.json) · [Offline notional comparison](notional-comparison.json) · [Prior phase verification](../phase_6_9_3/verification.md)

## Published evidence and decision

- MetaQuotes defines account currency digits as display precision. The Python reference describes an estimate in account currency for the current trading environment. The AlgoBook lists the price-difference Forex formula. These sources leave rounding stages and tie rules unspecified. [Account properties](https://www.mql5.com/en/docs/constants/environment_state/accountinformation#enum_account_info_integer) · [Python calculator](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py) · [AlgoBook Forex formula](https://www.mql5.com/en/book/automation/experts/experts_ordercalcprofit)
- Exness lists XAUUSD contract size 100 troy ounces, pip size 0.01 and minimum volume 0.01 lot. Its P/L conversion article covers currency conversion when profit and account currencies differ. Neither specifies the MT5 Python rounding rule for USD-to-USD XAUUSD. [Exness commodities, Gold (XAU)](https://get.exness.help/hc/en-us/articles/17854173039388-Commodities) · [Exness P/L conversion](https://get.exness.help/hc/en-us/articles/360017456959-How-does-currency-convert-when-calculating-profit-loss)
- A community report on a different symbol and MT5 build documents half-cent anomalies. The moderator reply offers no technical confirmation. It supplies no authority for an Exness validator change. [MQL5 forum thread and reply](https://www.mql5.com/en/forum/520111)

No authoritative source found specifies the matched notional-first rule or the relationship between calculator results and booked P/L. The standalone diagnostic leaves the acceptance path unchanged. Historical execution, prospective collection, demo/live order execution, broker costs and clock/time verification remain outside this phase and unapproved. Personal Area Pro status remains unverified.

[Unsent support inquiry](support-inquiry.md)

## Offline regression and preservation

All 180 offline tests passed (176 prior tests and four new diagnostics tests), with OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1. The Phase 6.7 provenance test now recognizes this phase as later evidence. The generator reproduced all 13 files byte for byte in an isolated root. SHA-256 inventories taken from the actual GoldBot installation matched across all 71 protected files, including 69 prior report files and both original raw CSVs.

[Offline test output](offline-regression-final.txt) · [Phase 6.7 regenerated hashes](phase-6-7-regenerated.sha256) · [Before inventory](preserved-before.sha256) · [After inventory](preserved-after.sha256)
