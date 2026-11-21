# GoldBot Phase 6.1 historical market replay

Run from `D:\GoldBot` in PowerShell.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.backtesting.historical_replay
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

## Inputs and event order

The audit command checks the SHA-256 of each original XAUUSD CSV against
its pinned digest and requires 10,000 rows per file. Parsing uses the same
bytes that were hashed. It follows the analyzer's column schema and the
indicator export's interval rules. Headers, field counts, numeric domains,
OHLC bounds, and strictly increasing interval-aligned label differences
are checked before any events are returned. The lower-level
`load_replay` API also accepts shorter inputs for verification and records
whether a supplied digest was checked.

Each timeframe has its own independent sequence. Row numbers are one-based
within each CSV, with the header excluded. Each row emits an open event and
then a closed event. Both carry the original integer label, which identifies
the candle, and the raw difference from the previous observed label.
The label on the closed event represents the same candle and carries no
separate close timestamp.

- The open event exposes the open price and sequence and gap metadata.
  Earlier closed events have already been emitted.
- The closed event exposes OHLC, tick volume, spread, real volume, the
  existing SMA, EMA, RSI, MACD and ATR calculations, and the existing
  strategy decision and reasons. Warm-up indicator values serialize as JSON
  null. The final candle still emits both events and its closed event has
  no successor open.
- A difference longer than the nominal interval flags the next observed
  row. Indicators continue over observed rows and strategy evaluation
  applies the existing gap-crossover HOLD rule. Gaps produce no synthetic
  candles. The timeframe streams stay separate.

The loader validates and computes the complete input in memory using the
existing causal formulas, then exposes the ordered event sequence. Consumers
must process it in order and use only the current and previously emitted
events. Precomputed signal exports serve only as a verification reference.
In a future simulator, an observed successor open is the first event at
which a closed signal could be considered for execution. The replay itself
makes no eligibility or fill decision.

## Audit results

| Timeframe | Opens | Closes | Flagged gaps | BUY | SELL | HOLD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M15 | 10,000 | 10,000 | 114 | 53 | 79 | 9,868 |
| H1 | 10,000 | 10,000 | 446 | 66 | 61 | 9,873 |

The JSON audits include source provenance, decision and reason counts,
every flagged gap open, and sample events from the first and final row,
around the first gap, and at the first BUY and SELL decision. All 20,000
closed rows matched the archived Phase 4.1 indicators and signals by row
number, raw label, delta, gap flag and close. Both audit files reproduced
byte for byte. All 66 tests passed in the existing virtual environment,
including seven replay tests. Both original CSVs and all 15 pre-existing
reports matched their pre-implementation hashes.

## Limitations

Timezone, server offset and DST are unverified. Label differences can
reflect session breaks, missing observations or clock effects. The archive
does not establish quote freshness, explain gaps or attest historical broker
specifications. Phase 5.2 saw USD 0.10 per tick per lot in demo metadata
versus USD 1.00 implied by calculator probes. The discrepancy remains
unresolved and Phase 5.1 still rejects the broker inputs.

Daily risk resets need a verified risk-day boundary and evidence for the
corresponding account state. Raw labels alone cannot establish either.
Phase 6.1 ends at market events and strategy decisions. Phase 6.2 execution
simulation, including sizing, costs, fills and profitability, is deferred
pending review.
