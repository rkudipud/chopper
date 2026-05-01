"""CompilerService — P3 R1 merge algorithm.

Implements the provenance-aware include/exclude resolution in two passes:

1. **Per-source classification.** For every source ``s`` (base JSON plus
   each topo-sorted feature) and every relevant file ``F``, decide
   ``s``'s contribution as one of:

   * ``_NONE``   — source contributes nothing for this file;
   * ``_WHOLE``  — source wants the whole file (``FULL_COPY`` signal);
   * ``_TRIM(keep)`` — source wants the file with a specific proc subset.

   Same-source authoring diagnostics (``VW-09``, ``VW-11``, ``VW-12``,
   ``VW-13``) are emitted here.

2. **Cross-source aggregation.** Per-source contributions union: any
   ``_WHOLE`` wins and forces ``FULL_COPY``; otherwise every ``_TRIM``
   unions into a single ``PROC_TRIM`` survivor set. Cross-source vetoes
   (``VW-18``, ``VW-19``) are emitted here.

F1/F2 aggregation is **order-independent**. Feature order matters only
for the first-wins ``selection_source`` stamping on :class:`ProcDecision`
and for F3 ``flow_actions`` sequencing (delegated to
:mod:`chopper.compiler.flow_resolver`).

Not this service's job:

* trace (PI+) diagnostics — owned by :class:`TracerService` (P4);
* filesystem existence (``VE-06``) or post-trim integrity (``VE-16``) —
  owned by the validator.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from re import Pattern
from typing import Literal

from chopper.compiler.flow_resolver import resolve_stages
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.errors import ChopperError
from chopper.core.models import (
    BaseJson,
    CompiledManifest,
    FeatureJson,
    FileProvenance,
    FileTreatment,
    LoadedConfig,
    ParseResult,
    ProcDecision,
)

__all__ = ["CompilerService"]


# ---------------------------------------------------------------------------
# Per-source value objects (internal to this module).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SourceRef:
    """Identifies one JSON source for diagnostics + provenance tagging."""

    key: str  # "base" or feature.name
    source_path: Path  # original JSON path (for diagnostic provenance)


@dataclass(frozen=True)
class _SourceFacts:
    """Pre-computed per-source sets consumed by classification and aggregation."""

    ref: _SourceRef
    fi_literal: frozenset[Path]  # exact file paths named by files.include
    fi_glob_surviving: frozenset[Path]  # glob-matched files after same-source FE pruning
    fe_literal: frozenset[Path]  # files.exclude hits on parsed files (literal + glob)
    pi_by_file: dict[Path, frozenset[str]]  # procedures.include: file → {short/qualified name}
    pe_by_file: dict[Path, frozenset[str]]  # procedures.exclude: file → {short/qualified name}


@dataclass(frozen=True)
class _Contribution:
    """One (source, file) classification outcome."""

    kind: Literal["NONE", "WHOLE", "TRIM"]
    keep: frozenset[str] = frozenset()  # canonical_names (TRIM only)
    reason: str = ""  # kebab-case tag for FileProvenance.reason
    json_field: str = ""  # "files.include" | "procedures.include" | "procedures.exclude"


_NONE = _Contribution(kind="NONE")


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompilerService:
    """Phase 3 merge service.

    Stateless: every call to :meth:`run` is independent. The returned
    :class:`~chopper.core.models.CompiledManifest` is frozen and ready
    for consumption by :class:`~chopper.compiler.TracerService` (P4).
    """

    def run(self, ctx: ChopperContext, loaded: LoadedConfig, parsed: ParseResult) -> CompiledManifest:
        """Merge ``loaded`` against ``parsed`` per R1 and return the manifest."""
        sources, facts_by_source = _build_source_facts(loaded, parsed)

        # Universe of files the manifest reasons over: parsed files + every
        # literal path named by any source that the parser did not see
        # (non-.tcl companions such as config files surface here).
        universe = _collect_universe(parsed, facts_by_source.values())

        # Pre-compute all_procs(F) (canonical_name set) for quick classification.
        all_procs_by_file: dict[Path, frozenset[str]] = {
            path: frozenset(p.canonical_name for p in pf.procs) for path, pf in parsed.files.items()
        }
        for path in universe:
            all_procs_by_file.setdefault(path, frozenset())

        # ---- Pass 1: per-source per-file classification (L2) -----------------
        contribs_by_source: dict[_SourceRef, dict[Path, _Contribution]] = {}
        for src in sources:
            facts = facts_by_source[src]
            contribs_by_source[src] = _classify_source(ctx, facts, universe, all_procs_by_file, parsed)

        # ---- Pass 2: cross-source aggregation (L1 + L3) ----------------------
        file_decisions, proc_decisions, provenance = _aggregate(
            ctx, sources, contribs_by_source, facts_by_source, universe, all_procs_by_file, parsed
        )

        # ---- Pass 3: F3 flow-action resolution -----------------------------
        stages = resolve_stages(ctx, loaded.base.stages, loaded.features)
        _register_generated_stage_files(file_decisions, provenance, stages, loaded)

        return CompiledManifest(
            file_decisions=file_decisions,
            proc_decisions=proc_decisions,
            provenance=provenance,
            stages=stages,
            generate_stack=loaded.base.options.generate_stack,
        )


# ---------------------------------------------------------------------------
# Pass 3 helper — F3 generated-file registration
# ---------------------------------------------------------------------------


def _register_generated_stage_files(
    file_decisions: dict[Path, FileTreatment],
    provenance: dict[Path, FileProvenance],
    stages: tuple,
    loaded: LoadedConfig,
) -> None:
    """Record one :class:`FileTreatment.GENERATED` entry per resolved stage.

    ``GeneratorService`` emits ``<stage>.tcl`` at domain root for every
    resolved stage. These paths must appear in
    ``manifest.file_decisions`` so that the trimmer (P5) knows to skip
    them (generator owns the writes) and the audit bundle (P7) can
    surface them in ``compiled_manifest.json``.

    When ``base.options.generate_stack`` is ``True``, the same registration
    is performed for ``<stage>.stack`` so the stack files participate in
    the manifest, trimmer skip-set, and audit bundle just like the
    ``.tcl`` run scripts.

    Collisions with trimmer-managed paths are a programmer-authoring
    error; we raise :class:`ChopperError` (exit 3) rather than invent
    a cross-phase diagnostic.
    """

    if not stages:
        return

    # Record which sources contributed to the F3 pipeline. The base JSON
    # seeds stages; every feature with at least one flow_action mutates
    # it. Lex-sorted for determinism (matches FileProvenance invariant).
    contributors: list[str] = ["base:stages"]
    for feature in loaded.features:
        if feature.flow_actions:
            contributors.append(f"{feature.name}:flow_actions")
    input_sources = tuple(sorted(contributors))

    emit_stack = loaded.base.options.generate_stack

    for stage in stages:
        tcl_path = Path(f"{stage.name}.tcl")
        if tcl_path in file_decisions:
            raise ChopperError(
                f"F3 generated path {tcl_path.as_posix()!r} collides with an "
                f"existing file decision; rename the stage or drop the "
                f"colliding files.* entry"
            )
        file_decisions[tcl_path] = FileTreatment.GENERATED
        provenance[tcl_path] = FileProvenance(
            path=tcl_path,
            treatment=FileTreatment.GENERATED,
            reason="fi-literal",
            input_sources=input_sources,
            vetoed_entries=(),
            proc_model=None,
        )

        if emit_stack:
            stack_path = Path(f"{stage.name}.stack")
            if stack_path in file_decisions:
                raise ChopperError(
                    f"F3 generated path {stack_path.as_posix()!r} collides with an "
                    f"existing file decision; rename the stage, disable "
                    f"options.generate_stack, or drop the colliding files.* entry"
                )
            file_decisions[stack_path] = FileTreatment.GENERATED
            provenance[stack_path] = FileProvenance(
                path=stack_path,
                treatment=FileTreatment.GENERATED,
                reason="fi-literal",
                input_sources=input_sources,
                vetoed_entries=(),
                proc_model=None,
            )

    # CompiledManifest requires lex-sorted keys by POSIX form. Re-sort
    # file_decisions and provenance in place after insertion.
    _resort_by_posix(file_decisions)
    _resort_by_posix(provenance)


def _resort_by_posix(mapping: dict) -> None:
    sorted_items = sorted(mapping.items(), key=lambda kv: kv[0].as_posix())
    mapping.clear()
    mapping.update(sorted_items)


# ---------------------------------------------------------------------------
# Pass 1 — per-source fact extraction
# ---------------------------------------------------------------------------


def _build_source_facts(
    loaded: LoadedConfig, parsed: ParseResult
) -> tuple[list[_SourceRef], dict[_SourceRef, _SourceFacts]]:
    """Iterate sources in canonical order (base then features) and distill
    each into a :class:`_SourceFacts` record."""
    parsed_paths = frozenset(parsed.files.keys())

    sources: list[_SourceRef] = []
    facts: dict[_SourceRef, _SourceFacts] = {}

    base_ref = _SourceRef(key="base", source_path=loaded.base.source_path)
    sources.append(base_ref)
    facts[base_ref] = _extract_facts(base_ref, loaded.base, parsed_paths)

    for feature in loaded.features:
        f_ref = _SourceRef(key=feature.name, source_path=feature.source_path)
        sources.append(f_ref)
        facts[f_ref] = _extract_facts(f_ref, feature, parsed_paths)

    return sources, facts


def _extract_facts(
    ref: _SourceRef,
    source: BaseJson | FeatureJson,
    parsed_paths: frozenset[Path],
) -> _SourceFacts:
    """Partition ``files.include`` into literal / glob buckets, apply
    same-source FE pruning to the glob bucket, and collect PI/PE by file."""
    files = source.files
    fi_literal_set: set[Path] = set()
    fi_glob_patterns: list[str] = []
    for entry in files.include:
        if _is_glob(entry):
            fi_glob_patterns.append(entry)
        else:
            fi_literal_set.add(Path(entry))

    fe_literal_set: set[Path] = set()
    fe_glob_patterns: list[str] = []
    for entry in files.exclude:
        if _is_glob(entry):
            fe_glob_patterns.append(entry)
        else:
            fe_literal_set.add(Path(entry))

    # FE hits on parsed files: literal hits + glob matches against parsed_paths.
    fe_hits: set[Path] = {p for p in fe_literal_set if p in parsed_paths}
    for pattern in fe_glob_patterns:
        fe_hits.update(_match_glob(pattern, parsed_paths))

    # FI glob expansion against parsed_paths.
    fi_glob_matches: set[Path] = set()
    for pattern in fi_glob_patterns:
        fi_glob_matches.update(_match_glob(pattern, parsed_paths))
    # L2.1: same-source FE prunes same-source glob expansions; literal FI always survives.
    fi_glob_surviving = fi_glob_matches - fe_hits

    pi_by_file: dict[Path, set[str]] = {}
    for proc_ref in source.procedures.include:
        pi_by_file.setdefault(proc_ref.file, set()).update(proc_ref.procs)

    pe_by_file: dict[Path, set[str]] = {}
    for proc_ref in source.procedures.exclude:
        pe_by_file.setdefault(proc_ref.file, set()).update(proc_ref.procs)

    return _SourceFacts(
        ref=ref,
        fi_literal=frozenset(fi_literal_set),
        fi_glob_surviving=frozenset(fi_glob_surviving),
        fe_literal=frozenset(fe_hits),
        pi_by_file={k: frozenset(v) for k, v in pi_by_file.items()},
        pe_by_file={k: frozenset(v) for k, v in pe_by_file.items()},
    )


def _collect_universe(parsed: ParseResult, facts_iter: Iterable[_SourceFacts]) -> list[Path]:
    """Universe of files the manifest reasons over — lex-sorted by POSIX.

    Includes every parsed file plus every literal ``files.include`` path
    across all sources (literal FI can refer to non-``.tcl`` companion
    files that the parser does not cover).
    """
    paths: set[Path] = set(parsed.files.keys())
    for facts in facts_iter:
        paths.update(facts.fi_literal)
    return sorted(paths, key=lambda p: p.as_posix())


# ---------------------------------------------------------------------------
# Pass 1 — per-source per-file classification (L2)
# ---------------------------------------------------------------------------


def _classify_source(
    ctx: ChopperContext,
    facts: _SourceFacts,
    universe: list[Path],
    all_procs_by_file: dict[Path, frozenset[str]],
    parsed: ParseResult,
) -> dict[Path, _Contribution]:
    """Apply same-source R1 rules to every (source, file) in ``universe``.
    Emits ``VW-09``, ``VW-11``, ``VW-12``, ``VW-13``."""
    return {fp: _classify_one(ctx, facts, fp, all_procs_by_file, parsed) for fp in universe}


def _classify_one(
    ctx: ChopperContext,
    facts: _SourceFacts,
    file_path: Path,
    all_procs_by_file: dict[Path, frozenset[str]],
    parsed: ParseResult,
) -> _Contribution:
    """Classify one (source, file) pair per the 16-row same-source matrix.

    FI / FE / PI / PE are boolean flags describing whether this source
    has any include/exclude signal for ``file_path``. The
    literal-vs-glob distinction matters only for same-source FE
    interaction (literal survives its own FE; glob does not, and is
    already pruned out of ``facts.fi_glob_surviving``).
    """
    is_fi_literal = file_path in facts.fi_literal
    is_fi_glob = file_path in facts.fi_glob_surviving
    fi_any = is_fi_literal or is_fi_glob
    is_fe_hit = file_path in facts.fe_literal
    pi_set = facts.pi_by_file.get(file_path, frozenset())
    pe_set = facts.pe_by_file.get(file_path, frozenset())

    all_procs = all_procs_by_file.get(file_path, frozenset())

    # Build short/qualified → canonical_name map for this parsed file.
    short_to_canonical: dict[str, str] = {}
    parsed_file = parsed.files.get(file_path)
    if parsed_file is not None:
        for proc in parsed_file.procs:
            short_to_canonical[proc.short_name] = proc.canonical_name
            short_to_canonical[proc.qualified_name] = proc.canonical_name

    pi_canonical = frozenset(short_to_canonical[s] for s in pi_set if s in short_to_canonical)
    pe_canonical = frozenset(short_to_canonical[s] for s in pe_set if s in short_to_canonical)

    # Row 1: nothing.
    if not (fi_any or is_fe_hit or pi_set or pe_set):
        return _NONE

    # Row 12: FE + PE only (no FI, no PI) → same-source contradiction. Emit VW-11.
    if is_fe_hit and not fi_any and not pi_set and pe_set:
        _emit_vw11(ctx, facts.ref, file_path)
        return _NONE

    # Row 3: FE alone → NONE (candidate for cross-source veto surfacing).
    if is_fe_hit and not fi_any and not pi_set and not pe_set:
        return _NONE

    # Rows 7 / 13: PI + PE without FI. PI wins; emit VW-12.
    if pi_set and pe_set and not fi_any:
        _emit_vw12(ctx, facts.ref, file_path)
        return _Contribution(
            kind="TRIM",
            keep=pi_canonical,
            reason="pi-additive",
            json_field="procedures.include",
        )

    # Rows 8 / 14: FI + PI (no PE). PI redundant with WHOLE; emit VW-09.
    if fi_any and pi_set and not pe_set:
        _emit_vw09(ctx, facts.ref, file_path)
        return _whole(all_procs, is_fi_literal)

    # Rows 9 / 15: FI + PE (no PI). PE qualifies FI into TRIM(all − PE).
    if fi_any and pe_set and not pi_set:
        if is_fe_hit and not is_fi_literal:
            return _NONE  # Row 15 glob-only pruned by same-source FE
        keep = all_procs - pe_canonical
        if not keep and all_procs:
            _emit_vw13(ctx, facts.ref, file_path)
        return _Contribution(
            kind="TRIM",
            keep=keep,
            reason="fi-and-pe" if is_fi_literal else "pe-subtractive",
            json_field="procedures.exclude",
        )

    # Rows 10 / 16: FI + PI + PE. PI redundant with FI; PE qualifies. Emit VW-09.
    if fi_any and pi_set and pe_set:
        _emit_vw09(ctx, facts.ref, file_path)
        if is_fe_hit and not is_fi_literal:
            return _NONE
        keep = all_procs - pe_canonical
        if not keep and all_procs:
            _emit_vw13(ctx, facts.ref, file_path)
        return _Contribution(
            kind="TRIM",
            keep=keep,
            reason="fi-and-pe",
            json_field="procedures.exclude",
        )

    # Rows 2 / 4: FI only (literal or glob-surviving), possibly with same-source FE.
    if fi_any and not pi_set and not pe_set:
        return _whole(all_procs, is_fi_literal)

    # Row 11: FE + PI (no FI, no PE). PI contributes; FE is moot for same-source PI.
    if pi_set and is_fe_hit and not pe_set and not fi_any:
        return _Contribution(
            kind="TRIM",
            keep=pi_canonical,
            reason="pi-additive",
            json_field="procedures.include",
        )

    # Row 5: PI only.
    if pi_set and not pe_set and not fi_any and not is_fe_hit:
        return _Contribution(
            kind="TRIM",
            keep=pi_canonical,
            reason="pi-additive",
            json_field="procedures.include",
        )

    # Row 6: PE only (no FI, no FE, no PI).
    if pe_set and not pi_set and not fi_any and not is_fe_hit:
        keep = all_procs - pe_canonical
        if not keep and all_procs:
            _emit_vw13(ctx, facts.ref, file_path)
        return _Contribution(
            kind="TRIM",
            keep=keep,
            reason="pe-subtractive",
            json_field="procedures.exclude",
        )

    raise AssertionError(
        f"CompilerService: unclassified row (source={facts.ref.key!r}, file={file_path!r}, "
        f"FI_lit={is_fi_literal}, FI_glob={is_fi_glob}, FE={is_fe_hit}, "
        f"PI={bool(pi_set)}, PE={bool(pe_set)})"
    )


def _whole(all_procs: frozenset[str], is_fi_literal: bool) -> _Contribution:
    return _Contribution(
        kind="WHOLE",
        keep=all_procs,
        reason="fi-literal" if is_fi_literal else "fi-glob",
        json_field="files.include",
    )


# ---------------------------------------------------------------------------
# Pass 2 — cross-source aggregation (L1 + L3)
# ---------------------------------------------------------------------------


def _aggregate(
    ctx: ChopperContext,
    sources: list[_SourceRef],
    contribs_by_source: dict[_SourceRef, dict[Path, _Contribution]],
    facts_by_source: dict[_SourceRef, _SourceFacts],
    universe: list[Path],
    all_procs_by_file: dict[Path, frozenset[str]],
    parsed: ParseResult,
) -> tuple[dict[Path, FileTreatment], dict[str, ProcDecision], dict[Path, FileProvenance]]:
    file_decisions: dict[Path, FileTreatment] = {}
    proc_decisions: dict[str, ProcDecision] = {}
    provenance: dict[Path, FileProvenance] = {}

    # Pre-compute per-source PE canonical-name set per file — only actual
    # ``procedures.exclude`` entries contribute to VW-18 surfacing.
    # A source that simply did not name a proc via PI is not PE-ing it,
    # so must not trigger VW-18.
    pe_canonical_by_source: dict[_SourceRef, dict[Path, frozenset[str]]] = {}
    for src, facts in facts_by_source.items():
        per_file: dict[Path, frozenset[str]] = {}
        for file_path, pe_set in facts.pe_by_file.items():
            parsed_file = parsed.files.get(file_path)
            if parsed_file is None:
                continue
            short_to_canonical: dict[str, str] = {}
            for proc in parsed_file.procs:
                short_to_canonical[proc.short_name] = proc.canonical_name
                short_to_canonical[proc.qualified_name] = proc.canonical_name
            per_file[file_path] = frozenset(short_to_canonical[s] for s in pe_set if s in short_to_canonical)
        pe_canonical_by_source[src] = per_file

    for file_path in universe:
        treatment, pv, procs_stamped = _aggregate_one(
            ctx,
            sources,
            contribs_by_source,
            facts_by_source,
            pe_canonical_by_source,
            file_path,
            all_procs_by_file,
            parsed,
        )
        file_decisions[file_path] = treatment
        provenance[file_path] = pv
        for pd in procs_stamped:
            proc_decisions.setdefault(pd.canonical_name, pd)

    sorted_proc_decisions = {k: proc_decisions[k] for k in sorted(proc_decisions)}
    return file_decisions, sorted_proc_decisions, provenance


def _aggregate_one(
    ctx: ChopperContext,
    sources: list[_SourceRef],
    contribs_by_source: dict[_SourceRef, dict[Path, _Contribution]],
    facts_by_source: dict[_SourceRef, _SourceFacts],
    pe_canonical_by_source: dict[_SourceRef, dict[Path, frozenset[str]]],
    file_path: Path,
    all_procs_by_file: dict[Path, frozenset[str]],
    parsed: ParseResult,
) -> tuple[FileTreatment, FileProvenance, list[ProcDecision]]:
    """Cross-source aggregation for one file."""
    all_procs = all_procs_by_file.get(file_path, frozenset())

    whole_sources: list[_SourceRef] = []
    trim_contribs: list[tuple[_SourceRef, _Contribution]] = []
    for src in sources:
        contrib = contribs_by_source[src][file_path]
        if contrib.kind == "WHOLE":
            whole_sources.append(src)
        elif contrib.kind == "TRIM":
            trim_contribs.append((src, contrib))

    fe_sources: list[_SourceRef] = [s for s in sources if file_path in facts_by_source[s].fe_literal]
    contributing_sources: set[_SourceRef] = set(whole_sources) | {s for s, _ in trim_contribs}

    def _pe_of(src: _SourceRef) -> frozenset[str]:
        return pe_canonical_by_source.get(src, {}).get(file_path, frozenset())

    # ---- Case A: at least one WHOLE → FULL_COPY ------------------------------
    if whole_sources:
        treatment = FileTreatment.FULL_COPY
        winner = whole_sources[0]
        winner_contrib = contribs_by_source[winner][file_path]
        vetoed: list[str] = []
        for src in fe_sources:
            if src in contributing_sources:
                continue
            _emit_vw19(ctx, src, file_path, blocker=winner)
            vetoed.append(f"{src.key}:files.exclude")
        # VW-18: for every source with actual PE entries, each PE proc that
        # still survives (all procs survive under FULL_COPY) is vetoed.
        for src in sources:
            if src is winner:
                continue
            for proc_cn in sorted(_pe_of(src) & all_procs):
                _emit_vw18(ctx, src, file_path, proc_cn, blocker=winner)
                vetoed.append(f"{src.key}:procedures.exclude:{proc_cn}")
        input_sources = _stamp_input_sources(whole_sources, trim_contribs, contribs_by_source, file_path)
        pv = FileProvenance(
            path=file_path,
            treatment=treatment,
            reason=winner_contrib.reason,
            input_sources=tuple(sorted(input_sources)),
            vetoed_entries=tuple(sorted(vetoed)),
            proc_model=None,
        )
        procs_stamped = _stamp_procs_full_copy(parsed, file_path, winner, winner_contrib)
        return treatment, pv, procs_stamped

    # ---- Case B: TRIM only → PROC_TRIM ---------------------------------------
    if trim_contribs:
        union_keep: set[str] = set()
        proc_source_winner: dict[str, tuple[_SourceRef, _Contribution]] = {}
        for src, contrib in trim_contribs:
            for proc_cn in contrib.keep:
                union_keep.add(proc_cn)
                proc_source_winner.setdefault(proc_cn, (src, contrib))

        trim_vetoed: list[str] = []
        # VW-18: only actual PE entries that lose to another source's include.
        for src in sources:
            own_contrib = contribs_by_source[src][file_path]
            own_keep = own_contrib.keep if own_contrib.kind == "TRIM" else frozenset()
            for proc_cn in sorted(_pe_of(src)):
                if proc_cn not in union_keep or proc_cn in own_keep:
                    continue
                blocker_src = proc_source_winner[proc_cn][0]
                if blocker_src is src:
                    continue
                _emit_vw18(ctx, src, file_path, proc_cn, blocker=blocker_src)
                trim_vetoed.append(f"{src.key}:procedures.exclude:{proc_cn}")
        for src in fe_sources:
            if src in contributing_sources:
                continue
            _emit_vw19(ctx, src, file_path, blocker=trim_contribs[0][0])
            trim_vetoed.append(f"{src.key}:files.exclude")

        _, first_contrib = trim_contribs[0]
        reason = first_contrib.reason
        proc_model: Literal["additive", "subtractive"] = "additive" if "pi" in reason else "subtractive"

        input_sources = _stamp_input_sources([], trim_contribs, contribs_by_source, file_path)
        treatment = FileTreatment.PROC_TRIM
        pv = FileProvenance(
            path=file_path,
            treatment=treatment,
            reason=reason,
            input_sources=tuple(sorted(input_sources)),
            vetoed_entries=tuple(sorted(trim_vetoed)),
            proc_model=proc_model,
        )
        procs_stamped = []
        for proc_cn in sorted(union_keep):
            winner_src, winner_contrib = proc_source_winner[proc_cn]
            procs_stamped.append(
                ProcDecision(
                    canonical_name=proc_cn,
                    source_file=file_path,
                    selection_source=f"{winner_src.key}:{winner_contrib.json_field}",
                )
            )
        return treatment, pv, procs_stamped

    # ---- Case C: no contribution → REMOVE ------------------------------------
    # (GENERATED is a Stage 2d concern — no flow_actions here.)
    treatment = FileTreatment.REMOVE
    pv = FileProvenance(
        path=file_path,
        treatment=treatment,
        reason="default-exclude",
        input_sources=(),
        vetoed_entries=(),
        proc_model=None,
    )
    return treatment, pv, []


def _stamp_input_sources(
    whole_sources: list[_SourceRef],
    trim_contribs: list[tuple[_SourceRef, _Contribution]],
    contribs_by_source: dict[_SourceRef, dict[Path, _Contribution]],
    file_path: Path,
) -> list[str]:
    out: list[str] = []
    for src in whole_sources:
        out.append(f"{src.key}:{contribs_by_source[src][file_path].json_field}")
    for src, contrib in trim_contribs:
        out.append(f"{src.key}:{contrib.json_field}")
    return out


def _stamp_procs_full_copy(
    parsed: ParseResult,
    file_path: Path,
    winner: _SourceRef,
    winner_contrib: _Contribution,
) -> list[ProcDecision]:
    pf = parsed.files.get(file_path)
    if pf is None:
        return []  # non-parsed literal file (e.g. config): no procs
    return [
        ProcDecision(
            canonical_name=p.canonical_name,
            source_file=file_path,
            selection_source=f"{winner.key}:{winner_contrib.json_field}",
        )
        for p in pf.procs
    ]


# ---------------------------------------------------------------------------
# Diagnostic emit helpers
# ---------------------------------------------------------------------------


def _emit_vw09(ctx: ChopperContext, ref: _SourceRef, file_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-09",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {ref.key!r}: file {file_path.as_posix()!r} is in both "
                f"files.include and procedures.include; PI entries are redundant"
            ),
            path=file_path,
            hint=(
                "Remove from files.include for selective proc inclusion, or remove redundant procedures.include entries"
            ),
        )
    )


def _emit_vw11(ctx: ChopperContext, ref: _SourceRef, file_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-11",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {ref.key!r}: file {file_path.as_posix()!r} appears in both "
                f"files.exclude and procedures.exclude with no matching procedures.include; "
                f"source contributes nothing for this file"
            ),
            path=file_path,
            hint=(
                "Use files.exclude alone to drop the file, or procedures.exclude alone to keep it with procs removed"
            ),
        )
    )


def _emit_vw12(ctx: ChopperContext, ref: _SourceRef, file_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-12",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {ref.key!r}: file {file_path.as_posix()!r} has procs in both "
                f"procedures.include and procedures.exclude; PI takes precedence, PE ignored"
            ),
            path=file_path,
            hint="Choose one model per file: additive (PI) or subtractive (PE), not both",
        )
    )


def _emit_vw13(ctx: ChopperContext, ref: _SourceRef, file_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-13",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {ref.key!r}: procedures.exclude removes every proc in "
                f"{file_path.as_posix()!r}; file survives as comment/blank-only"
            ),
            path=file_path,
            hint="Consider using files.exclude to remove the entire file instead",
        )
    )


def _emit_vw18(ctx: ChopperContext, vetoed: _SourceRef, file_path: Path, proc_cn: str, blocker: _SourceRef) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-18",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {vetoed.key!r}: procedures.exclude of {proc_cn!r} vetoed because "
                f"source {blocker.key!r} contributes this proc via include"
            ),
            path=file_path,
            hint=("Remove the redundant procedures.exclude entry, or align with the other source's include intent"),
        )
    )


def _emit_vw19(ctx: ChopperContext, vetoed: _SourceRef, file_path: Path, blocker: _SourceRef) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-19",
            phase=Phase.P3_COMPILE,
            message=(
                f"Source {vetoed.key!r}: files.exclude of {file_path.as_posix()!r} vetoed "
                f"because source {blocker.key!r} contributes this file"
            ),
            path=file_path,
            hint=("Remove the redundant files.exclude entry, or verify the other source's inclusion is intentional"),
        )
    )


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, stateless)
# ---------------------------------------------------------------------------


_GLOB_METACHARS = frozenset("*?[")


def _is_glob(entry: str) -> bool:
    """Return True if ``entry`` contains glob metacharacters."""
    return any(ch in _GLOB_METACHARS for ch in entry)


def _match_glob(pattern: str, parsed_paths: frozenset[Path]) -> set[Path]:
    """Match ``pattern`` against every path in ``parsed_paths`` using POSIX
    semantics. Supports ``*``, ``?``, ``[...]``, and ``**`` (recursive,
    matching zero or more path components).

    ``PurePath.full_match`` (Python 3.13+) handles ``**`` natively; on
    older interpreters we translate the pattern into a regex so ``**/``
    correctly collapses to zero or more intermediate directories
    (``rules/**/*.fm.tcl`` matches ``rules/r1.fm.tcl`` and
    ``rules/sub/r2.fm.tcl`` alike). ``fnmatch.fnmatchcase`` does not
    honour the zero-directory case for ``**`` and is therefore used
    only as a final fallback for patterns that contain no ``**``.
    """
    regex = _glob_to_regex(pattern)
    hits: set[Path] = set()
    for path in parsed_paths:
        posix = path.as_posix()
        full_match = getattr(PurePosixPath(posix), "full_match", None)
        if full_match is not None:
            try:
                if full_match(pattern):
                    hits.add(path)
                    continue
            except ValueError:
                pass
        if regex is not None:
            if regex.fullmatch(posix):
                hits.add(path)
        elif fnmatchcase(posix, pattern):
            hits.add(path)
    return hits


def _glob_to_regex(pattern: str) -> Pattern[str] | None:
    """Thin re-export of :func:`chopper.core.globs.glob_to_regex`.

    The canonical implementation lives in :mod:`chopper.core.globs` so
    P1 surface-file collection (:mod:`chopper.config.service`) and P3
    conflict resolution (this module) and P1 / P3 validation
    (:mod:`chopper.validator.functions`) all share identical semantics
    without cross-service imports. Module-level alias kept so existing
    P3 call sites remain unchanged.
    """

    from chopper.core.globs import glob_to_regex  # noqa: PLC0415

    return glob_to_regex(pattern)
