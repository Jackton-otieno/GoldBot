# News blackout calendar (research only)

**Status: built and backtested. Research only; not approved for use.**
Self-tested, not independently validated. It changes none of the frozen
strategy cohorts and grants no trading authority. GoldBot remains **NO-GO**
under Phase 6.9.6. The manual news check in Stage C of the
[manual demo protocol](manual-demo-trades.md) stays in place.

## The rule

| Item | Rule |
| --- | --- |
| Events | US Employment Situation (NFP), CPI, and scheduled FOMC statements. Unscheduled meetings and notation votes cannot be known in advance and are excluded. |
| Window | No **new** entry from 30 minutes before to 30 minutes after each scheduled release, inclusive |
| Time | Every release time is converted from US Eastern to UTC, with daylight saving. GoldBot's server labels are converted to UTC with the measured rule in `goldbot/core/server_clock.py`. |
| Point in time | A decision at UTC time *t* uses only the latest capture of each schedule taken at or before *t*. A later reschedule is never visible early. |
| Fail closed | New entries are refused, never assumed safe: `CALENDAR_COVERAGE_MISSING` (no capture yet), `CALENDAR_STALE` (latest capture older than 35 days), `CALENDAR_HORIZON_EXCEEDED` (*t* is beyond the last release that capture lists) |
| Existing positions | Untouched. Signals only open positions, so stops and targets work as before. |
| One function | `NewsCalendar.decide(t)` in `goldbot/research/news_calendar.py` serves backtests and any future execution. It returns the reason and the event (name, scheduled UTC, source, capture time, content hash). |

## Sources and provenance

| Source | Page | How captured |
| --- | --- | --- |
| BLS Employment Situation | bls.gov/schedule/news_release/empsit.htm | Wayback Machine captures. BLS refuses automated requests, so it is not contacted directly. |
| BLS CPI | bls.gov/schedule/news_release/cpi.htm | Wayback Machine captures |
| FOMC | federalreserve.gov/monetarypolicy/fomccalendars.htm | Wayback Machine captures, sampled every 14 days |
| FOMC statement time | Fed press releases ("For release at 2:00 p.m. EST/EDT") | federalreserve.gov, one per past meeting |

Each Wayback capture carries the archive's own timestamp. That third-party
time is what makes the calendar point-in-time.

| Item | Value |
| --- | --- |
| Capture range | 1 Nov 2024 – 22 Nov 2026 |
| Captures kept | 94 NFP, 139 CPI, 48 FOMC (124 distinct pages) |
| Content check | All 283 downloads match the archive's own SHA-1 digest. Each stored page has a SHA-256. |
| Excluded | 2 NFP captures of a blank 762-byte page. A blank page confirms nothing, so it is not used. |
| FOMC statement time | 2:00 p.m. Eastern verified for all 17 meetings from Nov 2024 to Oct 2026; no mismatches |
| Calendar | `historical_data/news_calendar/calendar.json`. Internal seal `622e148d264c150aacd21d1bfb7b886a8312a21b3860baa864ce763a930c9b27`, file SHA-256 `8505ea5fe7950a6be1c764fd70e314dfbe71002638f60ad9e6face786556e405` |

### The 2025 shutdown, as the calendar saw it

| When | What the calendar knew | Decision |
| --- | --- | --- |
| 3 Oct and 7 Nov 2025 | The original jobs-report dates, still listed | Blocked. The releases did not happen, but this was the schedule known at the time. |
| 6 Oct – 18 Nov 2025 | No archive capture of the jobs schedule for 43 days | `CALENDAR_STALE` from 10 Nov |
| 20 Nov 2025 | The delayed September jobs report, first listed in the 18 Nov capture | Blocked |
| From 11 Oct 2025 | CPI moved to 24 Oct | Blocked on 24 Oct |
| Mid–late Jan 2026 | The captured BLS pages listed nothing after mid-January | `CALENDAR_HORIZON_EXCEEDED` until the 30–31 Jan captures |

## Backtest comparison

The same validated candles, Phase 6.10.3 signals, four cost scenarios, sizing,
stops and exits as Phase 6.10.4. The unfiltered runs were recomputed and
**matched the archived Phase 6.10.4 results exactly in all 32 runs**. The
filtered variant differs only in that refused entries become HOLD.
[Full results](../../reports/phase_6_11/news_filter/comparison.json)

