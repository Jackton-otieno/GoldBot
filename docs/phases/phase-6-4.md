# GoldBot Phase 6.4 Performance Analysis

Pass a completed, synthetic Phase 6.3 portfolio result to the offline analysis
engine. Analyze M15 and H1 separately because each coordinator starts with its
own USD 3,000 account.

```python
from goldbot.backtesting.performance_analysis import analyze_performance, performance_json

report = analyze_performance(result)
json_text = performance_json(result)
```

The engine independently reconciles position and signal transitions, each fill,
commission, liquidation marks, equity, margin, running peaks, and terminal state.
Malformed or empty ledgers raise ValueError. A complete ledger with no closed
trades produces a report. Validation covers the accounting inputs available in
the ledger. It does not replay OHLC fills or reevaluate risk decisions.

Balance changes by net closed-trade P/L. Marked equity adds the terminal
liquidation-side unrealized P/L. Both returns use their respective starting
values as denominators and are fractions. Closed-trade outcomes use signed net
P/L, including commission. Breakeven trades count toward expectancy and break
win and loss streaks. Mean losses and total losses are signed. Empty means are
null. Profit factor is finite with a positive loss denominator, infinite with
wins and zero losses, and undefined when both totals are zero. Infinite and
undefined values use JSON null plus a status and reason.

Event index 0 represents the starting account. Observations 1 onward are ledger
open and close events. The report supplies a series for plotting marked equity
and drawdown against event index. Currency and fractional maximum drawdowns
each select the first trough attaining their maximum and the latest preceding
observation at the associated peak. Recovery is the first subsequent
observation at or above that peak. Recovery length counts event intervals.
Negative equity can yield drawdown above 100%.

Exposure counts adjacent pairs of actual ledger observations whose first
observation leaves a position open. Each interval has equal weight, including
intervals spanning gaps. The starting baseline and the interval beyond the
terminal observation are excluded. This is an event-count statistic.
A terminal position remains marked, with unpaid commission shown separately.
Entry rejection counts include only directional signals actually attempted
and rejected. A pending terminal signal is reported separately.

Realized gross P/L uses modeled fills, which already reflect modeled spread
and slippage where applicable. The report attributes only commission separately.
Spread and slippage cost totals remain null because the ledger does not record
separate cost attribution. Annualized Sharpe, calendar returns, elapsed
exposure and day-based metrics are null with an explicit reason. Strict JSON
output uses decimal strings, sorted keys, and no run timestamp.

Historical execution remains deferred pending verification of risk-day
boundaries, server time and DST, historical quote and execution inputs, and
the broker tick-value discrepancy. Phase 6.5 cost sensitivity awaits review.

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```
