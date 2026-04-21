# setup.ps1 -- Bootstrap Python venv for Chopper JSON Kit on Windows PowerShell.
# Usage: . .\setup.ps1

param(
    [switch]$NoProxy = $false
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent (Get-Item $PSCommandPath).FullName

if (-not (Test-Path (Join-Path $scriptDir "README.md")) -or -not (Test-Path (Join-Path $scriptDir "schemas"))) {
    Write-Host "setup.ps1 expects to be sourced from the chopper_json_kit repository root." -ForegroundColor Red
    Write-Host "Either cd into the repo first or activate .venv directly." -ForegroundColor Red
    return
}

$venvDir = Join-Path $scriptDir ".venv"
$proxy = "http://proxy-chain.intel.com:928"

# Prefer python launcher, then python in PATH.
$usePyLauncher = $false
if (Get-Command py -ErrorAction SilentlyContinue) {
    $usePyLauncher = $true
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $usePyLauncher = $false
} else {
    Write-Host "No Python interpreter found in PATH (expected py or python)." -ForegroundColor Red
    return
}

Write-Host "=== Chopper JSON Kit Environment Setup ===" -ForegroundColor Cyan
Write-Host "Platform: Windows (PowerShell)" -ForegroundColor Cyan

if (-not (Test-Path $venvDir)) {
    Write-Host "[1/4] Creating virtual environment..." -ForegroundColor Yellow
    if ($usePyLauncher) {
        & py -3 -m venv $venvDir
    } else {
        & python -m venv $venvDir
    }
} else {
    Write-Host "[1/4] Virtual environment exists, reusing." -ForegroundColor Yellow
}

Write-Host "[2/4] Activating venv..." -ForegroundColor Yellow
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
} else {
    Write-Host "Activation script not found at $activateScript" -ForegroundColor Red
    return
}

if (-not $NoProxy) {
    Write-Host "[3/4] Configuring pip and Git proxy..." -ForegroundColor Yellow
    try {
        python -m pip config set global.proxy "$proxy" --quiet 2>$null
        python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>$null
        if (Get-Command git -ErrorAction SilentlyContinue) {
            git config --global http.proxy "$proxy" 2>$null
            git config --global https.proxy "$proxy" 2>$null
        }
    } catch {
        Write-Host "  (Proxy config skipped)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "[3/4] Skipping pip proxy configuration (-NoProxy)" -ForegroundColor Yellow
}

Write-Host "[4/4] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
# Repository docs require jsonschema for local schema validation examples.
python -m pip install jsonschema --quiet

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "  Platform : Windows (PowerShell)" -ForegroundColor Green
Write-Host "  Python   : $(python --version)" -ForegroundColor Green
Write-Host "  Venv     : $venvDir" -ForegroundColor Green
Write-Host "  Shell    : PowerShell" -ForegroundColor Green
Write-Host ""
Write-Host "To auto-activate on PowerShell startup:" -ForegroundColor Cyan
Write-Host "  Add-Content -Path `$PROFILE -Value `"& '$scriptDir\setup.ps1'`""
Write-Host ""
Write-Host "Next steps in this repo:" -ForegroundColor Cyan
Write-Host "  python -m json.tool examples/07_base_full/jsons/base.json > $null"
Write-Host '  python -c "import jsonschema; print(jsonschema.__version__)"'