| Timeframe | Strategy | Signals refused (news / calendar) | Baseline-cost P/L, unfiltered → filtered (USD) |
| --- | --- | --- | --- |
| M15 | Frozen baseline | 1 / 0 | −25.31 → −25.31 |
| M15 | Trend pullback | 13 / 0 | −7.97 → −7.97 |
| M15 | Donchian breakout | 17 / 0 | −58.73 → −58.73 |
| M15 | Bollinger mean reversion | 16 / 0 | −11.78 → −11.78 |
| H1 | Frozen baseline | 2 / 2 | −43.12 → −43.12 |
| H1 | Trend pullback | 0 / 4 | −53.30 → −53.30 |
| H1 | Donchian breakout | 0 / 5 | +1.46 → +1.46 |
| H1 | Bollinger mean reversion | 1 / 7 | +5.83 → +5.83 |

The refusals named 19 NFP, 16 FOMC and 15 CPI releases.

**Only one of the 32 runs changed its trades.** Under *ideal* costs, M15
Bollinger mean reversion lost one profitable entry: 8 → 7 trades, and
terminal P/L went from +15.89 to −10.69 USD. Removing that trade also
changed later sizing and positions, so the swing exceeds one trade's value.
In every other run, the refused signals would have been rejected anyway,
almost all as `BELOW_MINIMUM_VOLUME`.

**Interpretation:** inconclusive. These strategies place only 4–9 trades in
the whole history, so the filter has almost nothing to act on. These results
neither support nor refute news avoidance. All data used was already
exposed (exposure-log entry 6).

## Kenya time (display only)

All calculations use UTC. Kenya time (EAT, UTC+3 all year) is for display
only, through `display_times` and `describe_event` in
`goldbot/research/news_calendar.py`. The viewer shows the calendar's status
and upcoming releases:

```powershell
& .\.venv\Scripts\python.exe -B -m tools.news_schedule_611 --days 14
& .\.venv\Scripts\python.exe -B -m tools.news_schedule_611 --at 2026-03-11T15:00+03:00
```

| Release | New York | Kenya | UTC |
| --- | --- | --- | --- |
| NFP, US winter | 8:30 AM EST | 4:30 PM EAT | 13:30 |
| NFP, US summer | 8:30 AM EDT | 3:30 PM EAT | 12:30 |
| FOMC, US winter | 2:00 PM EST | 10:00 PM EAT | 19:00 |
| FOMC, US summer | 2:00 PM EDT | 9:00 PM EAT | 18:00 |

Tests cover these four cases, plus the weeks when the Exness server clock
(EU rule) and New York (US rule) disagree. In those weeks a US release sits
one hour earlier on the server clock: CPI on 11 Mar 2026 was 14:30 server,
12:30 UTC, 15:30 EAT, and the FOMC statement on 28 Oct 2026 was 20:00
server, 18:00 UTC, 21:00 EAT. Blackout edges are checked from server labels
in those weeks too. On 22 Nov 2026 the viewer listed NFP 4 Dec 16:30 EAT,
FOMC 9 Dec 22:00 EAT and CPI 10 Dec 16:30 EAT.

## Limitations

- **Freshness for forward use is not guaranteed.** On 22 Nov 2026 the latest
  captures were 7 days old (NFP, 15 Nov), 9 days old (CPI, 13 Nov) and 13
  days old (FOMC, 9 Nov), so the calendar currently allows decisions.
  (11 Oct 2026, quoted earlier, was only the last date the BLS page
  *content* changed. Later captures confirm it unchanged.) Without a new
  capture it becomes `CALENDAR_STALE` on 14 Dec 2026, when the FOMC capture
  turns 35 days old. The archive captured the jobs schedule only after a
  43-day gap in late 2025, so forward use needs either regular re-capture
  or a second route, such as the operator saving the pages from a browser
  with a recorded hash.
- **Archive timing.** A capture shows when the archive saw a schedule, which
  can be later than when it was announced. Reschedules are visible late
  rather than early, which is the safe direction for a backtest.
- **Scope.** Three US release types only. No other countries, speeches,
  minutes, unscheduled actions or market-moving news.
- **Server-time rule.** Measured for the 2026 transitions. Earlier dates
  (H1 data from Feb 2025) rely on the same EU rule.
- **No interpretation.** No news content, sentiment or AI analysis, by design.

## Reproduce

```powershell
& .\.venv\Scripts\python.exe -B -m tools.capture_news_calendar_611 --output <new dir> --from 20241101 --to 20261122
& .\.venv\Scripts\python.exe -B -m tools.build_news_calendar_611 --input <dir> --output <dir>\calendar.json
& .\.venv\Scripts\python.exe -B -m tools.compare_news_filter_611 --calendar <dir>\calendar.json --output <new file>
```

A new capture may differ if the archive gains captures later. The committed
capture set and calendar are the reference.
