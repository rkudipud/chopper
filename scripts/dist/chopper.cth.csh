#!/usr/intel/bin/tcsh -f
#
# Chopper CTH launcher (FB-style ward deployment).
#
# This is the executable installed at:
#     $ward/global/eouFW/bin/chopper        (on $PATH for every flow user)
#
# It runs the Chopper package that lives alongside the other flow code at:
#     $ward/global/common/chopper/src   (the chopper package source)
#
# Exit codes 0/1/2/3 are produced by Chopper itself; this launcher only
# adds exit 2 when the package dir is missing or no Python 3.13+ that can
# actually import chopper is found.

# --- resolve this script's real path --------------------------------------
# When invoked by bare name from $PATH, $0 has no slash -- look it up.
set _self = "$0"
if ( "$_self" !~ */* ) then
    set _self = `which "$_self"`
endif
# Canonicalise through any symlinks (a symlinked bin/chopper still works).
set _self = `readlink -f "$_self"`
set _bin    = `dirname "$_self"`        # .../global/eouFW/bin
set _eouFW  = `dirname "$_bin"`         # .../global/eouFW
set _global = `dirname "$_eouFW"`       # .../global
set _ward   = `dirname "$_global"`      # .../<ward>

set _src = "${_global}/common/chopper/src"

if ( ! -d "$_src" ) then
    echo "chopper: package source not found: $_src" > /dev/stderr
    echo "  Expected the FB-style layout:" > /dev/stderr
    echo "    <ward>/global/eouFW/bin/chopper     (this launcher)" > /dev/stderr
    echo "    <ward>/global/common/chopper/src    (chopper package)" > /dev/stderr
    exit 2
endif

# --- write the one-shot interpreter probe ---------------------------------
# Rather than only checking the version, the probe puts chopper's real src/
# on sys.path and imports `chopper.cli.main` -- the same module `-m chopper`
# itself pulls in -- so it transitively exercises every actual runtime
# dependency (jsonschema today, whatever pyproject.toml adds tomorrow). A
# Python that satisfies the version check but is missing a dependency is
# rejected here instead of failing later, mid-command, after exec.
#
# Created with mktemp (not a predictable name) so a symlink planted in
# advance at a guessable /tmp path can't redirect the write.
set _probe = `mktemp /tmp/chopper_probe.XXXXXX.py`
if ( $status != 0 ) then
    echo "chopper: could not create a temp file to probe Python interpreters" > /dev/stderr
    exit 2
endif

cat > "$_probe" <<PYEOF
import sys
if sys.version_info[:2] < (3, 13):
    sys.stdout.write(sys.executable)
    sys.exit(1)
sys.path.insert(0, sys.argv[1])
try:
    import chopper.cli.main
except Exception as e:
    sys.stdout.write(sys.executable + '|' + str(e))
    sys.exit(2)
sys.stdout.write(sys.executable)
sys.exit(0)
PYEOF

# --- build the candidate interpreter list -----------------------------------
# Priority:
#   1. Explicit override ($CHOPPER_PYTHON)
#   2. $AUTOBOTS_SDK_PYTHON_PATH -- set by CTH autobots setup; this venv is
#      Python 3.13 and carries all required packages (jsonschema etc.)
#   3. Every python3/python on $PATH via `where` (autobots bin is first on
#      CTH PATH anyway, so this is a reliable fallback)
#   4. Hardcoded Intel fallback
set _cands = ()
if ( $?CHOPPER_PYTHON ) then
    if ( "$CHOPPER_PYTHON" != "" ) set _cands = ( $_cands "$CHOPPER_PYTHON" )
endif
if ( $?AUTOBOTS_SDK_PYTHON_PATH ) then
    if ( "$AUTOBOTS_SDK_PYTHON_PATH" != "" ) then
        if ( -x "$AUTOBOTS_SDK_PYTHON_PATH" ) set _cands = ( $_cands "$AUTOBOTS_SDK_PYTHON_PATH" )
    endif
endif
foreach _name ( python3 python )
    set _cands = ( $_cands `where "$_name"` )
end
set _cands = ( $_cands /usr/intel/bin/python3.13.2 )

# --- probe each candidate, in order, until one actually works ---------------
# Skip reasons are appended to a log file rather than a tcsh array: tcsh
# silently re-splits array elements that contain spaces the next time the
# array is expanded (e.g. in `foreach`), which would mangle any message
# like "Python < 3.13" into separate elements.
set _py = ""
set _tmpf = `mktemp /tmp/chopper_pycheck.XXXXXX`
set _skiplog = `mktemp /tmp/chopper_skiplog.XXXXXX`
if ( $status != 0 ) then
    echo "chopper: could not create a temp file to probe Python interpreters" > /dev/stderr
    rm -f "$_probe" "$_tmpf"
    exit 2
endif
foreach _cand ( $_cands )
    # paren-subshell form: unlike `` `cmd 2>/dev/null` ``, this reliably
    # suppresses tcsh's own "Command not found." chatter for missing candidates.
    ( "$_cand" "$_probe" "$_src" > "$_tmpf" ) >& /dev/null
    set _rc = $status
    set _exe = `cat $_tmpf`
    if ( "$_exe" == "" ) continue
    if ( $_rc == 0 ) then
        set _py = "$_cand"
        break
    else if ( $_rc == 1 ) then
        echo "    - ${_exe}: Python < 3.13" >> "$_skiplog"
    else
        echo "    - ${_exe:s/|/: /}" >> "$_skiplog"
    endif
end
rm -f "$_tmpf" "$_probe"

if ( "$_py" == "" ) then
    echo "chopper: no usable Python >= 3.13 that can import chopper was found." > /dev/stderr
    echo "  Checked interpreters, in order:" > /dev/stderr
    cat "$_skiplog" > /dev/stderr
    rm -f "$_skiplog"
    echo "  Expected CTH Python via: \$AUTOBOTS_SDK_PYTHON_PATH (set by CTH autobots setup)" > /dev/stderr
    echo "  Or set CHOPPER_PYTHON, e.g.:" > /dev/stderr
    echo "    setenv CHOPPER_PYTHON /usr/intel/bin/python3.13.2" > /dev/stderr
    exit 2
endif
rm -f "$_skiplog"

# --- prepend the package src and hand off ----------------------------------
if ( $?PYTHONPATH ) then
    setenv PYTHONPATH "${_src}:${PYTHONPATH}"
else
    setenv PYTHONPATH "${_src}"
endif

exec "$_py" -m chopper $argv:q
