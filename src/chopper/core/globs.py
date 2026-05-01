"""Shared glob-to-regex translator (architecture doc §4 — R1 glob semantics).

Multiple services need identical glob semantics:

* P1 surface-file collection (:mod:`chopper.config.service`).
* P3 conflict resolution / merge (:mod:`chopper.compiler.merge_service`).
* P1 / P3 validation (:mod:`chopper.validator.functions`).

Keeping a single canonical translator in :mod:`chopper.core` is the only
way to guarantee those three layers agree, *and* it satisfies the import
contract in :file:`pyproject.toml` (services may not import each other —
only ``chopper.core``).

Semantics — POSIX-style glob with explicit ``**`` support:

* ``**``    → zero or more path segments (``(?:.*/)?`` when followed by
            ``/``, ``.*`` otherwise).
* ``*``     → any run of non-``/`` characters.
* ``?``     → exactly one non-``/`` character.
* ``[...]`` → character class; leading ``!`` is the negation form.

The ``glob_to_regex`` helper returns ``None`` for patterns with no ``**``
so the caller can fall back to :func:`fnmatch.fnmatchcase` (which is
faster and matches the documented `fnmatch` semantics for those cases).
"""

from __future__ import annotations

import re

__all__ = ["glob_to_regex"]


def glob_to_regex(pattern: str) -> re.Pattern[str] | None:
    """Translate a POSIX-style glob with ``**`` semantics into a compiled regex.

    Returns ``None`` for patterns containing no ``**`` so the caller can
    fall back to :func:`fnmatch.fnmatchcase`. The compiled regex matches
    the *entire* path (no implicit anchors are added — callers should use
    :meth:`re.Pattern.fullmatch` if they want anchored matching, which is
    what every current call site does).
    """

    if "**" not in pattern:
        return None
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape("["))
                i += 1
            else:
                cls = pattern[i + 1 : j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append("[" + cls + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out))
