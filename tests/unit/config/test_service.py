"""Unit tests for :mod:`chopper.config.service` — ConfigService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.config.service import ConfigService
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import DomainState, FileStat

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _InMemoryFS:
    def __init__(self, files: dict[Path, str]) -> None:
        self._files = files

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        if path not in self._files:
            raise OSError(f"No such file: {path}")
        return self._files[path]

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...  # pragma: no cover
    def exists(self, path: Path) -> bool:  # pragma: no cover
        return path in self._files

    def list(self, path: Path, *, pattern: str | None = None):  # pragma: no cover
        return ()

    def stat(self, path: Path) -> FileStat:  # pragma: no cover
        return FileStat(size=0, mtime=0.0, is_dir=False)

    def rename(self, src: Path, dst: Path) -> None: ...  # pragma: no cover
    def remove(self, path: Path, *, recursive: bool = False) -> None: ...  # pragma: no cover
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...  # pragma: no cover
    def copy_tree(self, src: Path, dst: Path) -> None: ...  # pragma: no cover


class _CollectingSink:
    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self.emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _NullProgress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


_DOMAIN = Path("/dom/my_domain")
_BACKUP = Path("/dom/my_domain_backup")


def _default_state() -> DomainState:
    return DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)


def _make_ctx(
    files: dict[Path, str],
    *,
    base_path: Path | None = None,
    feature_paths: tuple[Path, ...] = (),
    project_path: Path | None = None,
    domain_root: Path = _DOMAIN,
) -> tuple[ChopperContext, _CollectingSink]:
    sink = _CollectingSink()
    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=_BACKUP,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
        project_path=project_path,
        base_path=base_path,
        feature_paths=feature_paths,
    )
    ctx = ChopperContext(config=cfg, fs=_InMemoryFS(files), diag=sink, progress=_NullProgress())
    return ctx, sink


_MINIMAL_BASE = json.dumps(
    {
        "$schema": "chopper/base/v1",
        "domain": "my_domain",
        "files": {"include": ["setup.tcl"]},
    }
)

_MINIMAL_FEATURE = json.dumps(
    {
        "$schema": "chopper/feature/v1",
        "name": "dft",
        "files": {"include": ["procs/dft.tcl"]},
    }
)


# ---------------------------------------------------------------------------
# Direct-mode (--base / --features)
# ---------------------------------------------------------------------------


class TestDirectMode:
    def test_base_only(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx(
            {base_path: _MINIMAL_BASE},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.base.domain == "my_domain"
        assert result.features == ()
        assert result.project is None
        assert sink.emissions == []

    def test_base_plus_feature(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ctx, sink = _make_ctx(
            {base_path: _MINIMAL_BASE, feat_path: _MINIMAL_FEATURE},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert len(result.features) == 1
        assert result.features[0].name == "dft"
        assert sink.emissions == []

    def test_no_base_path_emits_ve02(self) -> None:
        ctx, sink = _make_ctx({})
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-02" for d in sink.emissions)

    def test_missing_file_emits_ve01(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({}, base_path=base_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-01" for d in sink.emissions)

    def test_invalid_json_emits_ve01(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: "{ not json }"}, base_path=base_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-01" for d in sink.emissions)

    def test_schema_violation_emits_ve02(self) -> None:
        # Base missing required 'domain' field.
        bad_base = json.dumps({"$schema": "chopper/base/v1", "files": {"include": ["a.tcl"]}})
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: bad_base}, base_path=base_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-02" for d in sink.emissions)

    def test_feature_schema_error_skipped_gracefully(self) -> None:
        # Feature with missing required 'name' — loads base fine, feature skipped.
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/bad.json"
        bad_feat = json.dumps({"$schema": "chopper/feature/v1"})  # missing name
        ctx, sink = _make_ctx(
            {base_path: _MINIMAL_BASE, feat_path: bad_feat},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.features == ()  # skipped
        assert any(d.code == "VE-02" for d in sink.emissions)


# ---------------------------------------------------------------------------
# Project-mode (--project)
# ---------------------------------------------------------------------------


class TestProjectMode:
    def _project_json(self, base: str = "jsons/base.json", features: list[str] | None = None) -> str:
        doc: dict = {
            "$schema": "chopper/project/v1",
            "project": "PROJ",
            "domain": "my_domain",
            "base": base,
        }
        if features:
            doc["features"] = features
        return json.dumps(doc)

    def test_project_base_only(self) -> None:
        proj_path = _DOMAIN / "project.json"
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx(
            {proj_path: self._project_json(), base_path: _MINIMAL_BASE},
            project_path=proj_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert result.project is not None
        assert result.project.project == "PROJ"
        assert result.base.domain == "my_domain"
        assert sink.emissions == []

    def test_project_with_feature(self) -> None:
        proj_path = _DOMAIN / "project.json"
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/dft.json"
        ctx, sink = _make_ctx(
            {
                proj_path: self._project_json(features=["jsons/features/dft.json"]),
                base_path: _MINIMAL_BASE,
                feat_path: _MINIMAL_FEATURE,
            },
            project_path=proj_path,
        )
        result = ConfigService().run(ctx, _default_state())
        assert len(result.features) == 1
        assert result.features[0].name == "dft"

    def test_project_file_missing_emits_ve01(self) -> None:
        proj_path = _DOMAIN / "project.json"
        ctx, sink = _make_ctx({}, project_path=proj_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-01" for d in sink.emissions)

    def test_project_schema_invalid_emits_ve12(self) -> None:
        proj_path = _DOMAIN / "project.json"
        bad_proj = json.dumps({"$schema": "chopper/project/v1", "project": "P", "domain": "d"})  # missing base
        ctx, sink = _make_ctx({proj_path: bad_proj}, project_path=proj_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-12" for d in sink.emissions)


# ---------------------------------------------------------------------------
# surface_files
# ---------------------------------------------------------------------------


class TestSurfaceFiles:
    def test_literal_proc_file_surfaces(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "d",
                "procedures": {"include": [{"file": "procs/core.tcl", "procs": ["setup"]}]},
            }
        )
        ctx, _ = _make_ctx({base_path: base_doc}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "procs/core.tcl" in posix_set

    def test_glob_pattern_not_in_surface(self) -> None:
        # Glob patterns must NOT appear in surface_files (no expansion here).
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "d",
                "files": {"include": ["procs/**/*.tcl", "setup.tcl"]},
            }
        )
        ctx, _ = _make_ctx({base_path: base_doc}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "setup.tcl" in posix_set
        assert "procs/**/*.tcl" not in posix_set

    def test_surface_files_are_lex_sorted(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/x.json"
        base_doc = json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "d",
                "procedures": {
                    "include": [
                        {"file": "z.tcl", "procs": ["a"]},
                        {"file": "a.tcl", "procs": ["b"]},
                    ]
                },
            }
        )
        feat_doc = json.dumps(
            {
                "$schema": "chopper/feature/v1",
                "name": "x",
                "procedures": {"include": [{"file": "m.tcl", "procs": ["c"]}]},
            }
        )
        ctx, _ = _make_ctx(
            {base_path: base_doc, feat_path: feat_doc},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        posix = [p.as_posix() for p in result.surface_files]
        assert posix == sorted(posix)

    def test_union_includes_both_base_and_feature_files(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/x.json"
        base_doc = json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": "d",
                "files": {"include": ["setup.tcl"]},
            }
        )
        feat_doc = json.dumps(
            {
                "$schema": "chopper/feature/v1",
                "name": "x",
                "files": {"include": ["extra.tcl"]},
            }
        )
        ctx, _ = _make_ctx(
            {base_path: base_doc, feat_path: feat_doc},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "setup.tcl" in posix_set
        assert "extra.tcl" in posix_set


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_features_topo_sorted(self) -> None:
        # Feature b depends on a — result must have a before b.
        base_path = _DOMAIN / "jsons/base.json"
        a_path = _DOMAIN / "jsons/features/a.json"
        b_path = _DOMAIN / "jsons/features/b.json"
        a_doc = json.dumps({"$schema": "chopper/feature/v1", "name": "a"})
        b_doc = json.dumps({"$schema": "chopper/feature/v1", "name": "b", "depends_on": ["a"]})
        ctx, _ = _make_ctx(
            {base_path: _MINIMAL_BASE, a_path: a_doc, b_path: b_doc},
            base_path=base_path,
            feature_paths=(b_path, a_path),  # deliberately reversed
        )
        result = ConfigService().run(ctx, _default_state())
        names = [f.name for f in result.features]
        assert names.index("a") < names.index("b")

    def test_service_is_stateless(self) -> None:
        base_path = _DOMAIN / "jsons/base.json"
        ctx1, _ = _make_ctx({base_path: _MINIMAL_BASE}, base_path=base_path)
        ctx2, _ = _make_ctx({base_path: _MINIMAL_BASE}, base_path=base_path)
        svc = ConfigService()
        r1 = svc.run(ctx1, _default_state())
        r2 = svc.run(ctx2, _default_state())
        assert r1.base.domain == r2.base.domain

    def test_frozen_dataclass(self) -> None:
        from dataclasses import FrozenInstanceError

        svc = ConfigService()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            svc.some_field = 1  # type: ignore[attr-defined]
