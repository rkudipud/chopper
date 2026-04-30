"""Core frozen dataclasses shared across every Chopper service.

Every record that crosses a service boundary is an immutable
:class:`dataclass` defined here. Services never declare their own
copies of these shapes. Later-phase shapes may not depend on earlier
phases' shapes in reverse (enforced by `import-linter`).

Key records by phase:

* :class:`FileTreatment`        — per-file decision vocabulary (P3 → P5).
* :class:`DomainState`          — P0 case classification.
* :class:`FileStat`             — ``stat`` result from :class:`FileSystemPort`.
* :class:`ProcEntry`            — per-proc record from the parser (P2).
* :class:`ParsedFile`           — per-file aggregate.
* :class:`ParseResult`          — domain-wide aggregate with canonical-name index.
* :class:`CompiledManifest`     — P3 output; drives trimmer + generator.
* :class:`DependencyGraph`      — P4 output; reporting-only.
* :class:`TrimReport`           — P5 audit record.
* :class:`RunRecord`            — snapshot of a whole run for the audit writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from chopper.core.diagnostics import DiagnosticSummary

__all__ = [
    "AddStageAction",
    "AddStepAction",
    "AuditArtifact",
    "AuditManifest",
    "BaseJson",
    "BaseOptions",
    "CompiledManifest",
    "DependencyGraph",
    "DomainState",
    "Edge",
    "FeatureJson",
    "FeatureMetadata",
    "FileOutcome",
    "FileProvenance",
    "FileStat",
    "FileTreatment",
    "FilesSection",
    "FlowAction",
    "GeneratedArtifact",
    "LoadFromAction",
    "LoadedConfig",
    "ParseResult",
    "ParsedFile",
    "ProcDecision",
    "ProcEntry",
    "ProcEntryRef",
    "ProceduresSection",
    "ProjectJson",
    "RemoveStageAction",
    "RemoveStepAction",
    "ReplaceStageAction",
    "ReplaceStepAction",
    "RunRecord",
    "RunResult",
    "StageDefinition",
    "StageSpec",
    "TrimReport",
]


class FileTreatment(StrEnum):
    """Per-file disposition emitted by the compiler.

    The four legal entries in ``CompiledManifest.file_decisions``:

    * ``FULL_COPY`` — file is included whole; trimmer copies it verbatim from
      ``<domain>_backup/`` to ``<domain>/``.
    * ``PROC_TRIM`` — file survives but some procs are dropped; trimmer
      rewrites the file with the excluded proc blocks removed.
    * ``GENERATED`` — file is synthesised by ``GeneratorService`` (F3 run
      files); no backup source exists.
    * ``REMOVE`` — file does not appear in the trimmed domain.

    :class:`enum.StrEnum` makes instances serialise directly to JSON as
    their string value without a custom encoder.
    """

    FULL_COPY = "FULL_COPY"
    PROC_TRIM = "PROC_TRIM"
    GENERATED = "GENERATED"
    REMOVE = "REMOVE"


@dataclass(frozen=True)
class DomainState:
    """Result of the Phase 0 ``DomainStateService`` classification.

    The state-machine observes ``<domain>/`` and ``<domain>_backup/``
    at invocation and classifies the workspace into one of four cases:

    * Case 1 — ``domain_exists=True``, ``backup_exists=False`` (first trim).
    * Case 2 — ``domain_exists=True``, ``backup_exists=True`` (re-trim).
    * Case 3 — ``domain_exists=False``, ``backup_exists=True`` (recovery
      re-trim; backup is authoritative).
    * Case 4 — ``domain_exists=False``, ``backup_exists=False`` (fatal;
      the CLI emits ``VE-21`` and exits 2).

    ``hand_edited`` is an informational flag only. Chopper does not emit a
    diagnostic on detection; the CLI prints a fixed pre-flight warning
    every re-trim regardless.
    """

    case: Literal[1, 2, 3, 4]
    domain_exists: bool
    backup_exists: bool
    hand_edited: bool


@dataclass(frozen=True)
class FileStat:
    """Lightweight stat record returned by :meth:`FileSystemPort.stat`.

    Chopper's port surface does not expose full ``os.stat_result`` semantics
    — services only need enough to decide whether a path is a directory and
    to size files for audit reporting.

    * ``size`` — file size in bytes (zero for directories).
    * ``mtime`` — POSIX modification timestamp. Only used by audit hashing
      contexts; comparisons use absolute equality, never "within N seconds".
    * ``is_dir`` — ``True`` iff the path resolves to a directory.
    """

    size: int
    mtime: float
    is_dir: bool


# ---------------------------------------------------------------------------
# Stage 1 — Parser outputs.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcEntry:
    """One Tcl proc definition extracted by :func:`chopper.parser.parse_file`.

    Canonical-name format: ``<domain-relative-posix-path>::<qualified_name>``.

    Call-site handoff fields (``calls`` and ``source_refs``) are the only
    coupling between parser and tracer. Both are textual / unresolved;
    resolution happens in P4.

    Invariants checked in ``__post_init__``:

    1. ``start_line`` / ``end_line`` / ``body_*`` are 1-indexed positive
       ints and ``start_line <= end_line``.
    2. Body lines are within ``[start_line, end_line]``. Empty-body form
       (``body_start_line > body_end_line``) is allowed — it signals that
       the body has zero content lines.
    3. Optional DPA and comment-banner spans, when set, are consistent
       (``start <= end`` and both non-None together).
    4. ``canonical_name`` equals ``f"{source_file.as_posix()}::{qualified_name}"``.
    5. ``calls`` is deduplicated and lexicographically sorted;
       ``source_refs`` is a tuple of POSIX strings (no ordering
       requirement at parse time).
    """

    canonical_name: str
    short_name: str
    qualified_name: str
    source_file: Path
    start_line: int
    end_line: int
    body_start_line: int
    body_end_line: int
    namespace_path: str
    calls: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    dpa_start_line: int | None = None
    dpa_end_line: int | None = None
    comment_start_line: int | None = None
    comment_end_line: int | None = None

    def __post_init__(self) -> None:  # noqa: C901 — invariants live together
        # 1. Line-number sanity on the required fields.
        for name in ("start_line", "end_line", "body_start_line", "body_end_line"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"ProcEntry.{name} must be a positive 1-indexed int, got {value!r}")
        if self.start_line > self.end_line:
            raise ValueError(f"ProcEntry.start_line ({self.start_line}) must be <= end_line ({self.end_line})")

        # 2. Body lines fall within [start_line, end_line]. Empty-body form
        #    (body_start_line > body_end_line) is allowed per §6.2.
        if not (self.start_line <= self.body_start_line <= self.end_line):
            raise ValueError(
                f"ProcEntry.body_start_line ({self.body_start_line}) must be in [{self.start_line}, {self.end_line}]"
            )
        if not (self.start_line <= self.body_end_line <= self.end_line):
            raise ValueError(
                f"ProcEntry.body_end_line ({self.body_end_line}) must be in [{self.start_line}, {self.end_line}]"
            )

        # 3. Optional span invariants: pairs must both be set or both None.
        for first, last, label in (
            (self.dpa_start_line, self.dpa_end_line, "dpa"),
            (self.comment_start_line, self.comment_end_line, "comment"),
        ):
            if (first is None) != (last is None):
                raise ValueError(f"ProcEntry {label}_start_line and {label}_end_line must both be set or both None")
            if first is not None and last is not None:
                if first < 1 or last < 1:
                    raise ValueError(f"ProcEntry {label} span must be 1-indexed positive ints")
                if first > last:
                    raise ValueError(f"ProcEntry {label}_start_line ({first}) must be <= {label}_end_line ({last})")

        # 4. Canonical-name format.
        expected = f"{self.source_file.as_posix()}::{self.qualified_name}"
        if self.canonical_name != expected:
            raise ValueError(
                f"ProcEntry.canonical_name {self.canonical_name!r} does not match "
                f"'<source_file.as_posix()>::<qualified_name>' = {expected!r}"
            )

        # 5. calls tuple is dedup + lex-sorted.
        if list(self.calls) != sorted(set(self.calls)):
            raise ValueError("ProcEntry.calls must be deduplicated and lexicographically sorted")


@dataclass(frozen=True)
class ParsedFile:
    """Per-file aggregate returned by ``ParserService`` for one Tcl file.

    Fields:

    * ``path`` — domain-relative :class:`~pathlib.Path`.
    * ``procs`` — tuple of :class:`ProcEntry`, sorted by ``start_line``.
    * ``encoding`` — the encoding used to decode the file
      (``"utf-8"`` when the initial decode succeeded; ``"latin-1"`` if the
      parser fell back and emitted ``PW-02``).

    Parse-error diagnostics are emitted via ``ctx.diag`` as they are
    discovered; they never appear on this record.
    """

    path: Path
    procs: tuple[ProcEntry, ...]
    encoding: Literal["utf-8", "latin-1"]

    def __post_init__(self) -> None:
        starts = [p.start_line for p in self.procs]
        if starts != sorted(starts):
            raise ValueError("ParsedFile.procs must be sorted by start_line")
        for proc in self.procs:
            if proc.source_file != self.path:
                raise ValueError(
                    f"ProcEntry.source_file ({proc.source_file!r}) does not match ParsedFile.path ({self.path!r})"
                )


@dataclass(frozen=True)
class ParseResult:
    """Domain-wide parser output with the canonical-name index.

    * ``files`` — maps domain-relative path to :class:`ParsedFile`. The
      parser constructs this as a plain :class:`dict` sorted lex on the
      POSIX form of the path; the mapping is frozen only in the sense
      that the enclosing :class:`ParseResult` is frozen (callers must
      not mutate). ``files`` is scoped to the *surface* set — the union
      of paths the user named (literal FI, glob-matched FI, proc-ref
      files). The compiler operates exclusively on this view.
    * ``index`` — maps ``canonical_name`` to :class:`ProcEntry` for O(1)
      lookup by the compiler and tracer. ``index`` is a **full-domain**
      proc index: it contains every proc defined in any ``.tcl`` file
      anywhere under ``domain_root``, including files outside ``files``.
      This lets the P4 tracer resolve calls into files the user did not
      surface so ``dependency_graph.json`` reports the actual defining
      file (the user can then add it to the JSON in a follow-up run).
      Trace remains reporting-only — a wider index does not change which
      files or procs survive (see Critical Principle #7).

    Invariants checked in ``__post_init__``:

    1. Every ``ProcEntry`` in every ``ParsedFile.procs`` appears in
       ``index`` under its ``canonical_name``, referring to the *same*
       :class:`ProcEntry` instance. ``index`` may also contain entries
       whose ``defined_in`` path is **not** a key of ``files`` — those
       are full-domain index entries for non-surfaced files.
    2. ``canonical_name`` keys in ``index`` are lex-sorted (required for
       deterministic dependency-graph output).
    """

    files: dict[Path, ParsedFile] = field(default_factory=dict)
    index: dict[str, ProcEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 1. Every proc listed in ``files`` must appear in ``index`` as
        #    the same instance. ``index`` may carry extra entries from
        #    non-surfaced files (full-domain coverage for trace).
        from_files: dict[str, ProcEntry] = {}
        for parsed in self.files.values():
            for proc in parsed.procs:
                if proc.canonical_name in from_files:
                    raise ValueError(f"ParseResult: duplicate canonical_name across files: {proc.canonical_name!r}")
                from_files[proc.canonical_name] = proc
        missing = set(from_files) - set(self.index)
        if missing:
            raise ValueError(f"ParseResult.index is missing entries listed in ParseResult.files: {sorted(missing)!r}")
        for cn, proc in from_files.items():
            if self.index[cn] is not proc:
                raise ValueError(
                    f"ParseResult.index[{cn!r}] does not refer to the same ProcEntry instance as files view"
                )

        # 2. Deterministic ordering of the index.
        if list(self.index.keys()) != sorted(self.index.keys()):
            raise ValueError("ParseResult.index keys must be lexicographically sorted")


# ---------------------------------------------------------------------------
# Stage 2a — Config-loader outputs (base / feature / project + aggregate).
# ---------------------------------------------------------------------------
#
# Authoritative schemas: schemas/{base,feature,project}-v1.schema.json.
#
# Every JSON record here is a frozen dataclass that is **one-to-one** with its
# schema after the loader has validated and hydrated it. The loader
# (:mod:`chopper.config.loaders`) is the only place that constructs these;
# downstream services consume them read-only.


@dataclass(frozen=True)
class ProcEntryRef:
    """A proc-level include/exclude reference — ``{file, procs[]}``.

    Matches the ``procEntry`` definition in ``base-v1`` / ``feature-v1``
    schemas (``procedures.include`` and ``procedures.exclude``). The
    ``file`` path is domain-relative (schema rejects ``..`` / absolute
    paths); ``procs`` must be non-empty (``VE-03`` at the loader).
    """

    file: Path
    procs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.procs:
            raise ValueError("ProcEntryRef.procs must be non-empty (VE-03 at loader)")


@dataclass(frozen=True)
class FilesSection:
    """``files`` block in base / feature JSON — per-source include/exclude."""

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProceduresSection:
    """``procedures`` block in base / feature JSON."""

    include: tuple[ProcEntryRef, ...] = ()
    exclude: tuple[ProcEntryRef, ...] = ()


@dataclass(frozen=True)
class StageDefinition:
    """One stage entry — from ``base.stages[]`` or a feature flow-action.

    Matches the ``stageDefinition`` definition shared by the base and
    feature schemas. This record preserves the authored values verbatim
    so the F3 generator can emit run scripts and stack lines
    deterministically.
    """

    name: str
    load_from: str
    steps: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    exit_codes: tuple[int, ...] = ()
    command: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    run_mode: Literal["serial", "parallel"] = "serial"
    language: Literal["tcl", "python"] = "tcl"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("StageDefinition.name must be non-empty")
        if not self.steps:
            raise ValueError("StageDefinition.steps must be non-empty")


# ---------------------------------------------------------------------------
# Flow-action union — seven variants discriminated by ``action``.
# Matches feature-v1.schema.json ``flowAction.oneOf``.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AddStepAction:
    """``add_step_before`` / ``add_step_after``."""

    action: Literal["add_step_before", "add_step_after"]
    stage: str
    reference: str
    items: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("AddStepAction.items must be non-empty")


@dataclass(frozen=True)
class AddStageAction:
    """``add_stage_before`` / ``add_stage_after``.

    The new stage is carried as a :class:`StageDefinition`; ``reference``
    names the existing stage to anchor against.
    """

    action: Literal["add_stage_before", "add_stage_after"]
    reference: str
    stage: StageDefinition


@dataclass(frozen=True)
class RemoveStepAction:
    """``remove_step``."""

    action: Literal["remove_step"]
    stage: str
    reference: str


@dataclass(frozen=True)
class RemoveStageAction:
    """``remove_stage``."""

    action: Literal["remove_stage"]
    reference: str


@dataclass(frozen=True)
class LoadFromAction:
    """``load_from`` — retarget a stage's predecessor."""

    action: Literal["load_from"]
    stage: str
    reference: str


@dataclass(frozen=True)
class ReplaceStepAction:
    """``replace_step``.

    The schema field is named ``with``; we rename to ``replacement`` here
    since ``with`` is a Python keyword. The loader performs the rename
    on hydration and the reverse rename on audit-artifact serialisation.
    """

    action: Literal["replace_step"]
    stage: str
    reference: str
    replacement: str


@dataclass(frozen=True)
class ReplaceStageAction:
    """``replace_stage``."""

    action: Literal["replace_stage"]
    reference: str
    replacement: StageDefinition


# Discriminated union type alias used by downstream services and the loader.
# Mypy treats this as the union of the seven dataclass types; discrimination
# is by the ``action`` literal.
FlowAction = (
    AddStepAction
    | AddStageAction
    | RemoveStepAction
    | RemoveStageAction
    | LoadFromAction
    | ReplaceStepAction
    | ReplaceStageAction
)
"""Tagged union over the seven flow-action variants (feature-v1 schema)."""


# ---------------------------------------------------------------------------
# JSON-record dataclasses — one per schema.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaseOptions:
    """``options`` block in base JSON.

    * ``cross_validate`` — defaults to ``True``; post-trim
      cross-validation emits ``VW-14`` / ``VW-15`` / ``VW-16``
      unless authors opt out.
    * ``generate_stack`` — defaults to ``False``; when ``True`` and
      the base JSON declares at least one stage, Chopper emits one
      ``<stage>.stack`` file per resolved stage alongside the
      ``<stage>.tcl`` run script. Stack-file format (N/J/L/D/I/O/R)
      is defined in architecture doc §3.6; derivation rules live in
      :mod:`chopper.generators.stack_emitter`.
    """

    cross_validate: bool = True
    generate_stack: bool = False


@dataclass(frozen=True)
class BaseJson:
    """Hydrated ``base-v1`` JSON.

    Required: ``$schema`` and ``domain``; at least one of ``files`` /
    ``procedures`` / ``stages`` must be present. The loader enforces
    the at-least-one rule via the jsonschema ``anyOf`` constraint and
    maps failures to ``VE-02``.

    ``source_path`` records where the JSON was loaded from — used for
    error-message provenance and audit artifacts. It is not part of the
    schema.
    """

    source_path: Path
    domain: str
    owner: str | None = None
    vendor: str | None = None
    tool: str | None = None
    description: str | None = None
    options: BaseOptions = field(default_factory=BaseOptions)
    files: FilesSection = field(default_factory=FilesSection)
    procedures: ProceduresSection = field(default_factory=ProceduresSection)
    stages: tuple[StageDefinition, ...] = ()


@dataclass(frozen=True)
class FeatureMetadata:
    """Optional ``metadata`` block on a feature JSON (documentation only).

    Chopper never evaluates these fields; they are preserved verbatim
    in audit artifacts.
    """

    owner: str | None = None
    tags: tuple[str, ...] = ()
    wiki: str | None = None
    related_ivars: tuple[str, ...] = ()
    related_appvars: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureJson:
    """Hydrated ``feature-v1`` JSON.

    Required: ``$schema`` and ``name``; everything else is optional.
    Feature ``name`` must be unique across a project (``VE-14``);
    ``depends_on`` prerequisites must be selected (``VE-15``) and
    acyclic (``VE-22``).
    """

    source_path: Path
    name: str
    domain: str | None = None
    description: str | None = None
    depends_on: tuple[str, ...] = ()
    metadata: FeatureMetadata = field(default_factory=FeatureMetadata)
    files: FilesSection = field(default_factory=FilesSection)
    procedures: ProceduresSection = field(default_factory=ProceduresSection)
    flow_actions: tuple[FlowAction, ...] = ()


@dataclass(frozen=True)
class ProjectJson:
    """Hydrated ``project-v1`` JSON.

    Required: ``$schema``, ``project``, ``domain``, ``base``. ``base``
    and each entry in ``features`` are domain-relative path strings
    as authored — the service layer resolves them to :class:`Path`
    against ``ctx.config.domain_root`` after the schema check.
    ``VE-13`` (unresolvable paths) is emitted by the CLI pre-pass
    before :class:`ConfigService` runs.
    """

    source_path: Path
    project: str
    domain: str
    base: str
    owner: str | None = None
    release_branch: str | None = None
    features: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadedConfig:
    """Aggregate returned by :class:`ConfigService`.

    * ``base`` — the one hydrated :class:`BaseJson` (exactly one per run;
      resolved from either ``project.base`` or ``--base``).
    * ``features`` — tuple of hydrated :class:`FeatureJson`, **topo-sorted
      by ``depends_on``**. A stable sort preserves project-feature order
      for equally-ranked features so F3 sequencing stays deterministic.
    * ``project`` — the :class:`ProjectJson` when invoked with
      ``--project``; ``None`` under direct ``--base`` / ``--features``.
    * ``surface_files`` — the union of every file named by any source
      (base + every feature). Tuple of domain-relative :class:`Path`
      entries, lex-sorted by POSIX form for determinism. This is what
      :class:`ParserService.run` consumes in P2. Glob expansion against
      the real filesystem is **not** done here — that is the compiler's
      responsibility in P3.
    * ``tool_command_pool`` — frozen set of known external tool-command
      bare names consulted by P4 trace (see architecture doc §3.10 and
      ``FR-44``). Composed by :class:`ConfigService` from the always-
      loaded built-in ``.commands`` files under
      ``src/chopper/data/tool_commands/`` plus any user lists passed via
      the CLI flag ``--tool-commands``. The pool is a single flat set of
      bare names; matching happens on raw token OR namespace-stripped
      leaf. Empty in unit tests that bypass the CLI layer.
    """

    base: BaseJson
    features: tuple[FeatureJson, ...] = ()
    project: ProjectJson | None = None
    surface_files: tuple[Path, ...] = ()
    tool_command_pool: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        # Feature names are unique (VE-14 is the loader's job; this is a
        # last-line programmer-error assertion).
        names = [f.name for f in self.features]
        if len(set(names)) != len(names):
            raise ValueError(f"LoadedConfig.features contains duplicate names: {names!r}")
        # surface_files is lex-sorted by POSIX form (determinism contract).
        posix = [p.as_posix() for p in self.surface_files]
        if posix != sorted(posix):
            raise ValueError("LoadedConfig.surface_files must be sorted by POSIX form")


# ---------------------------------------------------------------------------
# Stage 2b — Compiler outputs (P3 frozen manifest).
# ---------------------------------------------------------------------------
#
# The compiler (``CompilerService.run``) consumes a :class:`LoadedConfig` and
# a :class:`ParseResult` and emits exactly one :class:`CompiledManifest`.
# The manifest is frozen on construction — every downstream phase (trace,
# trim, generate, post-validate, audit) reads it but must not mutate it.


@dataclass(frozen=True)
class ProcDecision:
    """One surviving proc recorded in the compiled manifest.

    Every entry in ``procedures.surviving`` carries its canonical name,
    its source file, and the JSON source that caused it to survive.
    ``selection_source`` is a stable string of the form
    ``"<source_key>:<json_field>"``:

    * ``source_key`` is ``"base"`` for the base JSON, or the feature's
      ``name`` field for a feature JSON.
    * ``json_field`` is one of ``"files.include"`` (whole-file inclusion
      contributed this proc), ``"procedures.include"`` (explicit PI
      named the proc), or ``"procedures.exclude"`` (same-source PE
      kept the file as ``PROC_TRIM`` minus the excluded procs).

    When multiple sources contribute a proc the winner reported here is
    the first one encountered in compiler iteration order: base first,
    then each feature in topo-sorted order.
    """

    canonical_name: str
    source_file: Path
    selection_source: str

    def __post_init__(self) -> None:
        if "::" not in self.canonical_name:
            raise ValueError(
                f"ProcDecision.canonical_name must be '<file>::<qualified_name>', got {self.canonical_name!r}"
            )
        if ":" not in self.selection_source:
            raise ValueError(
                f"ProcDecision.selection_source must be '<source_key>:<json_field>', got {self.selection_source!r}"
            )


@dataclass(frozen=True)
class FileProvenance:
    """Per-file provenance record written into the compiled manifest.

    Mirrors the fields of a single entry in ``compiled_manifest.json``
    under the top-level ``files`` array:

    * ``path`` — domain-relative POSIX path of the file.
    * ``treatment`` — the authoritative :class:`FileTreatment` value.
    * ``reason`` — kebab-case tag naming the winning same-source rule.
      One of: ``"fi-literal"``, ``"fi-glob"``, ``"pi-additive"``,
      ``"pe-subtractive"``, ``"fi-and-pe"``, ``"default-exclude"``.
    * ``input_sources`` — stable tuple of ``"<source_key>:<json_field>"``
      tags recording every non-NONE, non-fully-vetoed contribution to
      this file. Lex-sorted for determinism.
    * ``vetoed_entries`` — tuple of ``"<source_key>:<json_field>"`` tags
      identifying authoring intents discarded by L3 (cross-source veto:
      every ``VW-18`` PE and ``VW-19`` FE vetoed by another source's
      include). Lex-sorted.
    * ``proc_model`` — ``"additive"`` if ``PROC_TRIM`` surviving procs
      were driven by ``procedures.include`` entries, ``"subtractive"``
      if driven by same-source ``procedures.exclude`` entries, or
      ``None`` for ``FULL_COPY`` / ``GENERATED`` / ``REMOVE``.
    """

    path: Path
    treatment: FileTreatment
    reason: str
    input_sources: tuple[str, ...] = ()
    vetoed_entries: tuple[str, ...] = ()
    proc_model: Literal["additive", "subtractive"] | None = None

    def __post_init__(self) -> None:
        if self.input_sources != tuple(sorted(self.input_sources)):
            raise ValueError("FileProvenance.input_sources must be lex-sorted")
        if self.vetoed_entries != tuple(sorted(self.vetoed_entries)):
            raise ValueError("FileProvenance.vetoed_entries must be lex-sorted")
        if self.proc_model is not None and self.treatment is not FileTreatment.PROC_TRIM:
            raise ValueError(
                f"FileProvenance.proc_model is only valid for PROC_TRIM files (got treatment={self.treatment})"
            )


@dataclass(frozen=True)
class StageSpec:
    """One resolved F3 stage in the compiled manifest.

    This is the post-``flow_actions`` artifact consumed by
    :class:`~chopper.generators.GeneratorService` at P5b. Structurally
    identical to :class:`StageDefinition` (the schema-hydrated authoring
    record); the type distinction exists so signatures make it clear
    whether a stage has been through the resolver.

    Invariants enforced in ``__post_init__``:

    1. ``name`` is non-empty.
    2. ``steps`` is non-empty — a stage with zero steps cannot produce a
         runnable ``<stage>.tcl``. The compiler raises ``VE-08`` earlier
         if authors emit an empty stage; this check catches
         programmer-error drift in the resolver itself.
    """

    name: str
    load_from: str = ""
    steps: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    exit_codes: tuple[int, ...] = ()
    command: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    run_mode: Literal["serial", "parallel"] = "serial"
    language: Literal["tcl", "python"] = "tcl"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("StageSpec.name must be non-empty")
        if not self.steps:
            raise ValueError(f"StageSpec.steps must be non-empty (stage {self.name!r})")


@dataclass(frozen=True)
class CompiledManifest:
    """Frozen output of :class:`~chopper.compiler.CompilerService` (P3).

    This dataclass is the single source of truth driving every later
    phase:

    * ``file_decisions`` — maps every relevant domain-relative file to
      its :class:`FileTreatment`. Relevant files are: every parsed file
      (by ``parsed.files`` keys), plus every extra literal path named
      by any source that the parser did not cover (non-``.tcl``
      companions such as config files surface here). Lex-sorted by
      POSIX form.
    * ``proc_decisions`` — maps every surviving proc's ``canonical_name``
      to a :class:`ProcDecision`. For ``FULL_COPY`` files every parsed
      proc appears here; for ``PROC_TRIM`` files only the kept subset
      appears. Keyed by ``canonical_name`` so the trimmer (P5) can
      membership-test per parsed proc in O(1). Lex-sorted.
    * ``provenance`` — per-file :class:`FileProvenance` records, with
      the same key set as ``file_decisions``. Lex-sorted.
    * ``stages`` — resolved F3 stages, in execution order. Empty when
      no base stage is declared; populated by
            :mod:`chopper.compiler.flow_resolver` when the base JSON declares
            at least one stage.
    * ``generate_stack`` — mirrored from ``base.options.generate_stack``;
      when ``True`` the generator (P5b) additionally emits one
      ``<stage>.stack`` file per resolved stage. Has no effect when
      ``stages`` is empty.

    Invariants enforced by ``__post_init__``:

    1. All three mapping field keys are lex-sorted by POSIX form.
    2. ``provenance`` and ``file_decisions`` have identical key sets.
    3. Every ``provenance[F].treatment`` equals ``file_decisions[F]``
       (no provenance/decision drift).
    """

    file_decisions: dict[Path, FileTreatment] = field(default_factory=dict)
    proc_decisions: dict[str, ProcDecision] = field(default_factory=dict)
    provenance: dict[Path, FileProvenance] = field(default_factory=dict)
    stages: tuple[StageSpec, ...] = ()
    generate_stack: bool = False

    def __post_init__(self) -> None:
        fd_keys = [p.as_posix() for p in self.file_decisions]
        if fd_keys != sorted(fd_keys):
            raise ValueError("CompiledManifest.file_decisions must be lex-sorted by POSIX form")
        if list(self.proc_decisions.keys()) != sorted(self.proc_decisions.keys()):
            raise ValueError("CompiledManifest.proc_decisions keys must be lex-sorted")
        pv_keys = [p.as_posix() for p in self.provenance]
        if pv_keys != sorted(pv_keys):
            raise ValueError("CompiledManifest.provenance must be lex-sorted by POSIX form")
        if set(self.provenance.keys()) != set(self.file_decisions.keys()):
            raise ValueError("CompiledManifest.provenance keys must match file_decisions keys")
        for path, treatment in self.file_decisions.items():
            pv_treatment = self.provenance[path].treatment
            if pv_treatment is not treatment:
                raise ValueError(
                    f"CompiledManifest: provenance/decision mismatch for {path!r}: "
                    f"file_decisions={treatment}, provenance.treatment={pv_treatment}"
                )


# ---------------------------------------------------------------------------
# Stage 2c — Tracer outputs (P4).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Edge:
    """One caller → callee edge recorded by :class:`TracerService` (P4).

    An edge is created per call-token occurrence: if the same caller token
    matches the same callee three times, three :class:`Edge` records
    appear, each with its own ``line`` and ``token``. Deduplication is a
    visited-set property, not an edge-set property.

    * ``caller`` — canonical proc name of the proc whose body contains the
      token. For file-level ``source`` / ``iproc_source`` edges emitted
      from a proc body, ``caller`` is still the enclosing proc's canonical
      name.
    * ``callee`` — canonical proc name of the resolved callee for
      ``kind="proc_call"``; the domain-relative POSIX path (as a string)
      for ``kind in {"source", "iproc_source"}``; empty string when
      ``status != "resolved"``.
    * ``kind`` — ``"proc_call"``, ``"source"``, or ``"iproc_source"``.
    * ``status`` — ``"resolved"``, ``"ambiguous"``, ``"unresolved"``,
      ``"dynamic"``, or ``"tool_command"``. The ``"tool_command"`` status
      is reported for call tokens whose raw name or namespace-stripped
      leaf matches the P4 tool-command pool (see architecture doc §3.10
      and ``FR-44``); those edges carry ``diagnostic_code="TI-01"``.
    * ``token`` — the raw call token the parser extracted. Retained for
      diagnostic rendering and for downstream tooling that wants to show
      the user what was written on the page.
    * ``line`` — 1-indexed source line at which the token was recorded.
      When the parser does not retain per-token line numbers, the tracer
      stamps the enclosing proc's ``body_start_line`` as a fallback.
    * ``diagnostic_code`` — the ``TW-*`` / ``TI-*`` code associated with
      this edge when ``status != "resolved"``; ``None`` for resolved
      edges.
    """

    caller: str
    callee: str
    kind: Literal["proc_call", "source", "iproc_source"]
    status: Literal["resolved", "ambiguous", "unresolved", "dynamic", "tool_command"]
    token: str
    line: int
    diagnostic_code: str | None = None

    def __post_init__(self) -> None:
        if self.status == "resolved" and not self.callee:
            raise ValueError("Edge.callee is required when status == 'resolved'")
        if self.status == "resolved" and self.diagnostic_code is not None:
            raise ValueError("Edge.diagnostic_code must be None for resolved edges")
        if self.status != "resolved" and self.diagnostic_code is None:
            raise ValueError(f"Edge.diagnostic_code is required when status == {self.status!r}")
        if self.line < 1:
            raise ValueError(f"Edge.line must be 1-indexed positive, got {self.line}")


@dataclass(frozen=True)
class DependencyGraph:
    """Frozen output of :class:`~chopper.compiler.TracerService` (P4).

    The graph is **reporting-only** — it never influences trimming. Its
    purpose is to let the domain owner see what their JSON selection
    transitively depends on.

    * ``pi_seeds`` — the PI set that seeded the BFS walk (every canonical
      proc name in ``manifest.proc_decisions`` at the time P4 started).
      Lex-sorted.
    * ``nodes`` — every canonical proc name reached by the walk (i.e.,
      PI+). Includes seeds plus every resolved callee. Lex-sorted.
    * ``reachable_from_includes`` — frozenset form of ``nodes``, exposed
      for O(1) membership tests by downstream consumers (trim report).
    * ``pt`` — ``nodes − pi_seeds`` (the traced-only set). Lex-sorted.
    * ``edges`` — every ``Edge`` recorded during the walk, sorted by
      ``(caller, kind, line, token, callee)`` so snapshot output is
      byte-stable.
    * ``unresolved_tokens`` — tuple of ``(caller, token, line,
      diagnostic_code)`` for every edge whose status is not ``"resolved"``;
      a convenience view derived from ``edges``. Kept frozen and
      lex-sorted.

    Invariants enforced in ``__post_init__``:

    1. ``nodes`` is lex-sorted and unique.
    2. ``pi_seeds`` ⊆ ``nodes`` and is lex-sorted.
    3. ``pt`` = ``nodes − pi_seeds`` exactly, lex-sorted.
    4. ``reachable_from_includes`` == ``frozenset(nodes)``.
    5. ``edges`` is sorted by ``(caller, kind, line, token, callee)``.
    """

    pi_seeds: tuple[str, ...]
    nodes: tuple[str, ...]
    pt: tuple[str, ...]
    edges: tuple[Edge, ...]
    reachable_from_includes: frozenset[str]
    unresolved_tokens: tuple[tuple[str, str, int, str], ...] = ()

    def __post_init__(self) -> None:
        if list(self.nodes) != sorted(self.nodes):
            raise ValueError("DependencyGraph.nodes must be lex-sorted")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("DependencyGraph.nodes must be unique")
        if list(self.pi_seeds) != sorted(self.pi_seeds):
            raise ValueError("DependencyGraph.pi_seeds must be lex-sorted")
        if not set(self.pi_seeds).issubset(set(self.nodes)):
            raise ValueError("DependencyGraph.pi_seeds must be a subset of nodes")
        expected_pt = tuple(sorted(set(self.nodes) - set(self.pi_seeds)))
        if self.pt != expected_pt:
            raise ValueError(
                f"DependencyGraph.pt must equal (nodes − pi_seeds), sorted; got {self.pt!r}, expected {expected_pt!r}"
            )
        if self.reachable_from_includes != frozenset(self.nodes):
            raise ValueError("DependencyGraph.reachable_from_includes must equal frozenset(nodes)")
        edge_keys = [(e.caller, e.kind, e.line, e.token, e.callee) for e in self.edges]
        if edge_keys != sorted(edge_keys):
            raise ValueError("DependencyGraph.edges must be sorted by (caller, kind, line, token, callee)")


# ---------------------------------------------------------------------------
# Stage 3a — Trimmer outputs (P5a).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileOutcome:
    """Per-file audit record produced by :class:`TrimmerService` (P5a).

    One outcome is emitted for every file the manifest reasoned over,
    regardless of
    treatment — ``REMOVE`` files appear too (with ``bytes_out=0`` and
    empty proc tuples) so the audit bundle has a complete ledger.

    * ``path`` — domain-relative POSIX path.
    * ``treatment`` — the :class:`FileTreatment` copied from the manifest.
    * ``bytes_in`` — size before trim. ``0`` when the file did not exist
      in backup (e.g. ``GENERATED`` treatment).
    * ``bytes_out`` — size after trim. ``0`` for ``REMOVE`` treatment.
    * ``procs_kept`` — canonical names of every proc retained in the
      output, lex-sorted.
    * ``procs_removed`` — canonical names of every proc deleted from
      the output, lex-sorted. Empty for ``FULL_COPY`` / ``REMOVE``.
    """

    path: Path
    treatment: FileTreatment
    bytes_in: int
    bytes_out: int
    procs_kept: tuple[str, ...]
    procs_removed: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.bytes_in < 0 or self.bytes_out < 0:
            raise ValueError(
                "FileOutcome byte counts must be non-negative, "
                f"got bytes_in={self.bytes_in}, bytes_out={self.bytes_out}"
            )
        if list(self.procs_kept) != sorted(self.procs_kept):
            raise ValueError("FileOutcome.procs_kept must be lex-sorted")
        if list(self.procs_removed) != sorted(self.procs_removed):
            raise ValueError("FileOutcome.procs_removed must be lex-sorted")
        if self.treatment is FileTreatment.REMOVE and self.bytes_out != 0:
            raise ValueError("FileOutcome: REMOVE treatment requires bytes_out == 0")
        if self.treatment in (FileTreatment.FULL_COPY, FileTreatment.REMOVE) and self.procs_removed:
            raise ValueError(f"FileOutcome: treatment {self.treatment} must not list procs_removed")


@dataclass(frozen=True)
class TrimReport:
    """Frozen output of :class:`~chopper.trimmer.TrimmerService` (P5a).

    Drives ``.chopper/trim_report.{json,txt}`` at P7.

    Invariants enforced in ``__post_init__``:

    1. ``outcomes`` is lex-sorted by POSIX path.
    2. The five aggregate counts equal the derived totals from
       ``outcomes``. This catches drift between the file-writer loop
       and the summary stamper.
    """

    outcomes: tuple[FileOutcome, ...]
    files_copied: int
    files_trimmed: int
    files_removed: int
    procs_kept_total: int
    procs_removed_total: int
    rebuild_interrupted: bool = False

    def __post_init__(self) -> None:
        paths = [o.path.as_posix() for o in self.outcomes]
        if paths != sorted(paths):
            raise ValueError("TrimReport.outcomes must be lex-sorted by POSIX path")

        expected_copied = sum(1 for o in self.outcomes if o.treatment is FileTreatment.FULL_COPY)
        expected_trimmed = sum(1 for o in self.outcomes if o.treatment is FileTreatment.PROC_TRIM)
        expected_removed = sum(1 for o in self.outcomes if o.treatment is FileTreatment.REMOVE)
        expected_kept = sum(len(o.procs_kept) for o in self.outcomes)
        expected_removed_procs = sum(len(o.procs_removed) for o in self.outcomes)

        if self.files_copied != expected_copied:
            raise ValueError(f"TrimReport.files_copied mismatch: got {self.files_copied}, derived {expected_copied}")
        if self.files_trimmed != expected_trimmed:
            raise ValueError(f"TrimReport.files_trimmed mismatch: got {self.files_trimmed}, derived {expected_trimmed}")
        if self.files_removed != expected_removed:
            raise ValueError(f"TrimReport.files_removed mismatch: got {self.files_removed}, derived {expected_removed}")
        if self.procs_kept_total != expected_kept:
            raise ValueError(
                f"TrimReport.procs_kept_total mismatch: got {self.procs_kept_total}, derived {expected_kept}"
            )
        if self.procs_removed_total != expected_removed_procs:
            raise ValueError(
                f"TrimReport.procs_removed_total mismatch: got {self.procs_removed_total}, "
                f"derived {expected_removed_procs}"
            )


# ---------------------------------------------------------------------------
# Stage 3b — Generator outputs (P5b).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedArtifact:
    """One file emitted by :class:`~chopper.generators.GeneratorService` (P5b).

        Generated run files live alongside normal domain files and are
        subject to post-trim validation at P6.

    * ``path`` — domain-relative POSIX path where the file was written.
        * ``kind`` — output kind. Only ``"tcl"`` is emitted in v1
            (``<stage>.tcl`` run files). ``"stack"`` and ``"csv"`` are
            reserved for optional stack-file and manifest emissions.
    * ``content`` — the full generated text. Kept on the record so the
      audit writer hashes exactly the emitted bytes.
    * ``source_stage`` — the :class:`StageSpec.name` that produced this
      artifact, for audit correlation.
    """

    path: Path
    kind: Literal["stack", "tcl", "csv"]
    content: str
    source_stage: str

    def __post_init__(self) -> None:
        if not self.source_stage:
            raise ValueError("GeneratedArtifact.source_stage must be non-empty")


# ---------------------------------------------------------------------------
# Stage 3c — Audit bundle (P7).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditArtifact:
    """One file written under ``.chopper/`` by :class:`AuditService`.

        Each artifact carries its own sha256 hash so downstream reviewers
        can verify byte-stability without re-running Chopper.

    * ``name`` — basename under ``.chopper/`` (e.g. ``"trim_report.json"``).
            Entries in :attr:`AuditManifest.artifacts` must be lex-sorted by
            this field.
    * ``path`` — absolute path the file was written to. Always under
      :attr:`RunConfig.audit_root`.
    * ``size`` — byte length of the written content.
    * ``sha256`` — hex-encoded SHA-256 of the content bytes (UTF-8).
    """

    name: str
    path: Path
    size: int
    sha256: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("AuditArtifact.name must be non-empty")
        if self.size < 0:
            raise ValueError(f"AuditArtifact.size must be non-negative, got {self.size}")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"AuditArtifact.sha256 must be a 64-char hex string, got {self.sha256!r}")


