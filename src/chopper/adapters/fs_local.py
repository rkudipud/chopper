"""Production :class:`~chopper.core.protocols.FileSystemPort` adapter.

:class:`LocalFS` is a thin wrapper over :mod:`pathlib` and :mod:`shutil`.
It preserves the exact signatures of the port and enforces the
``copy_tree`` ``.chopper/`` exclusion contract.

Write-scope enforcement (restricting writes to the configured roots) is
deliberately *not* implemented here. The production runner resolves all
paths against :class:`~chopper.core.context.RunConfig` roots before
handing them to services; this adapter trusts its inputs.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from chopper.core.models import FileStat

__all__ = ["LocalFS"]


class LocalFS:
    """Concrete filesystem adapter backed by :mod:`pathlib`."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return path.read_text(encoding=encoding)

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]:
        children = list(path.iterdir())
        if pattern is not None:
            children = [p for p in children if p.match(pattern)]
        return tuple(sorted(children, key=lambda p: p.as_posix()))

    def stat(self, path: Path) -> FileStat:
        st = path.stat()
        return FileStat(size=st.st_size, mtime=st.st_mtime, is_dir=path.is_dir())

    def rename(self, src: Path, dst: Path) -> None:
        src.rename(dst)

    def remove(self, path: Path, *, recursive: bool = False) -> None:
        if path.is_dir():
            if recursive:
                shutil.rmtree(path)
            else:
                path.rmdir()
            return
        path.unlink()

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def copy_tree(self, src: Path, dst: Path) -> None:
        def _ignore(directory: str, names: list[str]) -> list[str]:  # noqa: ARG001
            # Only exclude `.chopper/` at the top level of the source tree.
            if Path(directory).resolve() == src.resolve():
                return [name for name in names if name == ".chopper"]
            return []

        shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=False)
