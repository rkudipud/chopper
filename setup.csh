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
set default_proxy = "http://proxy-chain.intel.com:912"
if ( $?CHOPPER_PROXY ) then
    set proxy = "$CHOPPER_PROXY"
else
    set proxy = "$default_proxy"
endif
set use_proxy = 1
if ( $?CHOPPER_NO_PROXY ) then
    if ( "$CHOPPER_NO_PROXY" == "1" ) set use_proxy = 0
endif

echo "=== Chopper Dev Environment Setup ==="
echo "Platform: Unix/Linux/macOS (PRIMARY: tcsh - bash/zsh NOT available)"

# Apply proxy to the current shell environment now so that every network
# operation in this script (git pull, pip install, ...) already sees the proxy
# without waiting for step [4/6].  Step [4/6] still writes pip config and
# git global config so the settings persist beyond this shell session.
if ( $use_proxy == 1 ) then
    setenv HTTP_PROXY  "$proxy"
    setenv HTTPS_PROXY "$proxy"
    setenv http_proxy  "$proxy"
    setenv https_proxy "$proxy"
endif

echo "[1/6] Updating repository (git pull)..."
which git >& /dev/null
if ( $status == 0 ) then
    git -C "$script_dir" pull
    if ( $status != 0 ) then
        echo "WARN: git pull failed (network issue or local changes). Continuing with current code."
    endif
else
    echo "WARN: git not found on PATH; skipping update."
endif

if ( ! -d "$venv_dir" ) then
    echo "[2/6] Creating virtual environment..."
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
        echo "[2/6] Virtual environment exists and is healthy, reusing."
    else
        echo "[2/6] Existing .venv is stale or relocated — recreating..."
        rm -rf "$venv_dir"
        $python_cmd -m venv "$venv_dir"
    endif
endif

echo "[3/6] Activating venv..."
source "$venv_dir/bin/activate.csh"

if ( $use_proxy == 1 ) then
    echo "[4/6] Updating pip and Git proxy..."
    echo "  Proxy: $proxy"
    setenv HTTP_PROXY "$proxy"
    setenv HTTPS_PROXY "$proxy"
    setenv http_proxy "$proxy"
    setenv https_proxy "$proxy"
    python -m pip config set global.proxy "$proxy" --quiet >& /dev/null
    python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null
    which git >& /dev/null
    if ( $status == 0 ) then
        git config --global http.proxy "$proxy"
        git config --global https.proxy "$proxy"
    endif
else
    echo "[4/6] Skipping proxy configuration (CHOPPER_NO_PROXY=1)."
endif


# Install dependencies only when the installed chopper version differs from
# the source version in this checkout (or if chopper is not installed yet).
echo "[5/6] Syncing Chopper install with repo version..."
python -m pip install --upgrade pip --quiet
set repo_version = `python -c "import pathlib, tomllib; p=pathlib.Path('pyproject.toml'); print(tomllib.loads(p.read_text(encoding='utf-8'))['project']['version'])"`
set installed_version = `python -c "import importlib.metadata as m; print(next((d.version for d in m.distributions() if d.metadata.get('Name', '').lower() == 'chopper'), '__MISSING__'))"`
if ( "$installed_version" != "$repo_version" ) then
    if ( "$installed_version" == "__MISSING__" ) then
        echo "  chopper is not installed in this venv. Installing version $repo_version..."
    else
        echo "  Installed chopper version $installed_version differs from repo version $repo_version. Reinstalling..."
        python -m pip uninstall -y chopper --quiet
    endif
    python -m pip install -e ".[dev]" --quiet
    python -m pip install -e . --force-reinstall --no-deps --quiet
else
    echo "  Installed chopper version matches repo version ($repo_version). Skipping reinstall."
endif

echo "[6/6] Validating venv and Chopper launcher..."
set active_prefix = `python -c "import sys; print(sys.prefix)"`
if ( "$active_prefix" != "$venv_dir" ) then
    echo "ERROR: Active Python is not using the expected venv."
    echo "  Expected: $venv_dir"
    echo "  Actual  : $active_prefix"
    return 1
endif

set chopper_version = `python -c "import chopper; print(chopper.__version__)"`
chopper --help >& /dev/null
if ( $status == 0 ) then
    set chopper_line = "$chopper_version (launcher OK)"
else
    echo "ERROR: chopper launcher validation failed."
    echo "  Chopper  : $chopper_version (launcher FAILED - run 'python -m pip install -e . --force-reinstall --no-deps')"
    return 1
endif

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (PRIMARY: tcsh)"
echo "  Python   : `python --version`"
echo "  Chopper  : $chopper_line"
echo "  Venv     : $venv_dir"
if ( $use_proxy == 1 ) then
    echo "  Proxy    : $proxy"
else
    echo "  Proxy    : disabled for this run"
endif
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
echo "Venv is active; handing control back to you."

