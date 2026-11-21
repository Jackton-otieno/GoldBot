# GoldBot Phase 6.6 strategy validation infrastructure

The existing XAUUSD M15 and H1 exports were previously inspected. All three
partitions in each export are retrospective, including the partition named
`test`. They provide no genuine unseen holdout. This phase performed no strategy
tuning, historical decisions or execution, historical P/L calculation,
prospective collection, or MT5 calls. It did not run `main.py` or override
production risk settings.

## Retrospective partition audit

Run from the GoldBot root.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.backtesting.strategy_validation --report reports/validation_phase_6_6/validation.json
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

[The audit](../../reports/validation_phase_6_6/validation.json) verifies each
original CSV's byte-level SHA-256 before parsing. It validates the headers,
row counts, candle structure and strictly increasing raw labels on the
appropriate timeframe grid. It splits each series independently by original
row sequence. It neither joins the timeframes nor interprets their labels
as wall-clock times. Calendar coverage may overlap across timeframes.

| Partition | Source rows, inclusive | Rows per timeframe | M15 raw labels, inclusive | H1 raw labels, inclusive |
| --- | ---: | ---: | --- | --- |
| Development | 1-6,000 | 6,000 | 1781128800 to 1789469100 | 1740704400 to 1772794800 |
| Validation | 6,001-8,000 | 2,000 | 1789470000 to 1792125900 | 1772798400 to 1783976400 |
| Test | 8,001-10,000 | 2,000 | 1792126800 to 1794930300 | 1783980000 to 1794927600 |

The strategy manifest records the existing strategy, thresholds, indicator
parameters, risk limits, and source-code hashes. Synthetic execution uses the
Phase 6.5 baseline assumptions and the existing illustrative USD 3,000
account. The boundary manifest binds the strategy hash to the input hashes,
provenance, original row ranges, labels and warmup policy. Manifest hashes
cover compact, sorted UTF-8 JSON without a trailing newline. Decimal values
are finite exact strings, and the pretty report embeds both manifest values.
The report contains counts and provenance with no execution results.

## Synthetic evaluation semantics

Commit the fixture byte hash, strategy manifest hash and synthetic boundary
manifest hash before evaluation. The evaluator checks these commitments and
accepts one explicitly selected timeframe and partition. Fixtures use
relative integer labels starting at 1. Relative labels distinguish fixtures
from the original raw exports. Fixture authors are responsible for ensuring
the candles are generated or hand-authored. A digest or a rebased label
cannot prove that a fixture is synthetic.

At a partition open, the account, peak equity, risk gates, pending signal
and position start fresh. All preceding closes in that timeframe can seed
causal indicators and previous-candle state. Warmup rows do not enter the
account. Close decisions use indicators through the current close, including
the original gap flag. Any eligible signal enters at the earliest on the
next open within that same partition. The risk schedule has one explicit
synthetic risk period beginning at the first open, without calendar resets.
Ledger row numbers are partition-local and the boundary's warmup count
maps them back to original fixture rows.

At the final close, a pending signal expires unfilled and a still-open
position is recorded as unresolved. Neither transfers to the next account.
Any final close valuation uses the last observed candle. There is no forced
liquidation, successor open, later exit or optimization using future prices.
The warmup policy deliberately uses all preceding rows to preserve recursive
indicator state. Prefix-invariance tests check both truncation and future
price changes.

## Prospective holdout protocol

1. Before collection, freeze the strategy source, indicator inputs,
   execution and broker evidence, risk schedule, warmup policy, evaluation
   horizon, acceptance metrics and acceptance thresholds. Record canonical
   hashes with an independently timestamped precommitment. Document the
   treatment of gaps, invalid inputs and unresolved positions up front.
2. Inventory all prior inputs, derivatives, and previously viewed or
   collected date ranges across every timeframe and source used in research.
   Include the existing CSVs and exports used to produce earlier reports.
   Record each file hash, raw label range and verified candle coverage.
   Establish a single latest evaluated coverage endpoint across the inventory.
3. Collect fresh candles formed after both the precommitment and the latest
   prior coverage endpoint. Use verified broker clock, timestamp convention,
   timezone and DST evidence to compare full candle intervals across all
   timeframes and sources. Require the start of each candidate interval to
   be at or after the end of all prior intervals, with a verified post-commit
   start. Reject repeated intervals within a stream, overlap with any
   previously observed coverage, prior file or row fingerprints,
   and inputs whose provenance or coverage cannot be established. M15 and H1
   within the new collection may describe the same market time but must be
   evaluated independently. A different file hash alone is insufficient.
4. Keep holdout values from strategy development until the committed run.
   Record acquisition evidence, immutable source hashes, overlap audit,
   and boundaries before running. Previously known candles may seed
   indicators only if precommitted, strictly preceding and from the
   same timeframe. Run the committed evaluation once, preserve the results,
   and disclose any failed eligibility or integrity check. A strategy change
   after seeing results requires a fresh precommitment and new collection.

## Verification and disposition

The generated report matched a fresh render byte for byte. Both original
CSV hashes and all 18 earlier report hashes, including Phase 6.5, matched
their values recorded before implementation. All 107 offline tests passed
using the existing virtual environment.

Historical execution remains deferred pending verified broker server time,
DST and risk-day boundaries, historical executable bid/ask and other
execution inputs, and resolution of the broker tick-value discrepancy.
Prospective eligibility also requires a complete prior-data inventory and
verified interval provenance. Phase 6.7 is deferred pending review.
