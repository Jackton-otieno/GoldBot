# Personal research track

GoldBot is developed and tested by one operator. This track lets that work
continue without outside reviewers at every step. It labels its results
honestly and does not weaken any authorization gate. **GoldBot remains
NO-GO** for automated demo and live trading under Phase 6.9.6.

## Stages

| Stage | Scope | Results are labelled |
| --- | --- | --- |
| **1. Personal testing (now)** | Code, historical data, indicators, risk calculations and broker accounting. Bounded manual demo experiments after protocol review and operator approval. | Self-tested |
| **2. Personal strategy research** | The eight frozen strategy and timeframe cohorts on recorded historical data and on data recorded going forward. Track P/L, costs, drawdowns and failures. | Self-tested, not independently validated |
| **3. Independent validation (later)** | Outside developers or trading researchers review methodology, code and evidence once results are promising and reproducible. | Independently reviewed, under Phase 6.10.6 |
| **4. Trading authorization** | A separate decision under Phase 6.9.6: automated demo first, and much later any live decision. | — |

## What can proceed now

| Activity | Status |
| --- | --- |
| Develop and debug GoldBot | Yes |
| Offline tests and backtests | Yes |
| Analyze historical XAUUSD data | Yes, within its verified research scope |
| Bounded [manual demo experiments](manual-demo-trades.md) | After protocol review **and** operator approval |
| Collect self-attested research observations | Yes, labelled self-tested |
| Claim independent or prospective validation | **No** |
| Automated demo trading | **NO-GO** |
| Live trading | **NO-GO** |

## The exposure rule

**Data examined in this track is exposed, permanently.** It may support
self-tested research. It can never be presented later as an untouched
dataset for independent or prospective validation.

The rule is recorded in `docs/evidence/exposure-log.jsonl`, an append-only
log in which each entry carries the SHA-256 of the previous one:

- `tools.exness_archive_611 analyze` and `tools.read_demo_deals_611` append
  an entry automatically for every dataset they examine. Each entry records
  the source, the SHA-256 of the data, its UTC coverage, the purpose and the
  tool.
- Data examined any other way (a notebook, a spreadsheet, a chart) must be
  appended by hand with `goldbot.research.exposure_log.append`.
- Both tools check the whole chain before running and refuse to run if any
  earlier entry was edited, removed or truncated. `exposure_log.verify()`
  performs the same check on demand.
- Commit the log with the work it describes. The log shows only that
  something was looked at, not that anything else was left unseen. That
  limit is why Stage 3 needs data registered before it exists.

The log starts with the Phase 6.11 archive months (March and October 2026)
and a pointer to the Phase 6.10.6 exposure map, which covers all earlier
material, including the MT5 M15 and H1 exports.

## Labelling results

Every report, summary or chart from this track should state:

- **"Self-tested, not independently validated"**
- the data used, by its exposure-log entry
- the cohorts included. Report all eight, including failed and inconclusive
  ones.

Results stay under the [evidence standard](evidence-standard.md) rules for
scope and limitations, whether or not that standard has been adopted.
