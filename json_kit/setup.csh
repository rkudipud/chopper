#!/usr/bin/env tcsh
# setup.csh -- Bootstrap Python venv for Chopper JSON Kit on tcsh/csh systems.
# Usage: source setup.csh

set script_dir = `pwd`

if ( ! -f "$script_dir/README.md" || ! -d "$script_dir/schemas" ) then
    echo "setup.csh expects to be sourced from the chopper_json_kit repository root."
    echo "Either cd into the repo first or source .venv/bin/activate.csh directly."
    return 1
endif

set venv_dir = "$script_dir/.venv"
set proxy = "http://proxy-chain.intel.com:928"

# Prefer python3, then python.
set python_cmd = ""
if ( `which python3 >& /dev/null; echo $?` == 0 ) then
    set python_cmd = "python3"
else if ( `which python >& /dev/null; echo $?` == 0 ) then
    set python_cmd = "python"
else
    echo "No Python interpreter found in PATH (expected python3 or python)."
    return 1
endif

echo "=== Chopper JSON Kit Environment Setup ==="
echo "Platform: Unix/Linux/macOS (PRIMARY: tcsh/csh)"

if ( ! -d "$venv_dir" ) then
    echo "[1/4] Creating virtual environment..."
    $python_cmd -m venv "$venv_dir"
    if ( $status != 0 ) then
        echo "Failed to create virtual environment at $venv_dir"
        return 1
    endif
else
    echo "[1/4] Virtual environment exists, reusing."
endif

echo "[2/4] Activating venv..."
source "$venv_dir/bin/activate.csh"
if ( $status != 0 ) then
    echo "Failed to activate venv from $venv_dir/bin/activate.csh"
    return 1
endif

echo "[3/4] Configuring pip and Git proxy..."
pip config set global.proxy "$proxy" --quiet >& /dev/null
pip config set global.trusted-host "pypi.org files.pythonhosted.org" --quiet >& /dev/null
if ( `which git >& /dev/null; echo $?` == 0 ) then
    git config --global http.proxy "$proxy" >& /dev/null
    git config --global https.proxy "$proxy" >& /dev/null
endif

echo "[4/4] Installing dependencies..."
pip install --upgrade pip --quiet
# Repository docs require jsonschema for local schema validation examples.
pip install jsonschema --quiet

echo ""
echo "=== Setup complete ==="
echo "  Platform : Unix/Linux/macOS (PRIMARY: tcsh/csh)"
echo "  Python   : `python --version`"
echo "  Venv     : $venv_dir"
echo "  Shell    : tcsh/csh (PRIMARY - bash/zsh NOT available)"
echo ""
echo "To auto-activate on terminal startup:"
echo "  echo 'source $script_dir/setup.csh' >> ~/.tcshrc"
echo ""
echo "Next steps in this repo:"
echo "  python -m json.tool examples/07_base_full/jsons/base.json > /dev/null"
echo "  python -c 'import jsonschema; print(jsonschema.__version__)'"
