# Manual demo trade experiment (staged, optional)

**Status: PROPOSED. Nothing has been executed. Each stage needs its own
operator approval, recorded at the end of this document. A blank record
means that stage may not start.** This is a Stage 1 activity on the
[personal research track](research-track.md), and its results are
**self-tested, not independently validated**. GoldBot remains **NO-GO**
under Phase 6.9.6. Every trade is placed by hand by the operator. GoldBot
places none, and the reader refuses every MT5 trading and position
function.

## Stages

| Stage | Activity | Approval |
| --- | --- | --- |
| A | Preparation: account identity, account type, instrument specification | Required before B |
| B | Baseline read-only ledger check, which must meet its acceptance criteria | Required before C |
| C | **One** 0.01-lot trade with a protective stop | Separate approval |
| D | Read and reconcile the ledger for that trade | Required before any further trade |
| E | More short trades (2–7 and 9), only if D is consistent | Not approved; separate decision |
| F | Partial close (8) and overnight trades (10, 11) | Deferred. Limits must be revised first: on the 22 Nov specification, swap could push trade 11 above its cap. |

## Purpose and limits of what it can show

The experiment records how Exness books small XAUUSD demo trades. A result
describes **the tested trades on this demo account on the dates traded**.
It says nothing about other dates, volumes or accounts, a live account, or
fast markets. A single trade (stage C) establishes only what that one trade
shows.

| Hypothesis | Measured from | Not established |
| --- | --- | --- |
| H1. Booked gross P/L equals `direction × (exit − entry) × 100 × volume` | `deal.profit` on each exit | Rounding in cases not sampled; the broker's internal calculation |
| H2. Commission per lot (expected 0 on Pro) | `deal.commission` on each deal | Other account types or dates |
| H3. Swap on an overnight hold (stage F) | `deal.swap` on the exit | When the charge was applied; swap-free status beyond this account |
| H4. Fills sit close to the same-side quote just before them | Fill price vs last ask (buys) or bid (sells) seen ≤ 2 s before the fill | Execution slippage against the price on screen at the click |

**Cent rounding is an open question on this account.** The 22 Nov baseline
shows `XAUUSD` with **three-decimal prices** (tick 0.001). One tick at 0.01
lot is USD 0.001, so the nominal formula can give fractions of a cent. How
Exness books them (exactly, or rounded, and by which rule) is what H1
tests. The earlier calculator probes (Phases 6.9.3 and 6.10.5.1) used the
previous two-decimal specification and don't settle it for this account.
The monetary-precision blocker stays open. See the
[Stage B result](stage-b-baseline-2026-11-22.md).

## Known limitations

- **A stop does not guarantee a maximum loss.** A gap, fast market or
  slippage can fill a stop beyond its level. The loss caps are planning
  limits, not guarantees.
- **Post-trade checks detect violations. They cannot prevent them.** The
  reader's `protocol_check` finds breaches in the ledger afterwards. The
  operator enforces every limit **before and during** each trade, using the
  pre-trade checklist.
- **The exposure log detects accidental edits, not deliberate ones.** Its
  hash chain shows edits, deletions and truncation. It becomes evidence
  against deliberate rewriting only once its latest hash is anchored
  outside your control, for example in a pushed commit or an OpenTimestamps
  proof. That is acceptable for self-tested research, provided no claim of
  independent validation is made.
- **Ledger reconciliation finds aggregate discrepancies. It cannot prove
  completeness.** The reader requires the deals in its window to sum exactly
  to the current balance. A mismatch shows something is missing or extra.
  An exact match does not prove every historical entry is present: two
  omitted entries with equal and opposite effects leave the sum unchanged.
  An opening-equity result of `SUPPORTED` is read with that limit.

## Risk limits

