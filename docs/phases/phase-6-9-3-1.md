# Phase 6.9.3.1 Exness monetary precision investigation

[Verification and decision](../../reports/phase_6_9_3_1/verification.md)

From D:\GoldBot, use the masked local setup in [Phase 6.9.2](phase-6-9-2.md) for the specific executable, full local demo account reference and exact server. In the same shell and before the cleanup in that setup, run:

```powershell
& .\.venv\Scripts\python.exe -B -m tools.verify_exness_precision |
    Set-Content -LiteralPath .\reports\phase_6_9_3_1\probes-new.json -Encoding utf8
```

The runner checks the exact ExnessKE-MT5Trial9 USD demo ending 9498, full account identity, 1:100 leverage, disabled Algo Trading and the non-custom XAUUSD contract. It repeats the unchanged 144 P/L and 24 margin validations, then runs two passes on the same exact Decimal grid. Quotes determine the four anchors, so another attachment can sample different entry prices. Keep the archived run and write subsequent evidence to a new name. The diagnostic has no authority to grant acceptance. Check the embedded contract status independently of the diagnostic exit code.

For offline regression, run with OPENBLAS_NUM_THREADS and OMP_NUM_THREADS both set to 1. For byte comparison, copy the existing GoldBot data and reports into an isolated root, generate there, and compare the relative paths and SHA-256 hashes of the 13 consolidated Phase 6.7 files against the originals. Hash all existing reports and both raw CSVs in the actual GoldBot installation before and after the phase.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest discover -v
& .\.venv\Scripts\python.exe -B -m goldbot.reporting.generate --root $isolatedRoot
```
