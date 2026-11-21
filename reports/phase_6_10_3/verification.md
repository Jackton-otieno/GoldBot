# Phase 6.10.3 verification

The candidate ledger covers 10,000 original closed candles per timeframe.
Counts describe signal coverage. Each row below totals 10,000.

| Timeframe | Candidate | BUY | SELL | HOLD | WARMUP | GAP |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| M15 | EMA/RSI trend pullback | 360 | 358 | 6,998 | 2,170 | 114 |
| M15 | Donchian breakout | 403 | 438 | 6,875 | 2,170 | 114 |
| M15 | Bollinger/RSI mean reversion | 182 | 162 | 7,486 | 2,056 | 114 |
| H1 | EMA/RSI trend pullback | 24 | 28 | 1,082 | 8,420 | 446 |
| H1 | Donchian breakout | 66 | 34 | 1,034 | 8,420 | 446 |
| H1 | Bollinger/RSI mean reversion | 23 | 38 | 1,514 | 7,979 | 446 |

- Two separate CLI processes produced byte-identical JSON with SHA-256
  `2e5d0a7230beaa3839babbf47acdb8fd3f43d603ed9af6700a961bc1e470c60e`.
  [Candidate ledger](candidate-signals.json)
- All 202 existing tests and six new tests passed with both
  OPENBLAS_NUM_THREADS and OMP_NUM_THREADS set to 1. New tests exercise both
  directions, channel equality, the momentum filter, gap resets, every prefix
  of a synthetic series spanning four segments, altered future candles at
  every cutoff and reconciliation across all frozen source rows.
  [Regression log](offline-regression.txt)
- The Phase 6.7 generator rebuilt all 13 files in a temporary directory and
  direct byte comparisons matched the archived HTML, JSON and 11 SVGs.
  [Regenerated SHA-256 inventory](phase-6-7-regenerated.sha256)
- Before and after hashes match for 132 files across earlier reports, raw
  data, original strategy and risk policy. The existing Phase 6.7 provenance
  test's later-phase directory list now includes Phase 6.10.3 so its original
  source-inventory assertion still applies. [Before](preserved-before.sha256) ·
  [After](preserved-after.sha256)

NO-GO remains in effect. Performance comparison is deferred to Phase 6.10.4.
