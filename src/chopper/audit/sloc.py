"""SLOC (logical source lines) counter — bible §5.5.13.

Counts logical source lines per language-aware rules for the
``sloc_before`` / ``sloc_after`` fields in :file:`trim_report.json` and
:file:`trim_stats.json`.

Detection is **extension-based only** (bible §5.5.13 rule 1). Unknown
extensions use the fallback rule: every non-blank line counts as SLOC.

Public helpers:

* :func:`count_sloc` — count logical source lines in one file's text.
* :func:`count_raw` — count non-blank lines in one file's text; used
  for ``raw_lines_before`` / ``raw_lines_after``.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["count_raw", "count_sloc"]


# Bible §5.5.13 language detection table.
_HASH_COMMENT_EXTENSIONS = frozenset({".tcl", ".sh", ".csh", ".bash", ".pl", ".pm"})
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
    """Return logical source-line count for ``text`` per bible §5.5.13.

    Language is derived from ``path.suffix`` lowercased. For Tcl / Perl /
    Shell, full-line comments (first non-whitespace char is ``#``, except
    a ``#!`` shebang on line 1 for shell) and blank lines do not count.
    For CSV, a line containing only commas/whitespace does not count.
    JSON has no comment syntax; every non-blank line counts. Unknown
    extensions use the fallback (same as JSON).
    """

    suffix = path.suffix.lower()

    if suffix in _HASH_COMMENT_EXTENSIONS:
        return _count_hash_comment(text, is_shell=suffix in {".sh", ".csh", ".bash"})

    if suffix in _CSV_EXTENSIONS:
        return _count_csv(text)

    # JSON + fallback: every non-blank line counts.
    if suffix in _NO_COMMENT_EXTENSIONS:
        return count_raw(text)
    return count_raw(text)


def _count_hash_comment(text: str, *, is_shell: bool) -> int:
    """Count non-blank, non-full-line-comment lines.

    Shell shebang on line 1 (``#!``) counts as SLOC (it is executable);
    every other ``#``-leading line is a comment.
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
