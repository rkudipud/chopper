#!/usr/bin/env tcsh
# setup.csh — Bootstrap the chopper development environment (PRIMARY setup for Unix/Linux/macOS).
# Platform: Unix/Linux/macOS
# Shell: tcsh/csh (PRIMARY - bash is NOT available on this system)
# Auto-activate: source this script at startup (add to ~/.tcshrc or ~/.cshrc)
#   echo "source ~/.chopper_venv.csh" >> ~/.tcshrc
# Usage: source setup.csh

set script_dir = `pwd`

if ( ! -f "$script_dir/pyproject.toml" ) then
    echo "setup.csh expects to be sourced from the repository root."
    echo "Either cd into the repo first or source .venv/bin/activate.csh directly."
    return 1
endif

set venv_dir = "$script_dir/.venv"
# Project runtime floor is Python 3.11 (pyproject.toml `requires-python`).
# Dev venv is pinned to 3.13 so contributors share one toolchain. Prefer
# python3.13 explicitly; fall back to python3 only if 3.13 is not on PATH.
which python3.13 >& /dev/null
if ( $status == 0 ) then
    set python_cmd = "python3.13"
else
    set python_cmd = "python3"
    echo "WARN: python3.13 not found on PATH; falling back to `python3 --version`."
    echo "      Contributors are expected to install Python 3.13 for the dev venv."
endif
set proxy = "http://proxy-chain.intel.com:928"

echo "=== Chopper Dev Environment Setup ==="
echo "Platform: Unix/Linux/macOS (PRIMARY: tcsh - bash/zsh NOT available)"

if ( ! -d "$venv_dir" ) then
    echo "[1/4] Creating virtual environment..."
    $python_cmd -m venv "$venv_dir"
else
    echo "[1/4] Virtual environment exists, reusing."
endif

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate.csh"

echo "[3/4] Configuring pip and Git proxy..."
pip config set global.proxy "$proxy" --quiet >& /dev/null
pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null
# Configure Git proxy


echo "[4/4] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (PRIMARY: tcsh)"
echo "  Python   : `python3 --version`"
echo "  Venv     : $venv_dir"
echo "  Shell    : tcsh/csh (PRIMARY - bash/zsh NOT available)"
echo ""
echo "To auto-activate on terminal startup:"
echo "  echo 'source $script_dir/setup.csh' >> ~/.tcshrc"
echo ""
echo "For other platforms:"
echo "  Windows PowerShell : . setup.ps1"
echo "  Windows cmd.exe    : setup.bat"
echo "  bash/zsh (if available - fallback only) : source setup.sh"
echo ""
echo "Run: chopper --help"
echo "Test: pytest"

