# One-shot wall-clock scheduling hint. Raw observations determine whether a boundary crossed.
[CmdletBinding()]
param([Parameter(Mandatory)][DateTimeOffset]$TargetUtc)

$ErrorActionPreference = 'Stop'
if ($TargetUtc.Offset -ne [TimeSpan]::Zero -or ($TargetUtc.ToUnixTimeMilliseconds() % 900000) -ne 0) {
    throw 'Use a whole UTC quarter-hour as a scheduling hint.'
}
$launch = $TargetUtc.AddSeconds(-22)
$wait = $launch - [DateTimeOffset]::UtcNow
if ($wait.TotalSeconds -lt 0 -or $wait.TotalSeconds -gt 900) {
    throw 'Launch must be within the next fifteen minutes.'
}
$timer = [Diagnostics.Stopwatch]::StartNew()
while ($timer.Elapsed -lt $wait) {
    Start-Sleep -Milliseconds ([Math]::Min(1000, [Math]::Max(1, ($wait - $timer.Elapsed).TotalMilliseconds)))
}
if ([Math]::Abs(([DateTimeOffset]::UtcNow - $launch).TotalSeconds) -gt 5) {
    throw 'The wall clock moved or the launch window was missed.'
}
Write-Output ('Nominal boundary scheduling hint (UTC): ' + $TargetUtc.ToString('o'))
& (Join-Path $PSScriptRoot 'exness_phase_6941.ps1') -Action RunPhase696
exit $LASTEXITCODE
