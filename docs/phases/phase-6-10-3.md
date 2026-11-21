# Phase 6.10.3 GoldBot alternative strategy research

**NO-GO remains in effect.** This phase records entry-direction hypotheses on the
frozen XAUUSD M15 and H1 exports. Each candidate runs independently on each
timeframe. Phase 6.10.4 owns performance comparison. This phase uses no
historical profitability optimization, broker connection, order execution,
or formal prospective validation.

## Fixed candidate rules

Let C, H, and L denote the close, high and low. Subscript t denotes the candle
that has just closed. All lookbacks count candles within the current contiguous
segment. The rules use symmetric long and short conditions and apply the same
parameters to M15 and H1.

| Candidate | BUY | SELL | First eligible segment bar |
| --- | --- | --- | --- |
| Trend pullback | EMA rises, C[t−1] ≤ EMA[t−1], C[t] > EMA[t], RSI[t] > 50 | EMA falls, C[t−1] ≥ EMA[t−1], C[t] < EMA[t], RSI[t] < 50 | 21 |
| Donchian breakout | C[t] > max H[t−20…t−1] | C[t] < min L[t−20…t−1] | 21 |
| Bollinger mean reversion | C[t] < lower[t] and RSI[t] ≤ 30 | C[t] > upper[t] and RSI[t] ≥ 70 | 20 |

- **Trend pullback.** EMA(20) starts at the arithmetic mean of the first 20
  closes. Each later value is EMA[t−1] + (2/21) × (C[t] − EMA[t−1]).
  Twenty candles give the trend filter a fixed smoothing horizon. The reclaim
  of that average represents the end of a one-or-more-bar pullback, with the
  EMA direction and RSI's neutral midpoint serving as confirmation.
- **Donchian breakout.** The channel is the highest high and lowest low of the
  preceding 20 complete candles. The fixed 20-bar horizon represents a recent
  range. A strict closing breach selects moves that finish outside that range.
  An equal close or an intrabar breach alone yields HOLD. Each qualifying close
  can generate a signal, including consecutive closes.
- **Bollinger mean reversion.** The center is the arithmetic mean of the 20
  closes ending at t. Population deviation is the square root of the sum of
  squared distances from that mean divided by 20. The upper and lower bands
  are center plus and minus twice that deviation. The 20-bar, two-deviation
  bands and RSI 30/70 thresholds are conventional starting points. Their
  conjunction requires both a price excursion and extreme momentum. Equal
  closes at the bands and zero-width flat windows produce no band breach.
  Each qualifying close can generate a signal.
- **Wilder RSI(14).** For each consecutive pair of closes, gain is
  max(C[t] − C[t−1], 0) and loss is max(C[t−1] − C[t], 0). Seed the
  two averages with the arithmetic means of the first 14 changes, so
  RSI first exists on bar 15. Update each average by adding
  (observation − previous average)/14. RSI is 100 − 100/(1 + average
  gain/average loss). With zero average loss, use 100 for positive
  average gain and 50 when both averages are zero. Zero average gain
  with positive average loss yields 0.

## Source and gap handling

The builder checks the frozen SHA-256 and the expected 10,000 rows per export,
then validates source-order labels and OHLC through the historical replay
validator. Labels remain the original integers. Expected label steps are 900
seconds for M15 and 3,600 seconds for H1. Repeated, backward or off-grid label
steps fail validation. A longer on-grid step starts a fresh segment and marks
its first candle GAP for all candidates. That candle seeds the segment as bar
one. Windows, previous-close references and smoothing never cross gaps.
There is no interpolation or calendar adjustment. Short contiguous segments
can have zero eligible decisions, particularly in H1.

WARMUP marks a candle with insufficient same-segment history. HOLD marks an
eligible candle where neither rule fires. BUY and SELL mark directions
observable at the source candle close. The terminal candle may be scored at
its close. No successor observation, fill, exit, sizing, cost or P/L is used.
The ledger includes all candles and decision counts for every candidate.
Use timeframe and the one-based source row to locate a candle in the raw file.
The research tool is separate from GoldBot's trading entry point and risk
policy.

## Reproduction

Run from the GoldBot root with a fresh output path.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m tools.research_strategies_phase_6103 --output .\candidate-signals-recheck.json
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

[Candidate signal ledger](../../reports/phase_6_10_3/candidate-signals.json) ·
[Verification record](../../reports/phase_6_10_3/verification.md) ·
[Archived NO-GO assessment](../../reports/phase_6_9_6/assessment.json)

