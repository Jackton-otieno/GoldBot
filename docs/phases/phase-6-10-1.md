# GoldBot Phase 6.10.1 retrospective trade audit

**RESEARCH · NO-GO.** All eight frozen Phase 6.8.5 simulations reconciled
byte for byte to the archived assumptions and results. Each ended flat,
with no pending signal and a negative realized and terminal marked P/L.
The 57 closed-trade records are repeated scenario observations on two
previously inspected XAUUSD exports. The sample is small, the exports
share instrument and market history, and the scenarios share inputs
within each timeframe. These results cannot establish independent
validation, profitability, or execution readiness.

[Row-level trade and rejection audit](../../reports/phase_6_10_1/audit.json) ·
[Verification record](../../reports/phase_6_10_1/verification.md) ·
[Frozen assumptions](../../reports/research_phase_6_8_5/assumptions.json) ·
[Frozen results](../../reports/research_phase_6_8_5/results.json) ·
[Phase 6.9.6 readiness](../../reports/phase_6_9_6/readiness.md)

## Exact results and rejection funnel

Each run began with a separate hypothetical USD 3,000 account. Gross,
commission, net and observed maximum drawdown are in USD. The last four
columns balance to 132 directional attempts per M15 run and 127 per H1
run. All 10,000 closes per timeframe yielded 53 BUY, 79 SELL and 9,868
HOLD on M15, and 66 BUY, 61 SELL and 9,873 HOLD on H1. Each directional
signal had a successor open. The funnel counts the recorded first
decision for each attempt, so it cannot quantify checks that were never
reached. No directional attempt recorded a position-limit or margin
rejection.

| Frame | Scenario | Gross | Commission | Net | Max drawdown | Filled | Below min. volume | Gap entry | Loss limit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M15 | Ideal | -23.950 | 0.00 | -23.950 | 41.165 | 8 | 123 | 1 | 0 |
| M15 | Low | -24.350 | 0.24 | -24.590 | 41.885 | 8 | 123 | 1 | 0 |
| M15 | Baseline | -24.750 | 0.56 | -25.310 | 42.645 | 8 | 94 | 1 | 29 |
| M15 | Stress | -34.980 | 0.90 | -35.880 | 44.535 | 6 | 125 | 1 | 0 |
| H1 | Ideal | -19.935 | 0.00 | -19.935 | 35.255 | 7 | 114 | 6 | 0 |
| H1 | Low | -20.235 | 0.21 | -20.445 | 35.905 | 7 | 114 | 6 | 0 |
| H1 | Baseline | -42.695 | 0.42 | -43.115 | 43.115 | 6 | 115 | 6 | 0 |
| H1 | Stress | -19.115 | 1.05 | -20.165 | 25.965 | 7 | 114 | 6 | 0 |

## Entries, exits and raw-label gaps

Every entry filled at 0.01 lot on the next observed row's open using
that signal close's decision and ATR. The labels advanced 900 raw seconds
for every M15 entry and 3,600 for every H1 entry. These are differences
between candle labels. The handoff was from the signal close to the
successor open, and the physical delay between those events is unknown.
The audit uses one-based data rows, excluding the CSV header, and retains
raw integer labels. UTC, calendar sessions, and cross-timeframe alignment
were unavailable.

| Frame | Scenario | Buys / sells | Stops / targets | Same-row exits | Largest entry-to-exit row difference |
| --- | --- | ---: | ---: | ---: | ---: |
| M15 | Ideal | 7 / 1 | 6 / 2 | 1 | 8 |
| M15 | Low | 7 / 1 | 6 / 2 | 1 | 8 |
| M15 | Baseline | 7 / 1 | 6 / 2 | 1 | 8 |
| M15 | Stress | 6 / 0 | 5 / 1 | 1 | 14 |
| H1 | Ideal | 6 / 1 | 5 / 2 | 0 | 18 |
| H1 | Low | 6 / 1 | 5 / 2 | 0 | 18 |
| H1 | Baseline | 6 / 0 | 5 / 1 | 0 | 18 |
| H1 | Stress | 5 / 2 | 5 / 2 | 0 | 18 |

M15 had 114 raw-label gaps and H1 had 446. There were no opening or
gap-row exits and no observed both-touch exits. One position crossed a
raw-label gap in each H1 run. In ideal, low and baseline it was the buy
from row 404 to 422. In stress it was the sell from row 2,757 to 2,775.
The absent intervals have unknown quote paths and fill eligibility.
Under the frozen model, an adverse opening stop uses the opening exit
quote plus adverse slippage and price-grid rounding, a target receives the
target price, and a both-touch candle resolves stop-first. This sample
contains no instance of those opening or both-touch branches. All
observed modeled stop losses equaled their planned values inclusive of
commission.

## Hypothetical costs and path differences

