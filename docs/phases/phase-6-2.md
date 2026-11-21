# GoldBot Phase 6.2 Trade Execution Simulator

Phase 6.2 models execution mechanics on synthetic fixtures. Each
`ExecutionSimulator` consumes one Phase 6.1 M15 or H1 stream. Pass each
`OpenEvent` to `on_open` and its matching `ClosedEvent` to `on_closed`.
Supply an `EntryState` at the candidate open with its account snapshot,
risk-day snapshot and independently assigned expected risk-day ID. Call
`finish` after the final close to seal the stream.

## Event timing and risk checks

- A closed BUY or SELL can be considered once, at the immediately following
  observed open. A flagged gap at that open rejects the entry. The Phase 5
  planner also rejects signals from a flagged signal interval. HOLD cannot
  enter. Duplicate, stale, skipped or mismatched replay events raise a
  sequence error. Raw labels are used for sequence validation.
- Require an explicit `SimulationSpec` with named hypothetical evidence,
  internally consistent USD linear XAUUSD specifications, valid price and
  lot grids, and explicit execution costs and margin. The validation attests
  the hypothetical inputs for this run. The Phase 5.1 planner sizes the
  entry using the current synthetic open, the prior close's ATR and signal,
  and the supplied account and risk-day snapshots. Missing or invalid
  snapshots and any planner rejection block entry.
- A position held when the open arrives blocks a new entry at that open,
  including when the opening quote closes the existing position. The
  caller supplies a fresh, coherent account and risk-day snapshot for
  future entry attempts. The simulator reports fills and P/L without
  maintaining a portfolio, updating equity or resetting a risk day.
- `finish` identifies the row of a terminal directional signal and returns
  any unresolved position with its original plan. No terminal fill or
  realized P/L is generated for that position.

## Prices and costs

Treat OHLC as midpoint for the synthetic scenario. Model bid as midpoint
minus half the configured spread and ask as midpoint plus half the spread.
Spread is fixed within a run and the candle's archived spread field is
unused. The midpoint interpretation is an assumption for fixtures. The
archive's historical quote basis and spread behavior remain unverified.

The planner uses ask for BUY entries and bid for SELL entries. Apply the
configured adverse entry slippage and round BUY up and SELL down on the
price tick grid. The planner uses 1.5 ATR from the entry-side reference for
the stop, rounds that stop outward and places the target two rounded
entry-to-stop distances away. It sizes from the resulting entry fill and
stop distance, including the upward tick-rounded stop slippage and
round-trip commission. It floors volume on the lot grid, caps it at the
configured maximum and rejects volume below the minimum. Fixed margin per
lot times volume must fit in supplied free margin. Margin is a requirement
for entry and is excluded from P/L.

- At an open, check the current executable quote for existing positions.
  BUY exits use bid and SELL exits use ask. If the quote has crossed the
  stop, apply adverse stop slippage to that quote, then round a BUY
  position's exit down or a SELL position's exit up. This also applies at
  a flagged gap. An opening quote through the target fills at the target.
- At close, check the executable side's high and low against stop and
  target. A stop fills at the stop adjusted for adverse slippage and tick
  rounding. Targets fill at the limit with zero target slippage. If both
  levels are touched, choose the stop and report the ambiguity. This
  applies on the entry candle as well. Opening decisions cannot see the
  current high or low.
- Gross USD P/L is the signed difference between filled entry and exit
  prices times contract size and lots. That difference incorporates the
  modeled spread and applied slippage. Subtract round-trip commission
  once on exit to get net USD P/L. Gap losses can exceed planned stop loss.
  A price scenario implying a nonpositive executable quote or stop fill
  raises an error.

## Synthetic results and verification

The fixture uses a midpoint open of 100, ATR of 1, tick size of 0.10, lot
step of 0.10, contract size of 10, spread of 0.20, entry slippage of 0.03,
stop slippage of 0.04 and USD 0.50 round-trip commission per lot. The
supplied USD 3,000 equity produces a USD 15 risk budget. Both sides size
to 0.80 lots, with USD 14 modeled stop loss, USD 160 required margin and
USD 0.40 commission.

| Case | BUY fill | SELL fill | Gross USD | Net USD |
| --- | ---: | ---: | ---: | ---: |
| Target, including a favorable opening quote | 103.40 | 96.60 | 25.60 | 25.20 |
| Intrabar stop, including same-bar ambiguity | 98.50 | 101.50 | -13.60 | -14.00 |
| Adverse opening gap stop | 96.80 | 103.20 | -27.20 | -27.60 |

From PowerShell in `D:\GoldBot`:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

All 79 tests passed in the existing virtual environment, including 13 new
simulator tests. The raw exports and all 17 earlier report files matched
their pre-implementation SHA-256 hashes. No historical execution or
profitability report was generated.

## Remaining blockers

The demo metadata of USD 0.10 per tick per lot still conflicts with the
USD 1.00 implied by calculator probes. Production broker rejection
continues to apply. Historical specifications, quote basis and freshness,
server timezone and DST, and risk-day reset boundaries require independent
verification. Phase 6.3 portfolio management, daily resets and historical
performance evaluation remain deferred pending review.
