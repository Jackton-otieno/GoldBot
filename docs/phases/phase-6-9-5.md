# Phase 6.9.5 bounded XAUUSD diagnostics

[Verification results](../../reports/phase_6_9_5/verification.md) · [Draft holdout protocol](../../reports/validation_phase_6_8_6/draft-protocol.md)

The diagnostic uses the existing Windows-user DPAPI opt-in. It independently recovers the expected exact account and installation from the Phase 6.9.2 journal and installation marker, compares them with the decrypted profile, and checks the running terminal. The live gate requires Exness (KE) Limited, USD demo ending 9498 on ExnessKE-MT5Trial9, the pinned installation, connected status, disabled Algo Trading and exact non-custom XAUUSD. The collector checks terminal and account identity around every data read and checks the full gate again on reattachment. Missing or ambiguous evidence stops the runner before attachment. The profile and exact account travel through process input only. Do not invoke the Python worker directly.

## Authorized one-shot smoke

From `D:\GoldBot` in PowerShell 7, use the same Windows user as the profile enrollment. Run only with explicit authorization for a bounded diagnostic and with the independently verified demo already selected.

```powershell
.\tools\exness_phase_6941.ps1 -Action RunPhase695
& .\.venv\Scripts\python.exe -B -m tools.collect_exness_phase_695 --verify
```

The worker has a 55-second watchdog, two total attachment attempts, eight total poll attempts, and one second between normal polls. Each poll asks for one quote snapshot and at most two closed-position rows per timeframe. Connection and null-read errors can trigger a bounded reattachment. Identity mismatches, malformed data and exhausted attempts stop collection. A completed run can contain interruptions or zero eligible bars. No scheduler or tick history requests are used.

## Observations and integrity

- Quotes are snapshots of the terminal's latest visible state. Raw seconds, milliseconds, bid, ask, last, flags and volume fields are preserved. Every poll has its own provenance even when the content is identical. Between-poll tick coverage and the number of missed ticks are unknown.
- Bars preserve the raw open label, OHLC, tick volume, spread and real volume. The collector uses positions 1 and 2, checks alignment and OHLC, and requires raw open plus period to be at or before the sampled quote label. New bar labels must close strictly after the first raw quote on that attachment. This also excludes new labels at or before the reconnect quote. Previously admitted labels can be reobserved. A bar may have opened before the first poll, and relative close and gap checks depend on the raw labels. Gaps, discarded preexisting rows, interruptions and unknown coverage are recorded without filling missing slots.
- Host Unix UTC nanoseconds and monotonic brackets accompany reads. Two opportunistic Cloudflare NTP probes measure the host clock separately from the broker. Probe failure leaves the independent clock assessment unavailable. Raw broker labels stay unmapped to production UTC.
- `reports/phase_6_9_5/diagnostic.sqlite3` is a separate, bounded local SQLite journal. A Windows lock excludes concurrent writers. Full-sync transactions commit each event, payload and its SHA-256 chain entry together. Exact payload duplicates become references, preserving every observation and any revision or reversion. A restart validates the chain, leaves prior rows intact, and records an unfinished run as interrupted. The store reserves space for a complete run under its event cap. Save the count and chain head externally if later truncation must be detectable. The local hash chain provides no independent timestamp or tamper-resistant custody.
- Every event is exposed and ineligible for a formal holdout. Sessions, costs, archive continuity, risk-day boundary and production time mapping remain unverified. The Exness monetary-precision rejection and MetaQuotes rejection remain in force. [Exness precision evidence](../../reports/phase_6_9_3_1/verification.md) · [MetaQuotes evaluation](../../reports/phase_6_9_1/demo-verification.md)

## Offline reproduction

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest tests.test_exness_phase_695 -v
& .\.venv\Scripts\python.exe -B -m unittest discover -v

Get-Content .\reports\phase_6_9_5\preserved-before.sha256 | ForEach-Object {
    $expected, $path = $_ -split '  ', 2
    if ((Get-FileHash -LiteralPath $path).Hash -ine $expected) {
        throw "Preserved file differs: $path"
    }
}
```
