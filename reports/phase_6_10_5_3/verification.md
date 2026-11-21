# Phase 6.10.5.3 verification

**Engineering completed. New research-data and execution-grade acceptance
blocked. GoldBot remains NO-GO.**

- The acquisition code pins the provider route and instrument, saves originals
  exclusively, and checks byte limits. HistData processing streams its ZIP
  member and retains only one hour for analysis. The BI5 decoder caps
  decompression, record size and count. Audit checks cover source order, equal
  labels, repeated payloads, bid/ask and spread validity, absence of synthetic
  candles, and causal UTC binning. Real UTC candle production remains blocked
  pending an accepted source payload. [Manifest](data-manifest.json) ·
  [Quality results](data-quality.json)
- The exact independently pinned Exness demo returned no rows for the two
  bounded history requests. A fresh diagnostic artifact and the prior
  312-tick artifact are listed separately. No accounts were switched,
  orders submitted, trades executed, or data purchased. The deferred
  MetaQuotes probe, strategy comparisons and prospective collection remain
  outside this phase. [Retrieval evidence](source-evidence.md)
- All 222 offline regression tests passed with OPENBLAS_NUM_THREADS=1 and
  OMP_NUM_THREADS=1. The 217 existing tests remain in the suite. Five new
  tests cover causal bins and gaps, duplicates and malformed ticks, BI5
  decoding, transport limits, fixed EST, ZIP identity and digest, and
  fail-closed Exness identity and unavailable-history handling. The exact
  dashboard regression regenerated and matched all 13 Phase 6.7 outputs.
  [Regression log](offline-regression.txt)
- SHA-256 verification covers 279 prior files, including the previous
  protected reports, raw datasets and unchanged production modules.
  The existing launcher and reporting test's later-phase list were the only
  prior files edited. The manifest records all new and intentionally
  changed files. [Before](preserved-before.sha256) ·
  [After](preserved-after.sha256) · [Artifact manifest](phase-artifacts.sha256)

The next data acceptance decision requires a complete bounded provider
payload and verification of scope, rights, time encoding and actual
coverage. No source is accepted for Exness execution or prospective
validation. The existing monetary precision, timestamp, dated-session
and daily-risk dependencies remain in force. [Readiness](historical-readiness.json)
