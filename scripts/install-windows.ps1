<#
.SYNOPSIS
  (SheepFox) Firefox - Windows installer / uninstaller.

.DESCRIPTION
  Installs the SheepFox speed + privacy suite into a real Firefox profile
  (user.js) and the SheepShields enterprise policy
  (distribution\policies.json), which preinstalls uBlock Origin and
  Decentraleyes when Firefox next starts. -System additionally installs the
  AutoConfig files (sheepfox.cfg + defaults\pref\local-settings.js).

  All text files are written as BOM-free UTF-8: Firefox's AutoConfig loader
  and its JSON parser must never see a byte-order mark.

.PARAMETER System
  Install the policy + AutoConfig into the Firefox installation directory.
  On by default - use -ProfileOnly to keep everything inside the profile.
  Automatically re-launches itself elevated (UAC) when needed.

.PARAMETER ProfileOnly
  Only touch the Firefox profile: no policies.json, so uBlock Origin and
  Decentraleyes are not preinstalled. Needs no administrator rights.

.PARAMETER NoExtensions
  Install the SheepShields policy but drop the uBlock Origin + Decentraleyes
  entries, so nothing is preinstalled.

.PARAMETER Strict
  Append config\overrides\strict-paranoia.override.js (strict RFP (ResistFingerprinting) mode).

.PARAMETER Uninstall
  Remove the files SheepFox installed. Timestamped backups are left untouched.

.PARAMETER LowMemory
  Append config\overrides\low-memory.override.js (fewer content processes,
  smaller caches). Disables Fission site isolation - see the file header.

.PARAMETER Doctor
  Diagnose an existing install: report the profile in use, whether user.js is in
  the right place and carries the SheepFox prefs, and whether the policy is
  installed. Writes nothing.

.PARAMETER DryRun
  Print every action without touching the disk.

.PARAMETER ProfilePath
  Explicit Firefox profile directory (skips profiles.ini detection).

.PARAMETER FirefoxDir
  Explicit Firefox installation directory (default: auto-detected).

.PARAMETER Report
  Run the doctor and write the whole transcript to sheepfox-report.txt in the
  current folder, so it can be pasted into a bug report.

.EXAMPLE
  .\scripts\install-windows.bat

.EXAMPLE
  .\scripts\install-windows.bat -System -Strict

.NOTES
  Prefer install-windows.bat: it bypasses ExecutionPolicy for you, so a fresh
  Windows install never fails with "not digitally signed".
#>
[CmdletBinding()]
param(
    [switch]$System,
    [switch]$ProfileOnly,
    [switch]$NoExtensions,
    [switch]$Strict,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$Doctor,
    [switch]$LowMemory,
    [switch]$Report,
    [string]$ProfilePath = "",
    [string]$FirefoxDir = "",
    # Catches stray tokens (for example a '::' comment copied from cmd.exe docs)
    # so the user gets an actionable message instead of a binding error.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($RemainingArguments -and $RemainingArguments.Count -gt 0) {
    Write-Host "[error] Unexpected arguments: $($RemainingArguments -join ' ')" -ForegroundColor Red
    Write-Host ""
    Write-Host "        This usually means a documentation comment was copied along with the command." -ForegroundColor Yellow
    Write-Host "        In PowerShell a comment starts with '#'. The '::' form is a cmd.exe-only" -ForegroundColor Yellow
    Write-Host "        comment and becomes an argument here." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "        Try one of:" -ForegroundColor Yellow
    Write-Host "          .\scripts\install-windows.bat" -ForegroundColor Gray
    Write-Host "          .\scripts\install-windows.bat -System" -ForegroundColor Gray
    Write-Host "          .\scripts\install-windows.bat -System -Strict" -ForegroundColor Gray
    Write-Host "          .\scripts\install-windows.bat -Uninstall -System" -ForegroundColor Gray
    exit 2
}

