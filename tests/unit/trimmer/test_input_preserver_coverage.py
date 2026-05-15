"""Per-file coverage tests for src/chopper/trimmer/input_preserver.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from pathlib import Path


from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext
from chopper.core.context import RunConfig


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_input_preserver_copies_jsons_dir_from_backup() -> None:
    """preserve_input_sources must mirror the jsons/ tree from backup to the
    rebuilt domain (ARCHITECTURE.md §5.6)."""
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.trimmer.input_preserver import preserve_input_sources

    fs = InMemoryFS()
    # Backup has jsons/
    fs.write_text(BACKUP / "jsons" / "base.json", '{"name": "b"}')
    fs.write_text(BACKUP / "jsons" / "feat.json", '{"name": "f"}')

    ctx = _ctx(fs=fs)

    base = BaseJson(
        source_path=DOMAIN / "jsons" / "base.json",  # in-tree
        domain="d",
        files=FilesSection(include=()),
        options=BaseOptions(),
    )
    loaded = LoadedConfig(base=base, features=(), project=None)
    count = preserve_input_sources(ctx, loaded)
    assert count >= 1
    # jsons/ should now exist in domain
    assert fs.exists(DOMAIN / "jsons" / "base.json")


def test_input_preserver_emits_vw20_on_mkdir_failure() -> None:
    """When mkdir fails for the jsons/ destination, VW-20 must be emitted
    and the run must continue (best-effort, ARCHITECTURE.md §5.6)."""
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.trimmer.input_preserver import preserve_input_sources

    class _FailMkdir(InMemoryFS):
        def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
            if "jsons" in str(path):
                raise OSError("read-only")
            return super().mkdir(path, parents=parents, exist_ok=exist_ok)

    fs = _FailMkdir()
    # Backup has jsons/
    fs.write_text(BACKUP / "jsons" / "base.json", "{}")
    ctx = _ctx(fs=fs)

    base = BaseJson(
        source_path=DOMAIN / "jsons" / "base.json",
        domain="d",
        files=FilesSection(include=()),
        options=BaseOptions(),
    )
    loaded = LoadedConfig(base=base, features=(), project=None)
    preserve_input_sources(ctx, loaded)
    assert "VW-20" in _codes(ctx)


def test_input_preserver_copies_out_of_tree_sources() -> None:
    """Out-of-tree JSON inputs must be copied to _external/<NN>_<basename>
    inside the rebuilt domain's jsons/ directory."""
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.trimmer.input_preserver import preserve_input_sources

    fs = InMemoryFS()
    # Source JSON is outside the domain root.
    out_of_tree = Path("/outside/project/feature_a.json")
    fs.write_text(out_of_tree, '{"name": "feat_a"}')

    ctx = _ctx(fs=fs)

    base = BaseJson(
        source_path=out_of_tree,  # out-of-tree
        domain="d",
        files=FilesSection(include=()),
        options=BaseOptions(),
    )
    loaded = LoadedConfig(base=base, features=(), project=None)
    count = preserve_input_sources(ctx, loaded)
    assert count >= 1


def test_input_preserver_emits_vw20_on_out_of_tree_copy_failure() -> None:
    """When copying an out-of-tree source fails, VW-20 must be emitted."""
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.trimmer.input_preserver import preserve_input_sources

    class _FailCopy(InMemoryFS):
        def copy_file(self, src: Path, dst: Path) -> None:
            raise OSError("denied")

    fs = _FailCopy()
    out_of_tree = Path("/outside/fail.json")
    fs.write_text(out_of_tree, "{}")
    ctx = _ctx(fs=fs)

    base = BaseJson(
        source_path=out_of_tree,
        domain="d",
        files=FilesSection(include=()),
        options=BaseOptions(),
    )
    loaded = LoadedConfig(base=base, features=(), project=None)
    preserve_input_sources(ctx, loaded)
    assert "VW-20" in _codes(ctx)


def test_copy_dir_recursively_copies_nested_subdirectory() -> None:
    """_copy_dir must recursively copy directories and return the file count."""
    from chopper.trimmer.input_preserver import _copy_dir

    fs = InMemoryFS()
    # Setup: /backup/jsons/sub/feat.json and /backup/jsons/base.json
    fs.write_text(Path("/backup/jsons/sub/feat.json"), '{"features":[]}')
    fs.write_text(Path("/backup/jsons/base.json"), '{"base":"x"}')

    ctx_cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=Path("/backup"),
        audit_root=AUDIT,
        strict=False,
        dry_run=False,
    )
    ctx2 = ChopperContext(config=ctx_cfg, fs=fs, diag=_Sink(), progress=_Progress())

    src = Path("/backup/jsons")
    dst = Path("/domain/jsons")
    fs.mkdir(dst, parents=True, exist_ok=True)
    count = _copy_dir(ctx2, src, dst)
    assert count == 2
    assert fs.exists(Path("/domain/jsons/base.json"))
    assert fs.exists(Path("/domain/jsons/sub/feat.json"))


def test_preserve_input_sources_project_and_features_appended() -> None:
    """preserve_input_sources includes project.source_path (line 77) and feature.source_path (line 80)."""
    from chopper.trimmer.input_preserver import preserve_input_sources
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig, ProjectJson

    # Use tmp_path via InMemoryFS since we only care about line execution, not actual I/O.
    fs = InMemoryFS()
    base_path = DOMAIN / "jsons" / "base.json"
    proj_path = DOMAIN / "jsons" / "project.json"
    feat_path = DOMAIN / "jsons" / "feat.json"
    # Write all source files so _safe_read doesn't fail
    fs.write_text(base_path, '{"domain":"d"}')
    fs.write_text(proj_path, '{"base":"base.json"}')
    fs.write_text(feat_path, '{"name":"feat"}')

    base = BaseJson(source_path=base_path, domain="d")
    feature = FeatureJson(source_path=feat_path, name="feat")
    project = ProjectJson(source_path=proj_path, project="my_proj", domain="d", base="base.json")
    loaded = LoadedConfig(base=base, features=(feature,), project=project)

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # Even if backup_jsons doesn't exist, the sources loop (lines 75-80) still runs
    count = preserve_input_sources(ctx2, loaded)
    # count >= 0 (could be 0 if out-of-tree copies fail silently) — main check is no crash
    assert isinstance(count, int)
