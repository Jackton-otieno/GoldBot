# Proposed GoldBot prospective protocol

**Draft v1. The dates, thresholds and rules require explicit independent
approval. Collection, evaluation and trading authorization are blocked.**

## Horizon and study units

- Proposed window is **[2027-02-01 00:00 UTC, 2028-02-01 00:00 UTC)**,
  including all warmup, signal and fill inputs. This is 03:00 Nairobi time
  on each endpoint date.
- Evaluate the Phase 6.6 baseline, EMA/RSI pullback, Donchian breakout and
  Bollinger/RSI mean reversion independently on M15 and H1. Report all
  eight results together. No cross-timeframe inputs, pooled portfolios,
  parameter tuning, replacement candidates or selection based on prior results.
- Each cohort begins with isolated USD 3,000 reference equity, 0.5% risk per
  trade, one position, a 1.5 ATR stop, a 2:1 target-to-stop ratio, a 2% daily
  loss limit and a 10% drawdown latch.
- Use closed candle inputs and the next eligible executable quote only
  after signal availability. Freeze exact bar construction, timestamp and
  ordering rules, delay, gaps, spread, stops, tick/volume rounding, margin,
  currency conversion, commission, swaps, costs and fill handling before
  registration. Use independently verified daily boundaries and exact opening
  equity. Fills in the study are simulated using the approved evidence.

## Proposed scoring

Each cohort requires at least **100 closed trades**, strictly positive net
P/L after all modeled costs, **profit factor at least 1.3**, observed
drawdown strictly below **10%**, zero protocol violations, and no unresolved
position at the end. Profit factor is gross winning net trade amounts
divided by absolute gross losing net trade amounts. Positive wins with
zero losses give positive infinity. A cohort with insufficient trades is
inconclusive. The fixed horizon does not extend to reach a sample target.
Breaches and economic failures are reported separately from insufficient or
unverifiable evidence. A passing cohort carries no promotion or trading
authorization.

Violations include premature access, lookahead, retrospective selection,
unregistered changes, unverified source/time or missing coverage,
unsupported fills, sizing and risk breaches, conflicting receipts, and
unresolved exposure at the end. Allow an integrity or safety stop only
with its rationale recorded and affected results marked accordingly.

## Independent approval, registration and custody

An independent approver signs the exact fixed plan and the complete prior
exposure declaration, including verified UTC envelopes and external
sources. A separate registrar signs its canonical digest and an
independently verifiable timestamp before the window starts. Confirm
independent review scope, authority, identity, conflicts and trust roots
before relying on receipts. Approval dates and receipt timestamps may not
be fabricated or inferred from filesystem times.

Use registered source bytes with continuous documented UTC coverage of
the whole horizon. Each chunk covers at most 24 hours and requires a
separate custody receipt issued no earlier than its end and no more than
24 hours afterward. Document explicit broker closures as coverage evidence
with original source records or attestations. Interpolation and unexplained
gaps cannot supply missing evidence. Prior diagnostic, retrospective or
otherwise seen records are ineligible across providers. A distinct
independent reviewer attests the sealed post-horizon intake manifest,
including source, date, bid/ask, session, completeness, costs, access
records and proof of predeclared selection. Verify every digest again on
entry to any future evaluator. Perform only the single fixed-horizon
evaluation with the separately approved evaluator and publish all outcomes.

[Machine-readable proposal](proposed-protocol.json) ·
[Candidate registry](candidate-registry.json) · [Prior exposure](exposure-map.json)