# A normal install includes the SheepShields policy: that is what preinstalls
# uBlock Origin and Decentraleyes. -ProfileOnly opts out (and needs no UAC).
if (-not ($ProfileOnly -or $Doctor -or $DryRun -or $Report)) {
    $System = $true
}

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
function Write-SheepFox {
    param([string]$Message, [string]$Color = "Gray")
    Write-Host $Message -ForegroundColor $Color
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-MarkOfTheWeb {
    # Files downloaded from the internet carry a Zone.Identifier alternate data
    # stream. Unblocking them keeps PowerShell 7+ and AppLocker happy.
    foreach ($file in @($PSCommandPath, (Join-Path $PSScriptRoot "install.py"))) {
        if ($file -and (Test-Path $file)) {
            try { Unblock-File -Path $file -ErrorAction Stop } catch { }
        }
    }
}

function Write-Utf8NoBom {
    # CRITICAL: Set-Content's UTF8 encoding writes a BOM on PowerShell 5.1, which
    # breaks Firefox's JSON parser. Always go through .NET with BOM-free UTF8.
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Backup-ExistingFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$Path.sheepfox-backup-$stamp"
    Copy-Item -Path $Path -Destination $backup -Force
    Write-SheepFox "  [backup] $backup" "DarkYellow"
}

function Read-ProfileIni {
    <#
      Minimal profiles.ini parser: returns an ordered list of hashtables with
      the section name plus its key/value pairs. Avoids depending on
      Get-IniContent (not available on stock Windows).
    #>
    param([string]$IniPath)
    $sections = New-Object System.Collections.ArrayList
    if (-not (Test-Path $IniPath)) { return $sections }
    $current = $null
    foreach ($line in (Get-Content -Path $IniPath -Encoding UTF8)) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $current = @{ Name = $Matches[1]; Values = @{} }
            [void]$sections.Add($current)
            continue
        }
        if (-not $current) { continue }
        if ($trimmed -eq "" -or $trimmed.StartsWith(";") -or $trimmed.StartsWith("#")) { continue }
        $pair = $trimmed.Split("=", 2)
        if ($pair.Count -eq 2) {
            $current.Values[$pair[0].Trim()] = $pair[1].Trim()
        }
    }
    return $sections
}

function Resolve-ProfileFromIni {
    param([string]$IniPath)
    $root = Split-Path -Parent $IniPath
    $sections = Read-ProfileIni -IniPath $IniPath

    # 1. [InstallXXXXXXXX] Default=... is authoritative (Firefox 67+).
    foreach ($section in $sections) {
        if ($section.Name -like "Install*" -and $section.Values.ContainsKey("Default")) {
            $candidate = Join-Path $root $section.Values["Default"]
            if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
        }
    }

    # 2. [ProfileN] Default=1
    foreach ($section in $sections) {
        if ($section.Name -like "Profile*" -and $section.Values.ContainsKey("Path")) {
            if ($section.Values.ContainsKey("Default") -and $section.Values["Default"] -eq "1") {
                $relative = $section.Values["Path"]
                $candidate = if ($section.Values.ContainsKey("IsRelative") -and $section.Values["IsRelative"] -eq "0") {
                    $relative
                } else {
                    Join-Path $root $relative
                }
                if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
            }
        }
    }

    # 3. Any *.default-release profile
    foreach ($section in $sections) {
        if ($section.Name -like "Profile*" -and $section.Values.ContainsKey("Path")) {
            if ($section.Values["Path"] -like "*.default-release") {
                $candidate = Join-Path $root $section.Values["Path"]
                if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
            }
        }
    }
    return $null
}

function Resolve-FirefoxDir {
    param([string]$Explicit)
    if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path }

    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Mozilla Firefox") }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Mozilla Firefox") }

    foreach ($key in @(
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe")) {
        try {
            $item = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($item."(default)") { $candidates += (Split-Path -Parent $item."(default)") }
        } catch { }
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return (Resolve-Path $candidate).Path }
    }
    return $null
}

