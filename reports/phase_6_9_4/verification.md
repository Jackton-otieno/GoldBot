# Phase 6.9.4 verification

**Broker time, sessions and history remain unverified for the selected account.** Target scope is XAUUSD on the selected Exness (KE) Limited ExnessKE-MT5Trial9 USD demo ending 9498. On 18 November 2026, the selection profile was absent in the execution session. An elevated read-only process check found one MT5 process, whose account was not independently identified. The diagnostic refused attachment. It recorded zero quotes, bars and archive rows. [Diagnostic JSON](diagnostic.json)

## Independent time observation

The diagnostic's two NIST TCP Daytime requests timed out. A separate bounded Windows NTP stripchart against Cloudflare succeeded from 17:08:49 to 17:08:52 Nairobi time (14:08:49–14:08:52 UTC). Its four offsets were +22.553, +20.377, +26.522 and +20.991 ms. Round trips were 50.130, 36.794, 50.272 and 38.924 ms. The union of observed offset ± half round trip is approximately −2.513 to +51.658 ms, conditional on the remote reference and nonnegative one-way network delays. This is a standalone host check. Windows Time source inspection was denied, and no independent UTC bracket coincided with any terminal quote.

```powershell
w32tm /stripchart /computer:time.cloudflare.com /samples:4 /period:1
```

## Published policy reviewed 18 November 2026

- Exness's MetaTrader timezone article, updated 22 August 2026, states GMT+0. Its instrument-hours article, updated 14 November 2026, states UTC+0 for trading servers. These are general statements with publication updates. The effective dates for returned raw timestamps and archive request coordinates on this particular server remain unknown. MetaQuotes describes Python tick and bar data as UTC in its general reference. [Exness timezone](https://get.exness.help/hc/en-us/articles/360014390760-What-is-the-default-timezone-set-for-MetaTrader) · [Exness instrument hours](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours) · [MetaQuotes Python reference](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py)
- Exness's 3 November update dates the DST schedule change to 1 November 2026. For XAUUSD in winter UTC, Sunday close-only starts at 23:01:30 and open starts at 23:05. Monday–Thursday the daily break begins at 21:58, close-only starts at 23:00:30, and open resumes at 23:02. Friday closes at 21:58. The corresponding summer times are one hour earlier. Saturday is closed. The general schedule lists Thanksgiving on 26 November and Christmas on 25 December and directs clients to holiday notices for instrument-level changes. Account/server-specific historical quote and trade intervals, holiday overrides and maintenance exceptions remain unverified. [Dated DST notice](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026) · [Holidays and maintenance](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)
- The tick history article, updated 30 September 2026, names MT4 Real 1, Real 3 and Real 9 as sources and says users cannot choose the server. Its CSV schema includes timestamp, bid and ask. Start date, effective timestamp semantics, continuity, correction history and equivalence to the selected KE MT5 demo remain unknown. Exness's separate order-history policy describes transaction records and demo retention, which supplies no tick archive coverage or exact policy-day opening equity. [Tick history](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history) · [Trading history](https://get.exness.help/hc/en-us/articles/360017359859-Trading-history)
- Exness describes rollover around 21:00 UTC in summer and 22:00 in winter. The GoldBot risk day still requires its own approved account-scoped boundary and positive opening equity attested at that exact instant. A current balance/equity snapshot or a rollover time alone is insufficient evidence. No opening equity was collected. [Exness rollover](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)

## Remaining evidence

The read-only runner is ready for the exact independently selected profile. Repeated advancing quotes, raw seconds and milliseconds against independent UTC, matching tick/M1 observations, range and count response behavior, closed M15/H1 labels, gaps, ordering, OHLC and bid/ask candle basis are all unobserved in this run. Even successful current probes would need effective-dated history and exception evidence before use under the existing TimeManager, session and historical archive guards. The [broker inquiry](broker-support-inquiry.md) is unsent.

The phase grants no production offset or broker acceptance. Exness rounding remains unresolved despite the Phase 6.9.3.1 fit, and MetaQuotes remains rejected. No prospective holdout collection, historical execution, order calls, account switch, Algo Trading change, or automated demo/live trading occurred.

## Offline integrity

All 182 tests passed with OPENBLAS_NUM_THREADS and OMP_NUM_THREADS set to 1. The consolidated test regenerated all 13 Phase 6.7 files byte-identically in an isolated temporary root. The pre/post comparison preserved all 77 prior report files and both raw CSVs by SHA-256. [Pre-change manifest](preserved-before.sha256)