@dataclass(frozen=True)
class AuditManifest:
    """Inventory of every file :class:`AuditService` wrote under ``.chopper/``.

    This record is the in-memory projection of the audit bundle plus
    the ``artifacts`` inventory used by downstream tooling.

    * ``run_id`` — UUID v4 for this run. Stamped on every artifact.
    * ``started_at`` / ``ended_at`` — UTC timestamps bounding the run.
    * ``exit_code`` — the runner's final exit code (0/1/2/3).
    * ``artifacts`` — every :class:`AuditArtifact` written this run,
      lex-sorted by ``name``.
    * ``diagnostic_counts`` — mapping of severity → count, produced by
      :meth:`DiagnosticSink.finalize`.
    """

    run_id: str
    started_at: datetime
    ended_at: datetime
    exit_code: int
    artifacts: tuple[AuditArtifact, ...]
    diagnostic_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("AuditManifest.run_id must be non-empty")
        if self.exit_code not in (0, 1, 2, 3):
            raise ValueError(f"AuditManifest.exit_code must be 0/1/2/3, got {self.exit_code}")
        if self.ended_at < self.started_at:
            raise ValueError("AuditManifest.ended_at must be >= started_at")
        names = [a.name for a in self.artifacts]
        if names != sorted(names):
            raise ValueError("AuditManifest.artifacts must be lex-sorted by name")
        if len(set(names)) != len(names):
            raise ValueError("AuditManifest.artifacts must have unique names")