| Limit | Value |
| --- | --- |
| Concurrent positions | **1**. No other positions or pending orders on the account. |
| Protective stop | Entered in the order dialog **before** clicking Buy or Sell, on every trade. |
| Stop distances | Measured from the **entry price** (the ask for a BUY, the bid for a SELL). Trades 1–6: 2.50 · trade 7: 1.20 · trade 8: 0.70 · trade 9: 1.00 · trades 10–11: 4.50 |
| Per-trade loss cap | USD 3 for short trades, USD 5 for overnight trades. The loss at an exact stop fill must fit the cap. The remainder is the allowance for slippage. |
| Experiment loss cap | Stop once cumulative realized net loss reaches **USD 15** |
| Largest volume | 0.03 lot (stage F only). Stages C and E use 0.01–0.02. |
| Weekends | Never hold a position over a weekend. No entries after 18:00 UTC on Friday. |
| News | No entries from 30 minutes before to 30 minutes after scheduled high-impact US releases. Checked by hand against a current economic calendar. The research [news blackout calendar](news-blackout.md) does not replace this check, because it is not approved. Its viewer (`tools.news_schedule_611`) can be consulted as a cross-check: it shows releases in Kenya time and reports when its captures are stale. |
| Spread | No entry if the displayed spread exceeds 0.60 |

### How a stop works in MT5 (worked example for stage C)

A BUY fills at the **ask** and is closed at the **bid**. Its stop triggers
when the **bid** reaches the stop price. For a SELL, the roles of bid and
ask swap.

| | Value |
| --- | --- |
| Quote when clicking | bid 4000.000, ask 4000.168 (spread 0.168, as at the 22 Nov baseline) |
| BUY 0.01 fills at the ask | 4000.168 |
| Stop, 2.50 below the entry | **3997.668** |
| How far the bid must fall to trigger | 4000.000 − 3997.668 = 2.332 (the distance minus the spread) |
| Booked loss at an exact stop fill | (3997.668 − 4000.168) × 100 oz × 0.01 = **−USD 2.50** |
| Each extra 0.01 of slippage | −USD 0.01 (each 0.001 is −USD 0.001) |
| Room before the USD 3 cap | USD 0.50, which is 0.50 of price slippage |

The spread was paid at entry, so it does not add to the loss at the stop. It
only shortens the distance to the trigger. The broker's minimum stop
distance (stops level × point) applies to that trigger distance, measured
from the bid for a BUY. Because the fill can differ slightly from the ask
on screen, the stop's real distance is measured from the **actual fill**.
The reader does that after the trade (`stop_geometry`).

The baseline read recomputes all of this from the live specification and
spread (`planned_stop_check`).

## Stage A — Preparation

1. Keep **Algo Trading off** in MT5. Run the identity check and keep its
   output:

   ```powershell
   $env:GOLDBOT_DEMO_PROFILE = 'exness-ke-mt5-pro-demo'
   $env:GOLDBOT_EXNESS_TERMINAL = 'C:\path\to\terminal64.exe'
   $env:GOLDBOT_EXNESS_DEMO_SERVER = 'ExnessKE-MT5Trial9'
   $env:GOLDBOT_EXNESS_DEMO_LOGIN = '<your demo login>'
   & .\.venv\Scripts\python.exe -B -m tools.verify_exness_demo
   ```

   It must report mode `demo`, server `ExnessKE-MT5Trial9`, a USD account
   and non-custom `XAUUSD`.
2. In the Exness Personal Area, confirm that the account is **Pro**, and note
   the **date the account was opened**. Save a screenshot with the login
   hidden, and record its SHA-256.
3. Open the Specification window for `XAUUSD` (no suffix) and save a
   screenshot. Record:
   - contract size, digits, volume minimum and step
   - **stops level** and freeze level
   - swap type, long and short rates, and the 3-day swap day
   - the **Sessions** list (quote and trade sessions are listed separately)

## Stage B — Baseline read

Set `--from` to the account's opening date **or earlier**, so that the
history covers every deal. Read at a quiet moment, with no open positions:

```powershell
& .\.venv\Scripts\python.exe -B -m tools.read_demo_deals_611 `
    --from <account opening date> --boundary-utc <today>T00:00:00Z `
    --output reports\phase_6_11\demo-baseline.json
```