The ideal, low, baseline and stress models used spread of 0, 0.15,
0.30 and 1.00 USD/oz, respectively, with adverse entry and stop slippage
of 0, 0.05, 0.10 and 0.50 USD/oz each. Round-trip commission was 0,
3, 7 and 15 USD/lot, booked at exit. OHLC was modeled as midpoint,
with an assumed 0.005 USD/oz grid and 100 oz/lot. The CSV spread played
no role. Financing, swap and rollover were omitted. The audit shows
entry fill versus opening midpoint and stop fill versus stop level as
fill differences. Isolated realized spread and slippage costs remain
unavailable because these assumptions also enter order levels, sizing
and path selection.

Within each timeframe, the comparison matches trades by source signal row
and side. The USD bridge equals matched net differences plus the net from
scenario-only trades minus the net from ideal-only trades. The matched
column can include changed exit rows and price levels.

| Frame | Scenario vs. ideal | Matched count | Matched net difference | Ideal-only net | Scenario-only net | Total difference |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| M15 | Low | 8 | -0.640 | 0.000 | 0.000 | -0.640 |
| M15 | Baseline | 8 | -1.360 | 0.000 | 0.000 | -1.360 |
| M15 | Stress | 6 | -4.900 | 7.030 | 0.000 | -11.930 |
| H1 | Low | 7 | -0.510 | 0.000 | 0.000 | -0.510 |
| H1 | Baseline | 6 | -1.220 | 21.960 | 0.000 | -23.180 |
| H1 | Stress | 6 | -2.900 | -14.120 | -11.450 | -0.230 |

M15 stress rejected ideal signals 3,023 and 7,714 as below minimum
volume. H1 baseline rejected the ideal target trade from signal 2,086 on
the same reason. H1 stress rejected signal 540 and took signal 2,756,
which ideal had rejected. The H1 baseline net was below its stress net
with a different admitted trade set. H1 showed fewer fills than M15 in
ideal, low and baseline, more raw-label gap rejections across all scenarios,
and a larger maximum holding row difference. The unaligned streams and
small trade sets preclude attributing results to timeframe or separately
identifying the effects of individual cost inputs.

## Synthetic loss latch

Phase 6.8.5 used one synthetic risk bucket per run with a USD 60 threshold
and no reset. Loss usage is the greater of cumulative realized net losses
and the observed decline from opening equity. On M15 baseline, the
row 7,717 close event (raw label 1791842400) realized the final USD 7.47
loss and brought cumulative realized losses to USD 60.00. Equity there
was USD 2,974.69. Realized gains totaled USD 34.69 and did not offset the
loss counter. The next directional entry attempt was at row 7,841 and
recorded the first of 29 loss-limit rejections. Terminal loss usage for the
other runs ranged from USD 56.93 to 59.785. The observed drawdown,
insolvency and margin-deficit flags remained inactive across the eight
runs. The experiment has no verified risk-day boundaries or opening
equity attestation.

## MAE and MFE

The ledger reports lower magnitudes for maximum adverse and favorable
excursion in USD/oz under the hypothetical quote model. It measures
from the modeled entry fill to the hypothetical bid for buys or ask for
sells. It uses the entry open, later observed opens through the exit
row, and highs and lows only on whole bars the modeled trade survived.
Exit-row high, low and close are excluded because their order relative to
exit cannot be resolved. Gap interiors and modeled fill effects are
excluded. A reported zero means the selected observations show no
excursion in that direction. For a same-row exit only its opening quote
contributes. For example, the H1 ideal gap-crossing buy had MAE at least
9.14 and MFE at least 12.68 USD/oz in this model. Exact pre-exit extremes,
tick order and executable excursions remain unknown.

## Reproduction and readiness

The archive contains exact run summaries and closed fills. It omits the
transient per-open rejection detail and latch inputs. The authorized
isolated offline replay recovered those details by observing the
unchanged research runner's in-memory ledgers. It required byte equality
for both frozen JSON files before publishing the audit. The runner
checks raw CSV hashes and the frozen strategy manifest. The audit also
records SHA-256 provenance for the archived assumptions, results, and
readiness assessment.

From GoldBot, set both thread variables to 1. Copy its data and reports
to a separate scratch root with the same directory layout, then choose
a fresh output path inside that root.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m tools.audit_research_phase_6101 --scratch-root $scratchRoot --output (Join-Path $scratchRoot 'audit.json')
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

Phase 6.9.6 remains NO-GO for execution, verified historical execution
and prospective authorization. Readiness still requires authoritative
account and broker economics and monetary precision, dated UTC and
sessions evidence, executable quote coverage and costs, and an attested
risk-day opening and equity. Independent exposure attestation and a
precommitted sealed protocol remain prerequisites to seeking separate
prospective authorization. The isolated reproduction used local files
and the frozen strategy and configuration.