@dataclass(frozen=True)
class RunRecord:
    """Runtime snapshot handed to :class:`AuditService` at P7.

    Bundling the inputs into one record keeps the service signature
    stable as the bundle grows; the runner builds this once in its
    ``finally`` block and passes it in. Every field is ``Optional``
    because P7 runs even when earlier phases aborted.

    Field-to-artifact mapping:

    * ``chopper_run.json`` consumes ``run_id``, ``command``,
      ``started_at``, ``ended_at``, ``exit_code``, ``state``, ``loaded``.
    * ``compiled_manifest.json`` consumes ``manifest``.
    * ``dependency_graph.json`` consumes ``graph``.
    * ``trim_report.json`` / ``.txt`` consume ``manifest``, ``graph``,
      ``trim_report``, plus the diagnostic snapshot from ``ctx.diag``.
    * ``diagnostics.json`` consumes the diagnostic snapshot only.
    * ``trim_stats.json`` consumes ``parsed``, ``trim_report``,
      ``manifest``.
    * ``input_*`` files consume ``loaded`` (for source paths).
    """

    run_id: str
    command: Literal["validate", "trim", "cleanup"]
    started_at: datetime
    ended_at: datetime
    exit_code: int
    state: DomainState | None = None
    loaded: LoadedConfig | None = None
    parsed: ParseResult | None = None
    manifest: CompiledManifest | None = None
    graph: DependencyGraph | None = None
    trim_report: TrimReport | None = None
    generated_artifacts: tuple[GeneratedArtifact, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("RunRecord.run_id must be non-empty")
        if self.exit_code not in (0, 1, 2, 3):
            raise ValueError(f"RunRecord.exit_code must be 0/1/2/3, got {self.exit_code}")
        if self.ended_at < self.started_at:
            raise ValueError("RunRecord.ended_at must be >= started_at")


@dataclass(frozen=True)
class RunResult:
    """Typed result returned by :meth:`ChopperRunner.run`.

    The CLI's :mod:`chopper.cli.render` layer consumes this record and
    renders a human-readable summary; it also maps
    :attr:`exit_code` to the process exit status. Every optional field
    is ``None`` when the producing phase did not complete — the same
    contract :class:`RunRecord` honours for P7.

    ``exit_code`` meanings:

    * ``0`` — success, no warnings, no errors.
    * ``1`` — at least one ``ERROR`` diagnostic, **or** ``--strict``
      was set and at least one ``WARNING`` diagnostic was emitted.
    * ``2`` — CLI / environment error (missing domain, bad flags,
      user-facing ``VE-21`` Case 4, etc.).
    * ``3`` — internal programmer error (raised :class:`ChopperError`).
    """

    exit_code: int
    summary: DiagnosticSummary
    state: DomainState | None = None
    loaded: LoadedConfig | None = None
    parsed: ParseResult | None = None
    manifest: CompiledManifest | None = None
    graph: DependencyGraph | None = None
    trim_report: TrimReport | None = None
    generated_artifacts: tuple[GeneratedArtifact, ...] = ()

    def __post_init__(self) -> None:
        if self.exit_code not in (0, 1, 2, 3):
            raise ValueError(f"RunResult.exit_code must be 0/1/2/3, got {self.exit_code}")
