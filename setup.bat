@echo off
REM setup.bat - Bootstrap the chopper dev environment (Windows cmd.exe).
REM Usage: setup.bat
REM
REM NOTE: cmd.exe batch files modify the current shell's environment only when
REM run directly in an interactive cmd window. If you launch this as
REM 'cmd /c setup.bat' or from a non-interactive context, the venv activation
REM will not persist. Always run from an open cmd.exe prompt.
REM
REM We intentionally do NOT use 'setlocal' here -- it would scope the venv
REM environment changes to this script and discard them on exit.

set "scriptDir=%~dp0"
set "scriptDir=%scriptDir:~0,-1%"
set "venvDir=%scriptDir%\.venv"
set "localPy313=%scriptDir%\.local-python\3.13\python.exe"
set "defaultProxy=http://proxy-chain.intel.com:912"
set "proxy=%CHOPPER_PROXY%"
if "%proxy%"=="" set "proxy=%defaultProxy%"
set "useProxy=1"
if /i "%CHOPPER_NO_PROXY%"=="1" set "useProxy=0"

if not exist "%scriptDir%\pyproject.toml" (
    echo ERROR: Run setup.bat from the repository root.
    exit /b 1
)

echo === Chopper Setup (cmd.exe) ===

echo [1/7] Resolving Python 3.13+ interpreter...
set "pythonCmd="

REM Strategy step 1: probe PATH for any python whose version is >= 3.13.
for %%C in (python3.13 python python3) do (
    if not defined pythonCmd (
        where %%C >nul 2>&1
        if not errorlevel 1 (
            %%C -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
            if not errorlevel 1 set "pythonCmd=%%C"
        )
    )
)
if not defined pythonCmd (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
        if not errorlevel 1 set "pythonCmd=py -3.13"
    )
)

REM Strategy step 2 (Windows has no EC mount): local install under .local-python.
if not defined pythonCmd if exist "%localPy313%" set "pythonCmd=%localPy313%"

REM Strategy step 3: best-effort winget install, then re-resolve via py -3.13.
if not defined pythonCmd (
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo   Python 3.13 not found; attempting winget install...
        winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent
        py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
        if not errorlevel 1 set "pythonCmd=py -3.13"
    )
)

if not defined pythonCmd (
    echo ERROR: Python 3.13+ could not be resolved.
    echo Strategy: PATH ^(^>= 3.13^) -^> %localPy313% -^> winget install Python.Python.3.13.
    exit /b 1
)

if "%useProxy%"=="1" (
    set "HTTP_PROXY=%proxy%"
    set "HTTPS_PROXY=%proxy%"
    set "http_proxy=%proxy%"
    set "https_proxy=%proxy%"
)

echo [2/7] Running git pull...
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: git not found on PATH.
    exit /b 1
)
git -C "%scriptDir%" pull
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: git pull failed. Resolve git/network issue and rerun setup.
    exit /b 1
)

echo [3/7] Ensuring virtual environment...
set "venvPython=%venvDir%\Scripts\python.exe"
set "fresh=0"
if /i "%CHOPPER_FRESH%"=="1" set "fresh=1"
if "%fresh%"=="1" if exist "%venvDir%" (
    echo   CHOPPER_FRESH=1 set; removing existing venv at %venvDir%
    rmdir /s /q "%venvDir%"
)
if exist "%venvPython%" (
    "%venvPython%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo   Existing venv has wrong Python; recreating.
        rmdir /s /q "%venvDir%"
    ) else (
        echo   Reusing existing venv at %venvDir%
    )
)
if not exist "%venvPython%" (
    call %pythonCmd% -m venv "%venvDir%"
    if errorlevel 1 (
        echo ERROR: Failed to create venv with Python 3.13.
        exit /b 1
    )
)

echo [4/7] Activating venv...
call "%venvDir%\Scripts\activate.bat"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to activate venv.
    exit /b 1
)

echo [5/7] Configuring proxy for pip and npm...
if "%useProxy%"=="1" (
    set "HTTP_PROXY=%proxy%"
    set "HTTPS_PROXY=%proxy%"
    set "http_proxy=%proxy%"
    set "https_proxy=%proxy%"
    python -m pip config set global.proxy "%proxy%" --quiet 2>nul
    python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>nul
    where npm >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        npm config set proxy "%proxy%" --location=user >nul 2>&1
        npm config set https-proxy "%proxy%" --location=user >nul 2>&1
    )
) else (
    echo   Proxy disabled ^(CHOPPER_NO_PROXY=1^).
)

echo [6/7] Ensuring chopper package is installed...
python -m pip install --quiet --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip upgrade failed.
    exit /b 1
)
python -m pip install --quiet -e ".[dev]"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install -e .[dev] failed.
    exit /b 1
)

echo [7/7] Validating environment...
set "srcDir=%scriptDir%\src"
if "%PYTHONPATH%"=="" (
    set "PYTHONPATH=%srcDir%"
) else (
    echo ;%PYTHONPATH%; | findstr /i /c:";%srcDir%;" >nul
    if %ERRORLEVEL% NEQ 0 set "PYTHONPATH=%srcDir%;%PYTHONPATH%"
)

for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.prefix)" 2^>nul`) do set "activePrefix=%%P"
if /i not "%activePrefix%"=="%venvDir%" (
    echo ERROR: Active Python prefix mismatch.
    echo   Expected: %venvDir%
    echo   Actual  : %activePrefix%
    exit /b 1
)

"%venvDir%\Scripts\chopper.exe" --help >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: chopper launcher validation failed.
    exit /b 1
)
python -m chopper --help >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: python -m chopper validation failed.
    exit /b 1
)

echo.
echo === Setup complete ===
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "pythonVersion=%%i"
echo   Python : %pythonVersion%
echo   Venv   : %venvDir%
if "%useProxy%"=="1" (
    echo   Proxy  : %proxy%
) else (
    echo   Proxy  : disabled
)
echo   Chopper launchers: OK
echo.
echo Run: chopper --help
echo Test: pytest
