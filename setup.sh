#!/bin/bash
# setup.sh - Bootstrap the chopper dev environment (Unix fallback shell).
# Usage: source setup.sh

set -euo pipefail

# Must be sourced, not executed: venv activation only persists in the parent
# shell when this script is sourced.
(return 0 2>/dev/null) || {
    echo "ERROR: setup.sh must be SOURCED, not executed."
    echo "  Wrong : ./setup.sh    or    bash setup.sh"
    echo "  Right : source setup.sh    (or  . ./setup.sh)"
    exit 1
}

die() {
    echo "ERROR: $1"
    return 1 2>/dev/null || exit 1
}

if [[ -n "${BASH_SOURCE:-}" ]]; then
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    script_dir="$(cd "$(dirname "$0")" && pwd)"
fi

[[ -f "$script_dir/pyproject.toml" ]] || die "Run 'source setup.sh' from the repository root."

venv_dir="$script_dir/.venv"
# Python resolution strategy (in order):
#   1. PATH python (python3.13 / python3 / python) if version >= 3.13
#   2. EC system Python at /usr/intel/bin/python3.13.2
#   3. Local install of Python 3.13.4 under $script_dir/.local-python/3.13/
ec_py313="/usr/intel/bin/python3.13.2"
local_py313_root="$script_dir/.local-python/3.13"
local_py313="$local_py313_root/bin/python3.13"
default_proxy="http://proxy-chain.intel.com:912"
proxy="${CHOPPER_PROXY:-$default_proxy}"
use_proxy=1
[[ "${CHOPPER_NO_PROXY:-0}" == "1" ]] && use_proxy=0

echo "=== Chopper Setup (bash/zsh fallback) ==="

echo "[1/7] Resolving Python 3.13+ interpreter..."
python_cmd=""
# Strategy step 1: probe PATH for a Python whose version is >= 3.13.
for candidate in python3.13 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
       && "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >/dev/null 2>&1; then
        python_cmd="$candidate"
        echo "  Using PATH Python: $candidate (>= 3.13)"
        break
    fi
done
# Strategy step 2: EC system Python.
if [[ -z "$python_cmd" && -x "$ec_py313" ]]; then
    python_cmd="$ec_py313"
    echo "  Using EC Python: $ec_py313"
fi
# Strategy step 3: local install of Python 3.13.4 under $script_dir/.local-python.
if [[ -z "$python_cmd" ]]; then
    if [[ ! -x "$local_py313" ]] && command -v uv >/dev/null 2>&1; then
        echo "  Installing Python 3.13.4 via uv into $local_py313_root..."
        uv python install 3.13.4 --install-dir "$local_py313_root" >/dev/null 2>&1 || true
    fi
    if [[ -x "$local_py313" ]]; then
        python_cmd="$local_py313"
        echo "  Using local Python: $local_py313"
    fi
fi
[[ -n "$python_cmd" ]] || die "Python 3.13+ could not be resolved. Strategy: PATH (>= 3.13) -> $ec_py313 -> local install at $local_py313. Install 'uv' (https://docs.astral.sh/uv/) or place a Python 3.13.4 build at $local_py313."

if [[ $use_proxy -eq 1 ]]; then
    export HTTP_PROXY="$proxy"
    export HTTPS_PROXY="$proxy"
    export http_proxy="$proxy"
    export https_proxy="$proxy"
fi

echo "[2/7] Running git pull..."
command -v git >/dev/null 2>&1 || die "git not found on PATH."
git -C "$script_dir" pull || die "git pull failed. Resolve git/network issue and rerun setup."

echo "[3/7] Ensuring virtual environment..."
venv_python="$venv_dir/bin/python"
fresh=0
[[ "${CHOPPER_FRESH:-0}" == "1" ]] && fresh=1
if [[ $fresh -eq 1 && -d "$venv_dir" ]]; then
    echo "  CHOPPER_FRESH=1 set; removing existing venv at $venv_dir"
    rm -rf "$venv_dir"
fi
if [[ -x "$venv_python" ]]; then
    if "$venv_python" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >/dev/null 2>&1; then
        echo "  Reusing existing venv at $venv_dir"
    else
        echo "  Existing venv has wrong Python; recreating."
        rm -rf "$venv_dir"
    fi
fi
if [[ ! -x "$venv_python" ]]; then
    "$python_cmd" -m venv "$venv_dir"
fi

echo "[4/7] Activating venv..."
source "$venv_dir/bin/activate"

echo "[5/7] Configuring proxy for pip and npm..."
if [[ $use_proxy -eq 1 ]]; then
    export HTTP_PROXY="$proxy"
    export HTTPS_PROXY="$proxy"
    export http_proxy="$proxy"
    export https_proxy="$proxy"
    python -m pip config set global.proxy "$proxy" --quiet >/dev/null 2>&1 || true
    python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >/dev/null 2>&1 || true
    if command -v npm >/dev/null 2>&1; then
        npm config set proxy "$proxy" --location=user >/dev/null 2>&1 || true
        npm config set https-proxy "$proxy" --location=user >/dev/null 2>&1 || true
    fi
else
    echo "  Proxy disabled (CHOPPER_NO_PROXY=1)."
fi

echo "[6/7] Ensuring chopper package is installed..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"

echo "[7/7] Validating environment..."
case ":${PYTHONPATH:-}:" in
    *":$script_dir/src:"*) ;;
    *) export PYTHONPATH="$script_dir/src${PYTHONPATH:+:$PYTHONPATH}" ;;
esac

active_prefix="$(python -c "import sys; print(sys.prefix)")"
expected_prefix="$(cd "$venv_dir" && pwd -P)"
actual_prefix="$(cd "$active_prefix" 2>/dev/null && pwd -P || printf '%s' "$active_prefix")"
[[ "$actual_prefix" == "$expected_prefix" ]] || die "Active Python prefix mismatch. Expected $expected_prefix got $actual_prefix"

"$venv_dir/bin/chopper" --help >/dev/null 2>&1 || die "chopper launcher validation failed."
python -m chopper --help >/dev/null 2>&1 || die "python -m chopper validation failed."

echo
echo "=== Setup complete ==="
echo "  Python : $(python --version)"
echo "  Venv   : $venv_dir"
if [[ $use_proxy -eq 1 ]]; then
    echo "  Proxy  : $proxy"
else
    echo "  Proxy  : disabled"
fi
echo "  Chopper launchers: OK"
echo
echo "Run: chopper --help"
echo "Test: pytest"