**Acceptance criteria.** Stage C may not start unless every item holds:

| Check | Required value in the output |
| --- | --- |
| Identity | The read completed; the identity check passed at start and end |
| No exposure | `account_snapshot.margin` = 0 and `credit` = 0 |
| Ledger sums to balance | `ledger_check.sums_to_current_balance` = true. This shows no aggregate discrepancy; it does not prove completeness. |
| Opening equity | `risk_day_boundaries[0].opening_equity.status` = `SUPPORTED`. `CONDITIONAL` does **not** meet this criterion. Accepting it for a specific baseline would need a recorded operator decision. |
| Stops feasible | `planned_stop_check.status` = `OK`: each planned stop's trigger distance (distance minus current spread) is beyond the spread and at least the broker minimum, and its loss at an exact stop fill fits its cap |
| Ledger entries | `reconciliation.issues` is empty |
| Exposure log | The read appended an entry (the reader refuses to run on a broken chain) |

If any item fails, stop and record the output. Don't trade.

## Stage C — One trade

**Pre-trade checklist.** The operator confirms each item immediately
before clicking:

- [ ] **Pre-trade read**, no more than 30 minutes before the order, with
      the boundary at today's 00:00 UTC and a new output file:

      ```powershell
      & .\.venv\Scripts\python.exe -B -m tools.read_demo_deals_611 `
          --from 2026-11-18 --boundary-utc <today>T00:00:00Z `
          --output reports\phase_6_11\pretrade-<today>.json
      & .\.venv\Scripts\python.exe -B -m tools.check_pretrade_611 `
          --read reports\phase_6_11\pretrade-<today>.json
      ```

      Every automated check must print `PASS`. The checker compares the
      read with the accepted 22 Nov baseline, the only baseline covered by
      the [scoped Stage B exception](stage-b-baseline-2026-11-22.md). It
      fails if anything has changed: the account, the specification, the
      deals, the archived-deals entry, exposure, stop feasibility or
      freshness. It then lists the checks still to be done by hand, all of
      which are in this checklist.
- [ ] **Fresh session check:** in the `XAUUSD` Specification window, the
      current time falls inside **today's trade session**, not just a quote
      session. Take a screenshot. Repeat this check, rather than relying on
      stage A, during any week that contains a daylight-saving change
      (US: second Sunday of March, first Sunday of November; EU: last
      Sunday of March and of October).
- [ ] No open positions or pending orders
- [ ] Algo Trading is off
- [ ] Not within 30 minutes of the daily quote break (see Timing), not
      within 30 minutes of a scheduled high-impact US release, not after
      18:00 UTC on a Friday
- [ ] Displayed spread ≤ 0.60
- [ ] Order dialog: `XAUUSD`, **BUY 0.01**, market execution. **Stop loss =
      the ask shown in the dialog minus 2.50**, to all three decimals. Write
      both numbers in the log.
- [ ] Trade log row started, with the date, time, and the bid and ask shown

**The trade.** Click Buy. In the Trade tab, check the position:

1. Its **stop loss** shows the price you entered. If no stop shows, close
   the position immediately; that counts as a stop condition.
2. Its **open price** minus its stop loss is between 2.40 and 2.60. If the
   fill moved the distance outside that range, close the position
   immediately and record it.

Close the position by hand after 10–60 seconds. Finish the log row,
including the open price.

## Stage D — Read and reconcile

Run the reader again with the **same `--from`**, a new output file, and no
open positions:

```powershell
& .\.venv\Scripts\python.exe -B -m tools.read_demo_deals_611 `
    --from <account opening date> --output reports\phase_6_11\demo-trade-1.json
```

Record a scoped conclusion (template in the
[evidence standard](evidence-standard.md)) covering:

- `protocol_check.compliant` and any violations
- exactly one new position, with one entry deal and one exit deal
- `booked_usd` vs `exact_usd` and `matching_models`
- commission, swap and fee on each deal
- `fill_timing`: request-to-execution time, prior-quote age, and whether
  the quote was used
