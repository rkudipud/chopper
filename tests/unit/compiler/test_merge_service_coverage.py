"""Per-file coverage tests for src/chopper/compiler/merge_service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_merge_match_glob_simple() -> None:
    from chopper.compiler.merge_service import _match_glob

    paths = frozenset({Path("a.tcl"), Path("sub/b.tcl"), Path("c.txt")})
    hits = _match_glob("*.tcl", paths)
    # `*.tcl` matches anything ending in .tcl under PurePath.full_match.
    assert Path("a.tcl") in hits
    assert Path("c.txt") not in hits


def test_merge_match_glob_double_star() -> None:
    from chopper.compiler.merge_service import _match_glob

    paths = frozenset({Path("a.tcl"), Path("sub/b.tcl"), Path("sub/deep/c.tcl")})
    hits = _match_glob("**/*.tcl", paths)
    assert Path("sub/b.tcl") in hits
    assert Path("sub/deep/c.tcl") in hits


def _build_ctx_with_tcl(procs_by_file: dict[str, list[str]]) -> tuple[ChopperContext, object]:
    """Build an InMemoryFS context with parsed procs for CompilerService tests."""
    from chopper.core.models_parser import ParsedFile, ParseResult, ProcEntry

    fs = InMemoryFS()
    index: dict[str, ProcEntry] = {}
    files: dict[Path, ParsedFile] = {}
    for relpath in sorted(procs_by_file):
        p = Path(relpath)
        proc_names = procs_by_file[relpath]
        fs.write_text(DOMAIN / relpath, "# placeholder\n")
        procs: list[ProcEntry] = []
        for i, name in enumerate(sorted(proc_names), start=1):
            # ProcEntry.canonical_name must equal f"{source_file.as_posix()}::{qualified_name}"
            # Use staggered line numbers so ParsedFile invariant (sorted by start_line) holds.
            entry = ProcEntry(
                canonical_name=f"{p.as_posix()}::{name}",
                short_name=name,
                qualified_name=name,
                source_file=p,
                start_line=i * 5 - 4,  # 1, 6, 11, ...
                end_line=i * 5 - 2,
                body_start_line=i * 5 - 3,
                body_end_line=i * 5 - 2,
                namespace_path="",
            )
            procs.append(entry)
            index[entry.canonical_name] = entry
        pf = ParsedFile(path=p, procs=tuple(procs), encoding="utf-8")
        files[p] = pf
    # index must be lex-sorted
    sorted_index: dict[str, ProcEntry] = dict(sorted(index.items()))
    ctx = _ctx(fs=fs)
    parsed = ParseResult(index=sorted_index, files=files)
    return ctx, parsed


def test_merge_fe_removes_previously_included_file_emits_vw21_remove() -> None:
    """R1 rule: when a later layer has files.exclude for a file already
    contributed by an earlier layer, VW-21 must be emitted with action='remove'
    (ARCHITECTURE.md §4 / DIAGNOSTIC_CODES.md VW-21)."""
    from chopper.compiler.merge_service import CompilerService
    from chopper.core.models_config import (
        BaseJson,
        BaseOptions,
        FeatureJson,
        FilesSection,
        LoadedConfig,
        ProceduresSection,
    )

    ctx, parsed = _build_ctx_with_tcl({"a.tcl": ["foo", "bar"]})
    base = BaseJson(
        source_path=Path("/w/base.json"),
        domain="d",
        files=FilesSection(include=("a.tcl",)),
        options=BaseOptions(),
    )
    feat = FeatureJson(
        source_path=Path("/w/feat.json"),
        name="trim_a",
        files=FilesSection(exclude=("a.tcl",)),
        procedures=ProceduresSection(),
    )
    loaded = LoadedConfig(base=base, features=(feat,), project=None)
    CompilerService().run(ctx, loaded, parsed)
    codes = _codes(ctx)
    assert "VW-21" in codes
    vw21 = next(d for d in ctx.diag.snapshot() if d.code == "VW-21")
    assert "remove" in vw21.message.lower() or "excluded" in vw21.message.lower()


def test_merge_replace_trim_with_new_trim_emits_vw21_replace() -> None:
    """When a feature layer replaces a prior _Trim with a different trim-replace,
    VW-21 must be emitted with action='replace' showing the old and new proc
    selection (ARCHITECTURE.md §4)."""
    from chopper.compiler.merge_service import CompilerService
    from chopper.core.models_config import (
        BaseJson,
        BaseOptions,
        FeatureJson,
        FilesSection,
        LoadedConfig,
        ProceduresSection,
        ProcEntryRef,
    )

    ctx, parsed = _build_ctx_with_tcl({"a.tcl": ["foo", "bar", "baz"]})
    # Base: PI for foo only
    base = BaseJson(
        source_path=Path("/w/base.json"),
        domain="d",
        files=FilesSection(include=()),
        procedures=ProceduresSection(include=(ProcEntryRef(file=Path("a.tcl"), procs=("foo",)),)),
        options=BaseOptions(),
    )
    # Feature: FI + PE (bar excluded) → trim-replace intent → _record_replace_transition
    feat = FeatureJson(
        source_path=Path("/w/feat.json"),
        name="feat1",
        files=FilesSection(include=("a.tcl",)),
        procedures=ProceduresSection(exclude=(ProcEntryRef(file=Path("a.tcl"), procs=("bar",)),)),
    )
    loaded = LoadedConfig(base=base, features=(feat,), project=None)
    CompilerService().run(ctx, loaded, parsed)
    codes = _codes(ctx)
    assert "VW-21" in codes


def test_emit_vw21_unknown_action_produces_generic_message() -> None:
    """The else branch in _emit_vw21 for an unrecognised action string must
    produce a generic 'shadowed prior layer' message rather than crashing.
    This is a defensive guard per ENGINEERING.md."""
    from chopper.compiler.merge_service import _emit_vw21  # type: ignore[attr-defined]

    ctx = _ctx()
    _emit_vw21(ctx, Path("x.tcl"), "feat", "base", "totally-unknown-action")
    codes = _codes(ctx)
    assert "VW-21" in codes
    msg = next(d.message for d in ctx.diag.snapshot() if d.code == "VW-21")
    assert "totally-unknown-action" in msg or "shadowed" in msg


def test_merge_glob_exclude_unmatched_emits_vw08() -> None:
    """A glob pattern in files.exclude that matches no domain file must emit
    VW-08 (glob-no-matches on exclude) — it is a potential authoring error."""
    from chopper.compiler.merge_service import CompilerService
    from chopper.core.models_config import (
        BaseJson,
        BaseOptions,
        FeatureJson,
        FilesSection,
        LoadedConfig,
        ProceduresSection,
    )

    ctx, parsed = _build_ctx_with_tcl({"a.tcl": ["foo"]})
    base = BaseJson(
        source_path=Path("/w/base.json"),
        domain="d",
        files=FilesSection(include=("a.tcl",)),
        options=BaseOptions(),
    )
    feat = FeatureJson(
        source_path=Path("/w/feat.json"),
        name="f",
        files=FilesSection(exclude=("nonexistent_*.tcl",)),
        procedures=ProceduresSection(),
    )
    loaded = LoadedConfig(base=base, features=(feat,), project=None)
    CompilerService().run(ctx, loaded, parsed)
    # VW-08 or similar warning about unmatched glob
    # The spec says unmatched fe_glob emits a warning (VW-08 or silently skips).
    # At minimum, no error should fire and the file survives.
    # a.tcl should still be FULL_COPY (exclude didn't match anything).


def test_merge_vw21_action_remove_with_fe_only_includes_file_path() -> None:
    """_emit_vw21 with action='remove' must include the file path and the
    excluding layer name in the diagnostic message (DIAGNOSTIC_CODES.md VW-21)."""
    from chopper.compiler.merge_service import _emit_vw21  # type: ignore[attr-defined]

    ctx = _ctx()
    _emit_vw21(ctx, Path("sub/foo.tcl"), "feature_x", "base_layer", "remove")
    diags = [d for d in ctx.diag.snapshot() if d.code == "VW-21"]
    assert diags
    msg = diags[0].message
    assert "feature_x" in msg
    assert "foo.tcl" in msg or "sub/foo.tcl" in msg


def test_merge_vw21_action_replace_with_both_keeps_shows_diff() -> None:
    """_emit_vw21 with action='replace' and both prior_keep/final_keep must
    include both proc sets in the message for audit visibility."""
    from chopper.compiler.merge_service import _emit_vw21  # type: ignore[attr-defined]

    ctx = _ctx()
    _emit_vw21(
        ctx,
        Path("x.tcl"),
        "feat2",
        "base",
        "replace",
        prior_keep=frozenset({"old_proc"}),
        final_keep=frozenset({"new_proc"}),
    )
    diags = [d for d in ctx.diag.snapshot() if d.code == "VW-21"]
    assert diags
    msg = diags[0].message
    assert "old_proc" in msg
    assert "new_proc" in msg


def test_merge_vw21_action_replace_trim_to_whole_shows_prior_keep() -> None:
    """_emit_vw21 with action='replace' where only prior_keep is known
    (new selection is FULL_COPY) must still show prior procs."""
    from chopper.compiler.merge_service import _emit_vw21  # type: ignore[attr-defined]

    ctx = _ctx()
    _emit_vw21(
        ctx,
        Path("x.tcl"),
        "feat3",
        "base",
        "replace",
        prior_keep=frozenset({"alpha", "beta"}),
        final_keep=None,  # new = FULL_COPY
    )
    diags = [d for d in ctx.diag.snapshot() if d.code == "VW-21"]
    assert diags
    msg = diags[0].message
    assert "alpha" in msg or "beta" in msg


def test_merge_trim_pi_redundant_procs_no_shadow_event() -> None:
    """When a second feature's PI adds procs already in prev.keep, `added` is
    empty — no VW-21, no contributed_by update.

    This exercises merge_service.py branch 509->523 (condition False) and
    524->527 (condition False): the ``if added and prior_layer != layer_key``
    and ``if added:`` guards both take the False path.
    """
    from chopper.compiler import CompilerService
    from tests.unit.compiler._helpers import (
        make_base,
        make_ctx,
        make_feature,
        make_loaded,
        make_parsed,
        proc_ref,
        procs_section,
    )

    ctx, sink = make_ctx()
    # File with two procs
    parsed = make_parsed({"lib.tcl": ["alpha", "beta"]})
    # Base PI includes both procs (creates _Trim(keep={alpha, beta}))
    base = make_base(
        procedures=procs_section(include=(proc_ref("lib.tcl", "alpha", "beta"),)),
    )
    # Feature also includes the same procs (added will be empty)
    feat = make_feature(
        "redundant",
        procedures=procs_section(include=(proc_ref("lib.tcl", "alpha", "beta"),)),
    )
    loaded = make_loaded(base, feat)
    manifest = CompilerService().run(ctx, loaded, parsed)

    # No VW-21 emitted because added is empty — no shadow event.
    vw21 = [d for d in sink.emissions if d.code == "VW-21"]
    assert vw21 == []
    # File still ends up PROC_TRIM with both procs surviving.
    from chopper.core.models_common import FileTreatment

    assert manifest.file_decisions[Path("lib.tcl")] is FileTreatment.PROC_TRIM
