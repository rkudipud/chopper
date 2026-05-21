"""Concrete port adapters for Chopper's services.

Each adapter here implements a :class:`~typing.Protocol` declared in
:mod:`chopper.core.protocols`. Services depend only on the protocols and
are injected an adapter instance by the runner.

The package currently ships two :class:`~chopper.core.protocols.FileSystemPort`
implementations:

* :class:`~chopper.adapters.fs_local.LocalFS` — wraps :mod:`pathlib` and
  is used by the production runner.
* :class:`~chopper.adapters.fs_memory.InMemoryFS` — pure-Python model of
  a filesystem used by unit and integration tests.

Both adapters enforce the write-scope and ``copy_tree`` ``.chopper/``
exclusion contracts documented on
:class:`~chopper.core.protocols.FileSystemPort`.
"""

from __future__ import annotations

from chopper.adapters.fs_local import LocalFS
from chopper.adapters.fs_memory import InMemoryFS
from chopper.adapters.progress_rich import RichProgress, RichUnavailableError
from chopper.adapters.progress_silent import SilentProgress
from chopper.adapters.sink_collecting import CollectingSink

__all__ = [
    "CollectingSink",
    "InMemoryFS",
    "LocalFS",
    "RichProgress",
    "RichUnavailableError",
    "SilentProgress",
]
