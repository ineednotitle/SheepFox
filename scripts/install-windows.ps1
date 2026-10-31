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
  Diagnose an existing install: report the profile in use, whether user.js and
  chrome\userChrome.css are in the right place, and whether the stylesheet pref
  is actually saved. Writes nothing.

.PARAMETER NoUI
  Skip the chrome\userChrome.css + userContent.css floating-search theme, so
  Firefox keeps its stock toolbar and New Tab layout.

.PARAMETER Zen
  Configure Zen Browser instead of Firefox: its profile folder (the same
  per-profile user.js), its installation folder, and its own defaults. Zen
  already ships a floating omnibox, so the SheepFox pill is not installed
  unless -UI is given.

.PARAMETER UI
  Install the floating-search theme into Zen as well (opt-in there).

.PARAMETER DryRun
  Print every action without touching the disk.

.PARAMETER ProfilePath
  Explicit Firefox profile directory (skips profiles.ini detection).

.PARAMETER FirefoxDir
  Explicit Firefox installation directory (default: auto-detected).

.PARAMETER Probe
  Write chrome\sheepfox-probe.css, which turns the toolbar red. Start Firefox,
  open a new tab: red toolbar = the stylesheet is loaded. Remove with -Unprobe.

.PARAMETER Unprobe
  Delete the file written by -Probe.

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
    [switch]$NoUI,
    [switch]$Doctor,
    [switch]$LowMemory,
    [switch]$Probe,
    [switch]$Unprobe,
    [switch]$Zen,
    [switch]$UI,
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
if (-not ($ProfileOnly -or $Doctor -or $DryRun -or $Probe -or $Unprobe -or $Report)) {
    $System = $true
}

# Firefox and Zen Browser are the same engine with different folders: this is
# the only place the difference lives.
$Brand = if ($Zen) { "Zen Browser" } else { "Firefox" }
$ProcessName = if ($Zen) { "zen.exe" } else { "firefox.exe" }
$ProfileRootName = if ($Zen) { "zen" } else { "Mozilla\Firefox" }
$InstallHint = if ($Zen) { "$env:LOCALAPPDATA\Programs\zen" } else { "C:\Program Files\Mozilla Firefox" }

# Zen has its own floating omnibox and its own chrome, so SheepFox's pill is a
# choice there, not a default. -UI asks for it explicitly.
if ($Zen -and -not $UI) { $NoUI = $true }

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

