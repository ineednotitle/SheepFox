@echo off
rem ===========================================================================
rem (SheepFox) Firefox - Windows launcher
rem
rem CRITICAL: Windows blocks unsigned PowerShell scripts by default, so this
rem launcher starts PowerShell with -NoProfile -ExecutionPolicy Bypass. Users
rem therefore never hit "cannot be loaded because running scripts is disabled"
rem or "not digitally signed" errors.
rem
rem Usage:
rem   scripts\install-windows.bat
rem   scripts\install-windows.bat -System
rem   scripts\install-windows.bat -System -Strict
rem   scripts\install-windows.bat -Uninstall -System
rem ===========================================================================
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" %*
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
