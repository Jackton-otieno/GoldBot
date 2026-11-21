# Manual demo trade experiment (optional)

**Status: PROPOSED and optional. Nothing here has been executed. It needs
operator approval (record at the end) before any trade.** This is a Stage 1
activity on the [personal research track](research-track.md), and its
results are self-tested. GoldBot remains **NO-GO** under Phase 6.9.6. Every
trade is placed by hand by the operator. GoldBot places none, and the reader
below refuses every MT5 trading and position function.

## Purpose and limits of what it can show

The experiment records how Exness books a small number of XAUUSD demo
trades. It tests the hypotheses below on **this demo account during the
dates traded**. A result describes the tested trades only. It does not
establish behavior on other dates, volumes or accounts, on a live account,
or in fast markets. Each conclusion is accepted, if at all, under the
[evidence standard](evidence-standard.md) with its scope written down.

| Hypothesis | Measured from | Not established by this experiment |
| --- | --- | --- |
| H1. Booked gross P/L equals `direction × (exit − entry) × 100 × volume` | `deal.profit` on each exit | Rounding in cases not sampled; the broker's internal calculation |
| H2. Commission per lot (expected 0 on Pro) | `deal.commission` on each deal | Commission on other account types or dates |
| H3. Swap is charged on an overnight hold at the published rate | `deal.swap` on the exit | When the charge was applied; swap-free status beyond this account |
| H4. Fills sit close to the same-side quote just before them | Fill price vs last ask (buys) or bid (sells) seen ≤ 2 s before the fill | Execution slippage against the price on screen when you clicked (see below) |

### Cent rounding is a hypothesis, not a given

With two-decimal prices and a 0.01-lot step, the nominal formula always
gives a whole number of cents. That is a property of the formula, not
evidence of how Exness books P/L. The earlier calculator probes (Phases
6.9.3 and 6.10.5.1) returned results that differ from exact arithmetic.
The monetary-precision blocker therefore stays open until booked deals are
reviewed. A small sample matching one model supports that model **for the
sample only**.

## Risk limits

These limits apply on a demo account, as practice for the discipline a live
account would need.

| Limit | Value |
| --- | --- |
| Concurrent positions | **1**. No other positions or pending orders on the account. |
| Protective stop | Attached **when the order is placed**, on every trade, sized from the table below. |
| Per-trade loss cap | USD 3 for short trades, USD 5 for overnight trades (stop distance plus spread). |
| Experiment loss cap | Stop the experiment once cumulative realized net loss reaches **USD 15**. |
| Largest volume | 0.03 lot |
| Weekends | Never hold a position over a weekend. |
| News | No entries from 30 minutes before to 30 minutes after scheduled high-impact US releases. |
| Spread | Skip an entry if the displayed spread exceeds 0.60. |

A stop limits loss only at its level. A gap or fast market can fill it
worse, which is why weekends, news and the daily break are excluded.

## Before trading

1. **Account identity.** Keep **Algo Trading off** in MT5. Then run the
   identity check and keep its output:

   ```powershell
   $env:GOLDBOT_DEMO_PROFILE = 'exness-ke-mt5-pro-demo'
   $env:GOLDBOT_EXNESS_TERMINAL = 'C:\path\to\terminal64.exe'
   $env:GOLDBOT_EXNESS_DEMO_SERVER = 'ExnessKE-MT5Trial9'
   $env:GOLDBOT_EXNESS_DEMO_LOGIN = '<your demo login>'
   & .\.venv\Scripts\python.exe -B -m tools.verify_exness_demo
   ```

   It must report mode `demo`, server `ExnessKE-MT5Trial9`, a USD account
   and non-custom `XAUUSD`.
2. **Account type.** In the Exness Personal Area, confirm that this account
   is **Pro**. Save a screenshot with the login hidden, and record its
   SHA-256 in your trade log.
3. **Instrument.** Trade exactly `XAUUSD`, with no suffix. Open its
   Specification window and save a screenshot. Record:
   - contract size, digits, volume minimum and step, and stops level
   - swap type, long and short rates, and the 3-day swap day
   - the **Sessions** list, which shows quote and trade sessions separately
