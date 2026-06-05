"""Shared filesystem-tree walker.

Single helper consumed by both :mod:`chopper.audit.writers` and
:mod:`chopper.cli.loc_report` so the two phases agree byte-for-byte on
what counts as "a file in the domain". Prior to this module both
phases shipped near-identical BFS loops with subtly different
extension filters and exclude rules — a source of latent drift the
production-readiness review flagged (A1).

The walker is intentionally minimal:

* uses the engine's :class:`~chopper.core.protocols.FileSystemPort`
  so in-memory unit-test fixtures work unchanged;
* yields paths relative to ``root``, lex-sorted by POSIX form;
* always excludes the internal ``.chopper/`` directory;
* optional ``extensions`` whitelist (suffix-lowercased) — when ``None``
  every regular file is returned.

The ``TEXT_LIKE_EXTENSIONS`` constant centralises the "files we are
willing to read and SLOC-count" set; callers needing line-math should
pass this in, while callers needing a raw file-count should pass
``None``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chopper.core.protocols import FileSystemPort

__all__ = [
    "EXCLUDED_FILENAMES",
    "EXCLUDED_SUFFIXES",
    "TEXT_LIKE_EXTENSIONS",
    "walk_files",
]


# Extensions for which SLOC counting is meaningful.  Kept in sync with
# the legacy ``cli/loc_report._SLOC_EXTENSIONS`` set and extended with
# the markup formats cloc handles natively (md / xml / yml). When in
# doubt prefer adding an extension here over special-casing inside
# callers — symmetry between "before" and "after" walks is what
# guarantees the delta math is honest.
#
# ``.json`` is intentionally NOT in this set: JSON files are authoring
# inputs (base / feature / project JSONs and the preserved ``jsons/``
# subtree), not domain runtime code.  See ARCHITECTURE.md §5.5.13
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
# as domain source.  See ARCHITECTURE.md §5.5.13.
EXCLUDED_SUFFIXES = frozenset({".json"})
EXCLUDED_FILENAMES = frozenset({"instructions.md"})


def walk_files(
    fs: FileSystemPort,
    root: Path,
    *,
    extensions: Iterable[str] | None = None,
    exclude_dirs: Iterable[str] = (".chopper",),
) -> list[Path]:
    """Return every regular file under ``root``, lex-sorted.

    Paths are returned **relative** to ``root`` (POSIX form). The walk
    is BFS so results are deterministic across runs given identical
    inputs. Read errors on individual directory listings are swallowed
    (audit-style "last line of defence" — a missing subtree should not
    crash the report builder).

    Parameters
    ----------
    fs:
        Engine filesystem port. Real or in-memory.
    root:
        Tree root. If absent, returns ``[]``.
    extensions:
        Optional iterable of lowercased suffixes (with leading dot,
        e.g. ``".tcl"``). When provided, only matching files are
        returned. When ``None``, every regular file passes.
    exclude_dirs:
        Directory names (not paths) to skip at any depth. Defaults to
        ``(".chopper",)``; callers may pass additional names when the
        domain layout requires it.
    """

    if not fs.exists(root):
        return []

    ext_set: frozenset[str] | None = None
    if extensions is not None:
        ext_set = frozenset(e.lower() for e in extensions)
    excluded = frozenset(exclude_dirs)

    out: list[Path] = []
    frontier: deque[Path] = deque([root])
    while frontier:
        current = frontier.popleft()
        try:
            children = fs.list(current)
        except OSError:
            continue
        for child in children:
            try:
                rel = child.relative_to(root)
            except ValueError:
                continue
            # Top-level + nested directory-name exclusion.  We check the
            # first component (the directory directly under ``root``)
            # *and* the immediate parent name so deep ``.chopper`` dirs
            # nested inside a feature checkout are also skipped.
            parts = rel.parts
            if parts and parts[0] in excluded:
                continue
            try:
                st = fs.stat(child)
            except OSError:
                continue
            if st.is_dir:
                if child.name in excluded:
                    continue
                frontier.append(child)
                continue
            # Hard authoring-artifact exclusion (ARCHITECTURE.md §5.5.13):
            # apply BEFORE the optional extension filter so a caller
            # passing ``extensions=None`` (raw file-count walk) and a
            # caller passing ``TEXT_LIKE_EXTENSIONS`` (SLOC walk) both
            # observe the same exclusion semantics.
            if child.name in EXCLUDED_FILENAMES:
                continue
            if rel.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if ext_set is not None and rel.suffix.lower() not in ext_set:
                continue
            out.append(rel)
    out.sort(key=lambda p: p.as_posix())
    return out
