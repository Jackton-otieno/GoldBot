# Phase 6.9.4 Exness time, sessions and history

[Verification and outstanding evidence](../../reports/phase_6_9_4/verification.md)

Run from D:\GoldBot in PowerShell. Use the masked setup from [Phase 6.9.2](phase-6-9-2.md) in the same shell, with the selected terminal already running and the exact demo login independently confirmed. Run the following before clearing the profile variables. Use a new output filename for each diagnostic.

```powershell
& .\.venv\Scripts\python.exe -B -m tools.verify_exness_time_history |
    Out-File -LiteralPath .\reports\phase_6_9_4\diagnostic-new.json -Encoding utf8 -NoClobber
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

Exit code 1 keeps evaluation unverified. The diagnostic uses two independently bracketed NIST observations, eight quote reads, up to twelve bars per timeframe, one 128-row tick count request and one 60-second tick range request. The API offers no server-side row limit for a range. Responses above 4096 rows are rejected before recording tick data. The bar close check and range request use raw labels. The quote-age interval tests the UTC interpretation as a hypothesis. M1 tick reconstruction can corroborate a basis for a sampled minute only.

Production use remains subject to the existing TimeManager, verified session and historical archive guards. Those require scoped effective-dated offset windows, independently verified UTC, applicable session exceptions and historical archive evidence. Risk evaluation separately requires an approved account-scoped policy day and equity at its exact opening. This diagnostic supplies none of those approvals. Diagnostic samples are excluded from any prospective holdout.

The consolidated-report tests reproduce Phase 6.7 in a temporary isolated copy and compare every relative path and byte against the installed report.