4. **Baseline read.** Run the reader once before any trade. This records
   starting balance, equity, credit, symbol economics and the existing deal
   history:

   ```powershell
   & .\.venv\Scripts\python.exe -B -m tools.read_demo_deals_611 `
       --from <today> --output reports\phase_6_11\demo-baseline.json
   ```

   Proceed only if no positions are open (`margin` is 0) and `credit` is 0.

## Timing

Nairobi is UTC+3 all year. New York switches between EDT (UTC−4), from the
second Sunday of March to the first Sunday of November, and EST (UTC−5)
otherwise.

The Exness public archive shows **no quotes** during these windows:

| Period | No quotes (UTC) | New York | Nairobi | Observed in |
| --- | --- | --- | --- | --- |
| US daylight time | ≈ 20:58–22:00 | 16:58–18:00 EDT | 23:58–01:00 | Oct 2026 (17 weekdays); Mar 9–31, 2026 |
| US standard time | ≈ 21:58–23:00 | 16:58–18:00 EST | 00:58–02:00 | Mar 2–6, 2026 only. **Not yet observed for Nov 2026**, which is US standard time. |

These are gaps in the archive's quote feed. They do **not** establish when
orders can be opened, modified or only closed. No close-only interval has
been observed, and the evidence does not show one either way. Use the
terminal's trade sessions (step 3) for permissions. **Place no orders from 30
minutes before to 30 minutes after the window**, and keep any position away
from it unless it is an overnight trade (10 or 11).

## The trades

All trades are optional. Use market execution and attach the stop (and
target, where listed) in the order dialog. Fill in a log row for each trade
(template below).

| # | Order | Protective stop | Close | Purpose |
| --- | --- | --- | --- | --- |
| 1–3 | BUY 0.01 | 2.50 below entry (≈ USD 2.50) | Manually after 10–60 s | H1, H4 for buys |
| 4–6 | SELL 0.01 | 2.50 above entry | Manually after 10–60 s | H1, H4 for sells |
| 7 | BUY 0.02 | 1.20 below (≈ USD 2.40) | Manually after 10–60 s | H1 volume scaling, H2 per lot |
| 8 | BUY 0.03 | 0.70 below (≈ USD 2.10) | Close **0.01** (partial), then the remaining 0.02 | Partial-close booking |
| 9 | SELL 0.01 | Stop 1.00 above, target 1.00 below | Let one trigger. If neither has after 60 minutes, close manually and log "not triggered". | Stop or target fill vs quote |
| 10 | BUY 0.01, Monday–Thursday only | 4.50 below (≈ USD 4.50) | Open ≥ 1 hour before the window, close ≥ 1 hour after it | H3 swap |
| 11 | BUY 0.01, Wednesday only | 4.50 below | As for 10 | H3 triple-swap day |

Only start trade 10 if cumulative loss is below USD 8, and trade 11 if it is
below USD 10. A zero swap is a valid result (for example, a swap-free
account). Record it as observed. Don't treat it as an error.

### Stop the experiment if any of these happen

Close any open position by hand, record what happened, and make no further
trades:

- the identity check fails, or the account, server, symbol or account type
  differs from what was recorded before trading
- an order is rejected or requoted, or fills more than 0.50 from the price
  displayed when you clicked
- a stop fills more than 1.00 beyond its level
- the terminal disconnects while a position is open (close it on reconnect
  and record both times)
- a position or order appears that you did not place, or Algo Trading is
  found enabled
- cumulative realized net loss reaches USD 15

### Trade log template

| # | Date | Click time (Nairobi) | Side / volume | Bid / ask on screen | Stop / target | Close time | Notes, including stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |

The prices you write down are weak evidence, because they are typed by hand.
They are still the only record of what you saw when you clicked.

## Read the results

Run this after the last position closes, with no trading activity during
the read, using a new output file. `--from` is the date of the first trade.
History is read from one day earlier to the present. The boundary is the
proposed risk-day start, 00:00 UTC.

The server offset defaults to the measured rule in
`goldbot/core/server_clock.py`: UTC+2 between the last Sunday of October and
the last Sunday of March, UTC+3 otherwise, as measured for the 2026
transitions. `--server-offset-hours` overrides it. The output records
whether an override matches the rule.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.read_demo_deals_611 `
    --from 2026-11-23 --boundary-utc 2026-11-25T00:00:00Z `
    --output reports\phase_6_11\demo-deals.json
```

The reader prints the reconciliation summary and `protocol_compliant`. If it
is false, the listed violations stand, and the experiment's results are
reported together with them.

### How the reader handles the data

| Topic | Behavior |
| --- | --- |
| **History window** | All deals and orders from `--from` minus one day to the time of the read plus one day, in server labels. If MT5 returns no history, the reader stops with an error. A boundary before the window is refused. |
| **Completeness** | An exit whose opening deal precedes the window is flagged `MISSING_ENTRY` and excluded. Other flags are `STILL_OPEN` for open positions, `OTHER_SYMBOL` for other symbols, and `UNSUPPORTED_POSITION_SHAPE` for reversals and close-by. Deposits and other non-trading entries are listed separately. `ledger_check` compares the window's deals with the account balance. It reads true only if the window includes the account's opening. |
| **Partial closes** | Each exit deal is reconciled against the single opening deal. Commission is reported per deal and never allocated across exits. |
| **Booked amounts** | Gross P/L (`profit`), `commission`, `swap` and `fee` are reported separately. Each exit lists every rounding model it matches (`exact`, five cent-rounding rules, and cent-rounded notionals). |
| **Timestamps** | Raw server labels in milliseconds. Convert to UTC with the offset above. |
| **Quotes** | The last tick up to 10 s before each fill is recorded with its age and the side compared (ask for buys, bid for sells). Only quotes **≤ 2 s old** enter the comparison. Older ones are kept with `used: false`. A missing quote is null and never interpolated. |
| **Order timing** | Each deal lists its order's setup time, the order's reported `price_open`, and `request_to_execution_ms`. The meaning of `price_open` for market orders is not established, so it is reported but not interpreted. |
| **Execution slippage** | Not measurable from MT5 history. The price on screen at the click is not stored. The quote comparison and the log's hand-written prices are the available proxies. |
| **Opening equity** | Balance at a boundary is the current balance minus every later deal. `opening_equity.status` is `SUPPORTED` only if all of these hold: no position was open across the boundary, no position history is incomplete, every non-trading deal is a plain balance entry (type 2), no position is open at the read, and credit is 0. Otherwise it is `UNRESOLVED`, with reasons. |
| **Balance stability** | Balance and credit are read before and after the history read. If either changed, the reader stops. |
| **Protocol check** | Every position opened on or after `--from` is checked against this document's limits: one position at a time, at most 0.03 lot, a stop recorded on the entry order, no Saturday inside the holding period, per-trade caps (USD 3, or USD 5 when held 6 hours or more), and no entry after cumulative net loss reached USD 15. Results appear in `protocol_check`. |
| **Exposure log** | The reader checks the exposure log before reading and appends an entry with the output file's SHA-256. |

The reader leaves the login out of its output.

## Operator approval

Leave blank until you have reviewed this protocol. A blank record means no
trade may be placed.

- Approved by:
- Date (UTC):
- Trades approved (for example "1–9 only"):
- Changes to the limits, if any:
