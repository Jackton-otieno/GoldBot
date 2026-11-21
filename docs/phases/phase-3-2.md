# GoldBot Phase 3.2

Run the offline calculation with the existing environment from the project directory.

```powershell
.\.venv\Scripts\python.exe -B -m goldbot.analysis.indicators --charts
.\.venv\Scripts\python.exe -m unittest discover -v
```

The CSV calculation uses the Python standard library and the Phase 3.1 analyzer. The optional PNG charts use Matplotlib from the existing environment. Outputs default to `reports/indicators`.

The source exports were made by the closed-candle reader, which starts at MT5 candle position 1. Each export is validated independently and processed in its original order. SMA 20/50/200 uses the arithmetic mean of the trailing N observed closes, including the current close. EMA 9/21/50/200 seeds at observation N with the SMA of the first N closes. Each subsequent EMA equals the previous EMA plus 2/(N+1) times the difference between the current close and the previous EMA. The first N-1 values in each series are NaN, written as `nan` in the CSV. Every value uses only the current and earlier closed candles.

`raw_server_clock_label` preserves the integer `mt5_time_epoch` label. `raw_label_delta` is the arithmetic difference from the previous label and is blank on the first row. `gap_before` flags differences larger than 900 for M15 or 3600 for H1. Moving averages carry across gaps using observed candles only, without inserting rows or resetting. Chart lines break at flagged gaps. The chart axis uses the raw labels without timezone conversion. Server offsets, DST behavior, gap causes, and live or cross-timeframe alignment are outside this analysis.
