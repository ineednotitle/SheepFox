@echo off
rem ===========================================================================
rem (SheepFox) Zen Browser - Windows launcher
rem
rem The same installer as install-windows.bat, with -Zen already applied:
rem Zen's profile folder (%APPDATA%\zen), Zen's installation folder, and
rem Zen's own defaults. The floating pill is not installed unless -UI is
rem given, because Zen already has its own floating omnibox.
rem
rem CRITICAL: Windows blocks unsigned PowerShell scripts by default, so this
rem launcher starts PowerShell with -NoProfile -ExecutionPolicy Bypass. Users
rem therefore never hit "cannot be loaded because running scripts is disabled"
rem or "not digitally signed" errors.
rem
rem Usage:
rem   scripts\install-zen.bat                 (installs the policy too, asks for UAC)
rem   scripts\install-zen.bat -ProfileOnly    (profile only, no admin needed)
rem   scripts\install-zen.bat -UI             (also install the SheepFox pill)
rem   scripts\install-zen.bat -Doctor
rem   scripts\install-zen.bat -Uninstall
rem ===========================================================================
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" -Zen %*
set "SHEEPFOX_EXIT=%ERRORLEVEL%"

if not "%SHEEPFOX_EXIT%"=="0" (
    echo.
    echo [SheepFox] Installation failed with exit code %SHEEPFOX_EXIT%.
)

if /I not "%~1"=="-DryRun" (
    echo.
    pause
)

endlocal & exit /b %SHEEPFOX_EXIT%
