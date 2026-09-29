"""Intel-standard provenance + copyright header for Chopper-generated files.

Every artifact emitted by Chopper's F3 generators (P5 ``<stage>.tcl``
run scripts and ``<stage>.stack`` files) carries this header unless its
body already owns one -- see :func:`needs_header` and ARCHITECTURE.md
Sec.6.6.1. The header is **not** prepended to F1 ``FULL_COPY`` or F2
``PROC_TRIM`` files: those originate on disk and already carry their
own headers; rewriting them would be a destructive content edit outside
the trimmer's contract.

The header text is the canonical Intel legal-compliant copyright block
shipped with every Intel-owned EDA file. It is reproduced verbatim
below -- including the original whitespace (the trailing spaces after
the ``#`` on the blank-padding line and on a few of the wrapped lines
preserve the source byte-for-byte). Only the copyright **year** is
dynamic: it is computed at emission time from
``datetime.now().year`` so generated files always carry the current
calendar year without manual file edits.

Provenance lines (``# Chopper-generated <kind>: <name>`` and the
optional ``# load_from: <name>`` line) are appended **below** the
copyright block by the individual emitters; they are not part of this
helper.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

__all__ = ["intel_header_lines", "intel_header_text", "needs_header"]

# Verbatim Intel legal-compliant copyright header. Whitespace
# (including trailing spaces on a few lines) is preserved by design to
# match the canonical text shipped with every Intel-owned EDA file.
# The single dynamic field is ``{year}``; everything else is fixed.
#
# Do not edit the wording or whitespace without architecture-doc
# approval (see ARCHITECTURE.md Sec.6.6.1).
_HEADER_TEMPLATE = (
    "####################################################################################################\n"
    "#Intel Legal compliant copyright header\n"
    "####################################################################################################\n"
    "#\n"
    "#-- INTEL CONFIDENTIAL\n"
    "#-- Copyright (c) {year} Intel Corporation\n"
    "#                                                                     \n"
    "# This software and the related documents are Intel copyrighted materials, and your use of them \n"
    '# is governed by the express license under which they were provided to you ("License"). Unless the \n'
    "# License provides otherwise,you may not use,modify, copy, publish, distribute, disclose or transmit\n"
    "# this software or the related documents without Intel's prior written permission.\n"
    "#\n"
    "# This software and the related documents are provided as is, with no express or implied warranties,\n"
    "# other than those that are expressly stated in the License.\n"
    "#\n"
    "####################################################################################################\n"
)


def intel_header_text(*, year: int | None = None) -> str:
    """Return the verbatim Intel header as a single string.

    The returned string ends with a trailing newline so callers can
    concatenate further lines directly.

    ``year`` defaults to the current calendar year when ``None``. Tests
    that need byte-stable output should pass an explicit ``year``.
    """

    if year is None:
        year = datetime.now().year
    return _HEADER_TEMPLATE.format(year=year)


def intel_header_lines(*, year: int | None = None) -> tuple[str, ...]:
    """Return the header as a tuple of lines (no trailing newline on each line)."""

    return tuple(intel_header_text(year=year).rstrip("\n").split("\n"))


# Output types whose line comment is ``#`` -- the only syntax the header is
# written in. Any other type is left header-less rather than corrupted.
_HASH_COMMENT_SUFFIXES = frozenset(
    {".tcl", ".stack", ".py", ".pl", ".pm", ".sh", ".bash", ".csh", ".tcsh", ".zsh", ".ksh"}
)
_COPYRIGHT_WORD = re.compile(r"\bcopyright\b", re.IGNORECASE)
_COPYRIGHT_MARK = re.compile(r"\(c\)|\b\d{4}\b", re.IGNORECASE)


def needs_header(path: Path, lines: Sequence[str]) -> bool:
    """Return ``True`` when a generated file at ``path`` whose body is ``lines`` gets the Intel header.

    Only ``#``-comment output types qualify, and never a body that owns its
    header already. See ARCHITECTURE.md Sec.6.6.1.
    """

    return path.suffix.lower() in _HASH_COMMENT_SUFFIXES and not _has_own_header(lines)


def _has_own_header(lines: Sequence[str]) -> bool:
    """Return ``True`` for a line-1 ``#!`` shebang or a copyright notice in the leading comment block.

    A shebang only works on line 1, so nothing may be written above it. A
    notice is the word ``copyright`` plus ``(c)`` or a four-digit year on one
    line; the leading comment block is the contiguous blank / ``#`` lines at
    the top of the body.
    """

    if lines and lines[0].startswith("#!"):
        return True
    for line in lines:
        text = line.strip()
        if text and not text.startswith("#"):
            return False
        if _COPYRIGHT_WORD.search(text) and _COPYRIGHT_MARK.search(text):
            return True
    return False
