"""Unit tests for :mod:`chopper.orchestrator.simulate`.

``simulate_trim_in_memory`` replays the real P5 trim phases against an
in-memory copy of the source tree so ``chopper loc`` can count the
actual trimmed output. These tests verify the replay rebuilds the
domain correctly **and** leaves the real on-disk source untouched.
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters.fs_local import LocalFS
from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance, ProcDecision
from chopper.core.models_config import BaseJson, LoadedConfig
from chopper.core.models_parser import ParsedFile, ParseResult, ProcEntry
from chopper.orchestrator.simulate import SimulatedTrim, simulate_trim_in_memory


class _Sink:
    def emit(self, _d: Diagnostic) -> None:
        return None

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return ()

    def finalize(self) -> DiagnosticSummary:
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _Progress:
    def phase_started(self, _phase: Phase) -> None:
        return None

    def phase_done(self, _phase: Phase) -> None:
        return None

    def step(self, _message: str) -> None:
        return None


def _ctx(tmp_path: Path) -> ChopperContext:
    domain = tmp_path / "d"
    domain.mkdir()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "d_backup",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=True,
    )
    return ChopperContext(config=cfg, fs=LocalFS(), diag=_Sink(), progress=_Progress())


def test_simulate_rebuilds_domain_and_leaves_real_disk_untouched(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    domain = ctx.config.domain_root

    keep_text = "proc keep {} { return 1 }\n"
    trim_text = "proc stay {} {\n    return 1\n}\nproc drop {} {\n    return 2\n}\n"
    gone_text = "proc gone {} {}\n"
    (domain / "keep.tcl").write_text(keep_text, encoding="utf-8")
    (domain / "trim.tcl").write_text(trim_text, encoding="utf-8")
    (domain / "gone.tcl").write_text(gone_text, encoding="utf-8")

    keep_rel = Path("keep.tcl")
    trim_rel = Path("trim.tcl")
    gone_rel = Path("gone.tcl")

    stay = ProcEntry(
        canonical_name=f"{trim_rel.as_posix()}::stay",
        short_name="stay",
        qualified_name="stay",
        source_file=trim_rel,
        start_line=1,
        end_line=3,
        body_start_line=1,
        body_end_line=3,
        namespace_path="::",
    )
    drop = ProcEntry(
        canonical_name=f"{trim_rel.as_posix()}::drop",
        short_name="drop",
        qualified_name="drop",
        source_file=trim_rel,
        start_line=4,
        end_line=6,
        body_start_line=4,
        body_end_line=6,
        namespace_path="::",
    )
    parsed = ParseResult(
        files={trim_rel: ParsedFile(path=trim_rel, procs=(stay, drop), encoding="utf-8")},
        index=dict(
            sorted(
                {
                    stay.canonical_name: stay,
                    drop.canonical_name: drop,
                }.items()
            )
        ),
    )
    manifest = CompiledManifest(
        file_decisions={
            gone_rel: FileTreatment.REMOVE,
            keep_rel: FileTreatment.FULL_COPY,
            trim_rel: FileTreatment.PROC_TRIM,
        },
        proc_decisions={
            stay.canonical_name: ProcDecision(
                canonical_name=stay.canonical_name,
                source_file=trim_rel,
                selection_source="base:procedures.include",
            ),
        },
        provenance={
            gone_rel: FileProvenance(path=gone_rel, treatment=FileTreatment.REMOVE, reason="excluded"),
            keep_rel: FileProvenance(path=keep_rel, treatment=FileTreatment.FULL_COPY, reason="included"),
            trim_rel: FileProvenance(path=trim_rel, treatment=FileTreatment.PROC_TRIM, reason="proc-trim"),
        },
    )
    loaded = LoadedConfig(base=BaseJson(source_path=Path("base.json"), domain="d"))

    sim = simulate_trim_in_memory(ctx, loaded=loaded, parsed=parsed, manifest=manifest)

    assert isinstance(sim, SimulatedTrim)
    # Real on-disk source is untouched: all three files still present verbatim.
    assert (domain / "keep.tcl").read_text(encoding="utf-8") == keep_text
    assert (domain / "trim.tcl").read_text(encoding="utf-8") == trim_text
    assert (domain / "gone.tcl").read_text(encoding="utf-8") == gone_text
    assert not ctx.config.backup_root.exists()

    # In-memory backup holds the pristine source; rebuilt domain holds survivors.
    assert sim.fs.read_text(sim.backup_root / trim_rel) == trim_text
    assert sim.fs.exists(sim.domain_root / keep_rel)
    assert sim.fs.exists(sim.domain_root / trim_rel)
    assert not sim.fs.exists(sim.domain_root / gone_rel)
    # The dropped proc is gone from the rebuilt PROC_TRIM file.
    rebuilt = sim.fs.read_text(sim.domain_root / trim_rel)
    assert "proc stay" in rebuilt
    assert "proc drop" not in rebuilt


def test_source_root_prefers_backup_when_present(tmp_path: Path) -> None:
    """``_source_root`` returns ``backup_root`` once it exists on disk."""
    from chopper.orchestrator.simulate import _source_root

    ctx = _ctx(tmp_path)
    # No backup yet -> falls back to the domain root.
    assert _source_root(ctx) == ctx.config.domain_root
    # Once the backup exists, it is preferred (the pristine source).
    ctx.config.backup_root.mkdir()
    assert _source_root(ctx) == ctx.config.backup_root


class _FakeFS:
    """Minimal ``FileSystemPort`` stub exercising ``_read_text`` branches."""

    def __init__(self, behavior) -> None:
        self._behavior = behavior

    def exists(self, _path: Path) -> bool:
        return False

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        return self._behavior(path, encoding)


def _fake_ctx(tmp_path: Path, behavior) -> ChopperContext:
    cfg = RunConfig(
        domain_root=tmp_path / "d",
        backup_root=tmp_path / "d_backup",
        audit_root=tmp_path / "d" / ".chopper",
        strict=False,
        dry_run=True,
    )
    return ChopperContext(config=cfg, fs=_FakeFS(behavior), diag=_Sink(), progress=_Progress())


def test_read_text_latin1_fallback_succeeds(tmp_path: Path) -> None:
    """UTF-8 decode failure retries with latin-1 and returns the text."""
    from chopper.orchestrator.simulate import _read_text

    def behavior(_path: Path, encoding: str) -> str:
        if encoding == "utf-8":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")
        return "latin-1 text"

    ctx = _fake_ctx(tmp_path, behavior)
    assert _read_text(ctx, Path("x.tcl")) == "latin-1 text"


def test_read_text_latin1_fallback_oserror_returns_none(tmp_path: Path) -> None:
    """When the latin-1 retry also fails with OSError, the file is dropped."""
    from chopper.orchestrator.simulate import _read_text

    def behavior(_path: Path, encoding: str) -> str:
        if encoding == "utf-8":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")
        raise OSError("gone")

    ctx = _fake_ctx(tmp_path, behavior)
    assert _read_text(ctx, Path("x.tcl")) is None


def test_read_text_oserror_returns_none(tmp_path: Path) -> None:
    """A plain OSError on the first read yields ``None`` (file skipped)."""
    from chopper.orchestrator.simulate import _read_text

    def behavior(_path: Path, _encoding: str) -> str:
        raise OSError("missing")

    ctx = _fake_ctx(tmp_path, behavior)
    assert _read_text(ctx, Path("x.tcl")) is None


def test_simulate_skips_unreadable_source_file(tmp_path: Path, monkeypatch) -> None:
    """Files whose text cannot be read are skipped during seeding (no crash)."""
    import chopper.orchestrator.simulate as sim_mod

    ctx = _ctx(tmp_path)
    (ctx.config.domain_root / "unreadable.tcl").write_text("proc x {} {}\n", encoding="utf-8")

    monkeypatch.setattr(sim_mod, "_read_text", lambda _ctx, _path: None)

    manifest = CompiledManifest(file_decisions={}, proc_decisions={}, provenance={})
    loaded = LoadedConfig(base=BaseJson(source_path=Path("base.json"), domain="d"))
    parsed = ParseResult(files={}, index={})

    sim = simulate_trim_in_memory(ctx, loaded=loaded, parsed=parsed, manifest=manifest)
    # The unreadable file was skipped, so the in-memory domain is empty.
    assert not sim.fs.exists(sim.domain_root / Path("unreadable.tcl"))


def test_simulate_seeds_json_files_so_trimmer_loop_does_not_break(tmp_path: Path) -> None:
    """walk_files excludes ``.json`` via EXCLUDED_SUFFIXES; without the json seed
    fix the trimmer hits FileNotFoundError on jsons/base.json, breaks its per-file
    dispatch loop, and files sorted after jsons/ are never written to domain_root
    -- causing ``chopper loc`` to severely undercount sloc_after."""
    ctx = _ctx(tmp_path)
    domain = ctx.config.domain_root

    # Files sorted BEFORE jsons/ alphabetically.
    (domain / "alpha.tcl").write_text("proc alpha {} { return 1 }\n", encoding="utf-8")
    # json file that walk_files excludes -- the trimmer still needs it.
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text('{"$schema":"base-v1","domain":"d"}\n', encoding="utf-8")
    # File sorted AFTER jsons/ alphabetically -- previously dropped by the break.
    (domain / "zeta.tcl").write_text("proc zeta {} { return 99 }\n", encoding="utf-8")

    alpha_rel = Path("alpha.tcl")
    json_rel = Path("jsons/base.json")
    zeta_rel = Path("zeta.tcl")

    manifest = CompiledManifest(
        file_decisions={
            alpha_rel: FileTreatment.FULL_COPY,
            json_rel: FileTreatment.FULL_COPY,
            zeta_rel: FileTreatment.FULL_COPY,
        },
        proc_decisions={},
        provenance={
            alpha_rel: FileProvenance(path=alpha_rel, treatment=FileTreatment.FULL_COPY, reason="fi-literal"),
            json_rel: FileProvenance(path=json_rel, treatment=FileTreatment.FULL_COPY, reason="fi-literal"),
            zeta_rel: FileProvenance(path=zeta_rel, treatment=FileTreatment.FULL_COPY, reason="fi-literal"),
        },
    )
    loaded = LoadedConfig(base=BaseJson(source_path=domain / "jsons" / "base.json", domain="d"))
    parsed = ParseResult(files={}, index={})

    sim = simulate_trim_in_memory(ctx, loaded=loaded, parsed=parsed, manifest=manifest)

    # Both alpha.tcl (before jsons/) and zeta.tcl (after jsons/) must be
    # in the rebuilt domain -- the trimmer loop must not break on jsons/base.json.
    assert sim.fs.exists(sim.domain_root / alpha_rel), "alpha.tcl missing -- loop broke before jsons/"
    assert sim.fs.exists(sim.domain_root / zeta_rel), "zeta.tcl missing -- loop broke on jsons/base.json"
