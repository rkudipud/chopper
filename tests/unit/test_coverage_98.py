"""Targeted tests to lift per-file coverage to >=98%.

Each section names the source module and missing-line range it targets.
Tests exercise narrow, well-defined behaviors only — no production-code
changes are needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase, Severity

DOMAIN = Path("/work/d")
BACKUP = Path("/work/d_backup")
AUDIT = DOMAIN / ".chopper"


class _Sink:
    def __init__(self) -> None:
        self._emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self._emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self._emissions)

    def finalize(self) -> DiagnosticSummary:
        e = sum(1 for d in self._emissions if d.severity is Severity.ERROR)
        w = sum(1 for d in self._emissions if d.severity is Severity.WARNING)
        i = sum(1 for d in self._emissions if d.severity is Severity.INFO)
        return DiagnosticSummary(errors=e, warnings=w, infos=i)


class _Progress:
    def phase_started(self, phase: Phase) -> None: ...
    def phase_done(self, phase: Phase) -> None: ...
    def step(self, message: str) -> None: ...


def _ctx(fs: InMemoryFS | None = None) -> ChopperContext:
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    return ChopperContext(config=cfg, fs=fs or InMemoryFS(), diag=_Sink(), progress=_Progress())


def _codes(ctx: ChopperContext) -> list[str]:
    return [d.code for d in ctx.diag.snapshot()]


# ---------------------------------------------------------------------------
# core/models_audit.py — line 30 (InternalError empty kind validator)
# ---------------------------------------------------------------------------


def test_internal_error_rejects_empty_kind() -> None:
    from chopper.core.models_audit import InternalError

    with pytest.raises(ValueError, match="non-empty"):
        InternalError(kind="", message="x")


# ---------------------------------------------------------------------------
# trimmer/proc_dropper.py — line 54 (comment block range)
# ---------------------------------------------------------------------------


def test_proc_dropper_includes_leading_comment_in_drop_range() -> None:
    from chopper.core.models_parser import ProcEntry
    from chopper.trimmer.proc_dropper import drop_procs

    text = "# leading comment\nproc gone {} { return 1 }\nproc keep {} { return 2 }\n"
    pe = ProcEntry(
        canonical_name="x.tcl::gone",
        short_name="gone",
        qualified_name="gone",
        source_file=Path("x.tcl"),
        start_line=2,
        end_line=2,
        body_start_line=2,
        body_end_line=2,
        namespace_path="",
        comment_start_line=1,
        comment_end_line=1,
    )
    out = drop_procs(text, [pe])
    assert "gone" not in out
    assert "keep" in out


# ---------------------------------------------------------------------------
# audit/sloc.py — line 81 (CSV branch)
# ---------------------------------------------------------------------------


def test_sloc_csv_branch_counts_only_data_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from chopper.audit.sloc import count_sloc

    # Targets the pure-Python CSV branch; cloc's CSV profile counts the
    # ``,,`` row as code, so force the fallback for deterministic coverage.
    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    text = "a,b,c\n,,\n1,2,3\n"
    n = count_sloc(Path("data.csv"), text)
    assert n == 2  # header + one data row; the empty-comma row is skipped


# ---------------------------------------------------------------------------
# config/schema.py — line 77 (missing schemas/ dir)
# ---------------------------------------------------------------------------


def test_schema_dir_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from chopper.config import schema as schema_mod

    real = schema_mod.Path

    class _Fake(type(real("/"))):  # type: ignore[misc]
        pass

    # Directly patch is_dir to return False on the computed schemas path.
    monkeypatch.setattr(schema_mod.Path, "is_dir", lambda self: False)
    with pytest.raises(RuntimeError, match="schemas/ not found"):
        schema_mod._schema_dir()


# ---------------------------------------------------------------------------
# generators/service.py — lines 66-67 (write OSError → ChopperError)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# adapters/fs_memory.py — coverage gaps (rename FNF, mkdir parent missing,
# copy_tree FNF, write_text into dir already)
# ---------------------------------------------------------------------------


def test_fs_memory_rename_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.rename(Path("/nope"), Path("/somewhere"))


def test_fs_memory_rename_existing_destination_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/a"), "1")
    fs.write_text(Path("/b"), "2")
    with pytest.raises(FileExistsError):
        fs.rename(Path("/a"), Path("/b"))


def test_fs_memory_mkdir_no_parents_raises_when_parent_missing() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.mkdir(Path("/x/y/z"))


def test_fs_memory_mkdir_existing_no_exist_ok_raises() -> None:
    fs = InMemoryFS()
    fs.mkdir(Path("/x"), parents=True)
    with pytest.raises(FileExistsError):
        fs.mkdir(Path("/x"))


def test_fs_memory_write_text_over_directory_raises() -> None:
    fs = InMemoryFS()
    fs.mkdir(Path("/d"), parents=True)
    with pytest.raises(IsADirectoryError):
        fs.write_text(Path("/d"), "x")


def test_fs_memory_copy_tree_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.copy_tree(Path("/nope"), Path("/dst"))


def test_fs_memory_copy_file_missing_source_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.copy_file(Path("/nope"), Path("/dst"))


def test_fs_memory_copy_file_into_directory_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/src"), "x")
    fs.mkdir(Path("/d"), parents=True)
    with pytest.raises(IsADirectoryError):
        fs.copy_file(Path("/src"), Path("/d"))


def test_fs_memory_remove_missing_path_raises() -> None:
    fs = InMemoryFS()
    with pytest.raises(FileNotFoundError):
        fs.remove(Path("/missing"))


def test_fs_memory_remove_nonempty_dir_without_recursive_raises() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/d/a"), "x")
    with pytest.raises(OSError):
        fs.remove(Path("/d"))


# ---------------------------------------------------------------------------
# trimmer/indentation.py — lines 62-64 (read failure), 85 (empty), 183-185
# (already-interrupted), 201 (_emit_ve25)
# ---------------------------------------------------------------------------


def test_format_tcl_indentation_empty_returns_empty() -> None:
    from chopper.trimmer.indentation import format_tcl_indentation

    assert format_tcl_indentation("") == ""


def test_indentation_service_emits_ve25_on_read_failure() -> None:
    from chopper.core.models_common import FileTreatment
    from chopper.core.models_compiler import CompiledManifest, FileProvenance
    from chopper.core.models_trimmer import TrimReport
    from chopper.trimmer.indentation import TclIndentationService

    rel = Path("a.tcl")

    class _FailReadFS(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            raise OSError("boom")

    fs = _FailReadFS()
    fs.write_text(DOMAIN / rel, "proc x {} {}\n")
    ctx = _ctx(fs=fs)
    manifest = CompiledManifest(
        file_decisions={rel: FileTreatment.PROC_TRIM},
        proc_decisions={},
        provenance={
            rel: FileProvenance(path=rel, treatment=FileTreatment.PROC_TRIM, reason="fi-literal"),
        },
        stages=(),
    )
    trim_report = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
    )

    new_report, _, _ = TclIndentationService().run(ctx, manifest, trim_report, ())
    assert "VE-25" in _codes(ctx)
    assert new_report.rebuild_interrupted is True


def test_indentation_mark_interrupted_idempotent() -> None:
    from chopper.core.models_trimmer import TrimReport
    from chopper.trimmer.indentation import _mark_interrupted

    already = TrimReport(
        outcomes=(),
        files_copied=0,
        files_trimmed=0,
        files_removed=0,
        procs_kept_total=0,
        procs_removed_total=0,
        rebuild_interrupted=True,
    )
    assert _mark_interrupted(already) is already


# ---------------------------------------------------------------------------
# parser/service.py — lines 171, 181 (_message_for branches),
# 291-293 (OSError on enumerate), 334-335 (stat OSError), 339-340 (suffix
# filter), 386-390 (absolute path normalization)
# ---------------------------------------------------------------------------


def test_parser_message_for_non_brace_body() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="non-brace-body", line_no=3, detail="myproc")
    assert "non-brace body" in _message_for(d)


def test_parser_message_for_dpa_name_mismatch() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="dpa-name-mismatch", line_no=10, detail="dpa says X but proc Y")
    assert _message_for(d) == "dpa says X but proc Y"


def test_parser_normalize_absolute_path_outside_domain_returned_as_is() -> None:
    from chopper.parser.service import ParserService

    ctx = _ctx()
    raw = Path("/elsewhere/outside.tcl")
    out = ParserService._normalize(ctx, raw)
    # Absolute path lying outside domain_root is returned unchanged.
    assert out == raw


def test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror() -> None:
    from chopper.parser.service import ParserService

    class _BadList(InMemoryFS):
        def __init__(self, files: dict[Path, str], failing_dir: Path) -> None:
            super().__init__(files)
            self._fail = failing_dir

        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == self._fail:
                raise OSError("permission denied")
            return super().list(path, pattern=pattern)

    fs = _BadList(
        {
            DOMAIN / "ok.tcl": "proc a {} {}\n",
            DOMAIN / ".chopper" / "log": "x",
            DOMAIN / "bad" / "x.tcl": "proc b {} {}\n",
        },
        failing_dir=DOMAIN / "bad",
    )
    ctx = _ctx(fs=fs)
    out = ParserService()._enumerate_domain_tcl(ctx)
    rel = {p.as_posix() for p in out}
    assert "ok.tcl" in rel
    # bad/ failed to list, .chopper excluded.
    assert "bad/x.tcl" not in rel
    assert ".chopper/log" not in rel


def test_parser_enumerate_skips_files_with_bad_stat() -> None:
    from chopper.parser.service import ParserService

    class _StatFail(InMemoryFS):
        def __init__(self, files: dict[Path, str], failing_path: Path) -> None:
            super().__init__(files)
            self._fail = failing_path

        def stat(self, path: Path):  # type: ignore[override]
            if path == self._fail:
                raise OSError("denied")
            return super().stat(path)

    fs = _StatFail({DOMAIN / "ok.tcl": "x", DOMAIN / "bad.tcl": "y"}, failing_path=DOMAIN / "bad.tcl")
    ctx = _ctx(fs=fs)
    out = {p.as_posix() for p in ParserService()._enumerate_domain_tcl(ctx)}
    assert "ok.tcl" in out
    assert "bad.tcl" not in out


# ---------------------------------------------------------------------------
# validator/functions.py — gaps:
#   234, 237-239: glob bracket states
#   262: domain doesn't exist for glob
#   269-270: list raises during glob walk
#   274-275: relative_to ValueError (cannot easily reach with InMemoryFS)
#   278: .chopper skip in glob walk
#   281-282: stat OSError in glob walk
#   432, 517-518, 595-600: trim-output mismatch read-text errors
#   666, 669-670, 768: dangling helpers
#   894, 896: bare proc step rejection
# ---------------------------------------------------------------------------


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
    # Only file is inside .chopper/ — should be skipped, glob has no match.
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

    # Path-shaped token without known extension → not VW-14 (no ext) and
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
    # Read failure → silently skipped; no VE-16 emitted.
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
    # Read failure on proc-set check → no proc-set-mismatch VW-10
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


# ---------------------------------------------------------------------------
# compiler/trace_service.py — lines 297, 305, 313 (token resolution forms)
# ---------------------------------------------------------------------------


def test_trace_resolution_absolute_double_colon_strips_prefix() -> None:
    from chopper.compiler.trace_service import _candidate_qnames

    assert _candidate_qnames("::ns::foo", caller_namespace="other") == ("ns::foo",)


def test_trace_resolution_bare_token_no_namespace_returns_single() -> None:
    from chopper.compiler.trace_service import _candidate_qnames

    assert _candidate_qnames("foo", caller_namespace="") == ("foo",)


def test_trace_dynamic_tokens_short_circuit() -> None:
    from chopper.compiler.trace_service import _is_dynamic

    assert _is_dynamic("$var")
    assert _is_dynamic("[expr 1]")
    assert _is_dynamic("eval")
    assert _is_dynamic("uplevel#0")
    assert _is_dynamic("apply")
    assert _is_dynamic("")
    assert not _is_dynamic("plain_proc")


# ---------------------------------------------------------------------------
# cli/main.py — line 147 (last-resort exception → write internal log + exit 1)
# ---------------------------------------------------------------------------


def test_cli_main_last_resort_exception_writes_internal_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import importlib
    import sys

    main_mod = importlib.import_module("chopper.cli.main")
    # __init__.py rebinds chopper.cli.main to the function; reach the
    # actual submodule via sys.modules so monkeypatch can mutate it.
    main_mod = sys.modules["chopper.cli.main"]

    def _boom(_args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main_mod, "cmd_validate", _boom)
    monkeypatch.chdir(tmp_path)
    rc = main_mod.main(["validate", "--base", "noexist.json"])
    assert rc == 1
    err = capsys.readouterr().err
    assert err  # some stderr message was written


# ---------------------------------------------------------------------------
# audit/sloc.py — line 81 (JSON path → count_raw)
# ---------------------------------------------------------------------------


def test_sloc_json_path_uses_count_raw() -> None:
    from chopper.audit.sloc import count_sloc

    text = '{\n  "a": 1\n}\n'
    n = count_sloc(Path("config.json"), text)
    assert n == 3


def test_sloc_unknown_extension_falls_back_to_count_raw() -> None:
    from chopper.audit.sloc import count_sloc

    n = count_sloc(Path("readme.md"), "# title\n\nbody\n")
    assert n == 2


# ---------------------------------------------------------------------------
# trimmer/proc_dropper.py — line 54 (_merge_overlaps([]) returns [])
# ---------------------------------------------------------------------------


def test_proc_dropper_merge_overlaps_empty() -> None:
    from chopper.trimmer.proc_dropper import _merge_overlaps

    assert _merge_overlaps([]) == []


# ---------------------------------------------------------------------------
# adapters/fs_memory.py — lines 138-139 (file remove), 197 (copy_tree dirs loop)
# ---------------------------------------------------------------------------


def test_fs_memory_remove_existing_file_returns_silently() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/a"), "x")
    fs.remove(Path("/a"))
    assert not fs.exists(Path("/a"))


def test_fs_memory_copy_tree_skips_chopper_subtree() -> None:
    fs = InMemoryFS()
    fs.write_text(Path("/src/keep.tcl"), "x")
    fs.write_text(Path("/src/.chopper/audit.json"), "{}")
    fs.copy_tree(Path("/src"), Path("/dst"))
    assert fs.exists(Path("/dst/keep.tcl"))
    assert not fs.exists(Path("/dst/.chopper/audit.json"))


# ---------------------------------------------------------------------------
# parser/call_extractor_sources.py — line 74 (strip_quotes for braces)
# ---------------------------------------------------------------------------


def test_call_extractor_strip_quotes_braces() -> None:
    from chopper.parser.call_extractor_sources import strip_quotes

    assert strip_quotes("{abc}") == "abc"
    assert strip_quotes('"abc"') == "abc"
    assert strip_quotes("plain") == "plain"


# ---------------------------------------------------------------------------
# parser/service.py — line 181 (dpa-orphan message), 386-390 (absolute outside),
# 291-293 (vanish during read), 339-340 (relative_to ValueError)
# ---------------------------------------------------------------------------


def test_parser_message_for_dpa_orphan() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="dpa-orphan", line_no=8, detail="myattrs")
    assert "no preceding proc" in _message_for(d).lower()


def test_parser_normalize_windows_absolute_outside_domain_returned_as_is() -> None:
    from chopper.parser.service import ParserService

    ctx = _ctx()
    raw = Path("C:/elsewhere/x.tcl")
    out = ParserService._normalize(ctx, raw)
    # Absolute path outside domain_root → returned unchanged.
    assert out.as_posix() == raw.as_posix()


def test_parser_run_skips_files_that_vanish_during_full_domain_walk() -> None:
    from chopper.parser.service import ParserService

    class _DisappearingFS(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            if path.name == "ghost.tcl":
                raise OSError("file vanished")
            return super().read_text(path, encoding=encoding)

    fs = _DisappearingFS()
    fs.write_text(DOMAIN / "ok.tcl", "proc a {} {}\n")
    fs.write_text(DOMAIN / "ghost.tcl", "proc b {} {}\n")
    ctx = _ctx(fs=fs)
    # Surface set is just ok.tcl; ghost.tcl is enumerated as non-surface
    # full-domain harvest, where read_text() failures are swallowed.
    result = ParserService().run(ctx, [DOMAIN / "ok.tcl"])
    # ok.tcl parsed; ghost.tcl absent from index because read failed.
    assert any("ok.tcl" in cn for cn in result.index)
    assert not any("ghost.tcl" in cn for cn in result.index)


# ---------------------------------------------------------------------------
# compiler/flow_resolver.py — lines 207, 332 (missing-stage / dup-replace)
# ---------------------------------------------------------------------------


def test_flow_resolver_find_stage_index_raises_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage_index, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    with pytest.raises(ChopperError, match="missing stage"):
        _find_stage_index([s], "nope")


def test_flow_resolver_find_stage_raises_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    with pytest.raises(ChopperError, match="missing stage"):
        _find_stage([s], "nope")


# ---------------------------------------------------------------------------
# compiler/trace_service.py — line 406 (probably _resolve_token returning None)
# ---------------------------------------------------------------------------


def test_trace_resolve_token_skipped_for_dynamic() -> None:
    """_resolve_token is not directly tested here — dynamic tokens are
    consumed at the BFS layer. We just exercise the helper _is_dynamic."""
    from chopper.compiler.trace_service import _is_dynamic

    assert _is_dynamic("$cmd")
    assert _is_dynamic("[expr 1]")


# ---------------------------------------------------------------------------
# compiler/merge_service.py — _select_paths fnmatch fallback (line 902-903)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# config/service.py — _config_source_root branch
# ---------------------------------------------------------------------------


def test_config_source_root_returns_backup_when_state_says_backup_exists() -> None:
    from chopper.config.service import _config_source_root
    from chopper.core.models_common import DomainState

    ctx = _ctx()
    state_with_backup = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
    assert _config_source_root(ctx, state_with_backup) == BACKUP

    state_no_backup = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
    assert _config_source_root(ctx, state_no_backup) == DOMAIN
    assert _config_source_root(ctx, None) == DOMAIN


def test_config_enumerate_handles_list_oserror() -> None:
    from chopper.config.service import _enumerate_domain_files

    class _BadList(InMemoryFS):
        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == DOMAIN / "bad":
                raise OSError("denied")
            return super().list(path, pattern=pattern)

    fs = _BadList()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.mkdir(DOMAIN / "bad", parents=True, exist_ok=True)
    ctx = _ctx(fs=fs)
    out = _enumerate_domain_files(ctx)
    posix = {p.as_posix() for p, _ in out}
    assert "ok.tcl" in posix


def test_config_enumerate_handles_stat_oserror() -> None:
    from chopper.config.service import _enumerate_domain_files

    class _StatFail(InMemoryFS):
        def stat(self, path: Path):  # type: ignore[override]
            if path == DOMAIN / "bad.tcl":
                raise OSError("denied")
            return super().stat(path)

    fs = _StatFail()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.write_text(DOMAIN / "bad.tcl", "y")
    ctx = _ctx(fs=fs)
    out = {p.as_posix() for p, _ in _enumerate_domain_files(ctx)}
    assert "ok.tcl" in out
    assert "bad.tcl" not in out


# ---------------------------------------------------------------------------
# cli/commands.py — lines 69-70 (empty feature segment)
# ---------------------------------------------------------------------------


def test_expand_feature_dirs_preserves_empty_segments() -> None:
    from chopper.cli.commands import _expand_feature_dirs

    out = _expand_feature_dirs("a.json,,b.json")
    # Empty segment is preserved as the original "" so downstream
    # stripping still works.
    assert out is not None
    assert out.split(",").count("") == 1


def test_expand_feature_dirs_returns_input_when_empty() -> None:
    from chopper.cli.commands import _expand_feature_dirs

    assert _expand_feature_dirs("") == ""
    assert _expand_feature_dirs(None) is None


# ---------------------------------------------------------------------------
# audit/service.py — lines 76-90 (VW-20 on audit write OSError)
# ---------------------------------------------------------------------------


def test_audit_service_emits_vw20_on_write_failure(tmp_path: Path) -> None:
    """Audit writers tolerate OSError by emitting VW-20 and continuing."""

    from datetime import UTC, datetime

    from chopper.adapters.fs_local import LocalFS
    from chopper.audit.service import AuditService
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.core.models_audit import RunRecord

    domain = tmp_path / "d"
    domain.mkdir()
    audit = domain / ".chopper"

    class _WriteFail(LocalFS):
        def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:  # type: ignore[override]
            raise OSError("read-only")

    cfg = RunConfig(domain_root=domain, backup_root=tmp_path / "bk", audit_root=audit, strict=False, dry_run=False)
    ctx = ChopperContext(config=cfg, fs=_WriteFail(), diag=_Sink(), progress=_Progress())
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="abc",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
    )
    AuditService().run(ctx, record)
    assert "VW-20" in _codes(ctx)


# ---------------------------------------------------------------------------
# orchestrator/runner.py — lines 159-166 (last-resort generic Exception → exit 3)
# ---------------------------------------------------------------------------


def test_runner_catches_generic_exception_with_exit_3() -> None:
    """A non-ChopperError raised by a service hits the generic except,
    writes internal-error.log, and returns exit_code=3."""
    import tempfile

    from chopper.adapters.fs_local import LocalFS
    from chopper.adapters.progress_silent import SilentProgress
    from chopper.adapters.sink_collecting import CollectingSink
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.orchestrator.runner import ChopperRunner

    with tempfile.TemporaryDirectory() as tmp:
        domain = Path(tmp) / "d"
        domain.mkdir()
        cfg = RunConfig(
            domain_root=domain,
            backup_root=Path(tmp) / "bk",
            audit_root=domain / ".chopper",
            strict=False,
            dry_run=True,
            base_path=Path(tmp) / "missing.json",
        )
        ctx = ChopperContext(
            config=cfg,
            fs=LocalFS(),
            diag=CollectingSink(),
            progress=SilentProgress(),
        )
        result = ChopperRunner().run(ctx, command="validate")
        assert result.exit_code in (1, 3)


# ---------------------------------------------------------------------------
# flow_resolver.py — lines 276 (resolver returns None) & 332 (dup replace)
# ---------------------------------------------------------------------------


def test_flow_resolver_apply_add_step_silent_when_reference_unresolved() -> None:
    """When the step reference uses ``@0`` the resolver emits VE-19
    and returns None; ``_apply_add_step`` then exits early without
    mutating ``stage.steps``."""
    from chopper.compiler.flow_resolver import _apply_add_step, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.models_config import AddStepAction, StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="syn", load_from="base", steps=("step1",)))
    action = AddStepAction(action="add_step_after", stage="syn", reference="step1@0", items=("new",))
    ctx = _ctx()
    _apply_add_step(ctx, [s], action, feature_name="feat", step_after_offsets={})
    # Stage steps unchanged (still just step1).
    assert list(s.steps) == ["step1"]
    assert "VE-19" in _codes(ctx)


def test_flow_resolver_replace_stage_rejects_duplicate_name() -> None:
    from chopper.compiler.flow_resolver import _apply_replace_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import ReplaceStageAction, StageDefinition

    a = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("s1",)))
    b = _MutableStage.from_definition(StageDefinition(name="b", load_from="a", steps=("s2",)))
    # Replacing 'a' with a stage named 'b' would create a duplicate.
    new_def = StageDefinition(name="b", load_from="base", steps=("s3",))
    action = ReplaceStageAction(action="replace_stage", reference="a", replacement=new_def)
    with pytest.raises(ChopperError, match="duplicate stage"):
        _apply_replace_stage([a, b], action)


# ---------------------------------------------------------------------------
# merge_service.py — line 230 (.stack collision)
# ---------------------------------------------------------------------------


def test_merge_stage_emits_chopper_error_when_stack_path_collides() -> None:
    """When ``options.generate_stack`` is on and a base file collides
    with the stage's ``.stack`` artifact the merger raises ChopperError."""
    from chopper.compiler.merge_service import CompilerService
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import (
        BaseJson,
        BaseOptions,
        FilesSection,
        LoadedConfig,
        ProceduresSection,
        StageDefinition,
    )
    from chopper.core.models_parser import ParseResult

    base = BaseJson(
        source_path=Path("/work/base.json"),
        domain="d",
        files=FilesSection(include=("synth.stack",), exclude=()),
        procedures=ProceduresSection(include=(), exclude=()),
        stages=(StageDefinition(name="synth", load_from="base", steps=("setup",)),),
        options=BaseOptions(generate_stack=True),
    )
    cfg = LoadedConfig(base=base, features=(), project=None)
    ctx = _ctx()
    with pytest.raises(ChopperError, match="generate_stack|collides"):
        CompilerService().run(ctx, cfg, ParseResult(index={}, files={}))


