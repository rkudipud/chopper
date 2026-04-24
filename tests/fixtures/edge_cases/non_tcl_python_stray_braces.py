# Regression fixture for GitHub issue #2 — "[Bug] Parse is flagging TCL
# issues in Python script".
#
# This is a minimal Python source file whose *character-level* brace
# count does not return to zero because real Python constructs
# legitimately contain stray ``}``:
#
#   * closing-brace characters used as literal data inside string
#     literals (e.g. passed to ``str.replace`` to splice HTML),
#   * ``}`` used as the terminator of a regex group class inside a
#     raw string,
#
# neither of which a Tcl tokenizer can interpret. If this file is ever
# fed to the Tcl tokenizer it *will* emit
# ``TokenizerError(kind="negative_depth")`` and the parser service will
# translate that into a spurious ``PE-02 unbalanced-braces``.
#
# Contract under test: ``ParserService.run`` must skip every file whose
# suffix is not ``.tcl`` (case-insensitive), regardless of the file's
# byte content. The file still participates in F1 file-level treatment
# via the compiler's universe collection; only the Tcl tokenizer is
# bypassed.
#
# Do not "fix" the stray braces below — their presence is the whole
# point of the fixture.

import re

HIER_PATTERN = re.compile(r"hier\{([^}]+)\}")


def splice_hier_macro(value: str) -> str:
    # The literal ``"}"`` here is what blew up the Tcl tokenizer in the
    # original bug report (generate_summary_html.py:986).
    return value.replace("}", "}\n&nbsp;&nbsp;&nbsp;")


def extract_scenario(line: str) -> str | None:
    m = HIER_PATTERN.search(line)
    if m is None:
        return None
    # Another stray ``}`` inside an f-string for good measure.
    return f"scenario={m.group(1)}}}"
