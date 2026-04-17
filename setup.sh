#!/bin/bash
# setup.sh — Bootstrap the chopper development environment (Fallback for Unix/Linux/macOS with bash/zsh).
# Platform: Unix/Linux/macOS (bash/zsh/sh)
# Note: This is a FALLBACK script. The PRIMARY setup script for this system is setup.csh (tcsh).
# Auto-activate: source this script at startup (add to ~/.bashrc, ~/.bash_profile, or ~/.zshrc)
#   echo "source ~/.chopper_venv.sh" >> ~/.bashrc
# Usage: source setup.sh

set -e

# Get the script directory (works for bash/zsh/sh)
if [[ "$BASH_SOURCE" ]]; then
    script_dir="$(cd "$(dirname "$BASH_SOURCE")" && pwd)"
else
    # Fallback for sh/zsh
    script_dir="$(cd "$(dirname "$0")" && pwd)"
fi

if [[ ! -f "$script_dir/pyproject.toml" ]]; then
    echo "setup.sh expects to be sourced from the repository root."
    echo "Either cd into the repo first or source .venv/bin/activate directly."
    return 1 2>/dev/null || exit 1
fi

venv_dir="$script_dir/.venv"
python_cmd="python3"
proxy="http://proxy-chain.intel.com:928"

echo "=== Chopper Dev Environment Setup ==="
echo "Platform: Unix/Linux/macOS (bash/zsh - FALLBACK ONLY)"
echo "Note: tcsh is the PRIMARY shell for this system. Use setup.csh instead if available."

if [[ ! -d "$venv_dir" ]]; then
    echo "[1/4] Creating virtual environment..."
    $python_cmd -m venv "$venv_dir"
else
    echo "[1/4] Virtual environment exists, reusing."
fi

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate"

echo "[3/4] Configuring pip and Git proxy..."
pip config set global.proxy "$proxy" --quiet 2>/dev/null || true
pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>/dev/null || true
# Configure Git proxy
git config --global http.proxy "$proxy" 2>/dev/null || true
git config --global https.proxy "$proxy" 2>/dev/null || true
git config --global http.proxyStrictSSL false 2>/dev/null || true
git config --global core.noProxy "intel.com,.intel.com,127.0.0.1,.devtools.intel.com" 2>/dev/null || true
git config --global http.postBuffer 524288000 2>/dev/null || true
git config --global http.lowSpeedLimit 0 2>/dev/null || true
git config --global http.lowSpeedTime 999999 2>/dev/null || true

echo "[4/4] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (bash/zsh - FALLBACK)"
echo "  Python   : $(python3 --version)"
echo "  Venv     : $venv_dir"
echo "  Shell    : bash/zsh/sh (tcsh is PRIMARY on this system)"
echo ""
echo "Note: tcsh is the PRIMARY shell for this system."
echo "To auto-activate on terminal startup (if using bash/zsh):"
echo "  echo 'source $script_dir/setup.sh' >> ~/.bashrc"
echo "  or"
echo "  echo 'source $script_dir/setup.sh' >> ~/.zshrc"
echo ""
echo "For PRIMARY setup (tcsh) or other platforms:"
echo "  tcsh (PRIMARY)       : source setup.csh"
echo "  Windows PowerShell   : . setup.ps1"
echo "  Windows cmd.exe      : setup.bat"
echo ""
echo "Run: chopper --help"
echo "Test: pytest"
