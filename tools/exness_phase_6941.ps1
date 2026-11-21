# Explicit enrollment and read-only diagnostics for the selected Windows demo.
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('RecoverPhase692', 'Enroll', 'Run', 'RunPhase695', 'RunPhase696', 'RunPhase61051', 'RunPhase61052', 'RunPhase61053', 'Remove')]
    [string]$Action,

    [string]$Output,

    [long[]]$RawAnchor = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$server = 'ExnessKE-MT5Trial9'
$directory = Join-Path $env:LOCALAPPDATA 'GoldBot'
$file = Join-Path $directory 'exness-ke-9498.dpapi'
$root = Split-Path -Parent $PSScriptRoot

function Recover-Phase692 {
    $terminal = 'C:\Program Files\MetaTrader 5\terminal64.exe'
    $install = Split-Path -Parent $terminal
    $journals = @(
        Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'MetaQuotes\Terminal') -Directory |
        ForEach-Object {
            $origin = Join-Path $_.FullName 'origin.txt'
            if ((Test-Path -LiteralPath $origin -PathType Leaf) -and
                (Get-Content -Raw -LiteralPath $origin).Trim() -eq $install) {
                Join-Path $_.FullName 'logs\20261118.log'
            }
        }
    )
    if ($journals.Count -ne 1 -or !(Test-Path -LiteralPath $journals[0] -PathType Leaf)) {
        throw 'The prior installation journal could not be uniquely verified.'
    }
    # These entries precede the recorded 16:42 EAT verification. Later logins cannot seed recovery.
    $entries = @(Select-String -LiteralPath $journals[0] -Pattern (
        '\t16:2[45]:\d{2}\.\d{3}\tNetwork\t''([1-9]\d{0,19})'': authorized on ExnessKE-MT5Trial9(?:\s|$)'
    ))
    $logins = @($entries | ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique)
    if ($logins.Count -ne 1 -or !$logins[0].EndsWith('9498')) {
        throw 'The prior journal cannot supply a unique independently verified account.'
    }
    @{terminal = $terminal; server = $server; login = $logins[0]}
}

switch ($Action) {
    'Remove' {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
        return
    }
    { $_ -in 'Run', 'RunPhase695', 'RunPhase696', 'RunPhase61051', 'RunPhase61052', 'RunPhase61053' } {
        if ($Action -in 'RunPhase61051', 'RunPhase61052', 'RunPhase61053') {
            if (!$Output) {
                throw 'An output path is required for this diagnostic.'
            }
            if ($Action -eq 'RunPhase61051') {
                if (!(Test-Path -LiteralPath $Output -PathType Container)) {
                    throw 'Specify an existing output directory for the precision diagnostic.'
                }
                $Output = (Resolve-Path -LiteralPath $Output).Path
            } else {
                $Output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
            }
        }
        if (!(Test-Path -LiteralPath $file -PathType Leaf)) {
            throw 'The local opt-in profile is missing. Enroll or recover it explicitly first.'
        }
        try {
            $secure = Get-Content -LiteralPath $file -Raw | ConvertTo-SecureString
            $profile = [pscredential]::new('GoldBot', $secure).GetNetworkCredential().Password
        } catch {
            throw 'The local opt-in profile cannot be decrypted by this Windows user.'
        }
        Push-Location $root
        try {
            if ($Action -in 'RunPhase61051', 'RunPhase61052', 'RunPhase61053') {
                $trusted = Recover-Phase692
                $module = if ($Action -eq 'RunPhase61053') {
                    'tools.sample_exness_history_phase_61053'
                } elseif ($Action -eq 'RunPhase61052') {
                    'tools.verify_exness_time_phase_61052'
                } else {
                    'tools.verify_exness_precision_phase_61051'
                }
                $options = @('--output', $Output)
                if ($Action -eq 'RunPhase61051') { $options += '--profile-stdin' }
                if ($Action -eq 'RunPhase61053') {
                    foreach ($anchor in $RawAnchor) { $options += @('--anchor', [string]$anchor) }
                }
                $profile, ($trusted | ConvertTo-Json -Compress) |
                    & .\.venv\Scripts\python.exe -B -m $module @options
            } elseif ($Action -in 'RunPhase695', 'RunPhase696') {
                $trusted = Recover-Phase692
                $module = if ($Action -eq 'RunPhase696') {
                    'tools.collect_exness_phase_696'
                } else {
                    'tools.collect_exness_phase_695'
                }
                $profile, ($trusted | ConvertTo-Json -Compress) |
                    & .\.venv\Scripts\python.exe -B -m $module
            } else {
                $profile | & .\.venv\Scripts\python.exe -B -m tools.verify_exness_phase_6941
            }
            exit $LASTEXITCODE
        } finally {
            $profile = $null
            $trusted = $null
            $secure.Dispose()
            Pop-Location
        }
    }
    'RecoverPhase692' {
        $profile = Recover-Phase692
    }
    'Enroll' {
        $terminal = Read-Host 'Independently confirmed full terminal64.exe path'
        $confirmedServer = Read-Host 'Exact demo server from independent account evidence'
        $masked = Read-Host 'Exact demo account from independent evidence' -AsSecureString
        try {
            $login = [pscredential]::new('GoldBot', $masked).GetNetworkCredential().Password
            $profile = @{terminal = $terminal; server = $confirmedServer; login = $login}
        } finally {
            $masked.Dispose()
        }
    }
}

if ($profile.server -cne $server -or $profile.login -notmatch '^[1-9][0-9]{0,19}$' -or
    !$profile.login.EndsWith('9498') -or ![IO.Path]::IsPathFullyQualified($profile.terminal) -or
    [IO.Path]::GetFileName($profile.terminal) -ine 'terminal64.exe' -or
    !(Test-Path -LiteralPath $profile.terminal -PathType Leaf)) {
    throw 'The independently confirmed account and installation do not match the selected demo profile.'
}
$null = New-Item -Path $directory -ItemType Directory -Force
$secure = ($profile | ConvertTo-Json -Compress) | ConvertTo-SecureString -AsPlainText -Force
try {
    # Create exclusively, so a concurrent or accidental enrollment cannot replace a pin.
    $encrypted = ConvertFrom-SecureString -SecureString $secure
    $destination = [IO.File]::Open($file, [IO.FileMode]::CreateNew)
    try {
        $bytes = [Text.Encoding]::ASCII.GetBytes($encrypted)
        $destination.Write($bytes, 0, $bytes.Length)
    } finally {
        $destination.Dispose()
    }
} finally {
    $secure.Dispose()
}
Write-Output 'Stored the Windows-user-encrypted opt-in profile.'
