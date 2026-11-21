# GoldBot Phase 6.5 Execution-Cost Sensitivity

Run the synthetic comparison from the GoldBot root.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.backtesting.sensitivity_analysis
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The module writes strict JSON to standard output. The checked-in
[report](../../reports/sensitivity_phase_6_5/sensitivity.json) uses decimal
strings for financial quantities and contains no run timestamp.

## Inputs and execution

The four hypothetical cases use the requested spread, slippage and round-trip
commission. The XAUUSD quote unit is USD per troy ounce, so spread maps directly
to the full bid/ask price difference and slippage maps directly to each of the
entry and stop slippage fields. Commission maps directly to USD per lot per
round trip. The hypothetical USD-linear contract is 100 troy ounces per lot,
with a USD 0.005 price tick and point, USD 0.50 loss tick value per lot, volume
0.01 to 10 lots in 0.01-lot steps, zero minimum stop distance in points,
and USD 200 margin per lot.

Cost inputs must be finite nonnegative Decimal values. Half-spread and
slippage must be exact tick multiples. The converter rejects off-grid
cost inputs before the simulator can round fills. The execution engine
applies its existing rules to dynamic order levels and fills.

| Scenario | Spread USD/oz | Slippage USD/oz per modeled leg | Round-trip USD/lot |
| --- | ---: | ---: | ---: |
| Ideal | 0 | 0 | 0 |
| Low | 0.15 | 0.05 | 3 |
| Baseline | 0.30 | 0.10 | 7 |
| Stress | 1.00 | 0.50 | 15 |

The fixed comparison holds both reference prices and volume constant. A
0.10-lot buy uses midpoints 2,000 and 2,003, and a 0.10-lot sell uses 2,000 and
1,997. Each market leg pays half-spread and adverse slippage. Each round trip
pays commission once. For each trade, the USD 30 midpoint P/L less spread,
two slippage increments and commission reconciles to net P/L. This controlled
calculation has no stop or target triggers.

The dynamic comparison runs the existing portfolio, execution, risk and
performance engines on the same eight hand-authored M15 candles, fixed ATR of
1.0 and injected close signals. Each scenario starts with USD 3,000 in balance
and equity and its own coordinator. Explicit risk-day boundaries take effect
at the opens of rows 1 and 6. The replay labels are synthetic sequence
coordinates. The existing risk settings apply throughout.

The performance report gives realized and marked returns as fractions of
starting balance and equity, respectively. Its marked equity values terminal
positions at the liquidation-side quote and shows pending commission
separately. Drawdown uses observed ledger events. Dynamic spread and slippage
attribution are JSON null because the portfolio ledger records combined fill
prices. Scenario-to-scenario P/L changes also reflect position size, trigger
timing and risk gates.

## Results

All P/L, drawdown and commission values below are in USD. Percentage returns
are rounded for display. Commission includes closed positions.

| Scenario | Fixed net P/L | Dynamic realized net P/L | Marked equity | Realized return | Marked return | Max drawdown | Entries / closes / rejections | Commission paid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ideal | 60.00 | 60.00 | 3,065.00 | 2.000% | 2.167% | 0.00 | 3 / 2 / 4 | 0.00 |
| Low | 54.40 | -76.96 | 2,925.44 | -2.565% | -2.485% | 103.12 | 3 / 2 / 4 | 0.51 |
| Baseline | 48.60 | -67.52 | 2,933.28 | -2.251% | -2.224% | 95.76 | 3 / 2 / 4 | 1.12 |
| Stress | 17.00 | -65.75 | 2,934.25 | -2.192% | -2.192% | 73.25 | 2 / 1 / 5 | 0.75 |

The first buy sizes at 0.10, 0.09, 0.08 and 0.05 lots in scenario order. Ideal
hits its target on row 2. The other cases hold through the adverse row 3 gap,
fill at an open stop and reject two subsequent entries under the daily loss
limit. The explicit row 6 boundary resets the daily gate. Stress holds the
second trade through the end while the other scenarios close it at target
and enter a new buy. Stress loses less in realized terms than low or baseline
in this fixture as smaller sizes reduce the gap loss and exit paths diverge.
The controlled fixed trades show increasing cost across all four cases.

Historical execution remains deferred pending verification of broker risk-day
boundaries, server time and DST, historical executable quotes and execution
inputs, and resolution of the broker tick-value discrepancy. These synthetic
results provide no evidence of historical profitability. Phase 6.6 is pending
review.
