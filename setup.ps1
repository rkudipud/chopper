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
$proxy = "http://proxy-chain.intel.com:912"

Write-Host "=== Chopper Dev Environment Setup ===" -ForegroundColor Cyan
Write-Host "Platform: Windows (PowerShell)" -ForegroundColor Cyan

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
        Write-Host "[1/4] Existing .venv is stale or relocated — recreating..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
        Invoke-Expression "& $pythonCmd -m venv `"$venvDir`""
    } else {
        Write-Host "[1/4] Virtual environment exists and is healthy, reusing." -ForegroundColor Yellow
    }
} else {
    Write-Host "[1/4] Creating virtual environment (prefers Python 3.13)..." -ForegroundColor Yellow
    Invoke-Expression "& $pythonCmd -m venv `"$venvDir`""
}

# Activate venv
Write-Host "[2/4] Activating venv..." -ForegroundColor Yellow
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

# Configure pip proxy (optional, skip if -NoProxy)
if (-not $NoProxy) {
Write-Host "[3/4] Configuring pip and Git proxy..." -ForegroundColor Yellow
    try {
        python -m pip config set global.proxy "$proxy" --quiet 2>$null
        python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>$null
        # Configure Git proxy
        git config --global http.proxy "$proxy"
        git config --global https.proxy "$proxy"
    } catch {
        Write-Host "  (Proxy config skipped)" -ForegroundColor Gray
    }
} else {
    Write-Host "[3/4] Skipping pip proxy configuration (-NoProxy)" -ForegroundColor Yellow
}

# Install dependencies. `--force-reinstall --no-deps` on the last line
# regenerates the chopper.exe console-script shim against THIS venv's
# python, which fixes the common "copied venv" failure mode where the
# shim still points at the Python that originally created it.
Write-Host "[4/4] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
python -m pip install -e ".[dev]" --quiet
python -m pip install -e . --force-reinstall --no-deps --quiet

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "  Platform : Windows (PowerShell)" -ForegroundColor Green
Write-Host "  Python   : $(python --version)" -ForegroundColor Green
$chopperPkgVersion = (python -c "import chopper; print(chopper.__version__)" 2>&1)
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
    Write-Host "  Chopper  : $chopperPkgVersion (launcher FAILED — run 'python -m pip install -e . --force-reinstall --no-deps')" -ForegroundColor Red
}
Write-Host "  Venv     : $venvDir" -ForegroundColor Green
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
