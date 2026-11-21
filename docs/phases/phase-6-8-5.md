# Phase 6.8.5 RESEARCH historical backtesting

Eight hypothetical OHLC simulations used the original 10,000 XAUUSD rows per
timeframe. Every M15 and H1 run began with its own USD 3,000 portfolio. The
verified historical execution gate remains closed. The reports describe
behavior under specified assumptions and establish no trading readiness,
profitability, daily compliance, or genuine unseen holdout.

[Assumptions and hashes](../../reports/research_phase_6_8_5/assumptions.json) |
[Results and closed trades](../../reports/research_phase_6_8_5/results.json) |
[Phase 6.8.4 readiness](../../reports/phase_6_8_4/historical-readiness.json)

## Replay and risk

The runner checks the original CSV hashes and checks the current strategy
manifest against the saved Phase 6.6 freeze. Each timeframe's previously
inspected 60/20/20 partitions form one continuous row stream, with no
partition resets or tuning. The replay uses raw integer labels in original
row order. It recognizes 114 M15 and 446 H1 label gaps. It assigns no UTC,
aligns no timeframes, and inserts no rows.

The previous close supplies the signal and ATR for the next observed open.
Entries at gap opens are skipped. A position held at the open blocks another
entry there, even if it exits at that open. Gap stops use the adverse
opening quote plus slippage. Targets fill at the target price. A candle
touching both stop and target resolves stop-first. Terminal positions and
pending signals are reported as unresolved when present.

The existing planner retains its 0.5% per-trade risk cap, one-position
limit, 1.5 ATR stop, 2R target, and 10% observed drawdown latch. One synthetic
risk bucket starts at row 1 and stays open for the full run. Its USD 60
loss threshold counts the greater of cumulative net realized losses and
decline from opening equity. Profits do not cancel prior realized losses.
The planner can reduce the size or reject new positions as the budget
shrinks. Gaps can exceed the modeled risk. The latch has no automatic reset.

## Hypothetical quotes and costs

Treat OHLC as midpoint and apply fixed symmetric spread. The hypothetical
contract is 100 troy ounces per lot, with a USD 0.005 price grid and USD 0.50
per tick per lot. Volume ranges from 0.01 to 10 lots with a 0.01 lot step.
The modeled broker minimum stop distance is zero. Fixed USD 200 per lot is
reserved for margin. The model also checks marked free margin at entry and
records any later deficit. Broker margin calls and liquidation are omitted.
USD account, profit and margin currencies use identity conversion.

| Scenario | Spread USD/oz | Adverse entry and stop slippage USD/oz, each | Round-trip commission USD/lot |
| --- | ---: | ---: | ---: |
| Ideal | 0.00 | 0.00 | 0 |
| Low | 0.15 | 0.05 | 3 |
| Baseline | 0.30 | 0.10 | 7 |
| Stress | 1.00 | 0.50 | 15 |

These are Phase 6.5 hypothetical inputs. CSV spread is unused. Spread and
slippage are embedded in the modeled fills and are not separately attributed.
Commission is charged on exit. All scenarios omit funding, swap and rollover
charges. Marked P/L uses the exit side of the hypothetical quote, before
any prospective exit commission. Drawdown uses observed open and close
ledger events only. No annualized, elapsed-time, or calendar-day metrics
are computed.

## Results

All eight runs finished flat, with no pending signal. Realized net P/L
therefore equals terminal marked P/L in each row. Values are in USD.

| Timeframe | Scenario | Closed trades | Realized and marked P/L | Observed max drawdown |
| --- | --- | ---: | ---: | ---: |
| M15 | Ideal | 8 | -23.950 | 41.165 |
| M15 | Low | 8 | -24.590 | 41.885 |
| M15 | Baseline | 8 | -25.310 | 42.645 |
| M15 | Stress | 6 | -35.880 | 44.535 |
| H1 | Ideal | 7 | -19.935 | 35.255 |
| H1 | Low | 7 | -20.445 | 35.905 |
| H1 | Baseline | 6 | -43.115 | 43.115 |
| H1 | Stress | 7 | -20.165 | 25.965 |

The M15 baseline latched at the close of row 7,717 and recorded 29 subsequent
entry rejections with the loss-limit reason. No other run reached the latch
threshold. Remaining budget, lot size and exit conditions can change which
trades occur, so the different cost scenarios can follow different paths.

## Reproduction and remaining evidence

From D:\GoldBot, using its existing environment:

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.backtesting.research_phase_6_8_5
& .\.venv\Scripts\python.exe -B -m unittest discover
```

The Phase 6.8.4 probes recovered zero ticks. Archive coverage, historical
quote basis, UTC mapping, effective trading costs and contract economics,
currency conversion, margin schedules, sessions, risk-day boundaries and
fill eligibility remain unresolved. Phase 6.8.6 prospective validation
planning is pending review.
The [pre-change inventory](../../reports/research_phase_6_8_5/preserved-before.sha256)
contains both original CSVs and all 49 prior reports. The full offline suite
includes a byte-for-byte reproduction of the Phase 6.7 HTML, JSON and 11 SVGs.
