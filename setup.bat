@echo off
REM setup.bat — Bootstrap the chopper development environment (Windows with cmd.exe).
REM Platform: Windows (cmd.exe / Command Prompt)
REM Auto-activate: Add to system startup or create a batch file in Startup folder
REM Usage: setup.bat

setlocal enabledelayedexpansion

set "scriptDir=%~dp0"
set "scriptDir=%scriptDir:~0,-1%"
set "venvDir=%scriptDir%\.venv"
REM Project runtime floor is Python 3.11 (pyproject.toml `requires-python`).
REM Dev venv is pinned to 3.13. Prefer the `py` launcher at 3.13; fall back
REM to bare `python` only if the launcher cannot find 3.13.
set "pythonCmd=python"
py -3.13 -c "import sys" >nul 2>&1
if %ERRORLEVEL% EQU 0 set "pythonCmd=py -3.13"
set "proxy=http://proxy-chain.intel.com:928"

if not exist "%scriptDir%\pyproject.toml" (
    echo setup.bat expects to be run from the repository root.
    echo Please cd into the repo first.
    exit /b 1
)

echo.
echo === Chopper Dev Environment Setup ===
echo Platform: Windows (cmd.exe / Command Prompt)

echo [1/5] Updating repository (git pull)...
where git >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    git -C "%scriptDir%" pull
    if !ERRORLEVEL! NEQ 0 echo WARN: git pull failed (network issue or local changes). Continuing with current code.
) else (
    echo WARN: git not found on PATH; skipping update.
)

if not exist "%venvDir%" (
    echo [2/5] Creating virtual environment...
    call %pythonCmd% -m venv "%venvDir%"
) else (
    REM Detect a stale/relocated venv (e.g. copied from another repo): the
    REM venv's python should report sys.prefix == %venvDir%. If it doesn't,
    REM wipe and rebuild, otherwise pip-generated console scripts
    REM (chopper.exe) will carry the old launcher path forever.
    set "venvHealthy=0"
    if exist "%venvDir%\Scripts\python.exe" (
        for /f "usebackq delims=" %%P in (`"%venvDir%\Scripts\python.exe" -c "import sys; print(sys.prefix)" 2^>nul`) do set "reportedPrefix=%%P"
        if /i "!reportedPrefix!"=="%venvDir%" set "venvHealthy=1"
    )
    if "!venvHealthy!"=="1" (
        echo [2/5] Virtual environment exists and is healthy, reusing.
    ) else (
        echo [2/5] Existing .venv is stale or relocated - recreating...
        rmdir /s /q "%venvDir%"
        call %pythonCmd% -m venv "%venvDir%"
    )
)

echo [3/5] Activating venv...
call "%venvDir%\Scripts\activate.bat"

echo [4/5] Configuring pip and Git proxy...
REM Always invoke pip as `python -m pip`. pip's own shim (pip.exe) can be
REM stale when a venv is copied, and `python -m pip` bypasses the shim.
python -m pip config set global.proxy "%proxy%" --quiet 2>nul
python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>nul


REM Install dependencies. `--force-reinstall --no-deps` on the last line
REM regenerates the chopper.exe console-script shim against THIS venv's
REM python, fixing the common "copied venv" failure mode.
echo [5/5] Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -e ".[dev]" --quiet
python -m pip install -e . --force-reinstall --no-deps --quiet

for /f "usebackq delims=" %%V in (`python -c "import chopper; print(chopper.__version__)" 2^>nul`) do set "chopperVersion=%%V"
chopper --help >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "chopperLine=%chopperVersion% (launcher OK)"
) else (
    set "chopperLine=%chopperVersion% (launcher FAILED - run 'python -m pip install -e . --force-reinstall --no-deps')"
)

echo.
echo === Setup complete ===
for /f "tokens=*" %%i in ('%pythonCmd% --version 2^>^&1') do set "pythonVersion=%%i"
echo   Platform : Windows (cmd.exe)
echo   Python   : %pythonVersion%
echo   Chopper  : %chopperLine%
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
