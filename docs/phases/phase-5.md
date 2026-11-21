# GoldBot Phase 5.1

Call `risk_manager.evaluate_risk` with one Phase 4.1 CSV row as returned by
`csv.DictReader`. The planner consumes `decision`, `reasons`, `gap_before`
and `atr_14`. It requires BUY_SETUP or SELL_SETUP and an unflagged row.
HOLD produces a rejection without requiring market or account inputs. Signal
close and raw server-clock labels have no bearing on entry or risk-day state.

The caller supplies an independently assigned scenario ID, expected risk-day
ID, and evidence for the signal, account snapshot, risk-day state, instrument
specifications and execution assumptions. Evidence must carry a matching
scenario ID, named source and explicit verification flag. Verification is a
caller attestation. The planner cannot establish snapshot validity, account
identity, or a risk-day boundary independently. The risk-day snapshot must
match both the expected ID and the account reference. An offline caller must
establish date boundaries and historical applicability from independent
sources. All monetary and price inputs use `Decimal` except ATR, which is
parsed from the signal row.

## Risk and execution model

- The $3,000 equity is illustrative. The planner always uses supplied
  account equity. At $3,000, the 0.5% per-trade budget is $15 before other
  limits. One existing position anywhere on the account blocks a new plan.
- Daily loss usage is the greater of externally reported nonnegative loss
  to date and the equity decline from verified risk-day opening equity.
  The 2% daily limit uses opening equity. The 10% drawdown limit uses
  the caller's verified peak equity. Supply coherent equity figures and
  loss state on the same basis, with any cash-flow adjustments established
  by the caller. Reaching either limit blocks a plan. Remaining headroom
  also constrains modeled loss, which may equal the remaining budget.
- BUY starts from ask and SELL from bid. Place a stop 1.5 ATR from that
  reference, rounding away from it to the broker tick grid. Apply adverse
  entry slippage and round the modeled entry adversely. Measure the final
  entry-to-stop distance and place the target at exactly twice that
  distance on the favorable side. Check the broker stop level from the
  opposite quote used to close the position. Reject a stop at or through
  that quote.
- The modeled loss spans entry to the exit-side stop and includes modeled
  entry slippage in that distance. The bid/ask side convention accounts for
  spread, so there is no second spread surcharge. Add adverse stop
  slippage and round-trip commission per lot. The target multiple is a
  price ratio before costs. Supply the commission and both slippage
  estimates explicitly, including any justified zero values.
- Supported specs establish linear XAUUSD P/L with USD account, profit and
  margin currencies. Tick loss per lot must match tick size times contract
  size. Floor the largest risk-affordable volume on the broker grid and cap
  at the broker maximum. Reject volumes below minimum. The caller supplies a
  positive linear margin estimate per lot for the modeled entry and side.
  If the risk-sized volume exceeds free margin, reject it. Tiered margin,
  FX conversion, financing, dynamic commission schedules and pending order
  exposure are outside the model.
- A successful result is labeled INDICATIVE. It contains modeled prices,
  volume, stop loss, margin, risk budget and source labels. There is no
  fill assumption at signal close, order integration, martingale or state
  mutation. Gaps, spread changes, slippage beyond assumptions and execution
  conditions can produce losses above the model.

## Read-only demo observation

On 18 November 2026 at 00:06:25 Africa/Nairobi
(`2026-11-17T21:06:25.299064+00:00`), the running MT5 terminal reported
demo account mode, server `MetaQuotes-Demo`, USD account currency and
1:100 leverage. MetaTrader5 Python package `5.0.6231` supplied
`account_info`, `symbol_info("XAUUSD")` and the calculation probes below.
The quote is recorded as returned, with no assertion of freshness.

| XAUUSD field | Observed value |
| --- | --- |
| Bid / ask | 3847.41 / 3847.64 |
| Point / tick size | 0.01 / 0.01 |
| Reported loss tick value / contract size | 0.10 / 100 |
| Volume min / max / step | 0.01 / 100 / 0.01 |
| Directional volume limit / stops level (points) | 0.0 / 0 |
| Profit / margin currency | USD / USD |
| Trade calculation mode | 4 |

| Read-only calculation | Lots | Entry | Exit | Profit (USD) | Margin (USD) |
| --- | ---: | ---: | ---: | ---: | ---: |
| BUY | 0.01 | 3847.64 | 3846.64 | -1.00 | 38.48 |
| SELL | 0.01 | 3847.41 | 3848.41 | -1.00 | 38.47 |

The profit probes and contract size imply a USD 1.00 loss per 0.01 tick
per lot. That conflicts with the reported USD 0.10 tick value. Phase 5.1
rejects these specs with `INCONSISTENT_TICK_VALUE` under the USD linear
model. The probes are point-in-time observations. They establish neither
historical applicability nor a verified margin schedule. No broker-derived
plan was produced. Tests use explicitly hypothetical, internally consistent
USD fixtures.

[MT5 symbol information](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py)
and [MT5 margin calculator](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py)
describe the query and calculation interfaces.

## Verification

Run from `D:\GoldBot` in PowerShell.

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

Backtesting remains deferred until review. The production timezone and
freshness issue remains open.

All 44 tests passed, including 13 Phase 5.1 tests. SHA-256 matched before and after for both raw CSV exports and all 14 earlier report files.
