# Phase 6.10.2 market regime analysis

- Wilder ADX(14). Weak below 20, strong at or above 25, ambiguous in between. These are conventional Wilder interpretation bands.
- Direction is the sign of the five-bar change in EMA(20), with equal values classified flat. Twenty bars is a round smoothing horizon and five bars measures a short change relative to it.
- Volatility is ATR(14) divided by close, relative to the median of the preceding 20 normalized ATR observations in the same contiguous segment. Below two-thirds is low, above three-halves is high, and the inclusive middle is typical. The reciprocal boundaries require a multiplicative deviation by a factor of 1.5. The horizon matches the EMA horizon.
- Restart all indicator state on any non-nominal raw-label step. Mark the discontinuity row GAP and emit WARMUP independently for each component until ready. First strong/weak ADX evidence can appear on segment bar 28, direction on bar 25, and volatility on bar 35.
- Use the signal close for every scenario, including gap-rejected attempts. Retain successor gap evidence separately. Score every observed candle, including HOLD. No calendar conversion or cross-timeframe joins.


## Formulas and available evidence

For consecutive bars in a segment, true range is the maximum of high
minus low, absolute high minus prior close, and absolute low minus prior
close. Up movement is current high minus prior high. Down movement is
prior low minus current low. Positive and negative directional movement
take the respective movement only if it is positive and strictly greater
than the other. Ties contribute zero to both. Seed ATR and both smoothed
movements with the arithmetic means of the first 14 transitions. Update
each as (13 × previous + current observation) / 14. DX is 100 times the
absolute difference of the two smoothed movements divided by their sum.
The common ATR denominator of the directional indices cancels. A zero
movement sum contributes zero DX. ADX seeds with the first 14 DX values
and uses the same Wilder update thereafter.

EMA seeds at the mean of the first 20 closes and updates by adding
2/21 times the difference between the close and prior EMA. Slope is
(EMA now − EMA five bars ago) / 5 in USD/oz per bar. Normalized ATR is a
fraction of close. A zero historical median and zero current fraction
produce a ratio of one. A zero median with positive current fraction
produces UNDEFINED volatility. The raw inputs are validated against their
original SHA-256 digests. Invalid or absent source records fail input
validation. WARMUP means a required indicator or reference is unavailable.
AMBIGUOUS means measured ADX falls in the middle band. Slope direction
and ADX strength are distinct. A weak or ambiguous ADX can accompany
either slope direction.

A non-nominal step across observed labels is a discontinuity, regardless
of whether it reflects a closure or absent observations. The gap candle
seeds the new segment. Price movements across the boundary are excluded.
Source labels stay as raw integers in source order. Regime evidence uses
the current closed candle and its contiguous history. The successor open
establishes the attempt, including a separate successor-gap flag.
Exit data supplies outcomes only. A trade is grouped by its signal regime
for its entire observed outcome.

## Reconciled outcomes

Each case has a separate hypothetical account. Net amounts are USD. Wins
use positive net P/L, and win rates use closed trades as the denominator.
A group with zero closures has a null win rate. The audit records the
first rejection reason, which limits what can be inferred about checks
that were skipped.

| Frame | Costs | Signals / attempts | Filled / closed | Below minimum volume | Gap rejections | Loss-limit rejections | Wins / closed | Stops / targets | Net USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M15 | Ideal | 132 | 8 | 123 | 1 | 0 | 2/8 | 6/2 | -23.950 |
| M15 | Low | 132 | 8 | 123 | 1 | 0 | 2/8 | 6/2 | -24.590 |
| M15 | Baseline | 132 | 8 | 94 | 1 | 29 | 2/8 | 6/2 | -25.310 |
| M15 | Stress | 132 | 6 | 125 | 1 | 0 | 1/6 | 5/1 | -35.880 |
| H1 | Ideal | 127 | 7 | 114 | 6 | 0 | 2/7 | 5/2 | -19.935 |
| H1 | Low | 127 | 7 | 114 | 6 | 0 | 2/7 | 5/2 | -20.445 |
| H1 | Baseline | 127 | 6 | 115 | 6 | 0 | 1/6 | 5/1 | -43.115 |
| H1 | Stress | 127 | 7 | 114 | 6 | 0 | 2/7 | 5/2 | -20.165 |

M15 had 114 gap rows. Its longest contiguous segment had 92 bars.
Full three-axis coverage reached 6,120 of 10,000 candles and 79 of 132
directional signals. In baseline, six closures had complete evidence and
all six had typical volatility. The other two had all axes in warmup.
The table shows the baseline joint groups with closures. The report
includes all observed groups, even those with zero signals or closures.

| M15 baseline regime | Candles | Directional signals | Rejected | Below minimum volume | Wins / closed | Stops / targets | Net USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Down / weak / typical | 900 | 26 | 24 | 19 | 1/2 | 1/1 | 5.780 |
| Up / ambiguous / typical | 595 | 12 | 11 | 9 | 0/1 | 1/0 | -13.475 |
| Up / strong / typical | 1,424 | 5 | 4 | 2 | 0/1 | 1/0 | -7.470 |
| Up / weak / typical | 737 | 15 | 13 | 11 | 1/2 | 1/1 | 11.340 |
| Warmup / warmup / warmup | 2,626 | 36 | 34 | 27 | 0/2 | 2/0 | -21.485 |

H1 had 446 gap rows and a longest contiguous segment of 23 bars,
below the earliest availability of each axis. All 127 directional
signals and all H1 closures therefore had three warmup labels. H1
provides no outcomes with measured regimes under this rule.

The scenario records repeat the same underlying signals. The union of
closed signal rows contains eight M15 rows and eight H1 rows. The
intersection across all four cost scenarios contains six M15 rows and
five H1 rows. The report gives all six pairwise overlaps per timeframe,
including overlaps by regime where there were directional signals.
The 57 scenario closures describe a small set of reused entries, and
the two timeframes share an instrument and market history.

## Reproduction and research limits

[Regime report with row-level annotations and ledgers](../../reports/phase_6_10_2/market-regimes.json) ·
[Verification record](../../reports/phase_6_10_2/verification.md) ·
[Frozen trade audit](../../reports/phase_6_10_1/audit.json)

The report joins source rows, attempts and closed trades by timeframe and
one-based signal row. Fields under each axis and under the joint regime
are separate views of the same candles. Summing across those views would
duplicate observations. The builder reproduces the Phase 6.10.1 audit
and its two upstream simulation archives before checking each attempt,
fill and group total. Scenario tables are descriptive. The small groups,
shared histories, rejections and warmup coverage preclude attribution or
profitability inference.

To reproduce in a copy with the original layout, run
python -B -m tools.analyze_market_regimes_phase_6102 with a fresh output
path supplied through --output. Set OPENBLAS_NUM_THREADS and
OMP_NUM_THREADS to 1 for the full offline unittest regression. The
classifier and report are offline research additions.

Future research can first establish why H1 labels break continuity and
seek better coverage with verified candle schedules and clock semantics.
Record evidence on executable quotes, costs, contract precision and
risk-day inputs through the existing readiness process. Any proposal
for later independent validation needs a precommitted protocol,
nonoverlapping data and separate authorization. Phase 6.9.6 **NO-GO**
remains in effect.

