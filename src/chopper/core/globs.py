"""Shared glob matcher (architecture doc Sec.6.3.1 -- Path and Glob Semantics).

Multiple phases need identical glob semantics:

* P1 surface-file collection (:mod:`chopper.config.service`).
* P1 glob-has-matches validation (:mod:`chopper.validator.functions`).
* P3 conflict resolution / merge (:mod:`chopper.compiler.merge_service`).

One matcher in :mod:`chopper.core` is the only way to guarantee those
three layers agree, *and* it satisfies the import contract in
:file:`pyproject.toml` (services may not import each other -- only
``chopper.core``).

Semantics are the stdlib's :meth:`pathlib.PurePath.full_match`
(Python 3.13+), which is exactly the Sec.6.3.1 contract:

* ``*``     -> any run of characters within one path segment (never ``/``).
* ``?``     -> exactly one character within one path segment.
* ``**``    -> zero or more whole path segments.
* ``[...]`` -> character class; leading ``!`` is the negation form.

Matching is anchored (the whole path) and case-sensitive.
"""

from __future__ import annotations

from pathlib import PurePosixPath

__all__ = ["glob_match"]


def glob_match(pattern: str, posix_path: str) -> bool:
    """Return ``True`` iff domain-relative ``posix_path`` matches ``pattern``."""

    return PurePosixPath(posix_path).full_match(pattern)
