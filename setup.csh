#!/usr/bin/env tcsh
# setup.csh — Bootstrap the chopper development environment for tcsh users.
# Usage: source setup.csh

set script_dir = "$cwd"

if ( ! -f "$script_dir/pyproject.toml" ) then
    echo "setup.csh expects to be sourced from the repository root."
    echo "Either cd into the repo first or source .venv/bin/activate.csh directly."
    return 1
endif

set venv_dir = "$script_dir/.venv"
set python_cmd = "python3"
set proxy = "http://proxy-dmz.intel.com:912"

echo "=== Chopper Dev Environment Setup (tcsh) ==="

if ( ! -d "$venv_dir" ) then
    echo "[1/4] Creating virtual environment..."
    $python_cmd -m venv "$venv_dir"
else
    echo "[1/4] Virtual environment exists, reusing."
endif

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate.csh"

echo "[3/4] Configuring pip proxy..."
pip config set global.proxy "$proxy" --quiet >& /dev/null
pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null

echo "[4/4] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

echo ""
echo "=== Setup complete ==="
echo "  Python : `python3 --version`"
echo "  Venv   : $venv_dir"
echo "  tcsh   : source setup.csh"
echo "  Bash   : source setup.sh"
echo "  Run    : chopper --help"
echo "  Test   : pytest"

