# setup.ps1 — Bootstrap the chopper development environment (Windows with PowerShell).
# Platform: Windows (PowerShell 5.1+)
# Auto-activate: Source this script at startup (add to $PROFILE)
#   Add-Content -Path $PROFILE -Value "& '$PSScriptRoot\setup.ps1'"
# Usage: . .\setup.ps1 (or . setup.ps1)

param(
    [switch]$NoProxy = $false
)

$ErrorActionPreference = "Stop"

# Get the script directory
$scriptDir = Split-Path -Parent (Get-Item $PSCommandPath).FullName

if (-not (Test-Path "$scriptDir/pyproject.toml")) {
    Write-Host "setup.ps1 expects to be sourced from the repository root." -ForegroundColor Red
    Write-Host "Either cd into the repo first or activate .venv directly." -ForegroundColor Red
    return
}

$venvDir = Join-Path $scriptDir ".venv"
# Project runtime floor is Python 3.11 (pyproject.toml `requires-python`).
# Dev venv is pinned to 3.13 so contributors share one toolchain. Prefer the
# Windows `py` launcher targeted at 3.13; fall back to bare `python` only if
# the launcher cannot find a 3.13 install.
$pythonCmd = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.13 -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = "py -3.13"
    }
}
$defaultProxy = "http://proxy-chain.intel.com:912"
$proxy = $env:CHOPPER_PROXY
if ([string]::IsNullOrWhiteSpace($proxy)) { $proxy = $defaultProxy }

Write-Host "=== Chopper Dev Environment Setup ===" -ForegroundColor Cyan
Write-Host "Platform: Windows (PowerShell)" -ForegroundColor Cyan

# Apply proxy to the current shell environment now so that every network
# operation in this script (git pull, pip install, …) already sees the proxy
# without waiting for step [4/6].  Step [4/6] still writes pip config and
# git global config so the settings persist beyond this shell session.
if (-not $NoProxy) {
    $env:HTTP_PROXY  = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:http_proxy  = $proxy
    $env:https_proxy = $proxy
}

Write-Host "[1/6] Updating repository (git pull)..." -ForegroundColor Yellow
if (Get-Command git -ErrorAction SilentlyContinue) {
    try {
        git -C $scriptDir pull
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARN: git pull failed (network issue or local changes). Continuing with current code." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "WARN: git pull failed. Continuing with current code." -ForegroundColor Yellow
    }
} else {
    Write-Host "WARN: git not found on PATH; skipping update." -ForegroundColor Yellow
}

# Check if venv exists
if (Test-Path $venvDir) {
    # Detect a stale/relocated venv (e.g. copied from another repo): the venv's
    # python.exe should report sys.prefix == $venvDir. If it doesn't — or if it
    # refuses to launch at all — wipe and rebuild, otherwise pip-generated
    # console-script shims (chopper.exe) will carry the old path forever.
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $venvHealthy = $false
    if (Test-Path $venvPython) {
        try {
            $reportedPrefix = & $venvPython -c "import sys; print(sys.prefix)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $resolvedVenv = (Resolve-Path $venvDir).Path.TrimEnd('\')
                $resolvedPrefix = $reportedPrefix.Trim().TrimEnd('\')
                if ($resolvedPrefix -ieq $resolvedVenv) {
                    $venvHealthy = $true
                }
            }
        } catch {
            $venvHealthy = $false
        }
    }
    if (-not $venvHealthy) {
        Write-Host "[2/6] Existing .venv is stale or relocated — recreating..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
        Invoke-Expression "& $pythonCmd -m venv `"$venvDir`""
    } else {
        Write-Host "[2/6] Virtual environment exists and is healthy, reusing." -ForegroundColor Yellow
    }
} else {
    Write-Host "[2/6] Creating virtual environment (prefers Python 3.13)..." -ForegroundColor Yellow
    Invoke-Expression "& $pythonCmd -m venv `"$venvDir`""
}

# Activate venv
Write-Host "[3/6] Activating venv..." -ForegroundColor Yellow
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
} else {
    Write-Host "ERROR: Activation script not found at $activateScript" -ForegroundColor Red
    return
}

# Always invoke pip through the venv's python (`python -m pip`). pip's own
# console-script shim (pip.exe) can itself be stale when a venv is copied,
# and calling the shim fails before we ever get a chance to regenerate it.
# `python -m pip` bypasses the shim entirely.

