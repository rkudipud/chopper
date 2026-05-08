#!/usr/bin/env tcsh
# setup.csh - Bootstrap the chopper dev environment (PRIMARY Unix shell).
# Usage: source setup.csh

# Must be sourced, not executed: venv activation only persists in the parent
# shell when this script is sourced. When executed (./setup.csh), activation
# happens in a dying subshell and disappears the moment the script returns.
if ( ! $?prompt ) then
    echo "ERROR: setup.csh must be SOURCED from an interactive tcsh, not executed."
    echo "  Wrong : ./setup.csh    or    setup.csh"
    echo "  Right : source setup.csh"
    exit 1
endif

set script_dir = `pwd`
if ( ! -f "$script_dir/pyproject.toml" ) then
    echo "ERROR: Run 'source setup.csh' from the repository root."
    return 1
endif

set venv_dir = "$script_dir/.venv"
# Python resolution strategy (in order):
#   1. PATH python (python3.13 / python3 / python) if version >= 3.13
#   2. EC system Python at /usr/intel/bin/python3.13.2
#   3. Local install of Python 3.13.4 under $script_dir/.local-python/3.13/
set ec_py313 = "/usr/intel/bin/python3.13.2"
set local_py313_root = "$script_dir/.local-python/3.13"
set local_py313 = "$local_py313_root/bin/python3.13"
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

echo "=== Chopper Setup (tcsh primary) ==="

echo "[1/7] Resolving Python 3.13+ interpreter..."
unset python_cmd
# Strategy step 1: probe PATH for a Python whose version is >= 3.13.
foreach candidate ( python3.13 python3 python )
    which $candidate >& /dev/null
    if ( $status == 0 ) then
        $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >& /dev/null
        if ( $status == 0 ) then
            set python_cmd = "$candidate"
            echo "  Using PATH Python: $candidate (>= 3.13)"
            break
        endif
    endif
end
# Strategy step 2: EC system Python.
if ( ! $?python_cmd && -x "$ec_py313" ) then
    set python_cmd = "$ec_py313"
    echo "  Using EC Python: $ec_py313"
endif
# Strategy step 3: local install of Python 3.13.4 under $script_dir/.local-python.
if ( ! $?python_cmd ) then
    if ( ! -x "$local_py313" ) then
        which uv >& /dev/null
        if ( $status == 0 ) then
            echo "  Installing Python 3.13.4 via uv into $local_py313_root..."
            uv python install 3.13.4 --install-dir "$local_py313_root" >& /dev/null
        endif
    endif
    if ( -x "$local_py313" ) then
        set python_cmd = "$local_py313"
        echo "  Using local Python: $local_py313"
    endif
endif

if ( ! $?python_cmd ) then
    echo "ERROR: Python 3.13+ could not be resolved."
    echo "Strategy: PATH (>= 3.13) -> $ec_py313 -> local install at $local_py313."
    echo "Install 'uv' (https://docs.astral.sh/uv/) or place a Python 3.13.4 build at $local_py313."
    return 1
endif

if ( $use_proxy == 1 ) then
    setenv HTTP_PROXY "$proxy"
    setenv HTTPS_PROXY "$proxy"
    setenv http_proxy "$proxy"
    setenv https_proxy "$proxy"
endif

echo "[2/7] Running git pull..."
which git >& /dev/null
if ( $status == 0 ) then
    git -C "$script_dir" pull
    if ( $status != 0 ) then
        echo "ERROR: git pull failed. Resolve git/network issue and rerun setup."
        return 1
    endif
else
    echo "ERROR: git not found on PATH."
    return 1
endif

echo "[3/7] Ensuring virtual environment..."
set venv_python = "$venv_dir/bin/python"
set fresh = 0
if ( $?CHOPPER_FRESH ) then
    if ( "$CHOPPER_FRESH" == "1" ) set fresh = 1
endif
if ( $fresh == 1 && -d "$venv_dir" ) then
    echo "  CHOPPER_FRESH=1 set; removing existing venv at $venv_dir"
    rm -rf "$venv_dir"
endif
if ( -x "$venv_python" ) then
    "$venv_python" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >& /dev/null
    if ( $status == 0 ) then
        echo "  Reusing existing venv at $venv_dir"
    else
        echo "  Existing venv has wrong Python; recreating."
        rm -rf "$venv_dir"
    endif
endif
if ( ! -x "$venv_python" ) then
    "$python_cmd" -m venv "$venv_dir"
    if ( $status != 0 ) then
        echo "ERROR: Failed to create venv with Python 3.13."
        return 1
    endif
endif

echo "[4/7] Activating venv..."
# activate.csh references $prompt; ensure it's set so non-interactive contexts
# (e.g. nested sourcing) don't trip 'prompt: Undefined variable.'
if ( ! $?prompt ) set prompt = ''
source "$venv_dir/bin/activate.csh"
if ( $status != 0 ) then
    echo "ERROR: Failed to activate venv."
    return 1
endif

echo "[5/7] Configuring proxy for pip and npm..."
if ( $use_proxy == 1 ) then
    setenv HTTP_PROXY "$proxy"
    setenv HTTPS_PROXY "$proxy"
    setenv http_proxy "$proxy"
    setenv https_proxy "$proxy"
    python -m pip config set global.proxy "$proxy" --quiet >& /dev/null
    python -m pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null
    which npm >& /dev/null
    if ( $status == 0 ) then
        npm config set proxy "$proxy" --location=user >& /dev/null
        npm config set https-proxy "$proxy" --location=user >& /dev/null
    endif
else
    echo "  Proxy disabled (CHOPPER_NO_PROXY=1)."
endif

echo "[6/7] Ensuring chopper package is installed..."
python -m pip install --quiet --upgrade pip
if ( $status != 0 ) then
    echo "ERROR: pip upgrade failed."
    return 1
endif
python -m pip install --quiet -e ".[dev]"
if ( $status != 0 ) then
    echo "ERROR: pip install -e .[dev] failed."
    return 1
endif

echo "[7/7] Validating environment..."
if ( $?PYTHONPATH ) then
    echo "$PYTHONPATH" | grep -q "$script_dir/src"
    if ( $status != 0 ) then
        setenv PYTHONPATH "$script_dir/src":"$PYTHONPATH"
    endif
else
    setenv PYTHONPATH "$script_dir/src"
endif

set active_prefix = `python -c "import sys; print(sys.prefix)"`
if ( "$active_prefix" != "$venv_dir" ) then
    echo "ERROR: Active Python prefix mismatch."
    echo "  Expected: $venv_dir"
    echo "  Actual  : $active_prefix"
    return 1
endif

rehash
set chopper_cmd = "$venv_dir/bin/chopper"
"$chopper_cmd" --help >& /dev/null
if ( $status != 0 ) then
    echo "ERROR: chopper launcher validation failed."
    return 1
endif
python -m chopper --help >& /dev/null
if ( $status != 0 ) then
    echo "ERROR: python -m chopper validation failed."
    return 1
endif

echo ""
echo "=== Setup complete ==="
echo "  Python : `python --version`"
echo "  Venv   : $venv_dir"
if ( $use_proxy == 1 ) then
    echo "  Proxy  : $proxy"
else
    echo "  Proxy  : disabled"
endif
echo "  Chopper launchers: OK"
echo ""
echo "Run: chopper --help"
echo "Test: pytest"