- `protocol_check.positions[0].stop_geometry`: the stop price, its distance
  from the actual fill, and the loss at an exact stop fill. These must agree
  with the log and the worked example.
- the ledger still summing to the current balance

Stage E needs a separate decision, made after this review. If anything is
inconsistent or unexplained, stop and investigate before any further trade.

## Stop conditions (all stages)

Close any open position by hand, record what happened, and make no further
trades if any of these happen:

- the identity check fails, or the account, server, symbol or account type
  differs from stage A
- an order is rejected or requoted, or fills more than 0.50 from the price
  displayed at the click
- a stop is missing from an open position, or fills more than 1.00 beyond its
  level
- the terminal disconnects while a position is open (close it on reconnect
  and record both times)
- a position or order appears that you did not place, or Algo Trading is
  found enabled
- cumulative realized net loss reaches USD 15
- the reader reports a protocol violation or an unexplained ledger entry

## Timing

Nairobi is UTC+3 all year. New York is on EDT (UTC−4) from the second Sunday
of March to the first Sunday of November, and on EST (UTC−5) otherwise.

The Exness public archive shows **no quotes** during these windows:

| Period | No quotes (UTC) | New York | Nairobi | Observed in |
| --- | --- | --- | --- | --- |
| US daylight time | ≈ 20:58–22:00 | 16:58–18:00 EDT | 23:58–01:00 | Oct 2026 (17 weekdays); 9–31 Mar 2026 |
| US standard time | ≈ 21:58–23:00 | 16:58–18:00 EST | 00:58–02:00 | 2–6 Mar 2026 only. **Not yet observed for Nov 2026**, which is US standard time. |

These are gaps in the archive's quote feed. They do **not** establish when
orders can be opened, modified or only closed. No close-only interval has
been observed, and the evidence does not show one either way. Use the
terminal's trade sessions (stage A) for permissions, and place no orders
within 30 minutes either side of the window.

## Full trade list (stages C, E and F)

| # | Stage | Order | Protective stop | Close | Purpose |
| --- | --- | --- | --- | --- | --- |
| 1 | C | BUY 0.01 | 2.50 below | By hand after 10–60 s | H1, H4 (buy) |
| 2–3 | E | BUY 0.01 | 2.50 below | By hand after 10–60 s | H1, H4 (buy) |
| 4–6 | E | SELL 0.01 | 2.50 above | By hand after 10–60 s | H1, H4 (sell) |
| 7 | E | BUY 0.02 | 1.20 below | By hand after 10–60 s | H1 volume scaling, H2 per lot |
| 9 | E | SELL 0.01 | Stop 1.00 above, target 1.00 below | First to trigger, or by hand after 60 minutes (log "not triggered") | Stop or target fill vs quote |
| 8 | F | BUY 0.03 | 0.70 below | Close 0.01 (partial), then the remaining 0.02 | Partial-close booking |
| 10 | F | BUY 0.01, Monday–Thursday | 4.50 below | Open ≥ 1 hour before the quote break, close ≥ 1 hour after it | H3 swap |
| 11 | F | BUY 0.01, Wednesday | 4.50 below | As for 10 | H3 triple-swap day |

In stage F, only start trade 10 if cumulative loss is below USD 8, and trade
11 if it is below USD 10. A zero swap is a valid result to record, not an
error.

### Trade log template

| # | Date | Click time (Nairobi) | Side / volume | Bid / ask on screen | Stop / target | Stop shown on position? | Close time | Notes, including stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Hand-written prices are weak evidence. They are still the only record of
what was on screen at the click.

## How the reader handles the data

