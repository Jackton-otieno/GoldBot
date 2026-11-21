# Phase 6.9.3 Exness XAUUSD broker specifications

The read-only runner pins the already running executable and checks the exact demo account, server, broker entity, disabled Algo Trading and symbol before calculating the grid. It rechecks the pinned identity and contract metadata throughout. Use the local-only environment setup in [Phase 6.9.2](phase-6-9-2.md) and run this command in the same shell before clearing those variables.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.verify_exness_contract
```

The runner outputs sanitized JSON. A rejected contract returns exit code 1. The latest check verified the metadata and USD margin conversion and rejected six of 144 P/L probes. No broker approval or execution gate was opened. The offline `evaluate_xau_margin_risk` adapter requires an explicit USD margin amount per lot for an XAU conversion scenario, together with its existing account, risk-day, execution, and broker evidence checks.

[Verification report and probe results](../../reports/phase_6_9_3/verification.md)
