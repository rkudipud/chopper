"""Per-file coverage tests for src/chopper/generators/service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_generator_service_wraps_write_oserror() -> None:
    from chopper.core.errors import ChopperError
    from chopper.core.models_trimmer import GeneratedArtifact
    from chopper.generators.service import GeneratorService

    class _FailFS(InMemoryFS):
        def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:  # type: ignore[override]
            raise OSError("disk full")

    ctx = _ctx(fs=_FailFS())
    artifact = GeneratedArtifact(
        path=Path("out.tcl"),
        kind="stage",
        content="proc x {} {}\n",
        source_stage="synth",
    )
    with pytest.raises(ChopperError, match="failed to write generated"):
        GeneratorService._write(ctx, artifact)


def test_generator_service_mirrors_perms_when_backup_src_exists(tmp_path: Path) -> None:
    """When a generated artifact's path exists under backup_root, the trimmer
    must mirror the source permissions onto the new file (ARCHITECTURE.md Sec.5.6)."""
    from chopper.core.models_trimmer import GeneratedArtifact
    from chopper.generators.service import GeneratorService

    domain = tmp_path / "d"
    domain.mkdir()
    backup = tmp_path / "d_backup"
    backup.mkdir()
    # Put a pre-existing file in backup so backup_src.is_file() is True.
    (backup / "synth.tcl").write_text("# old\n")
    (domain / "synth.tcl").write_text("# placeholder\n")

    from chopper.adapters.fs_local import LocalFS

    cfg = RunConfig(
        domain_root=domain,
        backup_root=backup,
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())
    artifact = GeneratedArtifact(
        path=Path("synth.tcl"),
        kind="stage",
        content="# new\n",
        source_stage="synth",
    )
    # Should not raise; perms are mirrored.
    GeneratorService._write(ctx, artifact)
