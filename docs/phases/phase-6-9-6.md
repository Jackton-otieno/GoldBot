# Phase 6.9.6 integrated readiness assessment

**NO-GO.** Open the [offline dashboard](../../reports/phase_6_9_6/index.html)
or [readiness report](../../reports/phase_6_9_6/readiness.md). The
[machine-readable assessment](../../reports/phase_6_9_6/assessment.json)
contains the blocker register, source hashes and diagnostic outcomes.

## Design

The reporting module evaluates typed requirements with explicit broker or
study scopes, a fixed archive-hash baseline and an explicit assessment
date. Missing or unreadable inputs, hash mismatches, expired identity
evidence and known conflicts degrade the reported finding. All findings
retain their conditions and provenance. The identity freshness rule treats
the dated connectivity snapshot as stale after its observation date
(Africa/Nairobi). This rule is for reporting only. The assessment has
constant closed authorization outcomes and no execution integration.

The SHA-256 pins establish local byte preservation of the reviewed
baseline. External attestation and authoritative broker evidence are still
required. A hash mismatch calls for reviewing the source and updating the
baseline through a separate code review. The assessment imports no MT5
client. Its diagnostic summaries recheck the existing journal chain using
SQLite read-only mode. Diagnostic observations have unknown between-poll
coverage, unverified production UTC mapping, and permanent holdout
exclusion. The Phase 6.8.5 results use observed historical candle inputs
and simulated portfolios and fills. The Phase 6.8.6 protocol is a draft
with the exact UTC start/end unset.

## Reproduce offline

Run from the GoldBot root in PowerShell 7.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest discover -v
& .\.venv\Scripts\python.exe -B -m tools.assess_readiness_696 --as-of 2026-11-18
```

The original inputs and earlier reports are listed by relative path in
the [before](../../reports/phase_6_9_6/preserved-before.sha256) and
[after](../../reports/phase_6_9_6/preserved-after.sha256) inventories.
Compare these with the SHA-256 hashes in the current installation:

```powershell
Get-Content .\reports\phase_6_9_6\preserved-before.sha256 | ForEach-Object {
    $expected, $path = $_ -split '  ', 2
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $expected) {
        throw "Preserved file differs: $path"
    }
}
```

For the Phase 6.7 comparison, copy `data` and `reports` to a fresh
scratch root and remove the copied consolidated output before generation.
Run the existing generator against that isolated root and compare all
relative file paths and SHA-256 digests with the saved 13-file set.

```powershell
& .\.venv\Scripts\python.exe -B -m goldbot.reporting.generate --root $isolatedRoot
& .\.venv\Scripts\python.exe -B -m unittest tests.reporting.test_consolidated -v
```

## Read-only boundary diagnostic

The recorded attempt targeted 18:00 Nairobi time (15:00 UTC) as a
scheduling hint for a shared nominal M15/H1 boundary. The reproducible
command below shows the recorded invocation. A new run requires explicit
authorization, a future whole UTC quarter-hour and a fresh destination
for its journal and run log. The worker refuses to replace an existing
journal. Retain the archived artifact paths when reviewing this phase.

```powershell
.\tools\observe_exness_boundary_696.ps1 -TargetUtc '2026-11-18T15:00:00+00:00'
```

The one-shot foreground launcher waits at most 900 seconds and aims to
start 22 seconds before the nominal boundary. The market-data worker has
a 75-second subprocess watchdog, at most two attachment attempts,
eight poll attempts, and six seconds between normal polls. No persistent
scheduler is installed. Launch-time verification reuses the existing
DPAPI opt-in and independent Phase 6.9.2 journal recovery. Exact profile
equality, running installation, identity, strict entity, disabled Algo
Trading, and non-custom XAUUSD are checked by the guarded collector.
The sampler uses one quote snapshot and up to two closed-position rows
per timeframe per poll. Admission uses only rows returned by MT5 and raw
quote coordinates within that attachment. The desktop clock schedules
the attempt. The journal detects an observed close using quote and bar
labels, including when independent UTC cannot be verified.

## Outstanding evidence

The blocker register gives the action required for each condition.
Priorities are authoritative broker/account economics, dated UTC and
session evidence, executable quote coverage and costs, and an approved
risk-day opening with attested equity. The retrospective strategy result
remains adverse. Independently attest prior exposure and precommit the
fixed protocol before seeking separate authorization for a sealed
prospective study.
