"""Pure-Python in-memory filesystem used in Chopper's tests.

The adapter models files as a ``dict[PurePosixPath, str]`` keyed by the
POSIX normalization of the path. Directories are implicit — any path
that is an ancestor of a stored file counts as an existing directory.
Explicit empty directories created via :meth:`InMemoryFS.mkdir` are
tracked in a separate set so :meth:`exists` and :meth:`list` observe
them consistently.

All methods that accept a :class:`pathlib.Path` normalize the argument
through :meth:`pathlib.PurePath.as_posix` before hashing — tests may
pass mixed separators without affecting determinism. The write-scope
contract documented on
:class:`~chopper.core.protocols.FileSystemPort` is **not** enforced
here (test ergonomics outweigh the sandbox guarantee in unit scope).

Relationship to the parser's ``_InMemoryFS`` test double: that helper
was a minimal stub that only implemented ``read_text``. Stage 3a
promotes the in-memory filesystem to a first-class adapter so the
trimmer can be tested end-to-end without touching real disk.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from chopper.core.models import FileStat

__all__ = ["InMemoryFS"]


def _key(path: Path | PurePosixPath) -> PurePosixPath:
    """Return the POSIX-normalized key for ``path`` used by every store."""

    return PurePosixPath(Path(path).as_posix())


class InMemoryFS:
    """In-memory :class:`~chopper.core.protocols.FileSystemPort`.

    Parameters
    ----------
    files:
        Optional mapping of initial paths → text content. Keys may be
        :class:`pathlib.Path` or ``str``; they are normalized to POSIX
        internally. Parent directories are implicit.
    """

    def __init__(self, files: dict[Path, str] | None = None) -> None:
        self._files: dict[PurePosixPath, str] = {_key(p): c for p, c in (files or {}).items()}
        self._dirs: set[PurePosixPath] = set()
        # Seed implicit ancestor directories so the initial tree reports
        # them through ``exists``/``list`` without forcing tests to
        # pre-register every directory.
        for file_path in list(self._files):
            for ancestor in file_path.parents:
                self._dirs.add(ancestor)

    # ------------------------------------------------------------------
    # Read / metadata surface
    # ------------------------------------------------------------------
    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        key = _key(path)
        if key not in self._files:
            raise FileNotFoundError(f"InMemoryFS: no such file: {path.as_posix()}")
        return self._files[key]

    def exists(self, path: Path) -> bool:
        key = _key(path)
        return key in self._files or key in self._dirs

    def stat(self, path: Path) -> FileStat:
        key = _key(path)
        if key in self._files:
            return FileStat(size=len(self._files[key].encode("utf-8")), mtime=0.0, is_dir=False)
        if key in self._dirs:
            return FileStat(size=0, mtime=0.0, is_dir=True)
        raise FileNotFoundError(f"InMemoryFS: no such path: {path.as_posix()}")

    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]:
        key = _key(path)
        if key not in self._dirs and key not in self._files:
            raise FileNotFoundError(f"InMemoryFS: no such directory: {path.as_posix()}")
        children: set[PurePosixPath] = set()
        # Files whose parent == key
        for file_path in self._files:
            if file_path.parent == key:
                children.add(file_path)
        # Subdirectories whose immediate parent == key
        for dir_path in self._dirs:
            if dir_path.parent == key and dir_path != key:
                children.add(dir_path)
        results = sorted(children, key=lambda p: p.as_posix())
        if pattern is not None:
            results = [p for p in results if fnmatch.fnmatch(p.name, pattern)]
        return tuple(Path(p.as_posix()) for p in results)

    # ------------------------------------------------------------------
    # Mutating surface
    # ------------------------------------------------------------------
    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        key = _key(path)
        if key in self._dirs:
            raise IsADirectoryError(f"InMemoryFS: cannot write over directory: {path.as_posix()}")
        for ancestor in key.parents:
            self._dirs.add(ancestor)
        self._files[key] = content

    def rename(self, src: Path, dst: Path) -> None:
        src_key = _key(src)
        dst_key = _key(dst)
        if src_key not in self._files and src_key not in self._dirs:
            raise FileNotFoundError(f"InMemoryFS: rename source does not exist: {src.as_posix()}")
        if dst_key in self._files or dst_key in self._dirs:
            raise FileExistsError(f"InMemoryFS: rename target already exists: {dst.as_posix()}")
        # Move any files whose path starts with src_key
        moved: list[tuple[PurePosixPath, PurePosixPath]] = []
        for file_path in list(self._files):
            if file_path == src_key or _is_descendant(file_path, src_key):
                new_path = _rebase(file_path, src_key, dst_key)
                self._files[new_path] = self._files.pop(file_path)
                moved.append((file_path, new_path))
        for dir_path in list(self._dirs):
            if dir_path == src_key or _is_descendant(dir_path, src_key):
                new_path = _rebase(dir_path, src_key, dst_key)
                self._dirs.discard(dir_path)
                self._dirs.add(new_path)
        # Ensure every ancestor of moved paths is registered
        for _, new_path in moved:
            for ancestor in new_path.parents:
                self._dirs.add(ancestor)

    def remove(self, path: Path, *, recursive: bool = False) -> None:
        key = _key(path)
        if key in self._files:
            del self._files[key]
            return
        if key in self._dirs:
            # Does the directory have contents?
            has_children = any(_is_descendant(k, key) for k in self._files) or any(
                _is_descendant(d, key) for d in self._dirs
            )
            if has_children and not recursive:
                raise OSError(f"InMemoryFS: directory not empty: {path.as_posix()}")
            for file_path in list(self._files):
                if _is_descendant(file_path, key):
                    del self._files[file_path]
            for dir_path in list(self._dirs):
                if _is_descendant(dir_path, key) or dir_path == key:
                    self._dirs.discard(dir_path)
            return
        raise FileNotFoundError(f"InMemoryFS: no such path: {path.as_posix()}")

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        key = _key(path)
        if key in self._dirs:
            if exist_ok:
                return
            raise FileExistsError(f"InMemoryFS: directory already exists: {path.as_posix()}")
        if key in self._files:
            raise FileExistsError(f"InMemoryFS: file at target path: {path.as_posix()}")
        if not parents and key.parent not in self._dirs and key.parent != PurePosixPath(key.anchor or "."):
            # Allow the special case where the parent is the implicit root.
            if str(key.parent) not in ("/", ".", ""):
                raise FileNotFoundError(f"InMemoryFS: parent does not exist: {key.parent.as_posix()}")
        for ancestor in key.parents:
            self._dirs.add(ancestor)
        self._dirs.add(key)

    def copy_tree(self, src: Path, dst: Path) -> None:
        src_key = _key(src)
        dst_key = _key(dst)
        if src_key not in self._dirs and not any(_is_descendant(f, src_key) for f in self._files):
            raise FileNotFoundError(f"InMemoryFS: copy_tree source does not exist: {src.as_posix()}")
        # Register the destination root.
        for ancestor in dst_key.parents:
            self._dirs.add(ancestor)
        self._dirs.add(dst_key)
        # Copy every file under src, excluding any .chopper/ subtree that
        # sits directly under src (per the protocol contract).
        chopper_exclusion = src_key / ".chopper"
        for file_path in list(self._files):
            if not (_is_descendant(file_path, src_key) or file_path == src_key):
                continue
            if file_path == chopper_exclusion or _is_descendant(file_path, chopper_exclusion):
                continue
            new_path = _rebase(file_path, src_key, dst_key)
            self._files[new_path] = self._files[file_path]
            for ancestor in new_path.parents:
                self._dirs.add(ancestor)
        for dir_path in list(self._dirs):
            if not _is_descendant(dir_path, src_key):
                continue
            if dir_path == chopper_exclusion or _is_descendant(dir_path, chopper_exclusion):
                continue
            new_path = _rebase(dir_path, src_key, dst_key)
            self._dirs.add(new_path)


def _is_descendant(path: PurePosixPath, root: PurePosixPath) -> bool:
    """Return True if ``path`` is strictly under ``root``."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return path != root


def _rebase(path: PurePosixPath, src_root: PurePosixPath, dst_root: PurePosixPath) -> PurePosixPath:
    """Return ``path`` rebased from ``src_root`` onto ``dst_root``."""

    if path == src_root:
        return dst_root
    relative = path.relative_to(src_root)
    return dst_root / relative
