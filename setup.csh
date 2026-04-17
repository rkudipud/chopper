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
set python_cmd = "python3"
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
git config --global http.proxy "$proxy" >& /dev/null
git config --global https.proxy "$proxy" >& /dev/null
git config --global http.proxyStrictSSL false >& /dev/null
git config --global core.noProxy "intel.com,.intel.com,127.0.0.1,.devtools.intel.com" >& /dev/null
git config --global http.postBuffer 524288000 >& /dev/null
git config --global http.lowSpeedLimit 0 >& /dev/null
git config --global http.lowSpeedTime 999999 >& /dev/null

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