function Get-SheepFoxProfiles {
    # Every profile this machine has, across standard, Microsoft Store (MSIX)
    # and portable installs. Installing into all of them removes profile
    # detection as a failure mode.
    $results = @()
    $roots = @()
    if ($env:APPDATA) { $roots += (Join-Path $env:APPDATA "Mozilla\Firefox") }
    if ($env:LOCALAPPDATA) {
        $packages = Join-Path $env:LOCALAPPDATA "Packages"
        if (Test-Path $packages) {
            foreach ($dir in (Get-ChildItem -Path $packages -Directory -Filter "Mozilla.Firefox_*" -ErrorAction SilentlyContinue)) {
                $roots += (Join-Path $dir.FullName "LocalCache\Roaming\Mozilla\Firefox")
            }
        }
    }
    foreach ($root in $roots) {
        # installs.ini first: it records which profile each install opens.
        foreach ($name in @("installs.ini", "profiles.ini")) {
            $ini = Join-Path $root $name
            if (-not (Test-Path $ini)) { continue }
            $base = Split-Path -Parent $ini
            foreach ($section in (Read-ProfileIni -IniPath $ini)) {
                $relative = $null
                if ($section.Values.ContainsKey("Default")) { $relative = $section.Values["Default"] }
                elseif ($section.Values.ContainsKey("Path")) { $relative = $section.Values["Path"] }
                if (-not $relative) { continue }
                $candidate = if ($section.Values.ContainsKey("IsRelative") -and $section.Values["IsRelative"] -eq "0") {
                    $relative
                } else {
                    Join-Path $base $relative
                }
                if (-not (Test-Path $candidate)) { continue }
                $full = (Resolve-Path $candidate).Path
                if ($results -notcontains $full) { $results += $full }
            }
        }
    }
    return $results
}

# --------------------------------------------------------------------------
# Elevation
# --------------------------------------------------------------------------
Remove-MarkOfTheWeb

