"""Core frozen dataclasses shared across every Chopper service.

Per bible §5.12.3 and ARCHITECTURE_PLAN.md §9.1, every record that crosses
a service boundary is an immutable :class:`dataclass` defined here. Services
never declare their own copies of these shapes.

Stage 0 ships the records that have no stage dependency and are used
across the port/orchestrator surface from day one:

* :class:`FileTreatment` — the per-file decision vocabulary emitted by the
  compiler (:mod:`chopper.compiler`) and consumed by the trimmer
  (:mod:`chopper.trimmer`).
* :class:`DomainState` — the Case 1–4 classification produced by
  ``DomainStateService`` (bible §2.8).
* :class:`FileStat` — the ``stat`` result returned by
  :class:`~chopper.core.protocols.FileSystemPort`.

Stage 1 (parser) adds:

* :class:`ProcEntry` — the per-proc record produced by
  :func:`chopper.parser.parse_file` (TCL_PARSER_SPEC §6).
* :class:`ParsedFile` — the per-file aggregate (ARCHITECTURE_PLAN.md §9.1).
* :class:`ParseResult` — the domain-wide aggregate with canonical-name
  index (ARCHITECTURE_PLAN.md §9.1; bible §5.4.1).

Later stages (compiler, trimmer, audit) append their own records here —
each stage may not depend on a later stage's shapes (ARCHITECTURE_PLAN.md
§10.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

__all__ = [
    "AddStageAction",
    "AddStepAction",
    "BaseJson",
    "BaseOptions",
    "DomainState",
    "FeatureJson",
    "FeatureMetadata",
    "FileStat",
    "FileTreatment",
    "FilesSection",
    "FlowAction",
    "LoadFromAction",
    "LoadedConfig",
    "ParseResult",
    "ParsedFile",
    "ProcEntry",
    "ProcEntryRef",
    "ProceduresSection",
    "ProjectJson",
    "RemoveStageAction",
    "RemoveStepAction",
    "ReplaceStageAction",
    "ReplaceStepAction",
    "StageDefinition",
]


class FileTreatment(StrEnum):
    """Per-file disposition emitted by the compiler.

    The four values are defined by bible §5.5 and listed in the architecture
    plan as the only legal entries in ``CompiledManifest.file_decisions``
    (ARCHITECTURE_PLAN.md §9.1, :class:`FileOutcome`).

    * ``FULL_COPY`` — file is included whole; trimmer copies it verbatim from
      ``<domain>_backup/`` to ``<domain>/``.
    * ``PROC_TRIM`` — file survives but some procs are dropped; trimmer
      rewrites the file with the excluded proc blocks removed.
    * ``GENERATED`` — file is synthesised by ``GeneratorService`` (F3 run
      files); no backup source exists.
    * ``REMOVE`` — file does not appear in the trimmed domain.

    :class:`enum.StrEnum` makes instances serialise directly to JSON as
    their string value (bible §5.11.4) without a custom encoder.
    """

    FULL_COPY = "FULL_COPY"
    PROC_TRIM = "PROC_TRIM"
    GENERATED = "GENERATED"
    REMOVE = "REMOVE"


@dataclass(frozen=True)
class DomainState:
    """Result of the Phase 0 ``DomainStateService`` classification.

    Per bible §2.8, the state-machine observes ``<domain>/`` and
    ``<domain>_backup/`` at invocation and classifies the workspace into
    one of four cases:

    * Case 1 — ``domain_exists=True``, ``backup_exists=False`` (first trim).
    * Case 2 — ``domain_exists=True``, ``backup_exists=True`` (re-trim).
    * Case 3 — ``domain_exists=False``, ``backup_exists=True`` (recovery
      re-trim; backup is authoritative).
    * Case 4 — ``domain_exists=False``, ``backup_exists=False`` (fatal;
      the CLI emits ``VE-21`` and exits 2).

    ``hand_edited`` is an informational flag only. Chopper does not emit a
    diagnostic on detection (see bible §2.8 Case 2 and
    ARCHITECTURE_PLAN.md §16 Q2); the CLI prints a fixed pre-flight warning
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
    to size files for audit reporting (bible §5.5, P7 artifacts).

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

    Authoritative field list: TCL_PARSER_SPEC.md §6. Invariants: §6.1. Body
    boundary semantics: §6.2. Canonical-name format (``<domain-relative-
    posix-path>::<qualified_name>``) comes from bible §5.4.1.

    Call-site handoff fields (``calls`` and ``source_refs``) are the only
    coupling between parser and tracer. Both are textual / unresolved;
    resolution happens in P4 (bible §5.4 R3, TCL_PARSER_SPEC §5.3.1).

    Invariants checked in ``__post_init__``:

    1. ``start_line`` / ``end_line`` / ``body_*`` are 1-indexed positive
       ints and ``start_line <= end_line``.
    2. Body lines are within ``[start_line, end_line]``. Empty-body form
       (``body_start_line > body_end_line``) is allowed — it is the signal
       that the body has zero content lines (§6.2 edge case).
    3. Optional DPA and comment-banner spans, when set, are consistent
       (``start <= end`` and both non-None together).
    4. ``canonical_name`` equals ``f"{source_file.as_posix()}::{qualified_name}"``.
    5. ``calls`` is deduplicated and lexicographically sorted (§6.1
       invariant 5); ``source_refs`` is a tuple of POSIX strings (no
       ordering requirement at parse time — §6.1 invariant 6).
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

        # 4. Canonical-name format (bible §5.4.1).
        expected = f"{self.source_file.as_posix()}::{self.qualified_name}"
        if self.canonical_name != expected:
            raise ValueError(
                f"ProcEntry.canonical_name {self.canonical_name!r} does not match "
                f"'<source_file.as_posix()>::<qualified_name>' = {expected!r}"
            )

        # 5. calls tuple is dedup + lex-sorted per §6.1 invariant 5.
        if list(self.calls) != sorted(set(self.calls)):
            raise ValueError("ProcEntry.calls must be deduplicated and lexicographically sorted")


