# Phase 6.9.2–4 demo verification checklist

Pending manual broker approval. All probes below are future read-only work, outside the prospective window. Use a separately isolated desktop MT5 instance and an already active user-controlled demo session. Confirm the Kenyan entity, exact terminal, demo mode, server fingerprint, currency, account variant and exact non-custom symbol before and after each batch. Stop on mismatch or reconnect. Reports should omit account IDs and credentials. The existing connector autodiscovers MT5, so close unrelated terminals or use a reviewed diagnostic entry point that pins the isolated terminal. Never change a production setting or invoke the trading entry point.

## 6.9.2 — entity, symbol and economics

1. Record source versions, effective dates, public terms and written broker replies. Select USD account currency for like-for-like diagnostics. Confirm that quotes and history are available without funding or placing trades, and record demo expiry and renewal policy.
2. Capture terminal and Python builds, calculation/chart modes, bid/ask digits, point, tick size, contract size, volume min/max/step/limit, generic/profit/loss tick values, stop/freeze levels, account/profit/margin currency, rounding, leverage and swap fields. Repeat across sessions and log changes.
3. For exact XAUUSD, run the existing check from D:\GoldBot with the reviewed demo server label in the temporary local variable below. Choose a fresh artifact folder before running future captures. Check the process status and JSON together.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.diagnose_broker_specs --expected-server $demoServer > "$captureDir/specs.json"
```

4. Require agreement between metadata, the calculation-mode formula and the read-only `order_calc_profit` results for BUY/SELL, gains/losses, four prices, 1/10/100 ticks and 0.01/0.02/0.10 lots when valid. Preserve the existing validator's account precision tolerance (USD 0.00500001 at two decimals) and log each residual. Use `order_calc_margin` for the same account and valid grids; compare sampled ratios to tier rules and capture hedged and event-margin documentation. Keep unresolved differences as failures. No calculator probe enters an order.
5. If the symbol is suffixed, stop the exact-symbol tools. Obtain a separate reviewed diagnostic binding and document the symbol mapping and freeze implications before proceeding.

## 6.9.3 — freshness, clock, DST and sessions

1. During a confirmed open session, bracket 16 consecutive samples at two-second intervals with independent healthy UTC and monotonic readings. Compare raw seconds and milliseconds and bid/ask against bounded history and the M1 bar. Repeat in a second open session and around a known break. Distinguish stale cache, expected closure, no updates and conversion failure.
2. Use the existing parameterized tools with new output paths. DST year is chosen from the applicable evidence period. The DST command reports unverified status by design; its CME comparison is a proxy only.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.diagnose_time --expected-server $demoServer --samples 16 --interval 2 --output "$captureDir/quotes.json"
& .\.venv\Scripts\python.exe -B -m tools.verify_dst --year 2026 --server $demoServer --symbol XAUUSD --output "$captureDir/dst-2026.json"
```

3. Require an authenticated or independently reviewed UTC example and effective offset windows including relevant transitions. Distinguish chart time, returned epochs, request coordinates and statement/rollover time. Resolve quote and trade sessions independently as dated half-open UTC intervals with closure, exceptions and close-only states. Use a separately approved native read-only session lookup or broker evidence. The existing trading-sessions and execution-data tools hard-code the original server; they require separate research-only tooling before use against the selected demo.
4. Apply the existing Phase 6.8.3 requirement of a uniquely decoded, usable quote inside the open quote interval, at or before earliest possible now and at most 60 seconds old at latest possible now. Require approved GoldBot risk-day boundaries and exact opening-equity evidence separately from broker rollover. Leave unresolved evidence rejected.

## 6.9.4 — history, coverage and cost evidence

1. Predeclare small, dated smoke-test windows fully before the study and add them to prior exposure. Include a recent open session, a documented closed interval, a rollover/break boundary, a DST or holiday boundary and representative older windows. Record query coordinates and UTC bounds. Request bid/ask using `copy_ticks_range` and closed M1/M15/H1 bars using `copy_rates_range`. Start with 10–60-second tick windows and one bounded query at a time. Use an external per-request deadline, checkpoint each result and allow one limited retry after backoff. Distinguish timeouts, API errors, empty success and known closures. Save raw rows in order including same-millisecond ticks and flags.
2. Record requested and returned bounds, count, package/terminal errors, duration, retries, chart history limit and UTC acquisition bracket. Check finite ordered bid/ask, chart basis, price grid, gaps, duplicates, and alignment. Compare constructed Bid OHLC to closed bars where applicable. Hash files and record vendor/server/product, effective schedules, archive provenance and redistribution permissions. Broker archive and demo stream require separate lineage and coverage evidence. Small samples cannot certify a horizon.
3. Measure spreads by session from bid/ask; retain distribution and sample sizes. Obtain effective-dated commission per side and round trip, currency/minimum/rounding, gold long/short swap mode and calendar, conversion sides and rounding, leverage/margin schedules, slippage/fill assumptions and limits of demo–live comparison. Quote data and calculators leave fill behavior unresolved. Preserve the original CSVs and evidence.
4. Require independent acceptance of coverage/nonoverlap and the complete Phase 6.8.6 approval chain before authorizing any prospective collection. Technical acceptance does not authorize Phase 7, order placement, or replacement of frozen candidates.

## Questions for Exness KE or IC Markets (KE) — unsent

- Can a Kenyan resident use a no-funding MT5 desktop demo through your named CMA entity? Which USD demo variant and exact symbol provide ordinary weekday spot gold? Does read-only use prevent expiry, and can access survive renewals or resets without gaps?
- Can you supply the effective-dated contract and tick specification, volume grid, supported P/L mode, tick-value currency and one gain/loss example on each side? Which margin tiers, event limits, commission units and rounding, and long/short swap rules apply to this demo?
- Can you supply dated UTC gold quote and trade hours including breaks, close-only intervals, holidays and DST, an independently checkable example mapping a returned MT5 tick timestamp to UTC, and the history request time convention? How do rollover and statement days differ?
- What is actual retained tick and M1/M15/H1 coverage, query/page limit and known gap schedule for this demo? Are historical ticks executable bid/ask and which side builds bars? Does the archive match this symbol/account/server, and can the vendor attest coverage and authorize research retention? Are MetaQuotes Python reads supported on the MT5 desktop demo?
- For Exness, can you confirm Pro offers unsuffixed XAUUSD and how the Kenyan archive differs from its demo stream? For IC Markets, can you provide the MT5 gold sheet, confirm the DST rule for this demo, and explain what counts as activity?
