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
    # Detect a stale/relocated venv (e.g. copied from another repo): the
    # venv's python should report sys.prefix == $venv_dir. If it doesn't —
    # or won't launch at all — wipe and rebuild, otherwise pip-generated
    # console scripts (chopper) will carry the old shebang forever.
    set venv_healthy = 0
    if ( -x "$venv_dir/bin/python" ) then
        set reported = `"$venv_dir/bin/python" -c "import sys; print(sys.prefix)"`
        if ( "$reported" == "$venv_dir" ) then
            set venv_healthy = 1
        endif
    endif
    if ( $venv_healthy == 1 ) then
        echo "[1/4] Virtual environment exists and is healthy, reusing."
    else
        echo "[1/4] Existing .venv is stale or relocated — recreating..."
        rm -rf "$venv_dir"
        $python_cmd -m venv "$venv_dir"
    endif
endif

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate.csh"

echo "[3/4] Configuring pip and Git proxy..."
python -m pip config set global.proxy "$proxy" --quiet >& /dev/null
python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null
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

set chopper_version = `python -c "import chopper; print(chopper.__version__)"`
chopper --help >& /dev/null
if ( $status == 0 ) then
    set chopper_line = "$chopper_version (launcher OK)"
else
    set chopper_line = "$chopper_version (launcher FAILED - run 'python -m pip install -e . --force-reinstall --no-deps')"
endif

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (PRIMARY: tcsh)"
echo "  Python   : `python3 --version`"
echo "  Chopper  : $chopper_line"
echo "  Venv     : $venv_dir"
echo "  Shell    : tcsh/csh (PRIMARY - bash/zsh NOT available)"echo ""
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

