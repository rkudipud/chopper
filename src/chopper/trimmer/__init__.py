"""P5 trimmer — rebuilds the domain directory from backup.

The only service permitted to mutate the filesystem inside the domain
tree. Consumes the compiled manifest, parse results, and domain state,
and produces:

* filesystem backup / rebuild,
* per-file FULL_COPY / PROC_TRIM / REMOVE writes,
* a :class:`TrimReport` audit record.

F3 ``GENERATED`` files are emitted by :mod:`chopper.generators`. Under
``--dry-run`` no filesystem mutations occur; the report is still
produced so P7 can faithfully describe what would have happened.
"""

from __future__ import annotations

from chopper.trimmer.service import TrimmerService

__all__ = ["TrimmerService"]
