# GoldBot Phase 6.3 Offline Portfolio Ledger

Use `run_portfolio(replay, spec=spec, schedule=schedule)` for a complete
Phase 6.1 replay. For incremental use, create a `PortfolioCoordinator`,
pass each open and matching close in order, then call `finish()`.
The result keeps the specification, schedule provenance, event ledger, and
terminal state. Each coordinator starts with USD 3,000 and has its own USD
balance, peak equity, risk-day state, signal and position. Run M15 and H1
with separate coordinators and timeframe-specific schedules.

## Event order and accounting

At a close, Phase 6.2 checks stops and targets using its stop-first rule
when both are touched, then the coordinator records the result and any
pending directional signal. At the next observed open, Phase 6.2 checks a
held position first. A held position blocks entry at that open even when it
exits there. When flat, a candidate uses the prior close's signal and ATR,
the observed opening quote, and the current coordinator account and risk-day
state. The Phase 6.2 gap and signal checks still apply. A candidate is
consumed once. Each open records its entry status and any attempted signal.

Equity is balance plus unrealized P/L. Mark a surviving BUY on bid and a
surviving SELL on ask using the fixed hypothetical spread. Unrealized P/L
is the difference from the actual entry fill, including its slippage,
times signed contract exposure. The full round-trip commission is charged
once at exit. It is shown separately as due while a position is open and
excluded from unrealized P/L and equity until exit. A fill adds net P/L to
balance, including its commission and any modeled exit slippage. Used margin
is the plan's fixed margin while the position is held. Free margin is equity
less used margin. The planner checks pre-fill free margin and the simulator's
admission check also requires nonnegative free margin at the immediate
post-fill liquidation-side mark. Margin is released on exit.

Each observed event contributes one equity observation. When an event
produces an exit, the observation uses realized balance after the fill.
Otherwise it uses the open or close mark. High and low drive simulated
stop/target detection at close only. They never create additional equity
marks or update the peak. The ledger includes the current peak, drawdown
amount and fraction, margin and risk flags, and all fills. At end of data
the last ledger record retains the marked account and open position, and
the terminal record identifies any unresolved position or pending signal.

## Risk schedule and limits

Supply a `RiskSchedule` with named evidence matching the hypothetical
specification's scenario ID and explicit, strictly increasing source-row
open boundaries, starting at row 1, with unique day IDs. Boundaries apply
before the corresponding open. A replay prefix can end before a future
boundary. Missing or mismatched provenance raises an error before
execution. Raw server-clock labels are used for replay sequencing only.

The first day starts at USD 3,000. A new day starts at the previous event's
observed equity, including any carried mark, and clears the daily latch and
realized loss accumulator. Any gap and fill at the boundary belong to the
new day. Each negative net fill contributes its full loss to the day of
exit, including a trade carried through a boundary. Positive fills leave
that accumulator intact. The Phase 5 daily usage formula takes the greater
of accumulated negative net fills and the shortfall from the opening equity.
This means a carried trade can count its full realized loss for the new day
even when part of the loss was reflected in the prior close mark.

The Phase 5 planner uses the existing 0.5% risk-per-trade, 2% daily loss,
10% drawdown, and single-position settings. It also caps the planned loss
by the remaining daily and drawdown budgets and compounds from current
equity. Observed equality or breach latches the corresponding entry gate
for the remainder of the day for daily loss, or the entire run for drawdown.
Insolvency at equity of zero or below permanently blocks entries and the
ledger retains any actual negative balance. Daily threshold comparisons
require positive opening equity. Negative free margin is flagged while it
persists. Gaps can exceed the modeled trade budget or either risk limit.
The coordinator books the actual modeled fill, keeps any overshoot visible,
and continues to run existing positions through Phase 6.2 stop/target
logic. It introduces no margin-call, stop-out or terminal liquidation fill.

## Verification and historical scope

With the Phase 6.2 synthetic prices and USD 3,000 starting equity, both
directions size to 0.8 lots. The immediate mark is USD 2.40 below balance,
with USD 160 used margin and USD 0.40 commission due on exit. A target
settles at USD 3,025.20 balance with commission paid once. An intrabar stop
settles at USD 2,986.00. An adverse BUY opening gap to midpoint 90 produces
a USD 83.60 net loss and latches the USD 60 daily loss limit until the
next explicit boundary. Tests also cover exact daily and drawdown threshold
hits, insolvency, margin failures, compounding, independent timeframes,
prefix causality, determinism, and unresolved terminal state.

From PowerShell in the GoldBot folder:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The original M15 and H1 exports passed their pinned SHA-256 and replay
validation checks with 10,000 candles each. Historical execution is deferred
because risk-day boundaries, server time and DST, historical quote basis and
broker/execution inputs are unresolved. The demo broker tick-value discrepancy
also remains open. No synthetic day schedule was applied to the historical
exports. Phase 6.4 historical performance analysis is deferred pending review.
