"""Per-file coverage tests for src/chopper/validator/functions.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _make_file_outcome,
    _make_trim_report,
    _Progress,
    _Sink,
)


def test_validator_glob_syntax_rejects_nested_open_bracket() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    ctx = _ctx()
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("[[abc.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VE-09" in _codes(ctx)


def test_validator_glob_syntax_rejects_stray_close_bracket() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    ctx = _ctx()
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("[a]b].tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VE-09" in _codes(ctx)


def test_validator_glob_syntax_accepts_balanced_charclass() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "ax.tcl", "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("[a-z]x.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VE-09" not in _codes(ctx)


def test_validator_glob_no_matches_when_domain_missing() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    # Domain root does not exist on the in-memory FS.
    ctx = _ctx()
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("*.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VW-03" in _codes(ctx)


def test_validator_glob_walk_skips_chopper_subtree() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    fs = InMemoryFS()
    # Only file is inside .chopper/ -- should be skipped, glob has no match.
    fs.write_text(DOMAIN / ".chopper" / "audit.tcl", "x")
    ctx = _ctx(fs=fs)
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("**/*.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VW-03" in _codes(ctx)


def test_validator_glob_walk_handles_list_oserror() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    class _BadList(InMemoryFS):
        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == DOMAIN / "blocked":
                raise OSError("denied")
            return super().list(path, pattern=pattern)

    fs = _BadList()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.mkdir(DOMAIN / "blocked", parents=True, exist_ok=True)
    ctx = _ctx(fs=fs)
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("*.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    # Top-level *.tcl should still match ok.tcl despite blocked/ failing.
    assert "VW-03" not in _codes(ctx)


def test_validator_glob_walk_handles_stat_oserror() -> None:
    from chopper.core.models_config import BaseJson, BaseOptions, FilesSection, LoadedConfig
    from chopper.validator import validate_pre

    class _StatFail(InMemoryFS):
        def stat(self, path: Path):  # type: ignore[override]
            if path == DOMAIN / "x.tcl":
                raise OSError("denied")
            return super().stat(path)

    fs = _StatFail()
    fs.write_text(DOMAIN / "x.tcl", "x")
    fs.write_text(DOMAIN / "y.tcl", "y")
    ctx = _ctx(fs=fs)
    base = BaseJson(
        source_path=Path("/cfg/base.json"),
        domain="d",
        files=FilesSection(include=("*.tcl",)),
        options=BaseOptions(),
    )
    validate_pre(ctx, LoadedConfig(base=base))
    assert "VW-03" not in _codes(ctx)


def test_validator_path_from_canonical_returns_none_for_nameless() -> None:
    from chopper.validator.functions import _path_from_canonical

    assert _path_from_canonical("nosep") is None
    assert _path_from_canonical("a.tcl::ok") == Path("a.tcl")


def _empty_graph():
    from chopper.core.models_compiler import DependencyGraph

    return DependencyGraph(pi_seeds=(), nodes=(), pt=(), edges=(), reachable_from_includes=frozenset())


def _make_manifest(stages=(), files=None, procs=None):
    from chopper.core.models_compiler import CompiledManifest, FileProvenance

    files = files or {}
    procs = procs or {}
    provenance = {
        p: FileProvenance(path=p, treatment=t, reason="fi-literal")
        for p, t in sorted(files.items(), key=lambda kv: kv[0].as_posix())
    }
    return CompiledManifest(
        file_decisions={p: files[p] for p in sorted(files, key=lambda x: x.as_posix())},
        proc_decisions={k: procs[k] for k in sorted(procs)},
        provenance=provenance,
        stages=stages,
    )


def test_validator_stage_step_external_absolute_path_emits_vw17() -> None:
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    stage = StageSpec(name="s", load_from="base", steps=("/abs/path/x.tcl",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-17" in _codes(ctx)


def test_validator_stage_step_with_dotdot_emits_vw17() -> None:
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    stage = StageSpec(name="s", load_from="base", steps=("../escape.tcl",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-17" in _codes(ctx)


def test_validator_stage_step_drive_letter_emits_vw17() -> None:
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    stage = StageSpec(name="s", load_from="base", steps=("C:/x/y.tcl",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-17" in _codes(ctx)


def test_validator_stage_step_source_command_resolves() -> None:
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    stage = StageSpec(name="s", load_from="base", steps=("source missing.tcl",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-16" in _codes(ctx)

    stage_ok = StageSpec(name="s", load_from="base", steps=("source present.tcl",))
    ctx2 = _ctx()
    validate_post(
        ctx2,
        _make_manifest(stages=(stage_ok,), files={Path("present.tcl"): FileTreatment.FULL_COPY}),
        _empty_graph(),
        rewritten=(),
    )
    assert "VW-16" not in _codes(ctx2)


def test_validator_stage_step_skip_comment_proc_token() -> None:
    """A leading-``#`` token is not classified as a bare proc step."""
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    stage = StageSpec(name="s", load_from="base", steps=("# comment line",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-15" not in _codes(ctx)


def test_validator_stage_step_path_separator_not_bare_proc() -> None:
    """A token containing '/' or '\\' isn't a bare proc and isn't VW-15."""
    from chopper.core.models_compiler import StageSpec
    from chopper.validator import validate_post

    # Path-shaped token without known extension -> not VW-14 (no ext) and
    # not VW-15 (has slash). Should produce no diagnostic.
    stage = StageSpec(name="s", load_from="base", steps=("subdir/some_token",))
    ctx = _ctx()
    validate_post(ctx, _make_manifest(stages=(stage,)), _empty_graph(), rewritten=())
    assert "VW-15" not in _codes(ctx)


def test_validator_brace_balance_skips_when_read_text_fails() -> None:
    from chopper.validator import validate_post

    class _ReadFail(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            raise OSError("denied")

    fs = _ReadFail()
    rel = DOMAIN / "x.tcl"
    fs.write_text(rel, "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    validate_post(ctx, _make_manifest(), _empty_graph(), rewritten=(rel,))
    # Read failure -> silently skipped; no VE-16 emitted.
    assert "VE-16" not in _codes(ctx)


def test_validator_proc_set_check_skips_when_read_text_fails() -> None:
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_trimmer import FileOutcome, TrimReport
    from chopper.validator import validate_post

    class _ReadFail(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            raise OSError("denied")

    fs = _ReadFail()
    rel = Path("trimmed.tcl")
    fs.write_text(DOMAIN / rel, "proc keep {} {}\n")
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=20,
        bytes_out=20,
        procs_kept=("trimmed.tcl::keep",),
        procs_removed=(),
    )
    report = TrimReport(
        outcomes=(outcome,),
        files_copied=0,
        files_trimmed=1,
        files_removed=0,
        procs_kept_total=1,
        procs_removed_total=0,
    )
    ctx = _ctx(fs=fs)
    validate_post(
        ctx,
        _make_manifest(files={rel: FileTreatment.PROC_TRIM}),
        _empty_graph(),
        rewritten=(),
        trim_report=report,
    )
    # Read failure on proc-set check -> no proc-set-mismatch VW-10
    vw10 = [d for d in ctx.diag.snapshot() if d.code == "VW-10" and d.context.get("reason") == "proc-set-mismatch"]
    assert vw10 == []


def test_validator_proc_set_emits_vw10_with_unexpected_only_message() -> None:
    """When trim_report says no procs but parsed file has one extra, VW-10 fires."""
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import ProcDecision
    from chopper.core.models_trimmer import FileOutcome, TrimReport
    from chopper.validator import validate_post

    fs = InMemoryFS()
    rel = Path("oops.tcl")
    fs.write_text(DOMAIN / rel, "proc unexpected {} { return 1 }\n")
    keep = "oops.tcl::expected"
    outcome = FileOutcome(
        path=rel,
        treatment=FileTreatment.PROC_TRIM,
        bytes_in=10,
        bytes_out=10,
        procs_kept=(keep,),
        procs_removed=(),
    )
    report = TrimReport(
        outcomes=(outcome,),
        files_copied=0,
        files_trimmed=1,
        files_removed=0,
        procs_kept_total=1,
        procs_removed_total=0,
    )
    ctx = _ctx(fs=fs)
    validate_post(
        ctx,
        _make_manifest(
            files={rel: FileTreatment.PROC_TRIM},
            procs={
                keep: ProcDecision(
                    canonical_name=keep,
                    source_file=rel,
                    selection_source="base:procedures.include",
                )
            },
        ),
        _empty_graph(),
        rewritten=(),
        trim_report=report,
    )
    msgs = [d.message for d in ctx.diag.snapshot() if d.code == "VW-10"]
    assert any("missing" in m and "unexpected" in m for m in msgs)


def test_validator_vw06_accepts_suffix_match_for_bare_source() -> None:
    """VW-06 must not fire when callee path bare-matches a surviving file."""
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import DependencyGraph, Edge, ProcDecision
    from chopper.validator import validate_post

    caller = "a.tcl::foo"
    surviving = Path("subdir/lib.tcl")
    manifest = _make_manifest(
        files={Path("a.tcl"): FileTreatment.FULL_COPY, surviving: FileTreatment.FULL_COPY},
        procs={
            caller: ProcDecision(
                canonical_name=caller,
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            )
        },
    )
    edge = Edge(
        caller=caller,
        callee="lib.tcl",
        kind="source",
        status="resolved",
        token="source lib.tcl",
        line=1,
    )
    graph = DependencyGraph(
        pi_seeds=(caller,),
        nodes=(caller,),
        pt=(),
        edges=(edge,),
        reachable_from_includes=frozenset({caller}),
    )
    ctx = _ctx()
    validate_post(ctx, manifest, graph, rewritten=())
    assert "VW-06" not in _codes(ctx)


def test_brace_delta_skips_braces_inside_quoted_strings() -> None:
    """_brace_delta must treat { and } inside a double-quoted string as
    non-structural so they don't affect the depth count (ARCHITECTURE.md Sec.5.4.9)."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    # Balanced: outer braces cancel, inner braces inside quotes are skipped.
    text = 'proc foo {} { set x "{open brace unclosed" }'
    delta = _brace_delta(text)
    assert delta == 0


def test_brace_delta_prev_open_brace_quote_is_literal() -> None:
    """When a double-quote is immediately preceded by '{', it is a literal
    character in a braced word per the Tcl 'Endekas rule 6'.  The spec
    example is ``set q {"}`` -- the ``}`` must close the brace, not be
    consumed by a quote-scan, so depth returns to zero (ARCHITECTURE.md
    Sec.5.4.9 / IMPLEMENTATION.md P-01a)."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    # set q {"} -- the " is literal (prev is {), the } closes the brace.
    text = 'set q {"}'
    delta = _brace_delta(text)
    assert delta == 0


def test_brace_delta_quoted_string_with_escaped_quote() -> None:
    """Backslash-escaped quotes inside a quoted string must not end the string
    scan prematurely.  The brace counter must still reach zero."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    # proc with a quoted arg containing escaped quote -- braces still balance.
    text = 'proc foo {} { set x "he said \\"hello\\"" }'
    delta = _brace_delta(text)
    assert delta == 0


def test_brace_delta_braced_word_quote_space_quote_is_literal() -> None:
    """Brace-depth-aware fix: inside a ``{...}`` braced data word that opens
    with a ``"``, EVERY ``"`` is a literal byte -- including a second quote
    separated by a space (``{" "}``).  The original checker special-cased
    only the immediately-after-brace quote, so the second quote opened a
    phantom quoted string that swallowed the closing ``}`` (false-positive
    VE-16).  These must all return 0 now (ARCHITECTURE.md Sec.5.4.9 /
    IMPLEMENTATION.md P-01a; mirrors tokenizer ``data_quote_brace_levels``)."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    assert _brace_delta('set q {" "}') == 0
    assert _brace_delta('{" "}') == 0
    # Real-world repro shape from fev_conformal default_procs.tcl:409.
    assert _brace_delta('regsub -all { \\s+} $X {" "} X') == 0


def test_brace_delta_regression_guards_for_legal_quote_constructs() -> None:
    """Regression guards: the brace-depth fix must NOT change the previously
    correct behaviours.  ``puts "{"`` opens a real quoted string at depth 0
    (delta 0) and ``set q {"}`` keeps the immediately-after-brace literal
    quote (delta 0)."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    assert _brace_delta('puts "{"') == 0
    assert _brace_delta('set q {"}') == 0


def test_brace_delta_repro_fixture_yields_zero() -> None:
    """The edge-case fixture capturing the ``{" "}`` braced-data-word
    construct (the same shape that caused the live false-positive VE-16 on
    the fev_conformal domain) must balance to delta 0 end-to-end."""
    from chopper.validator.functions import _brace_delta  # type: ignore[attr-defined]

    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "edge_cases" / "parser_braced_word_quote_space_quote.tcl"
    )
    assert _brace_delta(fixture.read_text(encoding="utf-8")) == 0


def test_check_brace_balance_no_ve16_on_braced_word_quote_space_quote() -> None:
    """End-to-end: a rewritten file containing the ``{" "}`` construct must
    NOT emit VE-16 from the post-trim brace-balance check."""
    from chopper.validator.functions import _check_brace_balance

    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "edge_cases" / "parser_braced_word_quote_space_quote.tcl"
    )
    ctx = _ctx()
    target = DOMAIN / "default_procs.tcl"
    ctx.fs.write_text(target, fixture.read_text(encoding="utf-8"))
    _check_brace_balance(ctx, (target,))
    assert "VE-16" not in _codes(ctx)


def test_check_feature_domain_skips_feature_with_none_domain() -> None:
    """_check_feature_domain must skip features where domain is None (no VW-04 emitted)."""
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig
    from chopper.validator.functions import _check_feature_domain

    base = BaseJson(source_path=Path("base.json"), domain="my_tool")
    feature = FeatureJson(
        source_path=Path("feat.json"),
        name="feat",
        domain=None,  # <-- must be silently skipped
    )
    loaded = LoadedConfig(base=base, features=(feature,))
    ctx = _ctx()
    _check_feature_domain(ctx, loaded)
    # No VW-04 should be emitted when domain is None.
    assert "VW-04" not in _codes(ctx)


def test_check_pattern_exclude_does_not_emit_vw03() -> None:
    """_check_pattern must NOT emit VW-03 for exclude patterns (is_include=False)."""
    from chopper.validator.functions import _check_pattern

    fs = InMemoryFS()
    ctx = _ctx(fs=fs)
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    fs.write_text(DOMAIN / "present.tcl", "proc foo {} {}")

    # A glob exclude pattern that matches nothing -- VW-03 must NOT fire for excludes.
    _check_pattern(ctx, "*.absent", source_key="base", field="files.exclude", is_include=False)
    assert "VW-03" not in _codes(ctx)


def test_check_pattern_literal_not_found_emits_ve06() -> None:
    """_check_pattern must emit VE-06 when a literal include path does not exist under domain."""
    from chopper.validator.functions import _check_pattern

    fs = InMemoryFS()
    ctx = _ctx(fs=fs)
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    # 'nonexistent.tcl' is NOT written to the filesystem.
    _check_pattern(ctx, "nonexistent.tcl", source_key="base", field="files.include", is_include=True)
    assert "VE-06" in _codes(ctx)


def test_check_pattern_exclude_literal_missing_emits_vw25() -> None:
    """_check_pattern must emit VW-25 (not VE-06) for a missing literal files.exclude path."""
    from chopper.validator.functions import _check_pattern

    fs = InMemoryFS()
    ctx = _ctx(fs=fs)
    fs.mkdir(DOMAIN, parents=True, exist_ok=True)
    # 'gone.tcl' is NOT written -- a literal exclude whose target is already absent.
    _check_pattern(ctx, "gone.tcl", source_key="base", field="files.exclude", is_include=False)
    codes = _codes(ctx)
    assert "VW-25" in codes
    assert "VE-06" not in codes


# =========================================================================
# BATCH 2 -- Targeted tests for remaining coverage gaps


def test_check_feature_domains_match_no_vw04() -> None:
    """check_feature_domains emits no VW-04 when feature.domain matches base (branch 124->121)."""
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig
    from chopper.validator.functions import validate_pre

    fs = InMemoryFS()
    base_path = DOMAIN / "base.json"
    feat_path = DOMAIN / "feat.json"
    fs.write_text(base_path, '{"domain":"my_domain"}')
    fs.write_text(feat_path, '{"name":"feat","domain":"my_domain"}')

    base = BaseJson(source_path=base_path, domain="my_domain")
    # Feature has domain matching base -> no VW-04
    feature = FeatureJson(source_path=feat_path, name="feat", domain="my_domain")
    loaded = LoadedConfig(base=base, features=(feature,))

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    sink = _Sink()
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=sink, progress=_Progress())

    validate_pre(ctx2, loaded)
    vw04s = [d for d in sink._emissions if d.code == "VW-04"]
    assert vw04s == []


def test_validate_post_removed_file_not_present_no_mismatch() -> None:
    """validate_post: file marked REMOVE that does NOT exist -> no mismatch diagnostic (432->443)."""
    from chopper.core.models_common import FileTreatment
    from chopper.validator.functions import _check_trim_outputs

    fs = InMemoryFS()
    # Do NOT write removed_file.tcl -> ctx.fs.exists returns False -> 432->443

    outcome = _make_file_outcome(
        "removed_file.tcl",
        FileTreatment.REMOVE,
        bytes_in=100,
        bytes_out=0,
    )
    trim_report = _make_trim_report(outcome)

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    sink = _Sink()
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=sink, progress=_Progress())

    _check_trim_outputs(ctx2, trim_report)
    # No mismatch diagnostic should be emitted (file doesn't exist = already removed)
    assert not any(d.code.startswith("VE") for d in sink._emissions)


def test_glob_has_matches_oserror_in_list_continues() -> None:
    """_glob_has_matches continues past OSError from ctx.fs.list (lines 269-270)."""
    from chopper.validator.functions import _glob_has_matches

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "foo.tcl", "")
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    with patch.object(fs, "list", side_effect=OSError("mocked list failure")):
        result = _glob_has_matches(ctx2, "**/*.tcl")

    assert result is False  # OSError -> continue -> no match found


def test_glob_has_matches_child_outside_domain_skipped() -> None:
    """_glob_has_matches skips children whose relative_to raises ValueError (274-275)."""
    from chopper.validator.functions import _glob_has_matches

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "foo.tcl", "")
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # Return a path that is NOT under DOMAIN -> relative_to raises ValueError
    outside_path = Path("/other/bar.tcl")
    with patch.object(fs, "list", return_value=[outside_path]):
        result = _glob_has_matches(ctx2, "**/*.tcl")

    assert result is False  # ValueError -> continue -> no match


def test_glob_has_matches_regex_pattern_matches_returns_true() -> None:
    """_glob_has_matches returns True via regex branch (lines 287-288) for ** glob."""
    from chopper.validator.functions import _glob_has_matches

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "lib" / "foo.tcl", "")
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # ** pattern -> glob_to_regex returns a Pattern; fullmatch on "lib/foo.tcl" returns True
    result = _glob_has_matches(ctx2, "**/*.tcl")
    assert result is True  # lines 287-288 covered


def test_glob_has_matches_regex_pattern_skips_non_matching_file() -> None:
    """When regex is not None but fullmatch is False for a file, the loop
    continues to the next child (covers branch 287->271)."""
    from chopper.validator.functions import _glob_has_matches

    fs = InMemoryFS()
    # aaa.py sorts before zzz.tcl -- regex skips aaa.py then matches zzz.tcl
    fs.write_text(DOMAIN / "aaa.py", "")
    fs.write_text(DOMAIN / "zzz.tcl", "")
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    result = _glob_has_matches(ctx2, "**/*.tcl")
    assert result is True  # zzz.tcl matches after skipping aaa.py


def test_glob_has_matches_fnmatchcase_no_match_continues() -> None:
    """_glob_has_matches continues when fnmatchcase returns False (289->271)."""
    from chopper.validator.functions import _glob_has_matches

    fs = InMemoryFS()
    # file is foo.py but pattern is *.tcl -> no match
    fs.write_text(DOMAIN / "foo.py", "")
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=True)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    # Non-** pattern -> glob_to_regex returns None, _fnmatchcase("foo.py", "*.tcl") is False
    result = _glob_has_matches(ctx2, "*.tcl")
    assert result is False


def test_brace_delta_full_line_comment_skipped() -> None:
    """_brace_delta skips braces in full-line comments (lines 672-674)."""
    from chopper.validator.functions import _brace_delta

    # Comment line contains unmatched braces -- they must not affect the count
    text = "# this is a comment with { and }\nset x {hello}\n"
    result = _brace_delta(text)
    assert result == 0  # balanced: one { one } from set x {hello}


def test_brace_delta_unclosed_quote_at_end_of_text() -> None:
    """_brace_delta handles text where opening quote is at the very end (689->698)."""
    from chopper.validator.functions import _brace_delta

    # Text ends with unmatched " -- the inner while loop exits immediately (i >= n)
    result = _brace_delta('some text "')
    assert result == 0  # No braces in the content


def test_looks_like_bare_proc_returns_false_for_file_extension() -> None:
    """_looks_like_bare_proc returns False when head ends with a file extension (line 919)."""
    from chopper.validator.functions import _looks_like_bare_proc

    # Step that looks like a file with extension -> not a bare proc
    assert _looks_like_bare_proc("foo.tcl") is False
    assert _looks_like_bare_proc("run_setup.py") is False
    # Non-file-extension -> bare proc
    assert _looks_like_bare_proc("my_proc") is True


def test_looks_like_bare_proc_returns_false_for_variable_refs_and_braces() -> None:
    """_looks_like_bare_proc returns False for Tcl variable refs ($var) and syntax artifacts."""
    from chopper.validator.functions import _looks_like_bare_proc

    # Variable reference -- not a bare proc call
    assert _looks_like_bare_proc("$env(HOME)") is False
    assert _looks_like_bare_proc("$var") is False
    # Syntax artifacts
    assert _looks_like_bare_proc("}") is False
    assert _looks_like_bare_proc("{") is False
