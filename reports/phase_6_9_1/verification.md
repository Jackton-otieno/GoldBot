# Offline verification

The existing GoldBot virtual environment completed all 165 offline tests in 66.080 seconds before installation. The first restricted launch could not start the Windows Store Python executable used by the virtual environment. An approved launch with both worker limits set to one passed. The earlier Phase 6.8.6 OpenBLAS allocation failure is the reason for the worker limits; no allocator error was observed in the approved Phase 6.9.1 run.

Run in a fresh PowerShell session from GoldBot, setting the limits before Python starts. They apply to that shell and its children.

```powershell
Set-Location D:\GoldBot
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest discover -v
```

The Phase 6.7 regression generated output in a temporary project copy and compared the complete file tree byte for byte with the deployed output, including HTML, JSON and 11 SVGs. No regeneration was written over the original report.

The [before inventory](preserved-before.sha256) contains 58 actual paths, including both raw CSVs and every prior report file (56). The pre-installation run left the complete path/digest inventory identical. All 54 entries in the 6.8.6 preservation manifest also matched this inventory. New Phase 6.9.1 files are excluded from preservation comparisons. The Phase 6.7 provenance regression explicitly excludes the new report directory, consistent with its original evidence scope.

After installation, all 165 offline tests passed again in 47.262 seconds, including exact Phase 6.7 reproduction and provenance reconciliation. The full before/after comparison found the same 58 paths and SHA-256 digests.
