# Phase 6.9.4.1 Exness local profile and read-only diagnostics

[Verification results](../../reports/phase_6_9_4_1/verification.md) · [Phase 6.9.4 failure evidence](../../reports/phase_6_9_4/verification.md)

## Profile lifecycle

Use PowerShell 7 from D:\GoldBot. Select the Exness (KE) Limited USD demo on ExnessKE-MT5Trial9 ending 9498 manually in MT5 and leave the selected terminal running with Algo Trading disabled.

The profile is optional. Its enrollment actions write a Windows-user DPAPI encrypted file at %LOCALAPPDATA%\GoldBot\exness-ke-9498.dpapi, outside the source and report directories. Enrollment refuses to replace an existing pin. The verifier decrypts it for that run and pipes the values into Python. It passes only the installation path and a timeout to MT5. Keep the exact account and any passwords local. No password is requested or stored.

Choose one enrollment method:

- RecoverPhase692 uses the prior verified installation path, checks its MT5 data-directory marker, and requires a unique matching exact account from the 18 November 2026 pre-verification journal entries at 16:24–16:25 EAT. It fails if the original journal or marker is missing or ambiguous. It does not consult current account state.
- Enroll prompts for independent local confirmation, such as the exact account and server shown on the Exness demo card and the executable of the installation the operator selected. Enter the account locally at the masked prompt. Reconfirm independently before enrolling on a different installation.

~~~powershell
.\tools\exness_phase_6941.ps1 -Action RecoverPhase692
# Or, with independently confirmed values:
.\tools\exness_phase_6941.ps1 -Action Enroll
~~~

Use Run explicitly for each diagnostic. A missing, undecryptable, invalid or mismatched profile stops the run. The terminal must be running on the pinned path. Each data request is bracketed by strict checks of connected status, installation, exact account, exact server, demo mode, USD, Kenyan entity and disabled Algo Trading. To revoke the opt-in, use Remove. To replace it, remove it and enroll again. Preserve existing JSON by using a fresh output filename.

~~~powershell
.\tools\exness_phase_6941.ps1 -Action Run |
    Out-File -LiteralPath .\reports\phase_6_9_4_1\diagnostic-new.json -Encoding utf8 -NoClobber
# Profile revocation, only if intended:
.\tools\exness_phase_6941.ps1 -Action Remove
~~~

Exit 1 after a JSON result means the diagnostic grants no deployment acceptance. A shell error can indicate that local enrollment is missing. Run with the same Windows user and host used for enrollment. Back up the documented recovery evidence separately if needed. The DPAPI file is local to the Windows user and should not be copied into reports.

## Time and history limits

Two Cloudflare NTPv4 UDP observations bracket the terminal sequence. Each uses a numeric endpoint and a two-second socket timeout. The code checks the echoed request stamp, synchronized server response, timing consistency and overlapping correction bounds. This is an unauthenticated external measurement, conditional on the remote reference. For a standalone Windows check, use a separately bounded process for w32tm /stripchart /computer:time.cloudflare.com /samples:4 /period:1. A standalone result cannot establish a bracket for terminal samples. A separately authorized NTP responder or NIST TCP Daytime can supply a rerun bracket if reachable. External clock failure leaves quote age unverified.

The diagnostic requests eight quotes, up to twelve M1, M15 and H1 bars each, up to 128 ticks at the quote anchor, and one raw 60-second tick range. Responses above 4096 ticks are rejected before recording the range. The range ends at the next raw minute boundary and reconstruction includes only the preceding half-open minute. The reported quote-age bounds assume the raw millisecond labels are UTC. The M15 and H1 close checks use raw labels. Full historical coverage, exceptions, effective-dated time mapping and a policy-day boundary with opening equity still require separate evidence.

[Cloudflare NTP endpoints](https://developers.cloudflare.com/time-services/ntp/usage/) · [NTPv4 protocol](https://www.rfc-editor.org/rfc/rfc5905.html)

## Offline reproduction

~~~powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& .\.venv\Scripts\python.exe -B -m unittest discover -v

Get-Content .\reports\phase_6_9_4_1\preserved-before.sha256 | ForEach-Object {
    $expected, $path = $_ -split '  ', 2
    if ((Get-FileHash -LiteralPath $path).Hash -ine $expected) {
        throw "Preserved file differs: $path"
    }
}
~~~

The Phase 6.7 test regenerates the consolidated report in an isolated temporary copy and compares all relative paths and bytes with the installed report.
