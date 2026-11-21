# GoldBot Phase 3.3

Run from the GoldBot directory using the existing Python environment.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.analysis.indicators --phase-3-3 --charts
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The phase flag generates separate CSVs and PNGs in `reports/indicators_phase_3_3`. The CSVs retain the Phase 3.2 columns and append five indicator columns. The PNGs show RSI, MACD with signal and histogram as lines, and ATR in three panels.

| CSV field | Leading NaN rows | First valid candle (one-based) |
| --- | ---: | ---: |
| `rsi_14` | 14 | 15 |
| `macd_12_26` | 25 | 26 |
| `macd_signal_9` | 33 | 34 |
| `macd_histogram` | 33 | 34 |
| `atr_14` | 13 | 14 |

- **RSI(14)** uses 14 close-to-close changes to seed separate simple averages of gains and losses. Both averages then use Wilder smoothing, updating by one fourteenth of the difference between the current input and the previous average. RSI is 50 when both averages are zero, 100 when only loss is zero, and 0 when only gain is zero. [RSI calculation](https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/)
- **MACD(12,26,9)** subtracts the 26-candle EMA from the 12-candle EMA on the same row. Both EMAs use the Phase 3.2 simple-average seed and alpha of 2 divided by period plus one. The signal uses the same convention, seeded by the first nine valid MACD values, including the current row. The histogram is MACD minus signal on that row.
- **ATR(14)** uses high minus low as the first true range. Subsequent true ranges are the maximum of high minus low, the absolute distance from high to the previous observed close, and the absolute distance from low to that close. The first ATR averages the first 14 true ranges and subsequent values use Wilder smoothing. [True range calculation](https://www.tradingview.com/support/solutions/43000501823-average-true-range-atr/)

Each timeframe is calculated independently in original export order using raw server-clock labels. Indicators at any row depend only on that closed candle and earlier observed candles. A flagged label gap carries forward the indicator state and the previous observed close, with no synthetic candles or time weighting. Charts break the lines at flagged gaps while retaining the candle immediately after each gap. Strategy is deferred for review.
