<#
.SYNOPSIS
  (SheepFox) Firefox — Windows PowerShell Installer
.DESCRIPTION
  Installs SheepFox speed & privacy user.js into the active Firefox profile,
  and optionally installs SheepShields (policies.json + uBlock Origin) and
  AutoConfig into C:\Program Files\Mozilla Firefox when run as Administrator.
.EXAMPLE
  .\scripts\install-windows.ps1
  .\scripts\install-windows.ps1 -System
#>
param(
    [switch]$System,
    [switch]$Strict,
    [switch]$DryRun,
    [string]$ProfilePath = "",
    [string]$FirefoxDir = "C:\Program Files\Mozilla Firefox"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$UserJsSrc = Join-Path $RepoRoot "config\user.js"
$StrictSrc = Join-Path $RepoRoot "config\overrides\strict-paranoia.override.js"
$PoliciesSrc = Join-Path $RepoRoot "config\distribution\policies.json"
$AutoCfgSrc = Join-Path $RepoRoot "config\autoconfig\sheepfox.cfg"
$LocalSetSrc = Join-Path $RepoRoot "config\autoconfig\defaults\pref\local-settings.js"

Write-Host "=== (SheepFox) Firefox Windows Installer ===" -ForegroundColor Cyan

if (-not $ProfilePath) {
    $ProfilesRoot = Join-Path $env:APPDATA "Mozilla\Firefox\Profiles"
    if (Test-Path $ProfilesRoot) {
        $Candidate = Get-ChildItem -Path $ProfilesRoot -Directory |
            Where-Object { $_.Name -match "\.default-release$" } |
            Select-Object -First 1
        if (-not $Candidate) {
            $Candidate = Get-ChildItem -Path $ProfilesRoot -Directory | Select-Object -First 1
        }
        if ($Candidate) { $ProfilePath = $Candidate.FullName }
    }
}

if ($ProfilePath -and (Test-Path $ProfilePath)) {
    $TargetUserJs = Join-Path $ProfilePath "user.js"
    $Combined = Get-Content -Raw $UserJsSrc
    if ($Strict) {
        $Combined += "`r`n" + (Get-Content -Raw $StrictSrc)
    }
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would write $TargetUserJs"
    } else {
        if (Test-Path $TargetUserJs) {
            $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
            Copy-Item $TargetUserJs "$TargetUserJs.sheepfox-backup-$Stamp"
        }
        Set-Content -Path $TargetUserJs -Value $Combined -Encoding UTF8
        Write-Host "[OK] Installed SheepFox user.js -> $TargetUserJs" -ForegroundColor Green
    }
} else {
    Write-Warning "No Firefox profile found automatically. Launch Firefox once or pass -ProfilePath."
}

if ($System) {
    if (-not (Test-Path $FirefoxDir)) {
        throw "Firefox directory not found at '$FirefoxDir'. Pass -FirefoxDir if installed elsewhere."
    }
    $DistDir = Join-Path $FirefoxDir "distribution"
    $PrefDir = Join-Path $FirefoxDir "defaults\pref"
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would install policies.json, sheepfox.cfg, and local-settings.js into $FirefoxDir"
    } else {
        New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
        New-Item -ItemType Directory -Force -Path $PrefDir | Out-Null
        Copy-Item -Force $PoliciesSrc (Join-Path $DistDir "policies.json")
        Copy-Item -Force $AutoCfgSrc (Join-Path $FirefoxDir "sheepfox.cfg")
        Copy-Item -Force $LocalSetSrc (Join-Path $PrefDir "local-settings.js")
        Write-Host "[OK] Installed System SheepShields (uBlock Origin policy) & AutoConfig -> $FirefoxDir" -ForegroundColor Green
    }
}

Write-Host "`nDone! Restart Firefox to enjoy Brave-level speed + LibreFox privacy." -ForegroundColor Cyan