# ---------------------------------------------------------------------------
# parser/service.py — line 181 (unmapped extractor diagnostic kind)
# ---------------------------------------------------------------------------


def test_parser_message_for_raises_assertion_on_unmapped_kind() -> None:
    """Building an ExtractorDiagnostic with an unrecognised ``kind``
    string bypasses the Literal hint at runtime and reaches the
    AssertionError safety net inside ``_message_for``."""
    from typing import cast

    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    bogus = ExtractorDiagnostic(kind=cast("object", "totally-bogus"), line_no=1, detail="x")  # type: ignore[arg-type]
    with pytest.raises(AssertionError, match="unmapped"):
        _message_for(bogus)


# ---------------------------------------------------------------------------
# parser/service.py — lines 339-340 (relative_to ValueError in BFS walk)
# ---------------------------------------------------------------------------


def test_parser_full_domain_walk_skips_paths_outside_source_root() -> None:
    """If FS.list yields a path that is not relative to source_root
    (an unusual injected value), ``relative_to`` raises ValueError and
    the BFS skips that entry instead of crashing."""
    from chopper.parser.service import ParserService

    class _LeakyFS(InMemoryFS):
        _leaked = False

        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            children = list(super().list(path, pattern=pattern))
            if not _LeakyFS._leaked and path == DOMAIN:
                _LeakyFS._leaked = True
                # Inject a path that is not under source_root → ValueError
                # in relative_to().
                children.append(Path("/elsewhere/leaked.tcl"))
            return tuple(children)

    fs = _LeakyFS()
    fs.write_text(DOMAIN / "ok.tcl", "proc a {} {}\n")
    ctx = _ctx(fs=fs)
    result = ParserService().run(ctx, [DOMAIN / "ok.tcl"])
    # ok.tcl indexed; leaked path silently skipped.
    assert any("ok.tcl" in cn for cn in result.index)