@dataclass(frozen=True)
class ParsedFile:
    """Per-file aggregate returned by ``ParserService`` for one Tcl file.

    Authoritative shape: ARCHITECTURE_PLAN.md §9.1. Fields held here:

    * ``path`` — domain-relative :class:`~pathlib.Path`.
    * ``procs`` — tuple of :class:`ProcEntry`, sorted by ``start_line``.
    * ``encoding`` — the encoding used to decode the file
      (``"utf-8"`` when the initial decode succeeded; ``"latin-1"`` if the
      parser fell back per TCL_PARSER_SPEC §2 and emitted ``PW-02``).

    Parse-error diagnostics are emitted via ``ctx.diag`` as they are
    discovered (ARCHITECTURE_PLAN.md §8.2 rule 1); they never appear on
    this record.
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

    Authoritative shape: ARCHITECTURE_PLAN.md §9.1; canonical-name format
    bible §5.4.1; test vectors TCL_PARSER_SPEC §4.3.1.

    * ``files`` — maps domain-relative path to :class:`ParsedFile`. The
      parser constructs this as a plain :class:`dict` sorted lex on the
      POSIX form of the path; the mapping is frozen only in the sense
      that the enclosing :class:`ParseResult` is frozen (callers must
      not mutate).
    * ``index`` — maps ``canonical_name`` to :class:`ProcEntry` for O(1)
      lookup by the compiler and tracer. The same :class:`ProcEntry`
      instance appears in ``files[path].procs`` and ``index[cn]``.

    Invariants checked in ``__post_init__``:

    1. Every ``ProcEntry`` in every ``ParsedFile.procs`` appears in
       ``index`` under its ``canonical_name``, and only those entries
       appear. This catches divergence between the two views.
    2. ``canonical_name`` keys in ``index`` are lex-sorted (required for
       deterministic dependency-graph output — bible §5.4.1).
    """

    files: dict[Path, ParsedFile] = field(default_factory=dict)
    index: dict[str, ProcEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 1. Index ↔ files consistency.
        from_files: dict[str, ProcEntry] = {}
        for parsed in self.files.values():
            for proc in parsed.procs:
                if proc.canonical_name in from_files:
                    raise ValueError(f"ParseResult: duplicate canonical_name across files: {proc.canonical_name!r}")
                from_files[proc.canonical_name] = proc
        if set(from_files) != set(self.index):
            raise ValueError("ParseResult.index keys diverge from the procs listed in ParseResult.files")
        for cn, proc in self.index.items():
            if from_files[cn] is not proc:
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
# Authoritative schemas: json_kit/schemas/{base,feature,project}-v1.schema.json.
# Authoritative prose:   bible §§3.1–3.3; ARCHITECTURE_PLAN.md §9.1.
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
    feature schemas. Field semantics follow bible §3.6 and the schema
    descriptions; this record preserves the authored values verbatim so
    the F3 generator can emit run scripts and stack lines deterministically.
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

    Only one flag in v1: ``cross_validate`` (bible §3.1 key fields
    table). Defaults to ``True`` — post-trim cross-validation emits
    ``VW-14`` / ``VW-15`` / ``VW-16`` unless authors opt out.
    """

    cross_validate: bool = True


@dataclass(frozen=True)
class BaseJson:
    """Hydrated ``chopper/base/v1`` JSON.

    Per bible §3.1: ``$schema`` and ``domain`` are required; at least
    one of ``files`` / ``procedures`` / ``stages`` must be present. The
    loader enforces the at-least-one rule via the jsonschema ``anyOf``
    constraint and maps failures to ``VE-02``.

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

    Chopper never evaluates these fields (bible §3.2); they are
    preserved verbatim in audit artifacts.
    """

    owner: str | None = None
    tags: tuple[str, ...] = ()
    wiki: str | None = None
    related_ivars: tuple[str, ...] = ()
    related_appvars: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureJson:
    """Hydrated ``chopper/feature/v1`` JSON.

    Per bible §3.2: ``$schema`` and ``name`` are required; everything
    else is optional. Feature ``name`` must be unique across a project
    (``VE-14``); ``depends_on`` prerequisites must be selected
    (``VE-15``) and acyclic (``VE-22``).
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
    """Hydrated ``chopper/project/v1`` JSON.

    Per bible §3.3: ``$schema``, ``project``, ``domain``, and ``base``
    are required. ``base`` and each entry in ``features`` are
    domain-relative path strings as authored — the service layer
    resolves them to :class:`Path` against ``ctx.config.domain_root``
    after the schema check. ``VE-13`` (unresolvable paths) is emitted
    by the CLI pre-pass before :class:`ConfigService` runs.
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

    Authoritative shape: ARCHITECTURE_PLAN.md §9.1.

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
      :class:`ParserService.run` consumes in P2 (ARCHITECTURE_PLAN.md
      §6.2). Glob expansion against the real filesystem is **not** done
      here — that is the compiler's responsibility in P3.
    """

    base: BaseJson
    features: tuple[FeatureJson, ...] = ()
    project: ProjectJson | None = None
    surface_files: tuple[Path, ...] = ()

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
