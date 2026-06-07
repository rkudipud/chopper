"""Cross-phase filesystem-permission helpers.

Two public entry points, used by every phase that materialises a file
into the rebuilt domain (``<domain>/``):

* :func:`ensure_executable` -- OR ``a+x`` onto a single destination path
  when no source-mode reference is available (e.g. a freshly emitted
  generator artifact that did not previously exist in the source).

* :func:`mirror_perms_plus_exec` -- copy ``src``'s mode bits onto
  ``dst`` (``shutil.copymode``-equivalent semantics) and then OR in
  ``a+x``. This is the canonical helper for any rebuilt file that
  *had* a source counterpart in ``<domain>_backup/`` -- ``FULL_COPY``
  and ``PROC_TRIM`` outputs, plus the regenerate-in-place case of
  ``GENERATED`` outputs. Source mode is preserved verbatim
  (read/write/setuid/sticky bits all carry through) and on top of
  that every rebuilt file is guaranteed runnable for user/group/other.

Errors are swallowed defensively so unusual filesystems (NFS exports
that reject ``chmod``, in-memory adapters used by unit tests) never
break a trim. The destination content is already correct by the time
these helpers run; only the perms are at risk.

This module is owned by ``core/`` so the trimmer and the generator can
both depend on it without crossing the ``services-are-independent``
import contract.
"""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

__all__ = ["EXEC_BITS", "ensure_executable", "mirror_perms_plus_exec"]


EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def ensure_executable(dst: Path) -> None:
    """OR ``a+x`` onto ``dst``'s existing mode if it is a real on-disk file."""

    try:
        if dst.is_file():
            current = dst.stat().st_mode
            dst.chmod(current | EXEC_BITS)
    except OSError:
        pass


def mirror_perms_plus_exec(src: Path, dst: Path) -> None:
    """Copy ``src``'s mode bits onto ``dst``, then OR in ``a+x``.

    No-op when either path is absent from the real filesystem (the
    unit-test in-memory adapter never materializes paths on disk) or
    when the platform rejects ``chmod`` for any reason.
    """

    try:
        if src.is_file() and dst.is_file():
            shutil.copymode(src, dst)
            ensure_executable(dst)
    except OSError:
        pass
