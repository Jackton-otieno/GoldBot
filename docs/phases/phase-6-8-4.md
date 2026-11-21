# GoldBot Phase 6.8.4 historical execution data verification

**Historical execution is blocked. Phase 6.8.5 remains pending review.**
Broker-realistic historical backtesting requires all applicable evidence
gates to pass for the requested dataset, account scope and date range.

## Evidence and interpretation

The original CSVs contain raw integer open labels, OHLC, tick volume, a
candle spread and real volume. The exporter passes through the terminal's
closed-rate fields. Neither the files nor the exporter establish an
effective-dated chart price basis, the original quote sequence, or the
price and side at which orders could have filled. MT5 charts can use Bid
or Last depending on the symbol. Current chart mode is a point-in-time
observation. [MetaQuotes chart mode reference](https://www.mql5.com/en/book/automation/symbols/symbols_chart_mode)

Phase 6.8.1 found that current XAUUSD demo tick-value fields (USD 0.10)
disagreed with current contract math and calculator results (USD 1.00
per price tick per lot). That discrepancy is still open. The current
margin probes and symbol/account properties provide no historical
schedule. Phase 6.8.2 did not verify the broker's clock convention or
historical offset boundaries. Phase 6.8.3 did not establish dated
quote or trade sessions or the policy risk day.
[Phase 6.8.1](phase-6-8-1.md) · [Phase 6.8.2](phase-6-8-2.md) · [Phase 6.8.3](phase-6-8-3.md)

| Dataset | Rows | First through last raw open label | Label gaps |
| --- | ---: | --- | ---: |
| H1 | 10,000 | 1740704400 through 1794927600 | 446 |
| M15 | 10,000 | 1781128800 through 1794930300 | 114 |

H1's selected gaps span 7,200 and 270,000 raw seconds. M15's selected
gaps span 4,500 and 190,800 raw seconds. These are adjacent label
differences, which include the first bar's nominal duration.

The [demo sample capture](../../reports/phase_6_8_4/demo-tick-samples.json)
records source scope, package and terminal versions, CSV hashes, raw
ranges, sample rationale, integer input bounds, host read brackets
and available return codes. When the API provides rows, the diagnostic
keeps their original order and flags, raw seconds and milliseconds,
bid/ask and per-row price-unit spread. Each range request uses
COPY_TICKS_ALL and spans at most 15 integer seconds. The full plan targets
the first, middle and last CSV rows, plus the edges and interior of
the shortest and longest raw label gaps in each file. Shared request
starts are coalesced. No date shift is applied. The Python API documents
UTC inputs and the native API documents inclusive millisecond bounds.
The actual broker mapping and Python end-second precision remain
unverified, so the capture keeps these as raw-coordinate probes.
[Python range API](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py) · [Native range API](https://www.mql5.com/en/docs/series/copyticksrange)

The installed Python package 5.0.6231 exposed both historical tick APIs.
The guarded retry confirmed the expected demo scope and terminal build
6320. Current metadata showed chart mode 0, consistent with Bid chart
mode, and account currency USD. Current swap fields were mode 1, long
-12.6 and short -4.6. The historical chart basis and applicable costs
remain unverified.

The initial full-plan attempt was stopped after approximately 20 minutes
without a saved response. In the checkpointed retry the last M15 label
range returned no array with code -1 after about 95 seconds. The last
H1 label request was still pending when the retry stopped. A separate
count-limited request for up to 32 ticks starting at the last M15 label
hit a two-minute process timeout including connection setup. This probe
had no upper timestamp bound. A failure or an interrupted request gives
no evidence that the requested interval was empty or that the broker has
no history for it.

Four focused range probes at the earliest H1 and M15 labels and inside
the selected H1 long gap and M15 short gap also returned no array.
Across the retries, all five completed range requests returned code -1
in 94.3 to 95.6 seconds. MetaTrader identifies -1 as a generic failure.
No tick rows were recovered, so there were no observed spreads, flag
patterns, or clock or candle-basis comparisons to validate. The archive's
coverage and the cause of the request failures remain unknown.
[MetaQuotes error codes](https://www.mql5.com/en/docs/python_metatrader5/mt5lasterror_py)

Same-millisecond rows keep their order. Unchanged sides are expected
when a tick updates only some fields. Other flag bits are kept and
counted. A missing or invalid field, backward timestamp, or crossed
quote has a separate finding. A valid quote can have zero spread.
An empty window, an API failure, a discontinuity and a known closure
are distinct. A sparse or empty sample cannot establish a closure or a
full archive gap without verified timing, session and completeness
evidence. [MetaQuotes tick structure](https://www.mql5.com/en/docs/constants/structures/mqltick)

## Readiness requirements

- Verify historical candle and tick price basis and independently map
  both timestamp streams to UTC using effective-dated offset evidence.
  Bind the complete candle file and each ordered tick batch to reviewed
  source evidence by SHA-256. Certify continuous tick archive coverage
  across the full candle interval, including any explicitly closed periods.
- Verify dated quote and trade session intervals separately, including
  holidays and exceptions. The validator flags uncovered or overlapping
  intervals, candle gaps overlapping open quote time, ticks outside an
  open quote session and silence beyond the supplied open-session limit.
  Choose and document that limit as part of the replay policy. The
  limit and samples cannot establish source completeness.
- Supply effective-dated contract size, price and volume grids and
  tick economics for both gains and losses, commission units, tiers
  and rounding, swap direction and rollover calendar, margin model
  and leverage tiers, and account/profit/margin currencies with
  applicable conversion prices, sides and rounding. Document zero
  charges and identity conversions explicitly where applicable. Current
  values and candle spread cannot establish any of these historic inputs.
- Supply the account-scoped GoldBot policy-day boundaries in UTC.
  Broker rollover and reporting boundaries need separate evidence.
  Any production latch reset remains subject to Phase 6.8.3's exact
  opening-equity requirement.
- Historical quotes can constrain the execution model. They cannot
  establish fill eligibility, fill size, latency, queue priority or
  slippage. Those assumptions need separate review and precommitment.

The standalone validator returns structured findings with code, subject
and detail. Each claim needs actual reviewed authority and a reference
whose contents the caller has resolved. Effective schedules are coverage
claims over reviewed artifacts. The validator checks their scope,
applicability, gaps and overlaps. It does not retrieve or authenticate
the referenced schedules, validate their financial formulas, or produce
execution or risk decisions. The test fixtures are synthetic. The candle
replay still emits raw-label events, and the existing execution simulator
uses hypothetical inputs. The Phase 6.8.4 modules have no path into the
production trading entry point or guards.
[Review findings](../../reports/phase_6_8_4/historical-readiness.json)

## Prospective collection

The [unsent broker inquiry](../../reports/phase_6_8_4/broker-support-inquiry.md)
requests the missing archive, clock, basis and contract evidence.
If it remains unavailable, freeze the strategy, parameters, execution
assumptions, scope, UTC test boundaries, exclusion and gap rules,
success metrics and review criteria before the first evaluation-period
observation. Hash and timestamp the precommitment and record who had
access. Keep a separate calibration period. Use a guarded read-only
demo collector with small bounded requests, backoff, immutable ordered
chunks and checksummed manifests. Record UTC acquisition brackets,
raw ticks, complete effective schedules and sessions, separately retained
conversion inputs and documented resets, interruptions and backfills.
Verify whether backfills are complete before certifying coverage.
Restrict access to evaluation data until the window closes and retain
the original capture alongside any derived data. No prospective
holdout was collected in this phase.

## Reproduction

From D:\GoldBot with the intended demo terminal already running, provide
a fresh output path. Exit 1 means historical readiness remains blocked
even if the terminal returns valid observations. The report checkpoints
completed requests and identifies any request still in progress. Archive
retrieval can be slow even when each requested interval is short.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.diagnose_execution_data --output .\tick-rerun.json
& .\.venv\Scripts\python.exe -B -m unittest discover
```

The existing GoldBot environment passed 149 offline tests, including
12 new regressions. The Phase 6.7 regression regenerated the HTML,
JSON and all 11 SVGs byte for byte and reconciled the original
provenance scope. SHA-256 verification covered both original CSVs and
all 45 earlier report files.
[Pre-change SHA-256 inventory](../../reports/phase_6_8_4/preserved-before.sha256)
