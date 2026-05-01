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


class _GlobFS(_InMemoryFS):
    """Extended FS double that supports ``list`` and ``stat`` for a synthetic
    directory tree.  ``tree_files`` is a set of domain-relative POSIX strings
    representing files that exist on the simulated disk."""

    def __init__(self, json_files: dict[Path, str], domain: Path, tree_files: set[str]) -> None:
        super().__init__(json_files)
        self._domain = domain
        # Build parent-dir registry
        self._dirs: set[Path] = {domain}
        self._tree: set[Path] = set()
        for rel in tree_files:
            abs_path = domain / rel
            self._tree.add(abs_path)
            for parent in abs_path.parents:
                if parent == domain or str(parent).startswith(str(domain)):
                    self._dirs.add(parent)

    def exists(self, path: Path) -> bool:
        return path in self._files or path in self._tree or path in self._dirs

    def list(self, path: Path, *, pattern: str | None = None):
        if path not in self._dirs:
            raise NotADirectoryError(path)
        children = {c for c in self._tree | self._dirs if c.parent == path and c != path}
        return tuple(sorted(children, key=lambda p: p.as_posix()))

    def stat(self, path: Path) -> FileStat:
        return FileStat(size=0, mtime=0.0, is_dir=(path in self._dirs))


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


def _make_glob_ctx(
    json_files: dict[Path, str],
    disk_tree: set[str],
    *,
    base_path: Path | None = None,
    feature_paths: tuple[Path, ...] = (),
    domain_root: Path = _DOMAIN,
) -> tuple[ChopperContext, _CollectingSink]:
    """Like ``_make_ctx`` but backed by ``_GlobFS`` so glob expansion works."""
    sink = _CollectingSink()
    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=_BACKUP,
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
        project_path=None,
        base_path=base_path,
        feature_paths=feature_paths,
    )
    ctx = ChopperContext(
        config=cfg,
        fs=_GlobFS(json_files, domain_root, disk_tree),
        diag=sink,
        progress=_NullProgress(),
    )
    return ctx, sink


_MINIMAL_BASE = json.dumps(
    {
        "$schema": "base-v1",
        "domain": "my_domain",
        "files": {"include": ["setup.tcl"]},
    }
)

