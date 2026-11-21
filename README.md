# GoldBot

Python tools for collecting XAUUSD demo-market data, validating historical candles, evaluating strategy signals and risk, and replaying historical candles offline.

| Location | Responsibility |
| --- | --- |
| `main.py` | Existing MT5 demo entry point |
| `goldbot/core/` | Configuration, demo connection, and time management |
| `goldbot/market_data/` | Quote and candle collection and export |
| `goldbot/analysis/` | Data validation and indicator calculation |
| `goldbot/strategy/` | Strategy rules, configuration, and signal export |
| `goldbot/risk/` | Broker validation, sizing, trade plans, and risk decisions |
| `goldbot/backtesting/` | Replay, execution simulation, and portfolio coordination |
| `tests/` | Offline tests organized by subsystem |
| `tools/` | MT5 diagnostics |
| `docs/phases/` | Development notes by phase |
| `data/` and `reports/` | Historical CSV inputs and report outputs |

Run commands in PowerShell from the project root. The offline test suite uses the existing reports as fixtures.

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -v
& .\.venv\Scripts\python.exe -B -m goldbot.analysis.data_analysis --help
& .\.venv\Scripts\python.exe -B -m goldbot.analysis.indicators --help
& .\.venv\Scripts\python.exe -B -m goldbot.strategy.signals --help
& .\.venv\Scripts\python.exe -B -m goldbot.backtesting.historical_replay --help
```

`& .\.venv\Scripts\python.exe main.py` runs the existing MT5 demo entry point. Diagnostic modules are invoked as `tools.diagnose_time`, `tools.verify_dst`, and `tools.diagnose_broker_specs` with `python -m`. Use `--help` to inspect their options offline.

## Phase notes

- [Phase 3.2](docs/phases/phase-3-2.md)
- [Phase 3.3](docs/phases/phase-3-3.md)
- [Phase 4](docs/phases/phase-4.md)
- [Phase 5](docs/phases/phase-5.md)
- [Phase 5.2](docs/phases/phase-5-2.md)
- [Phase 6.1](docs/phases/phase-6-1.md)
- [Phase 6.2](docs/phases/phase-6-2.md)
- [Phase 6.3](docs/phases/phase-6-3.md)
- [Phase 6.9.2](docs/phases/phase-6-9-2.md)
- [Phase 6.9.3](docs/phases/phase-6-9-3.md)
