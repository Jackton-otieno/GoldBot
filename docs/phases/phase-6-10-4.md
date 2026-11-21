# Phase 6.10.4 controlled strategy comparison

The Phase 6.10.3 strategy research in the main GoldBot checkout supplied the
frozen EMA/RSI pullback, Donchian breakout and Bollinger/RSI mean-reversion
signals. The comparison checked the published signal ledger digest and matched
each ledger row to the original candle by timeframe, source row and raw label.
The earlier H1 candle-gap investigation is deferred.

All 32 runs used the original, previously inspected candles. Within each
timeframe and scenario, the entry signal was the only input replaced. Each run
used a separate USD 3,000 account, the baseline replay's ATR, the same next-open
and gap rules, the same sizing and exits, and the Phase 6.8.5 hypothetical cost
settings and run-long loss budget. All eight baseline summaries matched the
archived Phase 6.8.5 results exactly.

Each cell shows terminal marked P/L in USD and the number of closed trades.

| Timeframe | Strategy | Directional signals | Ideal | Low | Baseline | Stress |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| M15 | Frozen baseline | 132 | −23.95 / 8 | −24.59 / 8 | −25.31 / 8 | −35.88 / 6 |
| M15 | Trend pullback | 718 | +45.52 / 9 | +22.85 / 8 | −7.97 / 7 | −34.47 / 6 |
| M15 | Donchian breakout | 841 | −57.38 / 5 | −58.03 / 5 | −58.73 / 5 | −53.05 / 4 |
| M15 | Bollinger mean reversion | 344 | +15.89 / 8 | −11.20 / 7 | −11.78 / 7 | −25.12 / 5 |
| H1 | Frozen baseline | 127 | −19.94 / 7 | −20.45 / 7 | −43.12 / 6 | −20.17 / 7 |
| H1 | Trend pullback | 52 | −52.22 / 4 | −52.74 / 4 | −53.30 / 4 | −28.55 / 5 |
| H1 | Donchian breakout | 100 | −7.58 / 7 | +1.90 / 6 | +1.46 / 6 | +2.71 / 6 |
| H1 | Bollinger mean reversion | 61 | +6.65 / 6 | +6.27 / 6 | +5.83 / 6 | −55.79 / 4 |

No strategy and timeframe combination had positive marked P/L under all four
cost scenarios. Minimum volume was the most common entry rejection for every
strategy under baseline costs. Costs also affected admission and trade paths,
so scenario differences include changes in which trades closed. Each run
closed between four and nine trades. These results are descriptive and support
no promotion or selection for trading.

The full report includes rejections, drawdown, terminal positions and closed
trades. Its SHA-256 is
`4829ae1bb824ac289a3328b92ad2bccb99c78d2b883a548fb24d9e08064dc5df`.
The comparison verified entry and closure counts and excluded invalid signal
rejections in all 32 runs. An initial adapter run used reason codes that the
simulator rejected. The corrected adapter uses the existing setup codes, and
the superseded output was discarded.

[Comparison results](../../reports/phase_6_10_4/comparison.json) ·
[Offline runner](../../tools/compare_strategies_phase_6104.py)

The research replay used no broker session. Future validation still needs
Exness account-variant and monetary-precision evidence, verified UTC and
session mapping, quote and execution-cost coverage, and documented risk-day
inputs. A historical source needs independently verified coverage and
provenance before it can support the prospective protocol.
[Readiness blocker register](../../reports/phase_6_9_6/readiness.md) ·
[Draft validation protocol](../../reports/validation_phase_6_8_6/draft-protocol.md)

GoldBot remains **NO-GO**.
