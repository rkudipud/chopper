#!/usr/intel/bin/tcsh -f
#
# Chopper standalone launcher.
#
# Runs the bundled Chopper package on the deploy host's own Python 3.13+
# interpreter -- no virtualenv, no `pip install`, no network access required
# at the deploy site. The bundle ships:
#
#     <bundle>/bin/chopper   this launcher (installed as the executable)
#     <bundle>/src/          the chopper package source
#     <bundle>/vendor/       runtime dependencies (jsonschema, ...)
#
# The launcher locates the bundle relative to itself, prepends src/ and
# vendor/ to PYTHONPATH, and exec's `python -m chopper`. It is the runtime
# equivalent of the development setup.csh, but resolves Python at deploy
# time and bakes in no path from the build host.
#
# Python resolution order (first interpreter that reports >= 3.13 wins):
#     1. $CHOPPER_PYTHON              explicit operator override
#     2. /usr/intel/bin/python3.13.2  Intel EC default
#     3. python3.13 / python3 / python  whatever is on $PATH
#
# Override the interpreter without rebuilding the bundle:
#     setenv CHOPPER_PYTHON /path/to/python3.13
#
# Exit codes 0/1/2/3 are produced by Chopper itself; this launcher only
# adds exit 2 when no suitable Python interpreter can be found.

# --- resolve this script's real path, then the bundle root ----------------
# When invoked by bare name from $PATH, $0 has no slash -- look it up.
set _self = "$0"
if ( "$_self" !~ */* ) then
    set _self = `which "$_self"`
endif
# Canonicalise through any symlinks (a symlinked bin/chopper still works).
set _self = `readlink -f "$_self"`
set _bin  = `dirname "$_self"`
set _root = `dirname "$_bin"`

set _src    = "${_root}/src"
set _vendor = "${_root}/vendor"

if ( ! -d "$_src" ) then
    echo "chopper: bundle source dir not found: $_src" > /dev/stderr
    echo "  This launcher must run from inside an intact chopper-bundle/." > /dev/stderr
    exit 2
endif

# --- pick a Python 3.13+ interpreter --------------------------------------
set _cands = ( /usr/intel/bin/python3.13.2 python3.13 python3 python )
if ( $?CHOPPER_PYTHON ) then
    if ( "$CHOPPER_PYTHON" != "" ) set _cands = ( "$CHOPPER_PYTHON" $_cands )
endif

set _py = ""
foreach _cand ( $_cands )
    # Try to run it directly; a missing command just yields nonzero status.
    ( "$_cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 13) else 1)' ) >& /dev/null
    if ( $status == 0 ) then
        set _py = "$_cand"
        break
    endif
end

if ( "$_py" == "" ) then
    echo "chopper: no Python >= 3.13 found on this host." > /dev/stderr
    echo "  Point CHOPPER_PYTHON at a 3.13+ interpreter and retry, e.g.:" > /dev/stderr
    echo "    setenv CHOPPER_PYTHON /usr/intel/bin/python3.13.2" > /dev/stderr
    exit 2
endif

# --- assemble PYTHONPATH and hand off -------------------------------------
if ( $?PYTHONPATH ) then
    setenv PYTHONPATH "${_src}:${_vendor}:${PYTHONPATH}"
else
    setenv PYTHONPATH "${_src}:${_vendor}"
endif

exec "$_py" -m chopper $argv:q
