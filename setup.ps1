# setup.ps1 - Bootstrap the chopper dev environment (Windows PowerShell).
# Usage: . .\setup.ps1

param(
    [switch]$NoProxy = $false
)

$ErrorActionPreference = "Stop"

# Must be dot-sourced, not executed: venv activation only persists in the
# parent shell when this script is dot-sourced. When executed (.\setup.ps1),
# activation happens in a child scope and disappears the moment the script
# returns.
if ($MyInvocation.InvocationName -ne '.') {
    Write-Host "ERROR: setup.ps1 must be DOT-SOURCED, not executed." -ForegroundColor Red
    Write-Host "  Wrong : .\setup.ps1" -ForegroundColor Red
    Write-Host "  Right : . .\setup.ps1     (note the leading dot + space)" -ForegroundColor Red
    exit 1
}

$scriptDir = Split-Path -Parent (Get-Item $PSCommandPath).FullName
if (-not (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    Write-Host "ERROR: Run '. .\setup.ps1' from the repository root." -ForegroundColor Red
    return
}

$venvDir = Join-Path $scriptDir ".venv"
$localPy313 = Join-Path $scriptDir ".local-python\3.13\python.exe"
$defaultProxy = "http://proxy-chain.intel.com:912"
$proxy = if ([string]::IsNullOrWhiteSpace($env:CHOPPER_PROXY)) { $defaultProxy } else { $env:CHOPPER_PROXY }
$useProxy = -not $NoProxy -and ($env:CHOPPER_NO_PROXY -ne "1")

Write-Host "=== Chopper Setup (PowerShell) ===" -ForegroundColor Cyan

Write-Host "[1/7] Resolving Python 3.13+ interpreter..." -ForegroundColor Yellow
$pythonCommand = $null

# Strategy step 1: probe PATH for any python whose version is >= 3.13.
foreach ($candidate in @("python3.13", "python", "python3")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = $candidate
            Write-Host "  Using PATH Python: $candidate (>= 3.13)" -ForegroundColor Gray
            break
        }
    }
}
if (-not $pythonCommand -and (Get-Command py -ErrorAction SilentlyContinue)) {
    & py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonCommand = "py -3.13"
        Write-Host "  Using PATH Python: py -3.13 (>= 3.13)" -ForegroundColor Gray
    }
}

# Strategy step 2 (Windows has no EC mount): local install under .local-python.
if (-not $pythonCommand -and (Test-Path $localPy313)) {
    $pythonCommand = $localPy313
    Write-Host "  Using local Python: $localPy313" -ForegroundColor Gray
}

# Strategy step 3: best-effort winget install, then re-resolve via py -3.13.
if (-not $pythonCommand -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "  Python 3.13 not found; attempting winget install..." -ForegroundColor Gray
    winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = "py -3.13"
            Write-Host "  Using winget-installed Python: py -3.13" -ForegroundColor Gray
        }
    }
}

if (-not $pythonCommand) {
    Write-Host "ERROR: Python 3.13+ could not be resolved." -ForegroundColor Red
    Write-Host "Strategy: PATH (>= 3.13) -> $localPy313 -> winget install Python.Python.3.13." -ForegroundColor Red
    Write-Host "Install Python 3.13 manually, place it under $localPy313, or run 'winget install Python.Python.3.13'." -ForegroundColor Red
    return
}

if ($useProxy) {
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:http_proxy = $proxy
    $env:https_proxy = $proxy
}

Write-Host "[2/7] Running git pull..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git not found on PATH." -ForegroundColor Red
    return
}
git -C $scriptDir pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: git pull failed. Resolve git/network issue and rerun setup." -ForegroundColor Red
    return
}

Write-Host "[3/7] Ensuring virtual environment..." -ForegroundColor Yellow
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$fresh = ($env:CHOPPER_FRESH -eq "1")
if ($fresh -and (Test-Path $venvDir)) {
    Write-Host "  CHOPPER_FRESH=1 set; removing existing venv at $venvDir" -ForegroundColor Gray
    Remove-Item -Recurse -Force $venvDir
}
if (Test-Path $venvPython) {
    & $venvPython -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Reusing existing venv at $venvDir" -ForegroundColor Gray
    } else {
        Write-Host "  Existing venv has wrong Python; recreating." -ForegroundColor Gray
        Remove-Item -Recurse -Force $venvDir
    }
}
if (-not (Test-Path $venvPython)) {
    Invoke-Expression "& $pythonCommand -m venv `"$venvDir`""
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create venv with Python 3.13." -ForegroundColor Red
        return
    }
}

Write-Host "[4/7] Activating venv..." -ForegroundColor Yellow
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Host "ERROR: Activation script missing: $activateScript" -ForegroundColor Red
    return
}
& $activateScript

Write-Host "[5/7] Configuring proxy for pip and npm..." -ForegroundColor Yellow
if ($useProxy) {
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:http_proxy = $proxy
    $env:https_proxy = $proxy
    python -m pip config set global.proxy "$proxy" --quiet 2>$null
    python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>$null
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        npm config set proxy "$proxy" --location=user *> $null
        npm config set https-proxy "$proxy" --location=user *> $null
    }
} else {
    Write-Host "  Proxy disabled (NoProxy switch or CHOPPER_NO_PROXY=1)." -ForegroundColor Gray
}

Write-Host "[6/7] Ensuring chopper package is installed..." -ForegroundColor Yellow
python -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip upgrade failed." -ForegroundColor Red
    return
}
python -m pip install --quiet -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install -e .[dev] failed." -ForegroundColor Red
    return
}

Write-Host "[7/7] Validating environment..." -ForegroundColor Yellow
$srcDir = Join-Path $scriptDir "src"
if ([string]::IsNullOrEmpty($env:PYTHONPATH)) {
    $env:PYTHONPATH = $srcDir
} elseif (-not ($env:PYTHONPATH.Split([IO.Path]::PathSeparator) -contains $srcDir)) {
    $env:PYTHONPATH = "$srcDir$([IO.Path]::PathSeparator)$($env:PYTHONPATH)"
}

$activePrefix = (python -c "import sys; print(sys.prefix)").TrimEnd('\\')
$expectedPrefix = (Resolve-Path $venvDir).Path.TrimEnd('\\')
if ($activePrefix -ine $expectedPrefix) {
    Write-Host "ERROR: Active Python prefix mismatch." -ForegroundColor Red
    Write-Host "  Expected: $expectedPrefix" -ForegroundColor Red
    Write-Host "  Actual  : $activePrefix" -ForegroundColor Red
    return
}

$chopperExe = Join-Path $venvDir "Scripts\chopper.exe"
& $chopperExe --help *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: chopper launcher validation failed." -ForegroundColor Red
    return
}
python -m chopper --help *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: python -m chopper validation failed." -ForegroundColor Red
    return
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "  Python : $(python --version)" -ForegroundColor Green
Write-Host "  Venv   : $venvDir" -ForegroundColor Green
if ($useProxy) {
    Write-Host "  Proxy  : $proxy" -ForegroundColor Green
} else {
    Write-Host "  Proxy  : disabled" -ForegroundColor Green
}
Write-Host "  Chopper launchers: OK" -ForegroundColor Green
Write-Host ""
Write-Host "Run: chopper --help" -ForegroundColor Gray
Write-Host "Test: pytest" -ForegroundColor Gray