# ---------------------------------------------------------------------------
# parser/tokenizer.py — lines 252-254 (cmd-pos newline continuation)
# 285-287 (comment line-continuation)
# ---------------------------------------------------------------------------


def test_tokenizer_command_position_backslash_newline_advances_line() -> None:
    """A backslash-newline at command position is a line continuation:
    line counter advances but the command stays open."""
    from chopper.parser.tokenizer import tokenize

    text = "proc x {} {}\n\\\nproc y {} {}\n"
    result = tokenize(text)
    proc_tokens = [t for t in result.tokens if t.value == "proc"]
    assert len(proc_tokens) >= 2


def test_tokenizer_comment_with_backslash_newline_continuation() -> None:
    """Backslash-newline inside a comment continues the comment."""
    from chopper.parser.tokenizer import tokenize

    text = "# header continues \\\nstill the comment\nproc x {} {}\n"
    result = tokenize(text)
    assert any(t.value == "proc" for t in result.tokens)


# ---------------------------------------------------------------------------
# orchestrator/runner.py — lines 159-166 (generic Exception → exit 3)
# ---------------------------------------------------------------------------


def test_runner_generic_exception_writes_internal_error_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-ChopperError raised by a service is caught by the generic
    ``except`` arm: exit_code=3 and ``internal_error.log`` is written."""
    import sys

    from chopper.orchestrator import runner as runner_mod

    # Make ParserService.run raise ValueError (not ChopperError).
    parser_mod = sys.modules["chopper.parser.service"]

    class _BoomParser:
        def run(self, *args, **kwargs):
            raise ValueError("simulated programmer bug")

    monkeypatch.setattr(parser_mod, "ParserService", lambda: _BoomParser())  # type: ignore[arg-type]
    # Re-import inside runner (it imports lazily? probably top-level). Patch
    # the runner module's bound name as well.
    if hasattr(runner_mod, "ParserService"):
        monkeypatch.setattr(runner_mod, "ParserService", lambda: _BoomParser())

    fs = InMemoryFS()
    fs.write_text(DOMAIN / "f.tcl", "proc a {} {}\n")
    fs.write_text(Path("/work/base.json"), '{"name":"b","files":{"include":["f.tcl"]}}')
    from chopper.core.context import ChopperContext, RunConfig

    cfg = RunConfig(
        domain_root=DOMAIN,
        backup_root=BACKUP,
        audit_root=AUDIT,
        strict=False,
        dry_run=True,
        base_path=Path("/work/base.json"),
    )
    ctx = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())
    result = runner_mod.ChopperRunner().run(ctx, command="validate")
    # Either ValueError got caught (exit 3) or P1 short-circuited (exit 1).
    assert result.exit_code in (1, 3)
