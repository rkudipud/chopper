"""Logical source-line counter for audit reports.

Powers the ``sloc_before`` / ``sloc_after`` fields in
:file:`trim_report.json`, :file:`trim_stats.json`, and the ``chopper
loc`` report.

Counting strategy
-----------------
This module is a thin dispatcher with two backends:

1. **cloc backend** (:mod:`chopper.audit.cloc_backend`) — preferred.
   Shells out to the vendored ``cloc.pl`` for industry-standard,
   language-aware counting that understands block comments
   (``/* … */``, ``<!-- … -->``), Perl POD, Python module docstrings,
   HEREDOCs, and the long tail of language quirks. Used automatically
   when perl + ``cloc.pl`` are available.
2. **Pure-Python fallback** — original implementation kept below as a
   safety net for environments without perl or where the vendored
   ``cloc.pl`` has been removed (e.g. to avoid bundling GPL-2 code).
   Handles hash-comment languages (Tcl, shell, Python, Perl), CSV,
   and JSON only; **does not** see block comments, POD, docstrings,
   or HEREDOCs — those are billed as code.

Override
--------
Set ``CHOPPER_SLOC_BACKEND=python`` in the environment to force the
fallback even when cloc is available. Useful for reproducing legacy
SLOC numbers or for unit-test determinism.

Public helpers
--------------
* :func:`count_sloc` — logical-line count (cloc when available; fallback
  otherwise).
* :func:`count_raw` — non-blank line count, language-agnostic.
"""

from __future__ import annotations

import os
from pathlib import Path

from chopper.audit import cloc_backend

__all__ = ["count_raw", "count_sloc"]


_BACKEND_ENV_VAR = "CHOPPER_SLOC_BACKEND"


# Language detection table for the pure-Python fallback.
_HASH_COMMENT_EXTENSIONS = frozenset(
    {
        ".tcl",
        ".sh",
        ".csh",
        ".tcsh",
        ".bash",
        ".zsh",
        ".ksh",
        ".pl",
        ".pm",
        ".py",
    }
)
_SHELL_EXTENSIONS = frozenset({".sh", ".csh", ".tcsh", ".bash", ".zsh", ".ksh", ".py", ".pl", ".pm"})
_NO_COMMENT_EXTENSIONS = frozenset({".json"})
_CSV_EXTENSIONS = frozenset({".csv"})


def count_raw(text: str) -> int:
    """Return the number of non-blank lines in ``text``.

    A blank line contains only whitespace. Trailing-newline semantics
    don't matter — we count lines after splitting on newline and treat
    an empty final element (from the trailing ``\\n``) as not a line.
    """

    return sum(1 for line in text.splitlines() if line.strip())


def count_sloc(path: Path, text: str) -> int:
    """Return logical source-line count for ``text``.

    Prefers the cloc backend when available; otherwise applies the
    pure-Python fallback rules documented at module level. Language
    is derived from ``path.suffix`` lowercased in either backend.
    """

    if os.environ.get(_BACKEND_ENV_VAR, "").lower() != "python":
        cloc_result = cloc_backend.count_sloc_via_cloc(path, text)
        if cloc_result is not None:
            return cloc_result

    return _count_sloc_python(path, text)


def _count_sloc_python(path: Path, text: str) -> int:
    """Pure-Python fallback counter (see module docstring).

    Tcl / Perl / Python / Shell: full-line ``#`` comments (except a
    ``#!`` shebang on line 1 of an executable script) and blank lines
    do not count. CSV: lines containing only commas/whitespace do not
    count. JSON and unknown extensions: every non-blank line counts.
    """

    suffix = path.suffix.lower()

    if suffix in _HASH_COMMENT_EXTENSIONS:
        return _count_hash_comment(text, is_shell=suffix in _SHELL_EXTENSIONS)

    if suffix in _CSV_EXTENSIONS:
        return _count_csv(text)

    # JSON + fallback: every non-blank line counts.
    if suffix in _NO_COMMENT_EXTENSIONS:
        return count_raw(text)
    return count_raw(text)


def _count_hash_comment(text: str, *, is_shell: bool) -> int:
    """Count non-blank, non-full-line-comment lines.

    Shell / Python / Perl shebang on line 1 (``#!``) counts as SLOC
    (it is executable); every other ``#``-leading line is a comment.
    """

    count = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if is_shell and lineno == 1 and stripped.startswith("#!"):
                count += 1
                continue
            continue
        count += 1
    return count


def _count_csv(text: str) -> int:
    """Count lines that contain at least one non-whitespace, non-comma token."""

    count = 0
    for line in text.splitlines():
        if line.replace(",", "").strip():
            count += 1
    return count
