# Phase 6.11 evidence without a broker inquiry

**Tools built and first results measured. No blocker is closed. GoldBot
remains NO-GO.** This phase gathers evidence by direct measurement instead of
waiting on the unsent
[Exness inquiry](../../reports/phase_6_10_7/consolidated-broker-inquiry.md).
The sources are Exness's public tick archive, the existing MT5 candle
exports, and a read-only reader for an optional, not yet executed,
[manual demo experiment](../evidence/manual-demo-trades.md). The
[proposed evidence standard](../evidence/evidence-standard.md) defines how a
scoped measurement could be accepted. It remains proposed, and it does not
change Phase 6.10.6 prospective approval or the Phase 6.9.6 gate.

## Findings (candidate evidence, scoped as stated)

| Question | Answer | Evidence |
| --- | --- | --- |
| Server clock versus UTC | **UTC+2 in winter, UTC+3 in summer.** The switch follows EU daylight-saving dates: +2→+3 on 29 Mar 2026 and +3→+2 on 25 Oct 2026. Every day separates cleanly (best OHLC gap about 0.13, runner-up 4–7). | [Oct](../../reports/phase_6_11/archive_2026_10/clock-offset.json) · [Mar](../../reports/phase_6_11/archive_2026_03/clock-offset.json) |
| Quote availability (not trade permissions) | The archive has no quotes from about 16:58 to 18:00 New York time: 20:58–22:00 UTC in US daylight time and 21:58–23:00 UTC in US standard time. Standard time was observed only on 2–6 Mar 2026. Weekend gaps run from Friday's break to Sunday's reopening. Trade permissions, close-only periods and holidays are not established by quote gaps. | [Oct](../../reports/phase_6_11/archive_2026_10/summary.json) · [Mar](../../reports/phase_6_11/archive_2026_03/summary.json) |
| Historical data | Exness publishes monthly bid/ask tick files in UTC with millisecond timestamps and three-decimal prices. Oct 2026 has 5.9 M ticks and passes every audit check. The same month downloaded twice returned identical SHA-256. | Manifests under `historical_data/phase_6_11/` |
| Spread (Pro archive) | Median 0.168 in Oct 2026 and 0.252 in Mar 2026, roughly USD 0.17–0.25 per 0.01 lot. | `summary.json` → `spread` |
| Archive versus this demo | Same market, different feed. Close-to-close gap median 0.13–0.16, 90th percentile 0.28–0.35. Use the archive for research, not as this demo's executable prices. | `clock-offset.json` → `price_agreement` |
| Booked P/L, commission, swap, fills | **Not measured.** The optional [manual experiment](../evidence/manual-demo-trades.md) and the read-only reader are ready. Any result will describe the tested trades only. | `tools.read_demo_deals_611` |

One unverified hypothesis: the 10× tick-value disagreement in
[Phase 6.8.1](../../reports/phase_6_8_1/current-demo.json) is consistent with
MT5's `trade_tick_value` field being scaled to a 0.001 price step (three
digits, as in the archive). The monetary-precision blocker stays open. The
earlier calculator probes showed results that differ from exact arithmetic,
and only booked deals can test the hypothesis.

## Components

- `goldbot/market_data/exness_archive.py` downloads one month to a new file
  with a 256 MB cap and records provenance. It verifies the pinned digest,
  then streams and validates every row: header, symbol, UTC month, ordering,
  uncrossed quotes, and integer-thousandths prices. It produces gaps, spread
  distributions and UTC bid candles.
- `goldbot/market_data/archive_comparison.py` infers the server-label offset
  for each UTC day from OHLC agreement and reports transitions.
- `goldbot/risk/booked_pnl.py` reconciles booked exits against exact contract
  arithmetic, five cent-rounding rules and cent-rounded notionals. It covers
  partial closes, exits whose entry precedes the window (`MISSING_ENTRY`),
  commission per deal, swaps, and fill-versus-prior-quote comparison (not
  execution slippage). The boundary balance is the current balance minus
  later deals.
- `tools/read_demo_deals_611.py` reuses the existing identity guard. It wraps
  MT5 in an allowlist proxy, so trading and position functions raise
  `PermissionError`. It reads deals and orders to the present and records
  order-request-to-execution times. It uses only quotes at most 2 s old, and
  reports opening equity as `SUPPORTED` or `UNRESOLVED` with reasons. It
  refuses to continue if the balance changes during the read, and checks
  every experiment position against the protocol's limits.
- `goldbot/core/server_clock.py` holds the measured offset rule: UTC+2 or
  UTC+3, switching on EU dates.
- `goldbot/research/exposure_log.py` keeps the append-only, hash-chained
  record of examined data for the [personal research track](../evidence/research-track.md).
  Both tools write to it automatically.

## Reproduce

```powershell
& .\.venv\Scripts\python.exe -B -m tools.exness_archive_611 fetch --month 2026-10 --output <new.zip>
& .\.venv\Scripts\python.exe -B -m tools.exness_archive_611 analyze --file <new.zip> --sha256 <digest> `
    --month 2026-10 --output <new directory> --mt5-m15 data\XAUUSD_M15.csv --mt5-h1 data\XAUUSD_H1.csv
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

Recorded digests: Oct 2026
`5f0d3751320641e1595cb019e349ae58cb7b93bdf7b50df23885ae82664fa4d2`, Mar 2026
`9645374633bbfaaa9e67afea63f9af414a1e55c6deb0a10af57e9275b1502957`.

## Next

1. Review both revised documents before deciding whether to run the bounded
   manual experiment.
2. Run the archive tool on Nov 2026 (once published), Dec 2025 and Jan 2026.
   These cover US standard time and holiday quote gaps. Then extend to the
   intended research range.
3. Review and adopt, amend or reject the evidence standard and the proposed
   00:00 UTC risk-day policy.
4. Strategy profitability is still not demonstrated. Better evidence makes the
   next evaluation trustworthy, but it does not change the earlier result.
