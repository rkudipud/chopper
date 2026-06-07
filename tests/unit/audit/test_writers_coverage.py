"""Per-file coverage tests for src/chopper/audit/writers.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

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


def test_render_files_removed_default_exclude_label() -> None:
    """A file that was never positively contributed must be labelled
    'default-exclude' in the removed-files listing."""
    from datetime import UTC, datetime

    from chopper.audit.writers import render_files_removed
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance

    rel = Path("a.tcl")
    prov = FileProvenance(
        path=rel,
        treatment=FileTreatment.REMOVE,
        reason="default-exclude",
        shadowed_by=(),
        contributed_by=None,
    )
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.REMOVE},
        proc_decisions={},
        provenance={rel: prov},
        stages=(),
    )
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="test",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        manifest=manifest,
    )
    ctx = _ctx()
    _hdr, body = render_files_removed(ctx, record)
    assert "default-exclude" in body


def test_render_files_removed_shadowed_by_label() -> None:
    """A file removed by a layer's files.exclude must carry the
    'removed-by:<layer>:files.exclude' provenance label."""
    from datetime import UTC, datetime

    from chopper.audit.writers import render_files_removed
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance, ShadowEvent

    rel = Path("b.tcl")
    shadow = ShadowEvent(layer="feat1", prior_layer="base", action="remove")
    prov = FileProvenance(
        path=rel,
        treatment=FileTreatment.REMOVE,
        reason="fi-literal",
        shadowed_by=(shadow,),
        contributed_by=None,
    )
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.REMOVE},
        proc_decisions={},
        provenance={rel: prov},
        stages=(),
    )
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="test2",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        manifest=manifest,
    )
    ctx = _ctx()
    _hdr, body = render_files_removed(ctx, record)
    assert "removed-by:feat1" in body


def test_render_files_removed_shadowed_by_pe_label() -> None:
    """A file removed where last shadow action is procedures.exclude
    must carry 'shadowed-by' label."""
    from datetime import UTC, datetime

    from chopper.audit.writers import render_files_removed
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance, ShadowEvent

    rel = Path("c.tcl")
    shadow = ShadowEvent(layer="feat2", prior_layer="base", action="remove-proc")
    prov = FileProvenance(
        path=rel,
        treatment=FileTreatment.REMOVE,
        reason="pi-overlay",
        shadowed_by=(shadow,),
        contributed_by=None,
    )
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.REMOVE},
        proc_decisions={},
        provenance={rel: prov},
        stages=(),
    )
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="test3",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        manifest=manifest,
    )
    ctx = _ctx()
    _hdr, body = render_files_removed(ctx, record)
    assert "shadowed-by:feat2" in body


def test_render_dependency_graph_with_non_none_graph() -> None:
    """render_dependency_graph builds edges and pt lists from a real DependencyGraph."""
    from datetime import datetime

    from chopper.audit.writers import render_dependency_graph
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_compiler import DependencyGraph, Edge

    edge = Edge(
        caller="a.tcl::foo",
        callee="a.tcl::bar",
        kind="proc_call",
        status="resolved",
        token="bar",
        line=1,
    )
    graph = DependencyGraph(
        pi_seeds=("a.tcl::foo",),
        nodes=("a.tcl::bar", "a.tcl::foo"),
        pt=("a.tcl::bar",),
        edges=(edge,),
        reachable_from_includes=frozenset({"a.tcl::bar", "a.tcl::foo"}),
    )
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="dep-r1",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        graph=graph,
    )
    name, payload = render_dependency_graph(record)
    assert name == "dependency_graph.json"
    data = json.loads(payload)
    assert len(data["edges"]) == 1
    assert data["edges"][0]["from"] == "a.tcl::foo"
    assert "a.tcl::bar" in data["pt"]


def test_render_compiled_manifest_with_traced_proc_having_colon_colon() -> None:
    """render_compiled_manifest extracts source_file from '::' canonical names."""
    from datetime import datetime

    from chopper.audit.writers import render_compiled_manifest
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_compiler import CompiledManifest, DependencyGraph, Edge

    edge = Edge(
        caller="sub/base.tcl::alpha",
        callee="sub/base.tcl::beta",
        kind="proc_call",
        status="resolved",
        token="beta",
        line=3,
    )
    graph = DependencyGraph(
        pi_seeds=("sub/base.tcl::alpha",),
        nodes=("sub/base.tcl::alpha", "sub/base.tcl::beta"),
        pt=("sub/base.tcl::beta",),
        edges=(edge,),
        reachable_from_includes=frozenset({"sub/base.tcl::alpha", "sub/base.tcl::beta"}),
    )
    manifest = CompiledManifest(
        file_decisions={},
        proc_decisions={},
        provenance={},
        stages=(),
    )
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="cm-r2",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        manifest=manifest,
        graph=graph,
    )
    name, payload = render_compiled_manifest(record)
    data = json.loads(payload)
    traced = data["procedures"]["traced"]
    # "sub/base.tcl::beta" -> source_file == "sub/base.tcl"
    assert any(t["source_file"] == "sub/base.tcl" for t in traced)


def test_before_root_returns_domain_root_when_no_backup() -> None:
    """_before_root returns ctx.config.domain_root when state is None (no backup taken)."""
    from datetime import datetime

    from chopper.audit.writers import _before_root
    from chopper.core.models_audit import RunRecord

    now = datetime.now(UTC)
    record = RunRecord(
        run_id="br-r3",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        state=None,
    )
    ctx = _ctx()
    result = _before_root(ctx, record)
    assert result == DOMAIN


def test_walk_relative_files_list_raises_filenotfound() -> None:
    """_recurse handles FileNotFoundError from ctx.fs.list (lines 399-400)."""
    from datetime import datetime

    from chopper.audit.writers import render_files_removed
    from chopper.core.models_audit import RunRecord

    fs = MagicMock()
    # exists returns True so source_root is not None; list raises immediately
    fs.exists.return_value = True
    fs.list.side_effect = FileNotFoundError("directory gone")

    now = datetime.now(UTC)
    record = RunRecord(run_id="r1", command="trim", started_at=now, ended_at=now, exit_code=0)
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # Should not raise; _recurse silently returns on list error
    name, content = render_files_removed(ctx2, record)
    assert name == "files_removed.txt"


def test_walk_relative_files_stat_raises_filenotfound() -> None:
    """_recurse handles FileNotFoundError from ctx.fs.stat (lines 406-407)."""
    from datetime import datetime

    from chopper.audit.writers import render_files_removed
    from chopper.core.models_audit import RunRecord

    child_path = BACKUP / "lib.tcl"
    fs = MagicMock()
    # exists(backup) -> True so source_root = backup; list returns one child; stat raises
    fs.exists.side_effect = lambda p: p == BACKUP
    fs.list.side_effect = lambda p: [child_path] if p == BACKUP else []
    fs.stat.side_effect = FileNotFoundError("stat vanished")

    now = datetime.now(UTC)
    record = RunRecord(run_id="r2", command="trim", started_at=now, ended_at=now, exit_code=0)
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    name, content = render_files_removed(ctx2, record)
    assert name == "files_removed.txt"


def test_resolve_before_path_with_state_none() -> None:
    """_resolve_before_path calls _before_root; with state=None returns domain_root/rel."""
    from datetime import datetime

    from chopper.audit.writers import _resolve_before_path
    from chopper.core.models_audit import RunRecord

    now = datetime.now(UTC)
    record = RunRecord(run_id="r3", command="trim", started_at=now, ended_at=now, exit_code=0, state=None)
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=InMemoryFS(), diag=_Sink(), progress=_Progress())

    result = _resolve_before_path(ctx2, record, Path("lib.tcl"))
    assert result == DOMAIN / "lib.tcl"
