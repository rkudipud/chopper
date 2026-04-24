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
# Project runtime floor is Python 3.11 (pyproject.toml `requires-python`).
# Dev venv is pinned to 3.13 so contributors share one toolchain. Prefer
# python3.13 explicitly; fall back to python3 only if 3.13 is not on PATH.
if command -v python3.13 >/dev/null 2>&1; then
    python_cmd="python3.13"
else
    python_cmd="python3"
    echo "WARN: python3.13 not found on PATH; falling back to $(python3 --version 2>&1)."
    echo "      Contributors are expected to install Python 3.13 for the dev venv."
fi
proxy="http://proxy-chain.intel.com:928"

echo "=== Chopper Dev Environment Setup ==="
echo "Platform: Unix/Linux/macOS (bash/zsh - FALLBACK ONLY)"
echo "Note: tcsh is the PRIMARY shell for this system. Use setup.csh instead if available."

if [[ ! -d "$venv_dir" ]]; then
    echo "[1/4] Creating virtual environment..."
    $python_cmd -m venv "$venv_dir"
else
    # Detect a stale/relocated venv (e.g. copied from another repo): the
    # venv's python should report sys.prefix == $venv_dir. If it doesn't —
    # or won't launch at all — wipe and rebuild, otherwise pip-generated
    # console scripts (chopper) will carry the old shebang forever.
    venv_healthy=0
    if [[ -x "$venv_dir/bin/python" ]]; then
        reported=$("$venv_dir/bin/python" -c "import sys; print(sys.prefix)" 2>/dev/null || true)
        if [[ "$reported" == "$venv_dir" ]]; then
            venv_healthy=1
        fi
    fi
    if [[ $venv_healthy -eq 1 ]]; then
        echo "[1/4] Virtual environment exists and is healthy, reusing."
    else
        echo "[1/4] Existing .venv is stale or relocated — recreating..."
        rm -rf "$venv_dir"
        $python_cmd -m venv "$venv_dir"
    fi
fi

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate"

echo "[3/4] Configuring pip and Git proxy..."
python -m pip config set global.proxy "$proxy" --quiet 2>/dev/null || true
python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet 2>/dev/null || true
# Configure Git proxy


# Install dependencies. `--force-reinstall --no-deps` on the last line
# regenerates the chopper console-script shim against THIS venv's python,
# which fixes the common "copied venv" failure mode. We invoke pip as
# `python -m pip` throughout: pip's own shim can itself be stale when a
# venv is copied, and `python -m pip` bypasses that shim entirely.
echo "[4/4] Installing dependencies..."
python -m pip install --upgrade pip --quiet
python -m pip install -e ".[dev]" --quiet
python -m pip install -e . --force-reinstall --no-deps --quiet

chopper_version=$(python -c "import chopper; print(chopper.__version__)" 2>&1)
if chopper --help >/dev/null 2>&1; then
    chopper_line="$chopper_version (launcher OK)"
else
    chopper_line="$chopper_version (launcher FAILED — run 'python -m pip install -e . --force-reinstall --no-deps')"
fi

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (bash/zsh - FALLBACK)"
echo "  Python   : $(python3 --version)"
echo "  Chopper  : $chopper_line"
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