# Configure proxy for this process plus pip/Git (optional, skip if -NoProxy).
if (-not $NoProxy) {
    Write-Host "[4/6] Updating pip and Git proxy..." -ForegroundColor Yellow
    Write-Host "  Proxy: $proxy" -ForegroundColor Gray
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:http_proxy = $proxy
    $env:https_proxy = $proxy
    try {
        python -m pip config set global.proxy "$proxy" --quiet 2>$null
        python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>$null
        if (Get-Command git -ErrorAction SilentlyContinue) {
            git config --global http.proxy "$proxy"
            git config --global https.proxy "$proxy"
        }
    } catch {
        Write-Host "  (Proxy config skipped)" -ForegroundColor Gray
    }
} else {
    Write-Host "[4/6] Skipping proxy configuration (-NoProxy)" -ForegroundColor Yellow
}

# Install dependencies only when the installed chopper version differs from
# the source version in this checkout (or if chopper is not installed yet).
Write-Host "[5/6] Syncing Chopper install with repo version..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
$repoVersion = python -c "import pathlib, tomllib; p=pathlib.Path('pyproject.toml'); print(tomllib.loads(p.read_text(encoding='utf-8'))['project']['version'])"
$installedVersion = python -c "import importlib.metadata as m; print(next((d.version for d in m.distributions() if d.metadata.get('Name', '').lower() == 'chopper'), '__MISSING__'))"
if ($installedVersion.Trim() -ne $repoVersion.Trim()) {
    if ($installedVersion.Trim() -eq "__MISSING__") {
        Write-Host "  chopper is not installed in this venv. Installing version $repoVersion..." -ForegroundColor Gray
    } else {
        Write-Host "  Installed chopper version $installedVersion differs from repo version $repoVersion. Reinstalling..." -ForegroundColor Gray
        python -m pip uninstall -y chopper --quiet
    }
    python -m pip install -e ".[dev]" --quiet
    python -m pip install -e . --force-reinstall --no-deps --quiet
} else {
    Write-Host "  Installed chopper version matches repo version ($repoVersion). Skipping reinstall." -ForegroundColor Gray
}

Write-Host "[6/6] Validating venv and Chopper launcher..." -ForegroundColor Yellow
$activePrefix = (python -c "import sys; print(sys.prefix)" 2>&1)
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not inspect active Python sys.prefix." -ForegroundColor Red
    return
}
$resolvedVenv = (Resolve-Path $venvDir).Path.TrimEnd('\')
$resolvedActivePrefix = $activePrefix.Trim().TrimEnd('\')
if ($resolvedActivePrefix -ine $resolvedVenv) {
    Write-Host "ERROR: Active Python is not using the expected venv." -ForegroundColor Red
    Write-Host "  Expected: $resolvedVenv" -ForegroundColor Red
    Write-Host "  Actual  : $resolvedActivePrefix" -ForegroundColor Red
    return
}

$chopperPkgVersion = (python -c "import chopper; print(chopper.__version__)" 2>&1)
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not import chopper from the active venv." -ForegroundColor Red
    Write-Host "$chopperPkgVersion" -ForegroundColor Red
    return
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "  Platform : Windows (PowerShell)" -ForegroundColor Green
Write-Host "  Python   : $(python --version)" -ForegroundColor Green
$chopperOk = $false
try {
    & chopper --help *> $null
    if ($LASTEXITCODE -eq 0) { $chopperOk = $true }
} catch {
    $chopperOk = $false
}
if ($chopperOk) {
    Write-Host "  Chopper  : $chopperPkgVersion (launcher OK)" -ForegroundColor Green
} else {
    Write-Host "ERROR: chopper launcher validation failed." -ForegroundColor Red
    Write-Host "  Chopper  : $chopperPkgVersion (launcher FAILED - run 'python -m pip install -e . --force-reinstall --no-deps')" -ForegroundColor Red
    return
}
Write-Host "  Venv     : $venvDir" -ForegroundColor Green
if (-not $NoProxy) {
    Write-Host "  Proxy    : $proxy" -ForegroundColor Green
} else {
    Write-Host "  Proxy    : disabled for this run" -ForegroundColor Green
}
Write-Host "  Shell    : PowerShell 5.1+"
Write-Host ""
Write-Host "To auto-activate on PowerShell startup:" -ForegroundColor Cyan
Write-Host "  Add-Content -Path `$PROFILE -Value `"& '$scriptDir\setup.ps1'`""
Write-Host ""
Write-Host "To view your PowerShell profile:"
Write-Host "  echo `$PROFILE"
Write-Host ""
Write-Host "For other platforms/shells:" -ForegroundColor Cyan
Write-Host "  Unix/Linux/macOS (bash/zsh) : . setup.sh"
Write-Host "  Unix/Linux/macOS (tcsh)     : source setup.csh"
Write-Host ""
Write-Host "Run: chopper --help" -ForegroundColor Gray
Write-Host "Test: pytest" -ForegroundColor Gray
Write-Host "Venv is active; handing control back to you." -ForegroundColor Green