_MINIMAL_FEATURE = json.dumps(
    {
        "$schema": "feature-v1",
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
        bad_base = json.dumps({"$schema": "base-v1", "files": {"include": ["a.tcl"]}})
        base_path = _DOMAIN / "jsons/base.json"
        ctx, sink = _make_ctx({base_path: bad_base}, base_path=base_path)
        ConfigService().run(ctx, _default_state())
        assert any(d.code == "VE-02" for d in sink.emissions)

    def test_feature_schema_error_skipped_gracefully(self) -> None:
        # Feature with missing required 'name' — loads base fine, feature skipped.
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/bad.json"
        bad_feat = json.dumps({"$schema": "feature-v1"})  # missing name
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
            "$schema": "project-v1",
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
        bad_proj = json.dumps({"$schema": "project-v1", "project": "P", "domain": "d"})  # missing base
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
                "$schema": "base-v1",
                "domain": "d",
                "procedures": {"include": [{"file": "procs/core.tcl", "procs": ["setup"]}]},
            }
        )
        ctx, _ = _make_ctx({base_path: base_doc}, base_path=base_path)
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "procs/core.tcl" in posix_set

    def test_glob_pattern_not_literal_in_surface(self) -> None:
        # The glob pattern string itself must never appear verbatim in
        # surface_files.  With _InMemoryFS (no real domain dir), glob
        # expansion yields no hits — only the literal path "setup.tcl"
        # surfaces.  A real-disk scenario is tested in
        # TestGlobExpansion.test_fi_glob_expands_via_disk_walk.
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
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
                "$schema": "base-v1",
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
                "$schema": "feature-v1",
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
                "$schema": "base-v1",
                "domain": "d",
                "files": {"include": ["setup.tcl"]},
            }
        )
        feat_doc = json.dumps(
            {
                "$schema": "feature-v1",
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
# Glob expansion in surface_files (regression for issue #12)
# ---------------------------------------------------------------------------


class TestGlobExpansion:
    """Verify that files.include glob patterns are expanded against the
    domain filesystem in P1 so that the P2 parser receives every matching
    file — fixing the silent data-loss bug reported in issue #12."""

    def test_fi_glob_expands_via_disk_walk(self) -> None:
        """files.include glob populates surface_files with matched files."""
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "files": {"include": ["reports/**"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc},
            {"reports/summary.tcl", "reports/sub/detail.tcl", "reports/data.py"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "reports/summary.tcl" in posix_set
        assert "reports/sub/detail.tcl" in posix_set
        assert "reports/data.py" in posix_set

    def test_double_star_glob_expands_subdirectories(self) -> None:
        """``**`` recurses into nested subdirectories."""
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "files": {"include": ["rules/**/*.tcl"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc},
            {"rules/r1.tcl", "rules/sub/r2.tcl", "rules/sub/r2.py"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "rules/r1.tcl" in posix_set
        assert "rules/sub/r2.tcl" in posix_set
        assert "rules/sub/r2.py" not in posix_set  # .py doesn't match *.tcl

    def test_glob_and_literal_combined(self) -> None:
        """Literal paths and glob expansions are merged into surface_files."""
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "files": {"include": ["setup.tcl", "procs/*.tcl"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc},
            {"procs/a.tcl", "procs/b.tcl"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "setup.tcl" in posix_set
        assert "procs/a.tcl" in posix_set
        assert "procs/b.tcl" in posix_set

    def test_chopper_dir_never_surfaces_via_glob(self) -> None:
        """.chopper/ audit dir is excluded from glob expansion."""
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "files": {"include": ["**"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc},
            {"setup.tcl", ".chopper/run.json"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "setup.tcl" in posix_set
        assert ".chopper/run.json" not in posix_set

    def test_feature_glob_also_expands(self) -> None:
        """Glob in a feature's files.include also surfaces matched files."""
        base_path = _DOMAIN / "jsons/base.json"
        feat_path = _DOMAIN / "jsons/features/srv.json"
        base_doc = json.dumps({"$schema": "base-v1", "domain": "my_domain", "files": {"include": ["core.tcl"]}})
        feat_doc = json.dumps(
            {
                "$schema": "feature-v1",
                "name": "srv",
                "files": {"include": ["server_reports/**"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc, feat_path: feat_doc},
            {"server_reports/activity.tcl", "server_reports/power.tcl"},
            base_path=base_path,
            feature_paths=(feat_path,),
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "server_reports/activity.tcl" in posix_set
        assert "server_reports/power.tcl" in posix_set

    def test_zero_match_glob_does_not_crash(self) -> None:
        """A glob that matches nothing leaves surface_files unaffected."""
        base_path = _DOMAIN / "jsons/base.json"
        base_doc = json.dumps(
            {
                "$schema": "base-v1",
                "domain": "my_domain",
                "files": {"include": ["missing_dir/**", "setup.tcl"]},
            }
        )
        ctx, _ = _make_glob_ctx(
            {base_path: base_doc},
            {"setup.tcl"},
            base_path=base_path,
        )
        result = ConfigService().run(ctx, _default_state())
        posix_set = {p.as_posix() for p in result.surface_files}
        assert "setup.tcl" in posix_set
        assert not any("missing_dir" in p for p in posix_set)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_features_topo_sorted(self) -> None:
        # Feature b depends on a — result must have a before b.
        base_path = _DOMAIN / "jsons/base.json"
        a_path = _DOMAIN / "jsons/features/a.json"
        b_path = _DOMAIN / "jsons/features/b.json"
        a_doc = json.dumps({"$schema": "feature-v1", "name": "a"})
        b_doc = json.dumps({"$schema": "feature-v1", "name": "b", "depends_on": ["a"]})
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


# ------------------------------------------------------------------
# Extracted from test_final_coverage_push.py (module-aligned consolidation).
# ------------------------------------------------------------------


def test_config_service_collects_surface_files_from_all_sections() -> None:
    """Cover all four harvest paths in ``_collect_surface_files``: each
    section (files.include, files.exclude, procedures.include,
    procedures.exclude) populated on at least one source."""
    from chopper.config.service import _collect_surface_files
    from chopper.core.models import (
        BaseJson,
        FeatureJson,
        FilesSection,
        ProceduresSection,
        ProcEntryRef,
    )

    base = BaseJson(
        source_path=Path("/dom/base.json"),
        domain="demo",
        files=FilesSection(include=("main.tcl", "lib/*.tcl")),
        procedures=ProceduresSection(),
    )
    feat = FeatureJson(
        source_path=Path("/dom/f1.feature.json"),
        name="extra",
        files=FilesSection(
            include=("extra.tcl",),
            exclude=("unwanted.tcl", "skip/*.tcl"),
        ),
        procedures=ProceduresSection(
            include=(ProcEntryRef(file=Path("extra.tcl"), procs=("good",)),),
            exclude=(ProcEntryRef(file=Path("extra.tcl"), procs=("bad",)),),
        ),
    )
    # Build a minimal ctx so _collect_surface_files can attempt disk expansion.
    # _InMemoryFS.exists() returns False for the domain root, so glob
    # expansion gracefully returns empty and only literals are surfaced.
    ctx, _ = _make_ctx({Path("/dom/base.json"): ""}, base_path=Path("/dom/base.json"), domain_root=Path("/dom"))
    surface, _domain_cache = _collect_surface_files(base, [feat], ctx)
    posix = {p.as_posix() for p in surface}
    # Literal include + exclude from both sources captured.
    assert "main.tcl" in posix
    assert "extra.tcl" in posix
    assert "unwanted.tcl" in posix
    # Glob entries not present as raw strings (expansion returned empty with InMemoryFS).
    assert "lib/*.tcl" not in posix
    assert "skip/*.tcl" not in posix
