"""Shared fixtures + builders for compiler unit tests.

Kept intentionally small: test files construct ``LoadedConfig`` and
``ParseResult`` directly through these helpers so each case is visible
without a lot of JSON/Tcl boilerplate.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models_common import DomainState, FileStat
from chopper.core.models_config import (
    BaseJson,
    FeatureJson,
    FilesSection,
    LoadedConfig,
    ProceduresSection,
    ProcEntryRef,
)
from chopper.core.models_parser import ParsedFile, ParseResult, ProcEntry


class CollectingSink:
    """Minimal diagnostic sink that records every emission in order."""

    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, d: Diagnostic) -> None:
        self.emissions.append(d)

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover
        return DiagnosticSummary(errors=0, warnings=0, infos=0)

    def codes(self) -> list[str]:
        return [d.code for d in self.emissions]


class _NullFS:
    """Placeholder FS — the compiler never reads from disk."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # pragma: no cover
        raise OSError("compiler must not read files")

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...  # pragma: no cover
    def exists(self, path: Path) -> bool:  # pragma: no cover
        return False

    def list(self, path: Path, *, pattern: str | None = None):  # pragma: no cover
        return ()

    def stat(self, path: Path) -> FileStat:  # pragma: no cover
        return FileStat(size=0, mtime=0.0, is_dir=False)

    def rename(self, src: Path, dst: Path) -> None: ...  # pragma: no cover
    def remove(self, path: Path, *, recursive: bool = False) -> None: ...  # pragma: no cover
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...  # pragma: no cover
    def copy_tree(self, src: Path, dst: Path) -> None: ...  # pragma: no cover


class _NullProgress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


DOMAIN_ROOT = Path("/dom/my_domain")


def make_ctx() -> tuple[ChopperContext, CollectingSink]:
    """Build a minimal ``ChopperContext`` wired to a recording sink."""
    sink = CollectingSink()
    cfg = RunConfig(
        domain_root=DOMAIN_ROOT,
        backup_root=Path("/dom/my_domain_backup"),
        audit_root=DOMAIN_ROOT / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(config=cfg, fs=_NullFS(), diag=sink, progress=_NullProgress())
    return ctx, sink


def default_state() -> DomainState:
    return DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)


# ---------------------------------------------------------------------------
# Builders for ProcEntry / ParsedFile / ParseResult.
# ---------------------------------------------------------------------------


def make_proc(
    file: str,
    name: str,
    *,
    qualified: str | None = None,
    namespace: str = "",
    start: int = 1,
    end: int = 3,
    calls: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
) -> ProcEntry:
    """Minimal ``ProcEntry`` constructor used by compiler tests."""
    path = Path(file)
    qualified_name = qualified if qualified is not None else name
    # ProcEntry invariant 5: calls must be dedup + lex-sorted.
    normalised_calls = tuple(sorted(set(calls)))
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{qualified_name}",
        short_name=name,
        qualified_name=qualified_name,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=start + 1,
        body_end_line=end - 1,
        namespace_path=namespace,
        calls=normalised_calls,
        source_refs=source_refs,
    )


def make_parsed(procs_by_file: dict[str, list[str]]) -> ParseResult:
    """Build a :class:`ParseResult` where each file holds procs with the
    given short names. Convenience for tests that don't care about line
    numbers or call edges.
    """
    files: dict[Path, ParsedFile] = {}
    index: dict[str, ProcEntry] = {}
    for file_str, names in sorted(procs_by_file.items()):
        path = Path(file_str)
        procs: list[ProcEntry] = []
        line = 1
        for name in names:
            proc = make_proc(file_str, name, start=line, end=line + 2)
            procs.append(proc)
            index[proc.canonical_name] = proc
            line += 3
        files[path] = ParsedFile(path=path, procs=tuple(procs), encoding="utf-8")
    # index must be lex-sorted per ParseResult invariant
    sorted_index = {k: index[k] for k in sorted(index)}
    return ParseResult(files=files, index=sorted_index)


# ---------------------------------------------------------------------------
# Builders for BaseJson / FeatureJson / LoadedConfig.
# ---------------------------------------------------------------------------


def proc_ref(file: str, *procs: str) -> ProcEntryRef:
    return ProcEntryRef(file=Path(file), procs=tuple(procs))


def files_section(include: tuple[str, ...] = (), exclude: tuple[str, ...] = ()) -> FilesSection:
    return FilesSection(include=tuple(include), exclude=tuple(exclude))


def procs_section(include: tuple[ProcEntryRef, ...] = (), exclude: tuple[ProcEntryRef, ...] = ()) -> ProceduresSection:
    return ProceduresSection(include=include, exclude=exclude)


def make_base(
    *,
    files: FilesSection | None = None,
    procedures: ProceduresSection | None = None,
    source_path: Path = Path("/dom/my_domain/base.json"),
) -> BaseJson:
    return BaseJson(
        source_path=source_path,
        domain="my_domain",
        files=files or FilesSection(),
        procedures=procedures or ProceduresSection(),
    )


def make_feature(
    name: str,
    *,
    files: FilesSection | None = None,
    procedures: ProceduresSection | None = None,
    source_path: Path | None = None,
) -> FeatureJson:
    return FeatureJson(
        source_path=source_path or Path(f"/dom/my_domain/{name}.feature.json"),
        name=name,
        files=files or FilesSection(),
        procedures=procedures or ProceduresSection(),
    )


def make_loaded(base: BaseJson, *features: FeatureJson, surface_files: tuple[Path, ...] = ()) -> LoadedConfig:
    return LoadedConfig(
        base=base,
        features=features,
        surface_files=surface_files,
    )
