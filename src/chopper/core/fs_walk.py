"""Shared filesystem-tree helpers over :class:`FileSystemPort`.

One domain walk for every phase. :func:`iter_domain_files` is the domain
as P1-P6 see it (P1 glob expansion, P1 glob-has-matches validation, P2
full-domain parse); :func:`walk_files` layers the LOC-accounting
exclusions on top for :mod:`chopper.audit.writers` and
:mod:`chopper.cli.loc_report`, so every phase agrees on what "a file in
the domain" is. :func:`copy_tree` is the matching recursive copy used by
the trimmer's ``jsons/`` sync and input preservation.

Every helper goes through the engine's
:class:`~chopper.core.protocols.FileSystemPort`, so in-memory unit-test
fixtures work unchanged. Walks skip any directory named ``.chopper``
(Chopper's own audit bundle) at every depth.

The ``TEXT_LIKE_EXTENSIONS`` constant centralises the "files we are
willing to read and SLOC-count" set; callers needing line-math should
pass this in, while callers needing a raw file-count should pass
``None``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chopper.core.protocols import FileSystemPort

__all__ = [
    "EXCLUDED_FILENAMES",
    "EXCLUDED_SUFFIXES",
    "TEXT_LIKE_EXTENSIONS",
    "copy_tree",
    "iter_domain_files",
    "walk_files",
]


# Extensions for which SLOC counting is meaningful.  Kept in sync with
# the legacy ``cli/loc_report._SLOC_EXTENSIONS`` set and extended with
# the markup formats cloc handles natively (md / xml / yml). When in
# doubt prefer adding an extension here over special-casing inside
# callers -- symmetry between "before" and "after" walks is what
# guarantees the delta math is honest.
#
# ``.json`` is intentionally NOT in this set: JSON files are authoring
# inputs (base / feature / project JSONs and the preserved ``jsons/``
# subtree), not domain runtime code.  See ARCHITECTURE.md Sec.5.5.13
# "Authoring artifacts excluded from all LOC accounting".
TEXT_LIKE_EXTENSIONS = frozenset(
    {
        ".tcl",
        ".py",
        ".pl",
        ".pm",
        ".sh",
        ".csh",
        ".tcsh",
        ".bash",
        ".zsh",
        ".ksh",
        ".csv",
        ".md",
        ".rst",
        ".txt",
        ".xml",
        ".yml",
        ".yaml",
    }
)


# Hard exclusions applied to **every** ``walk_files`` call regardless
# of the ``extensions`` filter.  These represent authoring metadata
# Chopper itself consumes (JSON config) or that ships alongside the
# domain as a README (``instructions.md``) and must never be counted
# as domain source.  See ARCHITECTURE.md Sec.5.5.13.
EXCLUDED_SUFFIXES = frozenset({".json"})
EXCLUDED_FILENAMES = frozenset({"instructions.md"})

_AUDIT_DIR_NAME = ".chopper"


def iter_domain_files(fs: FileSystemPort, root: Path) -> Iterator[Path]:
    """Yield every regular file under ``root`` as a ``root``-relative path.

    Breadth-first in :meth:`FileSystemPort.list` order (sorted per
    directory), so the sequence is deterministic. A missing ``root``
    yields nothing; unreadable directories and entries are skipped
    silently (a missing subtree must not crash a walk).
    """

    if not fs.exists(root):
        return
    frontier: deque[Path] = deque([root])
    while frontier:
        current = frontier.popleft()
        try:
            children = fs.list(current)
        except OSError:
            continue
        for child in children:
            if child.name == _AUDIT_DIR_NAME:
                continue
            try:
                rel = child.relative_to(root)
                is_dir = fs.stat(child).is_dir
            except (ValueError, OSError):
                continue
            if is_dir:
                frontier.append(child)
            else:
                yield rel


def walk_files(
    fs: FileSystemPort,
    root: Path,
    *,
    extensions: Iterable[str] | None = None,
) -> list[Path]:
    """Return the LOC-accounting view of ``root``: relative paths, lex-sorted.

    Drops the hard authoring-artifact exclusions (``.json`` files and
    ``instructions.md``; ARCHITECTURE.md Sec.5.5.13) before the optional
    ``extensions`` whitelist (lowercased suffixes with a leading dot), so
    a raw file-count walk (``None``) and a SLOC walk
    (``TEXT_LIKE_EXTENSIONS``) observe the same exclusions.
    """

    ext_set = None if extensions is None else frozenset(e.lower() for e in extensions)
    out = [
        rel
        for rel in iter_domain_files(fs, root)
        if rel.name not in EXCLUDED_FILENAMES
        and rel.suffix.lower() not in EXCLUDED_SUFFIXES
        and (ext_set is None or rel.suffix.lower() in ext_set)
    ]
    out.sort(key=lambda p: p.as_posix())
    return out


def copy_tree(fs: FileSystemPort, src: Path, dst: Path) -> int:
    """Recursively copy every file under ``src`` into ``dst``; return the file count.

    Creates intermediate directories as needed. Errors propagate -- the
    caller decides whether a failed copy is fatal.
    """

    count = 0
    for child in fs.list(src):
        target = dst / child.relative_to(src)
        if fs.stat(child).is_dir:
            fs.mkdir(target, parents=True, exist_ok=True)
            count += copy_tree(fs, child, target)
        else:
            fs.mkdir(target.parent, parents=True, exist_ok=True)
            fs.copy_file(child, target)
            count += 1
    return count
