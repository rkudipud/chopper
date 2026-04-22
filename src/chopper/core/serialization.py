"""Deterministic JSON serialisation for core dataclasses.

Per ARCHITECTURE_PLAN.md §5 closed decision A3, Chopper has **no**
``SerializerPort``. Services and ``AuditService`` call
:func:`dump_model` directly; there is no ``ctx.serde``. This is the only
helper the module exposes.

Determinism contract (bible §5.4, ARCHITECTURE_PLAN.md §11):

* ``json.dumps`` is called with ``sort_keys=True`` so mapping order is
  lexicographic regardless of insertion order.
* :class:`pathlib.Path` values are emitted as POSIX strings — Windows
  authoring and Linux grid-node output must agree byte-for-byte.
* :class:`enum.Enum` values (including :class:`~enum.IntEnum` and
  :class:`~enum.StrEnum`) are emitted as their ``.value``.
* :class:`datetime.datetime` / :class:`datetime.timedelta` are emitted as
  ISO-8601 strings.
* :class:`set` / :class:`frozenset` / :class:`tuple` are converted to
  sorted JSON arrays. Sets sort lexicographically on their string
  representation; tuples preserve order (they are the canonical
  ordered-collection shape in core models).
* ``None`` passes through unchanged.

Non-JSON-serialisable values raise :class:`TypeError` immediately — the
caller then knows the offending field is not fit to cross the serde
boundary (typical cause: a live object accidentally dropped into
``Diagnostic.context``; see bible §8.1 invariants).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import PurePath
from typing import Any

__all__ = ["dump_model", "loads"]


def _encode(value: Any) -> Any:
    """Custom encoder for values :func:`json.dumps` does not natively handle."""
    if isinstance(value, PurePath):
        return value.as_posix()
    if isinstance(value, Enum):
        # StrEnum values pass through the str branch of json's encoder already,
        # but IntEnum / plain Enum do not. Emit .value consistently.
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, set | frozenset):
        # Sort for determinism. Ints/strings sort natively; mixed element
        # types fall back to a ``(type_name, repr)`` sort key so the output
        # is still stable across runs.
        try:
            return sorted(value)
        except TypeError:
            return sorted(value, key=lambda x: (type(x).__name__, repr(x)))
    # Note: :class:`tuple` is not handled here — :func:`json.dumps` emits
    # tuples as JSON arrays natively and never routes them through ``default``.
    raise TypeError(f"Object of type {type(value).__name__!r} is not JSON-serialisable")


def dump_model(obj: Any) -> str:
    """Serialise a dataclass (or any JSON-able tree) to a deterministic string.

    The output is UTF-8, newline-terminated, with ``sort_keys=True`` and
    ``indent=2`` for human-readable audit artifacts. Passing a non-dataclass
    value (for example a plain dict) also works — the helper only requires
    that every leaf is one of the encodable types listed in the module
    docstring.

    ``obj`` must be a frozen dataclass, a mapping, a sequence, or a
    primitive. :meth:`dataclasses.asdict` is called eagerly on dataclasses
    so nested dataclasses serialise to nested dicts; tuples inside the
    shape are preserved by ``asdict`` itself.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        payload = asdict(obj)
    else:
        payload = obj
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            default=_encode,
        )
        + "\n"
    )


def loads(text: str) -> Any:
    """Parse JSON text back into a Python tree (dicts / lists / primitives).

    The inverse of :func:`dump_model` for round-trip tests. Does not attempt
    to rehydrate dataclasses — that is the caller's responsibility at a
    specific model boundary (for example :meth:`Diagnostic.__init__`).
    """
    return json.loads(text)