function Merge-PolicyDocument {
    <#
      SheepFox's own policy entries win; anything already in the file is kept.
      Both browsers take the first policy file they find instead of merging
      several, so overwriting must not drop policies the packager set - a
      packaged Zen ships DisableAppUpdate, and losing it would let the browser
      update itself behind the package manager.
    #>
    param([string]$ExistingText, [string]$OurText)
    if (-not $ExistingText) { return $OurText }
    try { $existing = $ExistingText | ConvertFrom-Json } catch { return $OurText }
    if (-not $existing -or -not $existing.policies) { return $OurText }
    $merged = $OurText | ConvertFrom-Json
    $known = @($merged.policies.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($property in @($existing.policies.PSObject.Properties)) {
        if ($known -contains $property.Name) { continue }
        $merged.policies | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value
        Write-SheepFox "  [keep] preserved existing policy: $($property.Name)" "DarkYellow"
    }
    return ($merged | ConvertTo-Json -Depth 64)
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
    if ($Zen) {
        # Zen's per-user installer (the default) goes to LOCALAPPDATA, not
        # Program Files - the same trap as Microsoft Store Firefox.
        if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Zen Browser") }
        if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Zen Browser") }
        if ($env:LOCALAPPDATA) {
            $candidates += (Join-Path $env:LOCALAPPDATA "Programs\zen")
            $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Zen Browser")
            $candidates += (Join-Path $env:LOCALAPPDATA "Zen Browser")
        }
    }
    if (-not $Zen -and $env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Mozilla Firefox") }
    if (-not $Zen -and ${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Mozilla Firefox") }

    $appPathKeys = if ($Zen) {
        @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\zen.exe",
          "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\zen.exe")
    } else {
        @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
          "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe")
    }
    foreach ($key in $appPathKeys) {
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
    if ($env:APPDATA) { $roots += (Join-Path $env:APPDATA $ProfileRootName) }
    if (-not $Zen -and $env:LOCALAPPDATA) {
        $packages = Join-Path $env:LOCALAPPDATA "Packages"
        if (Test-Path $packages) {
            foreach ($dir in (Get-ChildItem -Path $packages -Directory -Filter "Mozilla.Firefox_*" -ErrorAction SilentlyContinue)) {
                $roots += (Join-Path $dir.FullName "LocalCache\Roaming\Mozilla\Firefox")
            }
        }
    }
    if ($Zen -and $env:LOCALAPPDATA) {
        # Some Zen builds keep profiles next to the binary instead of in Roaming.
        $roots += (Join-Path $env:LOCALAPPDATA "zen")
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
    if ($NoUI) { $argumentList += "-NoUI" }
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
$ChromeSrcDir = Join-Path $RepoRoot "config\chrome"
# Profile-level CSS: the floating Zen/Arc-style new-tab search pill.
$UiFiles = @("userChrome.css", "userContent.css")
# Optional probe that userChrome.css @imports; proves the stylesheet is read.
$ProbeFile = "sheepfox-probe.css"

if (-not (Test-Path $UserJsSrc)) {
    Write-SheepFox "[error] config\user.js is missing. Run 'python mozbuild\scripts\build-configs.py' first." "Red"
    exit 1
}

Write-SheepFox ("=== (SheepFox) " + $Brand + " Windows Installer ===") "Cyan"

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
# Probe / unprobe (proves userChrome.css is being read)
# --------------------------------------------------------------------------
if ($Probe -or $Unprobe) {
    if (-not $ProfilePath -or -not (Test-Path $ProfilePath)) {
        Write-SheepFox "[error] No $Brand profile to write into. Pass -ProfilePath <dir>." "Red"
        exit 1
    }
    $probePath = Join-Path $ProfilePath "chrome\$ProbeFile"
    if ($Unprobe) {
        if (Test-Path $probePath) {
            if ($DryRun) {
                Write-SheepFox "  [dry-run] would remove $probePath"
            } else {
                Remove-Item -Path $probePath -Force
                Write-SheepFox "  [removed] $probePath" "Green"
            }
        } else {
            Write-SheepFox "  [info] no probe file present."
        }
        exit 0
    }
    $probeCss = @"
/* (SheepFox) CSS load probe - written by -Probe, removed by -Unprobe.
   A RED toolbar means $Brand is reading userChrome.css from this profile. */
#nav-bar {
  background: #cc0000 !important;
}
#urlbar {
  outline: 3px solid #00ff88 !important;
  outline-offset: -3px !important;
}
"@
    if ($DryRun) {
        Write-SheepFox "  [dry-run] would write $probePath"
    } else {
        Write-Utf8NoBom -Path $probePath -Content $probeCss
        Write-SheepFox "  [write] $probePath" "Green"
        Write-Host ""
        Write-SheepFox "  Now QUIT Firefox completely (Task Manager: no firefox.exe), start it and" "Cyan"
        Write-SheepFox "  open a new tab: a RED toolbar means the CSS is loading." "Cyan"
        Write-SheepFox "  Remove it with:  .\scripts\install-windows.bat -Unprobe" "Cyan"
    }
    exit 0
}

# --------------------------------------------------------------------------
# Doctor
# --------------------------------------------------------------------------
if ($Report) { $Doctor = $true }

if ($Doctor) {
    if ($Report) {
        $reportPath = Join-Path (Get-Location) "sheepfox-report.txt"
        try { Start-Transcript -Path $reportPath -Force | Out-Null } catch { Write-SheepFox "[warn] could not start transcript: $_" "Yellow" }
    }
    Write-SheepFox ("=== (SheepFox) " + $Brand + " doctor ===") "Cyan"
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
        Write-SheepFox "  [FAIL] no $Brand profile found. Launch $Brand once, or pass -ProfilePath." "Red"
        if ($Report) { Stop-Transcript | Out-Null; Write-SheepFox "  report: $reportPath" "Cyan" }
        exit 1
    }

    $userJs = Join-Path $ProfilePath "user.js"
    Report-Check (Test-Path $userJs) "user.js present"
    if (Test-Path $userJs) {
        $userJsText = [System.IO.File]::ReadAllText($userJs)
        Report-Check ($userJsText -match 'toolkit\.legacyUserProfileCustomizations\.stylesheets", true') `
            "user.js enables userChrome.css"
    }

    # A missing stylesheet is the expected state in Zen (unless it was
    # installed): report it as information, never as a failure.
    $uiExpected = -not $NoUI
    if (-not $uiExpected -and (Test-Path (Join-Path $ProfilePath "chrome\userChrome.css"))) { $uiExpected = $true }
    if (-not $uiExpected) {
        Write-SheepFox "  [info] UI theme not installed (default for Zen; add -UI to install the pill)" "Gray"
    } else {
        foreach ($pair in @(
                @{ Name = "userChrome.css"; Min = 2000 },
                @{ Name = "userContent.css"; Min = 400 })) {
            $target = Join-Path $ProfilePath "chrome\$($pair.Name)"
            $size = if (Test-Path $target) { (Get-Item $target).Length } else { 0 }
            Report-Check (($size -ge $pair.Min)) "chrome\$($pair.Name)" "$size bytes"
        }

        foreach ($name in $UiFiles) {
            $src = Join-Path $ChromeSrcDir $name
            $dst = Join-Path $ProfilePath "chrome\$name"
            if ((Test-Path $src) -and (Test-Path $dst)) {
                $same = (Get-FileHash $src -Algorithm SHA256).Hash -eq (Get-FileHash $dst -Algorithm SHA256).Hash
                Report-Check $same "chrome\$name matches this repo" $(if ($same) { "" } else { "stale - re-run the installer" })
            }
        }
    }

    if (Test-Path (Join-Path $ProfilePath "chrome\$ProbeFile")) {
        Write-SheepFox "  [info] probe active: run -Unprobe once you have looked at the toolbar" "Gray"
    }

    # Catch the number-one cause: installed into a profile Firefox never opens.
    if ($env:APPDATA) {
        $ini = Join-Path (Join-Path $env:APPDATA $ProfileRootName) "profiles.ini"
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
                if ((Test-Path (Join-Path $full "user.js")) -or (Test-Path (Join-Path $full "chrome\userChrome.css"))) {
                    Write-SheepFox "  [warn] SheepFox files also exist in another profile: $full" "Yellow"
                    Write-SheepFox "         $Brand launches the profile shown at the top of this report." "Yellow"
                }
            }
        }
    }

    $prefsJs = Join-Path $ProfilePath "prefs.js"
    $saved = $null
    if (Test-Path $prefsJs) {
        $hit = Select-String -Path $prefsJs -Pattern 'user_pref\("toolkit\.legacyUserProfileCustomizations\.stylesheets",\s*(true|false)\)' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($hit) {
            $saved = $hit.Matches[0].Groups[1].Value -eq "true"
        }
    }
    if ($null -eq $saved) {
        Write-SheepFox "  [info] prefs.js has no saved value yet; Firefox takes it from user.js on next start" "Gray"
    } else {
        Report-Check $saved "pref saved in prefs.js" $(if ($saved) { "true" } else { "false - set it to true in about:config" })
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
        Write-SheepFox "  $problems problem(s) found. Fix the FAIL lines above, then restart $Brand." "Yellow"
        Write-SheepFox "  Full reinstall:  .\scripts\install-windows.bat -System" "Yellow"
        if ($Report) { Stop-Transcript | Out-Null; Write-SheepFox "  report: $reportPath" "Cyan" }
        exit 1
    }

    Write-SheepFox "  Files are in place. To prove $Brand is actually reading the stylesheet:" "Cyan"
    Write-SheepFox "    1. .\scripts\install-windows.bat -Probe"
    Write-SheepFox "    2. QUIT $Brand completely (Task Manager: no $ProcessName), then start it."
    Write-SheepFox "    3. Open a new tab: RED toolbar = CSS is loading. Nothing = it is not."
    Write-SheepFox "    4. .\scripts\install-windows.bat -Unprobe"
    Write-SheepFox "  If the toolbar stays dark, open about:support in $Brand, compare its"
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
        foreach ($name in ($UiFiles + $ProbeFile)) { $targets += (Join-Path $profile "chrome\$name") }
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
# Install: profile payload (user.js + floating search UI), every profile
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

        if ($NoUI) {
            if ($Zen -and -not $UI) {
                Write-SheepFox "  [skip] UI theme not installed (Zen keeps its own omnibox; add -UI for SheepFox's pill)" "DarkYellow"
            } else {
                Write-SheepFox "  [skip] UI theme skipped (-NoUI)" "DarkYellow"
            }
            continue
        }
        foreach ($name in $UiFiles) {
            $source = Join-Path $ChromeSrcDir $name
            if (-not (Test-Path $source)) {
                Write-SheepFox "  [warn] missing UI asset: $source" "Yellow"
                continue
            }
            $target = Join-Path $profile "chrome\$name"
            if ($DryRun) {
                Write-SheepFox "  [dry-run] would write $target"
                continue
            }
            Backup-ExistingFile -Path $target
            Write-Utf8NoBom -Path $target -Content ([System.IO.File]::ReadAllText($source))
            Write-SheepFox "  [ok] installed floating search UI -> $target" "Green"
        }
    }
} elseif (-not $System) {
    Write-SheepFox "[warn] No $Brand profile found. Launch $Brand once, or pass -ProfilePath." "Yellow"
}

# --------------------------------------------------------------------------
# Install: system payload (AutoConfig + SheepShields)
# --------------------------------------------------------------------------
if ($System) {
    if (-not $FirefoxDir -or -not (Test-Path $FirefoxDir)) {
        Write-SheepFox "[error] $Brand installation directory not found. Pass -FirefoxDir '$InstallHint'." "Red"
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

    $existingPolicyText = ""
    if (Test-Path $policiesTarget) { $existingPolicyText = [System.IO.File]::ReadAllText($policiesTarget) }
    $policiesText = Merge-PolicyDocument -ExistingText $existingPolicyText -OurText $policiesText

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

Write-SheepFox "`nDone. Restart $Brand to activate SheepFox speed + privacy." "Cyan"
exit 0
