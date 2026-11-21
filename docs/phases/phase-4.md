# GoldBot Phase 4.1

From the GoldBot directory, use the existing Python environment.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.strategy.signals
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The command reads the Phase 3.3 indicator CSVs and writes one signal CSV and one
counts JSON per timeframe under `reports/signals_phase_4_1`. Each CSV retains the
original columns and source order. `source_row` counts candles from 1, excluding
the header. The JSON includes the SHA-256 of the exact derived input bytes.

## Rule

A BUY requires EMA50 > EMA200, the previous EMA9 <= EMA21 and current EMA9 >
EMA21, 50 < RSI(14) < 70, a positive MACD histogram, and finite ATR(14) > 0.
A SELL requires EMA50 < EMA200, the previous EMA9 >= EMA21 and current EMA9 <
EMA21, 30 < RSI(14) < 50, a negative histogram, and finite ATR(14) > 0.
Previous EMA equality can start a crossover. Current EMA equality cannot
complete one. All trend, RSI, histogram, and ATR thresholds are strict.

Each decision uses the current closed candle and the preceding observed
candle from its own timeframe. The first eligible row is candle 200.
The preceding candle supplies only EMA9 and EMA21. There is no timeframe
alignment, future-candle access, or state shared between files.

A crossover on a row with `gap_before=True` defaults to HOLD. The flag belongs
to the interval from the previous observed candle to the current one. The
following row can qualify normally if its own gap flag is false. Raw labels
and label deltas follow Phase 3.3. They do not establish elapsed UTC, and the
production timezone and freshness blocker remains unresolved.

## Reason codes

| Code | Meaning |
| --- | --- |
| BUY_SETUP / SELL_SETUP | All checks passed for that direction |
| WARMUP | A required indicator is warming up or there is no previous candle |
| NO_CROSSOVER | Neither strict current crossover condition was met |
| GAP_CROSSOVER | The crossover spans a flagged raw-label gap |
| TREND_FILTER | EMA50 and EMA200 did not confirm the crossover direction |
| RSI_FILTER | RSI fell outside the strict range for the direction |
| MACD_FILTER | The histogram lacked the required strict sign |
| ATR_FILTER | ATR was zero |
| INVALID_INPUT | Direct evaluation rejected invalid strategy input |

For a crossover, all applicable HOLD reasons are recorded in table order.
Reason counts can overlap. The report reader rejects malformed strategy
inputs, unexpected strategy-indicator NaNs, and inconsistent raw label
metadata with a source row error. It validates all rows before writing that
timeframe's report. Expected strategy warm-up NaNs produce HOLD.

## Observed results

| Timeframe | Candles | Raw-label gaps | BUY | SELL | HOLD | Gap-crossover HOLD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M15 | 10,000 | 114 | 53 | 79 | 9,868 | 6 |
| H1 | 10,000 | 446 | 66 | 61 | 9,873 | 22 |

Each timeframe produced 199 warm-up HOLD rows. These are offline candle
classifications. The reports contain no fills at close, trades, position
management, or profit estimates. Risk management and backtesting are deferred
until review.

All 31 tests passed in the existing virtual environment. SHA-256 matched
before and after for both raw exports and all ten prior report files,
including the Phase 3.2 and Phase 3.3 CSVs and charts. Independent report
generation produced byte-identical copies of all four Phase 4.1 files.
