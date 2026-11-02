"""Domain layout rules shared by every phase.

:func:`source_root` is the single owner of the rule "read the pristine
source from ``<domain>_backup/`` when it exists on disk, otherwise from
the domain itself" (``technical_docs/ARCHITECTURE.md`` Sec.2.8). P1, P2,
P6, P7, the ``chopper loc`` projection, and the trim-statistics rows all
call it instead of re-deriving the rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from chopper.core.context import ChopperContext

__all__ = ["source_root"]


def source_root(ctx: ChopperContext) -> Path:
    """Return the tree holding the pristine domain source.

    Re-trims (Case 2 / Case 3) rebuild from ``backup_root``, so every
    reader must see that same tree. After a first live trim, P5 has created
    the backup by the time P6 and P7 run, so the live ``fs.exists`` check --
    not the P0 :class:`~chopper.core.models_common.DomainState` snapshot --
    is authoritative.
    """

    backup = ctx.config.backup_root
    return backup if ctx.fs.exists(backup) else ctx.config.domain_root
