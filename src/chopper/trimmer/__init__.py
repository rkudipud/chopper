"""Phase 5a trimmer — rebuilds the domain directory from backup.

The trimmer is the only service permitted to mutate the filesystem
inside the domain tree. It consumes the frozen
:class:`~chopper.core.models.CompiledManifest` plus the
:class:`~chopper.core.models.ParseResult` and the Phase 0
:class:`~chopper.core.models.DomainState`, and drives three concrete
outputs:

* backup / rebuild of the filesystem per bible §2.8,
* per-file write operations (FULL_COPY / PROC_TRIM / REMOVE) per
  bible §5.2 P5,
* a frozen :class:`~chopper.core.models.TrimReport` audit record.

Stage 3a ships the state-machine that covers all four cases of
bible §2.8, FULL_COPY and PROC_TRIM execution (atomic proc drop with
descending-order line deletion), and the audit-shaped return. The
``GENERATED`` treatment is produced by the Stage 3b generators; until
then the trimmer aborts with :class:`NotImplementedError` if the
manifest asks for a ``GENERATED`` file.

``--dry-run`` mode: every filesystem *mutation* is skipped; the
:class:`TrimReport` is still produced so the audit bundle at P7 reports
exactly what would have happened.
"""

from __future__ import annotations

from chopper.trimmer.service import TrimmerService

__all__ = ["TrimmerService"]
