# GoldBot Phase 5.2

The read-only XAUUSD demo validation rejected the current broker specification.
MT5 reported USD 0.10 for the generic, profit and loss tick values. Each of
the 144 calculator observations implied USD 1.00 per actual tick per lot.
The contract-size formula also implied USD 1.00. The cause of the
tenfold difference remains unknown and Phase 5.1 continues to reject the
broker inputs.

## Run the diagnostic

From GoldBot in PowerShell:

```powershell
& .\.venv\Scripts\python.exe -B -m tools.diagnose_broker_specs
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The diagnostic defaults to the MetaQuotes-Demo server and accepts an
explicit expected server via `--expected-server`. It uses the existing demo
connection guard and checks terminal connectivity, demo mode, account
identity, server, currency precision, leverage and the selected symbol metadata
throughout the run. Account identity and server strings stay in memory.
Output includes MT5 versions, account mode and currency precision, match
status, a UTC observation timestamp and allowlisted instrument data. API
errors use numeric codes. Exit 1 indicates rejection and exit 0 indicates
consistent point-in-time probes.

The validator reuses Phase 5.1's BrokerSpecs and Evidence with verification
set to false. For supported OTC linear P/L modes and USD account, profit
and margin currencies, it compares calculator P/L to both direction-specific
tick metadata and signed price movement times contract size times lots.
Each probe normalizes by actual tick count and volume. The cash comparison
permits half a USD cent plus USD 0.00000001 for floating-point slack. A zero
cash result can pass when the formula result is within that tolerance.
Tick metadata must match the contract formula exactly. Comparing every
side, outcome, price, distance and volume against the same formula tests
P/L linearity across the sampled grid.

The validator checks the price grid, point, contract size, volume grid and
directional volume limit. It records and checks the stop and freeze levels
in points. Calculator probes use hypothetical prices and do not test order
admissibility, available margin or position-dependent exposure. Margin must
be positive and compatible with a single per-lot rate within the cash
tolerance for each side and price across sampled volumes. The spot checks
leave the wider margin schedule unverified.

## Live demo result

Captured 18 November 2026 at 00:22:33 Africa/Nairobi
(17 November at 21:22:33 UTC). MT5 Python 5.0.6231 connected to terminal
build 6320 with USD account, profit and margin currencies and 1:100 leverage.
The reported mode was 4 (CFDINDEX). Bid and ask were 3847.41 and 3847.64.
Both point and tick size were 0.01, with contract size 100. Volume minimum,
maximum and step were 0.01, 100 and 0.01 lots. The directional limit and
stop/freeze levels were zero.

- P/L used BUY and SELL, favorable and adverse moves of 1, 10 and 100
  ticks, 0.01, 0.02 and 0.10 lots, and entry prices 3808.93, 3847.41,
  3847.64 and 3886.11. All 144 values matched the formula and expected sign.
  All 144 disagreed with the reported tick values outside the cash tolerance.
- All 24 margin calls returned positive results from USD 38.09 to USD 388.61
  and passed the sampled volume linearity check. No API or connection errors
  were recorded during probing.
- [Sanitized JSON](../../reports/phase_5_2_broker_diagnostic.json) contains all
  observations and per-probe discrepancies, including the raw quote time
  as returned by MT5. The timestamp received no freshness or timezone
  reinterpretation.

The diagnostic gives no historical broker specification or freshness
attestation. Production time and freshness settings, Phase 5.1 risk checks
and stored data were preserved. No orders were submitted, Algo Trading
settings were untouched, and main.py was not run. Backtesting is deferred
until review.

## Verification

All 59 tests passed under the existing GoldBot virtual environment,
including 15 new mocked cases. SHA-256 matched for both original CSVs and
all 14 earlier reports.

References: [MT5 symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants),
[MT5 profit formulas](https://www.mql5.com/en/book/automation/experts/experts_ordercalcprofit)
and [MT5 margin calculator](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py).
