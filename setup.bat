@echo off
REM setup.bat — Bootstrap the chopper development environment (Windows with cmd.exe).
REM Platform: Windows (cmd.exe / Command Prompt)
REM Auto-activate: Add to system startup or create a batch file in Startup folder
REM Usage: setup.bat

setlocal enabledelayedexpansion

set "scriptDir=%~dp0"
set "scriptDir=%scriptDir:~0,-1%"
set "venvDir=%scriptDir%\.venv"
set "pythonCmd=python"
set "proxy=http://proxy-chain.intel.com:928"

if not exist "%scriptDir%\pyproject.toml" (
    echo setup.bat expects to be run from the repository root.
    echo Please cd into the repo first.
    exit /b 1
)

echo.
echo === Chopper Dev Environment Setup ===
echo Platform: Windows (cmd.exe / Command Prompt)

if not exist "%venvDir%" (
    echo [1/4] Creating virtual environment...
    call %pythonCmd% -m venv "%venvDir%"
) else (
    echo [1/4] Virtual environment exists, reusing.
)

echo [2/4] Activating venv...
call "%venvDir%\Scripts\activate.bat"

echo [3/4] Configuring pip and Git proxy...
pip config set global.proxy "%proxy%" --quiet 2>nul
pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>nul


echo [4/4] Installing dependencies...
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

echo.
echo === Setup complete ===
for /f "tokens=*" %%i in ('%pythonCmd% --version 2^>^&1') do set "pythonVersion=%%i"
echo   Platform : Windows (cmd.exe)
echo   Python   : %pythonVersion%
echo   Venv     : %venvDir%
echo   Shell    : cmd.exe / Command Prompt
echo.
echo To auto-activate on cmd startup:
echo   1. Create setup_auto.bat with: setup.bat
echo   2. Add setup_auto.bat to Windows Startup folder
echo      (C:\Users\[YourUsername]\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup)
echo   OR
echo   3. Create a shortcut to cmd.exe with target:
echo      %%comspec%% /k "cd /d %scriptDir% ^&^& setup.bat"
echo.
echo For other platforms/shells:
echo   Windows PowerShell : . setup.ps1
echo   Unix/Linux/macOS (bash/zsh) : . setup.sh
echo   Unix/Linux/macOS (tcsh)     : source setup.csh
echo.
echo Run: chopper --help
echo Test: pytest
echo.