| Topic | Behavior |
| --- | --- |
| **History window** | All deals and orders from `--from` minus one day to the time of the read plus one day, in server labels. An empty history reported by MT5 with a success code counts as empty; any other failed history read stops the reader. A boundary before the window is refused. |
| **Ledger reconciliation** | `ledger_check.sums_to_current_balance` is true only if the window's deals sum exactly to the current balance. That detects aggregate discrepancies. It cannot prove that every historical entry is present, because omissions that cancel each other leave the sum unchanged. |
| **Balance stability** | Balance and credit are read before and after the history read. If either changed, the reader stops. |
| **Position completeness** | An exit whose opening deal precedes the window is flagged `MISSING_ENTRY` and excluded. Other flags are `STILL_OPEN` for open positions, `OTHER_SYMBOL` for other symbols, and `UNSUPPORTED_POSITION_SHAPE` for reversals and close-by. Deposits and other non-trading entries are listed separately. |
| **Partial closes** | Each exit deal is reconciled against the single opening deal. Commission is reported per deal and never allocated across exits. |
| **Booked amounts** | Gross P/L (`profit`), `commission`, `swap` and `fee` are reported separately. Each exit lists every rounding model it matches. |
| **Timestamps** | Raw server labels in milliseconds. The offset defaults to the measured rule in `goldbot/core/server_clock.py` (UTC+2 from the last Sunday of October, UTC+3 from the last Sunday of March, measured for 2026). `--server-offset-hours` overrides it, and the output records whether an override matches the rule. |
| **Quotes** | The last tick up to 10 s before each fill is recorded with its age and the side compared. Only quotes **≤ 2 s old** enter the comparison. Older ones are kept with `used: false`. A missing quote is null and never interpolated. |
| **Order timing** | Each deal lists its order's setup time, its reported `price_open` (not interpreted for market orders), and `request_to_execution_ms`. Execution slippage against the price on screen is not measurable from MT5 history. |
| **Opening equity** | Balance at a boundary is the current balance minus every later deal. `SUPPORTED` requires all of these: no position open across the boundary, complete position history, only plain balance entries (type 2) among non-trading deals, **window deals that sum to the current balance**, no position open at the read, and credit 0. If any of these fails, the status is `UNRESOLVED`, with reasons. One narrow exception applies: a type-5 correction whose comment is exactly `Archived deals` and whose four amounts are all exactly zero does not count as an unverified entry. Its presence gives `CONDITIONAL`, with the condition `ARCHIVED_DEALS_CORRECTION_PRESENT` and a warning that historical completeness can't be established from the MT5 ledger alone. It never gives `SUPPORTED`. The entry and its comment are kept in `archived_deals_corrections`. No other comment is exported. |
| **Planned stops** | For each planned stop, `planned_stop_check` reports the distance from entry, the exit-side trigger distance (distance minus the current spread), the loss at an exact stop fill (distance × contract × volume, rounded up to the cent) and the slippage allowance left under the cap. The trigger distance must be beyond the spread and at least the broker minimum (`trade_stops_level × point`). Gaps can exceed the loss. |
| **Protocol check** | Every position opened on or after `--from` is checked against the risk limits above, using the ledger after the fact. `stop_geometry` measures the recorded stop from the **actual entry fill**, and flags a stop on the wrong side or one implying a loss above the cap. It assumes the stop was not moved after entry. |
| **Exposure log** | The chain is checked before reading, and an entry with the output file's SHA-256 is appended. |

The reader leaves the login out of its output.

## Operator approval

Record one line per stage. A blank line means the stage is not approved.

| Stage | Approved by | Date (UTC) | Scope and changes |
| --- | --- | --- | --- |
| A and B: preparation and baseline read | Jackton Otieno (operator) | 2026-11-22 | Stages A and B only, as written. Read-only; no trade approved. Recorded from the operator's message "i have approved". |
| B result: scoped conditional acceptance | Jackton Otieno (operator), on the technical reviewer's recommendation | 2026-11-22 | The 22 Nov baseline (`demo-baseline-2.json`) is accepted with conditions for considering one manual 0.01-lot trade only. Opening equity remains `CONDITIONAL`; criterion 4 is unchanged. See [the Stage B record](stage-b-baseline-2026-11-22.md). |
| C: one trade (trade 1 only) | | | |
| E: further short trades | | | |
| F: partial close and overnight | | | |