if ($System -and -not (Test-IsAdmin) -and -not $DryRun -and -not $Doctor) {
    Write-SheepFox "Administrator rights are required for -System; requesting elevation (UAC)..." "Yellow"
    $argumentList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-System"
    )
    if ($Strict) { $argumentList += "-Strict" }
    if ($LowMemory) { $argumentList += "-LowMemory" }
    if ($Uninstall) { $argumentList += "-Uninstall" }
    if ($NoExtensions) { $argumentList += "-NoExtensions" }
    if ($ProfilePath) { $argumentList += @("-ProfilePath", "`"$ProfilePath`"") }
    if ($FirefoxDir) { $argumentList += @("-FirefoxDir", "`"$FirefoxDir`"") }

    try {
        $elevated = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentList -Verb RunAs -Wait -PassThru
        exit $elevated.ExitCode
    } catch {
        Write-SheepFox "[error] Elevation was cancelled. Re-run from an elevated shell, or drop -System." "Red"
        exit 1
    }
}

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
$UserJsSrc = Join-Path $RepoRoot "config\user.js"
$StrictSrc = Join-Path $RepoRoot "config\overrides\strict-paranoia.override.js"
$LowMemorySrc = Join-Path $RepoRoot "config\overrides\low-memory.override.js"
$UserOverridesSrc = Join-Path $RepoRoot "config\overrides\user-overrides.js"
$PoliciesSrc = Join-Path $RepoRoot "config\distribution\policies.json"
$AutoCfgSrc = Join-Path $RepoRoot "config\autoconfig\sheepfox.cfg"
$LocalSettingsSrc = Join-Path $RepoRoot "config\autoconfig\defaults\pref\local-settings.js"
# Files SheepFox <= 1.2 wrote into the profile's chrome\ folder for the
# floating-search theme. That theme is gone; install and uninstall both clean
# up the leftovers so an upgrade from 1.2 does not leave a dead stylesheet.
$LegacyUiFiles = @("userChrome.css", "userContent.css", "sheepfox-probe.css")

if (-not (Test-Path $UserJsSrc)) {
    Write-SheepFox "[error] config\user.js is missing. Run 'python mozbuild\scripts\build-configs.py' first." "Red"
    exit 1
}

Write-SheepFox "=== (SheepFox) Firefox Windows Installer ===" "Cyan"

$Profiles = @()
if ($ProfilePath) {
    $Profiles = @($ProfilePath)
} else {
    $Profiles = @(Get-SheepFoxProfiles)
    if ($Profiles.Count -gt 0) { $ProfilePath = $Profiles[0] }
}
if (-not $FirefoxDir) {
    $FirefoxDir = Resolve-FirefoxDir -Explicit ""
}

Write-SheepFox ("Profile : " + $(if ($ProfilePath) { $ProfilePath } else { "not found (pass -ProfilePath)" }))
Write-SheepFox ("Install : " + $(if ($FirefoxDir) { $FirefoxDir } else { "not found (pass -FirefoxDir)" }))
Write-Host ""

# --------------------------------------------------------------------------
# Doctor
# --------------------------------------------------------------------------
if ($Report) { $Doctor = $true }

if ($Doctor) {
    if ($Report) {
        $reportPath = Join-Path (Get-Location) "sheepfox-report.txt"
        try { Start-Transcript -Path $reportPath -Force | Out-Null } catch { Write-SheepFox "[warn] could not start transcript: $_" "Yellow" }
    }
    Write-SheepFox "=== (SheepFox) Firefox doctor ===" "Cyan"
    Write-SheepFox ("  profiles : " + $(if ($Profiles.Count -gt 0) { $Profiles -join "; " } else { "none found" }))
    $problems = 0

    function Report-Check {
        param([bool]$Ok, [string]$Label, [string]$Detail = "")
        if (-not $Ok) { $script:problems++ }
        $mark = if ($Ok) { "OK  " } else { "FAIL" }
        $color = if ($Ok) { "Green" } else { "Red" }
        $suffix = if ($Detail) { " -> $Detail" } else { "" }
        Write-Host "  [$mark] $Label$suffix" -ForegroundColor $color
    }

    $version = "unknown"
    if ($FirefoxDir -and (Test-Path (Join-Path $FirefoxDir "application.ini"))) {
        foreach ($line in (Get-Content (Join-Path $FirefoxDir "application.ini") -ErrorAction SilentlyContinue)) {
            if ($line -like "Version=*") { $version = ($line -split "=", 2)[1].Trim() }
        }
    }
    Write-SheepFox ("  install   : " + $(if ($FirefoxDir) { "$FirefoxDir (v$version)" } else { "not detected (pass -FirefoxDir)" }))
    Write-SheepFox ("  profile   : " + $(if ($ProfilePath) { $ProfilePath } else { "not detected (pass -ProfilePath)" }))

    if (-not $ProfilePath -or -not (Test-Path $ProfilePath)) {
        Write-SheepFox "  [FAIL] no Firefox profile found. Launch Firefox once, or pass -ProfilePath." "Red"
        if ($Report) { Stop-Transcript | Out-Null; Write-SheepFox "  report: $reportPath" "Cyan" }
        exit 1
    }

    $userJs = Join-Path $ProfilePath "user.js"
    Report-Check (Test-Path $userJs) "user.js present"
    if (Test-Path $userJs) {
        $userJsText = [System.IO.File]::ReadAllText($userJs)
        $prefCount = ([regex]::Matches($userJsText, "user_pref\(")).Count
        Report-Check (($prefCount -ge 100)) "user.js carries the SheepFox prefs" "$prefCount user_pref lines"
    }

    $leftovers = @($LegacyUiFiles | ForEach-Object { Join-Path $ProfilePath "chrome\$_" } | Where-Object { Test-Path $_ })
    if ($leftovers.Count -gt 0) {
        Write-SheepFox "  [info] this profile still has files from the retired search-bar theme:" "Gray"
        foreach ($path in $leftovers) { Write-SheepFox "         $path" "Gray" }
        Write-SheepFox "         drop it with:  .\scripts\install-windows.bat -Uninstall" "Gray"
    }

    # Catch the number-one cause: installed into a profile Firefox never opens.
    if ($env:APPDATA) {
        $ini = Join-Path $env:APPDATA "Mozilla\Firefox\profiles.ini"
        if (Test-Path $ini) {
            $root = Split-Path -Parent $ini
            foreach ($section in (Read-ProfileIni -IniPath $ini)) {
                if ($section.Name -notlike "Profile*" -or -not $section.Values.ContainsKey("Path")) { continue }
                $candidate = if ($section.Values.ContainsKey("IsRelative") -and $section.Values["IsRelative"] -eq "0") {
                    $section.Values["Path"]
                } else {
                    Join-Path $root $section.Values["Path"]
                }
                if (-not (Test-Path $candidate)) { continue }
                $full = (Resolve-Path $candidate).Path
                if ($full -eq (Resolve-Path $ProfilePath).Path) { continue }
                if (Test-Path (Join-Path $full "user.js")) {
                    Write-SheepFox "  [warn] SheepFox files also exist in another profile: $full" "Yellow"
                    Write-SheepFox "         Firefox launches the profile shown at the top of this report." "Yellow"
                }
            }
        }
    }

    if ($FirefoxDir -and (Test-Path $FirefoxDir)) {
        $systemFiles = @("sheepfox.cfg", "defaults\pref\local-settings.js", "distribution\policies.json")
        $installed = @($systemFiles | Where-Object { Test-Path (Join-Path $FirefoxDir $_) })
        foreach ($rel in $installed) {
            Report-Check $true "system $rel"
        }
        if ($installed.Count -eq 0) {
            Write-SheepFox "  [info] no system install here (-System is optional):" "Gray"
            Write-SheepFox "         policies.json preinstalls uBlock Origin + Decentraleyes and locks the shields." "Gray"
            Write-SheepFox "         add them with:  .\scripts\install-windows.bat -System" "Gray"
        }
        $policiesFile = Join-Path $FirefoxDir "distribution\policies.json"
        if (Test-Path $policiesFile) {
            try {
                $policyObject = [System.IO.File]::ReadAllText($policiesFile) | ConvertFrom-Json
                $configured = @($policyObject.policies.ExtensionSettings.PSObject.Properties | ForEach-Object { $_.Name })
                $missing = @()
                foreach ($extensionId in @("uBlock0@raymondhill.net", "jid1-BoFifL9Vbdl2zQ@jetpack")) {
                    if ($configured -notcontains $extensionId) { $missing += $extensionId }
                }
                if ($missing.Count -gt 0) {
                    Write-SheepFox "  [info] extension preinstall skipped for: $($missing -join ', ')" "Gray"
                    Write-SheepFox "         re-run the installer without -NoExtensions to add them" "Gray"
                } else {
                    Report-Check $true "extension preinstall (uBlock Origin + Decentraleyes)"
                }
            } catch {
                Report-Check $false "distribution\policies.json parses" "$($_.Exception.Message)"
            }
        }
    }

    Write-Host ""
    if ($problems -gt 0) {
        Write-SheepFox "  $problems problem(s) found. Fix the FAIL lines above, then restart Firefox." "Yellow"
        Write-SheepFox "  Full reinstall:  .\scripts\install-windows.bat -System" "Yellow"
        if ($Report) { Stop-Transcript | Out-Null; Write-SheepFox "  report: $reportPath" "Cyan" }
        exit 1
    }

    Write-SheepFox "  Files are in place. QUIT Firefox completely (Task Manager: no firefox.exe)," "Cyan"
    Write-SheepFox "  then start it again."
    Write-SheepFox "  If nothing changed, open about:support in Firefox, compare its"
    Write-SheepFox "  'Profile Folder' with the path above, then:"
    Write-SheepFox '    .\scripts\install-windows.bat -ProfilePath "<that path>"'
    exit 0
}

# --------------------------------------------------------------------------
# Uninstall
# --------------------------------------------------------------------------
if ($Uninstall) {
    $targets = @()
    foreach ($profile in $Profiles) {
        $targets += (Join-Path $profile "user.js")
        foreach ($name in $LegacyUiFiles) { $targets += (Join-Path $profile "chrome\$name") }
    }
    if ($System -and $FirefoxDir) {
        $targets += @(
            (Join-Path $FirefoxDir "sheepfox.cfg"),
            (Join-Path $FirefoxDir "defaults\pref\local-settings.js"),
            (Join-Path $FirefoxDir "distribution\policies.json")
        )
    }
    if ($targets.Count -eq 0) {
        Write-SheepFox "[warn] Nothing to uninstall (no profile or install dir detected)." "Yellow"
        exit 0
    }
    foreach ($target in $targets) {
        if (-not (Test-Path $target)) { continue }
        if ($DryRun) {
            Write-SheepFox "  [dry-run] would remove $target"
        } else {
            Remove-Item -Path $target -Force
            Write-SheepFox "  [removed] $target" "Green"
        }
    }
    Write-SheepFox "`nSheepFox files removed. Timestamped .sheepfox-backup-* files were left in place." "Cyan"
    exit 0
}

# --------------------------------------------------------------------------
# Install: profile payload (user.js), every profile
# --------------------------------------------------------------------------
if ($Profiles.Count -gt 0) {
    $payload = [System.IO.File]::ReadAllText($UserJsSrc)
    if ($Strict) {
        $payload = $payload + "`r`n`r`n" + [System.IO.File]::ReadAllText($StrictSrc)
        Write-SheepFox "  [strict] appending strict RFP overrides" "DarkYellow"
    }
    if ($LowMemory) {
        $payload = $payload + "`r`n`r`n" + [System.IO.File]::ReadAllText($LowMemorySrc)
        Write-SheepFox "  [memory] appending low-memory overrides (Fission off)" "DarkYellow"
    }
    if (Test-Path $UserOverridesSrc) {
        $payload = $payload + "`r`n`r`n// --- Personal user overrides ---`r`n" + [System.IO.File]::ReadAllText($UserOverridesSrc)
        Write-SheepFox "  [custom] appending config\overrides\user-overrides.js" "DarkYellow"
    }

    foreach ($profile in $Profiles) {
        if (-not (Test-Path $profile)) { continue }
        if ($Profiles.Count -gt 1) { Write-SheepFox "`n  -> $profile" "Cyan" }

        $targetUserJs = Join-Path $profile "user.js"
        if ($DryRun) {
            Write-SheepFox "  [dry-run] would write $targetUserJs"
        } else {
            Backup-ExistingFile -Path $targetUserJs
            Write-Utf8NoBom -Path $targetUserJs -Content $payload
            Write-SheepFox "  [ok] installed user.js -> $targetUserJs" "Green"
        }

        # A profile upgraded from <= 1.2 still carries the retired theme.
        foreach ($name in $LegacyUiFiles) {
            $stale = Join-Path $profile "chrome\$name"
            if (-not (Test-Path $stale)) { continue }
            if ($DryRun) {
                Write-SheepFox "  [dry-run] would remove retired theme file $stale"
            } else {
                Remove-Item -Path $stale -Force
                Write-SheepFox "  [removed] retired theme file $stale" "Green"
            }
        }
    }
} elseif (-not $System) {
    Write-SheepFox "[warn] No Firefox profile found. Launch Firefox once, or pass -ProfilePath." "Yellow"
}

# --------------------------------------------------------------------------
# Install: system payload (AutoConfig + SheepShields)
# --------------------------------------------------------------------------
if ($System) {
    if (-not $FirefoxDir -or -not (Test-Path $FirefoxDir)) {
        Write-SheepFox "[error] Firefox installation directory not found. Pass -FirefoxDir 'C:\Program Files\Mozilla Firefox'." "Red"
        exit 1
    }

    $cfgTarget = Join-Path $FirefoxDir "sheepfox.cfg"
    $localSettingsTarget = Join-Path $FirefoxDir "defaults\pref\local-settings.js"
    $policiesTarget = Join-Path $FirefoxDir "distribution\policies.json"

    $policiesText = [System.IO.File]::ReadAllText($PoliciesSrc)
    if ($NoExtensions) {
        $policiesObject = $policiesText | ConvertFrom-Json
        foreach ($extensionId in @("uBlock0@raymondhill.net", "jid1-BoFifL9Vbdl2zQ@jetpack")) {
            $policiesObject.policies.ExtensionSettings.PSObject.Properties.Remove($extensionId)
            if ($policiesObject.policies.'3rdparty'.Extensions) {
                $policiesObject.policies.'3rdparty'.Extensions.PSObject.Properties.Remove($extensionId)
            }
        }
        $policiesText = $policiesObject | ConvertTo-Json -Depth 32
    }

    if ($DryRun) {
        Write-SheepFox "  [dry-run] would write $cfgTarget"
        Write-SheepFox "  [dry-run] would write $localSettingsTarget"
        Write-SheepFox "  [dry-run] would write $policiesTarget"
    } else {
        foreach ($item in @(
                @{ Text = [System.IO.File]::ReadAllText($AutoCfgSrc); Target = $cfgTarget },
                @{ Text = [System.IO.File]::ReadAllText($LocalSettingsSrc); Target = $localSettingsTarget },
                @{ Text = $policiesText; Target = $policiesTarget })) {
            Backup-ExistingFile -Path $item.Target
            Write-Utf8NoBom -Path $item.Target -Content $item.Text
            Write-SheepFox "  [ok] installed $($item.Target)" "Green"
        }
        if ($NoExtensions) {
            Write-SheepFox "  [ok] SheepShields policy installed (-NoExtensions: nothing preinstalled)" "Green"
        } else {
            Write-SheepFox "  [ok] SheepShields policy preinstalls uBlock Origin + Decentraleyes on next start" "Green"
        }
    }
}

Write-SheepFox "`nDone. Restart Firefox to activate SheepFox speed + privacy." "Cyan"
exit 0
