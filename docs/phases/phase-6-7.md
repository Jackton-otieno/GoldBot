# GoldBot Phase 6.7 offline reporting

Open the [local report](../../reports/consolidated_phase_6_7/index.html) in a
browser. The [JSON summary](../../reports/consolidated_phase_6_7/summary.json)
keeps exact source values, nullable metrics and reasons. The HTML uses local
CSS, existing indicator PNGs and generated SVGs. It requires no server,
JavaScript, or network connection. Keep the repository layout intact so
the links to source evidence and existing charts continue to work.

From PowerShell in `D:\GoldBot`:

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.reporting.generate
& .\.venv\Scripts\python.exe -B -m unittest discover -v
Start-Process .\reports\consolidated_phase_6_7\index.html
```

The generator validates the original exports and 19 earlier report files
before writing. Its provenance map contains SHA-256 digests of the
read bytes. It cross-checks market quality row counts and raw-label
histograms against the originals, reconciles strategy CSV counts with the
signal and replay audits, verifies published input and partition
commitments, and checks synthetic account and trade arithmetic against
the event series. A missing or inconsistent required input fails with
its path. Output has stable ordering and no generation timestamp.

Historical observations describe the original XAUUSD candles and derived
signals and replay events. Raw labels remain in source order without
timezone conversion. All Phase 6.6 partitions are retrospective.
The synthetic charts use only Phase 6.5 fixture values, with event index
for marked equity and drawdown. Realized net P/L comes from closed trades.
Marked equity includes terminal unrealized P/L. Pending commission and
unresolved positions remain separately identifiable.

Historical execution and profitability are unavailable. Genuine
out-of-sample validation and automated demo readiness remain blocked.
Resolve the broker tick-value discrepancy, verify broker clock, DST,
risk-day boundaries and historical executable quotes and execution
inputs, and prepare the precommitted, nonoverlapping holdout protocol
in a dedicated blocker-resolution phase before Phase 7.



## Verification

All 113 offline tests passed in the existing virtual environment, including
six reporting tests. The HTML, JSON and 11 generated SVG charts regenerated
byte for byte. Both original CSVs and all 19 earlier reports retained their
pre-implementation SHA-256 hashes. Phase 6 offline backtesting infrastructure
is complete. Phase 6.7 read saved evidence and did not run historical
execution, strategy tuning, MT5, or the trading entry point.
