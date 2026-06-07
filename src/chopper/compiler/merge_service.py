"""CompilerService -- P3 R1 ordered-overlay merge algorithm.

Implements the single-rule overlay specified in
``technical_docs/ARCHITECTURE.md`` Sec.4 (R1) and Sec.5.3 (P3 algorithm). Layers
are applied in declared order ``(base, *features)`` to a running per-file
signal map; the last layer that mentions a file or proc wins.

Per-layer apply step (one file at a time):

* Same-layer authoring conveniences (``VW-09``, ``VW-11``, ``VW-12``,
  ``VW-13``) emit here exactly as before -- they are local invariants and
  unchanged by the overlay model.
* Layer transitions that change a prior decision emit ``VW-21``
  ``layer-shadowed`` with ``(layer, prior_layer, action)``; the same
  events are recorded structurally on
  :attr:`FileProvenance.shadowed_by`.
* No-op excludes (FE/PE entries that match nothing in the running set or
  via glob expansion at this layer) are emitted as ``VE-27
  no-op-exclude`` directly from this service -- the typo cases live
  inline with the fold so the message can name the offending layer and
  entry exactly.

Not this service's job:

* trace (PI+) diagnostics -- owned by :class:`TracerService` (P4);
* filesystem existence (``VE-06``) or post-trim integrity (``VE-16``) --
  owned by the validator.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from re import Pattern
from typing import Literal

from chopper.compiler.flow_resolver import resolve_stages
from chopper.compiler.stack_graph import compute_stack_order
from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.errors import ChopperError
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance, ProcDecision, ShadowEvent
from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig
from chopper.core.models_parser import ParseResult

__all__ = ["CompilerService"]


# ---------------------------------------------------------------------------
# Per-source value objects (internal to this module).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SourceRef:
    """Identifies one JSON source for diagnostics + provenance tagging."""

    key: str  # "base" or "feature:<name>"
    source_path: Path  # original JSON path (for diagnostic provenance)


@dataclass(frozen=True)
class _SourceFacts:
    """Pre-computed per-layer sets consumed by the ordered fold."""

    ref: _SourceRef
    fi_literal: frozenset[Path]
    fi_glob_matched: frozenset[Path]
    fi_glob_surviving: frozenset[Path]
    fe_literal: frozenset[Path]
    pi_by_file: dict[Path, frozenset[str]]
    pe_by_file: dict[Path, frozenset[str]]
    fe_glob_unmatched: tuple[str, ...]


# ---------------------------------------------------------------------------
# Running-fold value objects (internal to this module).
# ---------------------------------------------------------------------------


@dataclass
class _Whole:
    """Running-set entry: file is currently included whole."""


@dataclass
class _Trim:
    """Running-set entry: file is currently included as PROC_TRIM with ``keep`` survivors."""

    keep: set[str] = field(default_factory=set)


_RunningSignal = _Whole | _Trim


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompilerService:
    """Phase 3 merge service (R1 ordered overlay)."""

    def run(self, ctx: ChopperContext, loaded: LoadedConfig, parsed: ParseResult) -> CompiledManifest:
        """Apply the R1 ordered overlay and return the compiled manifest."""
        sources, facts_by_source = _build_source_facts(loaded, parsed)
        universe = _collect_universe(parsed, facts_by_source.values())

        all_procs_by_file: dict[Path, frozenset[str]] = {
            path: frozenset(p.canonical_name for p in pf.procs) for path, pf in parsed.files.items()
        }
        for path in universe:
            all_procs_by_file.setdefault(path, frozenset())

        short_to_canonical_by_file: dict[Path, dict[str, str]] = {
            path: _build_short_to_canonical(pf) for path, pf in parsed.files.items()
        }

        # ---- Ordered fold over (base, *features) -------------------------
        running: dict[Path, _RunningSignal] = {}
        contributed_by: dict[Path, str] = {}
        shadow_events: dict[Path, list[ShadowEvent]] = {}
        input_sources_by_file: dict[Path, set[str]] = {}
        proc_winner: dict[tuple[Path, str], tuple[str, str]] = {}
        last_reason_by_file: dict[Path, str] = {}

        for src in sources:
            facts = facts_by_source[src]
            _apply_layer(
                ctx,
                src,
                facts,
                running,
                contributed_by,
                shadow_events,
                input_sources_by_file,
                proc_winner,
                last_reason_by_file,
                all_procs_by_file,
                short_to_canonical_by_file,
            )

        # ---- Derive manifest from final running state --------------------
        file_decisions, proc_decisions, provenance = _derive_manifest(
            universe,
            running,
            contributed_by,
            shadow_events,
            input_sources_by_file,
            proc_winner,
            last_reason_by_file,
            parsed,
        )

        # ---- F3 flow-action resolution -----------------------------------
        stages = resolve_stages(ctx, loaded.base.stages, loaded.features)
        _register_generated_stage_files(ctx, file_decisions, provenance, stages, loaded)
        stack_order = compute_stack_order(ctx, stages)

        return CompiledManifest(
            file_decisions=file_decisions,
            proc_decisions=proc_decisions,
            provenance=provenance,
            stages=stages,
            generate_stack=loaded.base.options.generate_stack,
            stack_order=stack_order,
        )


# ---------------------------------------------------------------------------
# F3 generated-file registration
# ---------------------------------------------------------------------------


def _register_generated_stage_files(
    ctx: ChopperContext,
    file_decisions: dict[Path, FileTreatment],
    provenance: dict[Path, FileProvenance],
    stages: tuple,
    loaded: LoadedConfig,
) -> None:
    """Record :class:`FileTreatment.GENERATED` entries for F3 artifacts.

    Per stage: one ``<stage>.tcl`` **unless** ``stage.standalone_stack``
    is ``True``, in which case ``<stage>.stack`` is registered instead
    (the standalone stack becomes the stage's sole driver). Once
    globally: one ``<basename(domain_root)>.stack`` when
    ``loaded.base.options.generate_stack`` is ``True`` and ``stages`` is
    non-empty. Diagnostics:

    * ``VE-28 aggregate-stack-collision`` -- aggregate path collides with
      an existing ``files.*`` entry.
    * ``VE-29 standalone-stack-collision`` -- per-stage standalone path
      collides with ``files.*`` or with the aggregate path.
    * ``VW-23 stack-stage-empty-command`` -- a stage included in the
      aggregate has an empty ``command``.
    """

    if not stages:
        return

    contributors: list[str] = ["base:stages"]
    for feature in loaded.features:
        if feature.flow_actions:
            contributors.append(f"feature:{feature.name}:flow_actions")
    input_sources = tuple(sorted(contributors))
    contributed_by_value = contributors[-1]

    emit_aggregate = loaded.base.options.generate_stack
    aggregate_path: Path | None = Path(f"{ctx.config.domain_root.name}.stack") if emit_aggregate else None

    def _make_provenance(path: Path) -> FileProvenance:
        return FileProvenance(
            path=path,
            treatment=FileTreatment.GENERATED,
            reason="fi-literal",
            input_sources=input_sources,
            contributed_by=contributed_by_value,
            shadowed_by=(),
            proc_model=None,
        )

    for stage in stages:
        tcl_path = Path(f"{stage.name}.tcl")
        if not stage.standalone_stack:
            if tcl_path in file_decisions:
                raise ChopperError(
                    f"F3 generated path {tcl_path.as_posix()!r} collides with an "
                    f"existing file decision; rename the stage or drop the "
                    f"colliding files.* entry"
                )
            file_decisions[tcl_path] = FileTreatment.GENERATED
            provenance[tcl_path] = _make_provenance(tcl_path)

        if stage.standalone_stack:
            standalone_path = Path(f"{stage.name}.stack")
            colliding_files_entry = standalone_path in file_decisions
            colliding_aggregate = aggregate_path is not None and standalone_path == aggregate_path
            if colliding_files_entry or colliding_aggregate:
                _emit_ve29(ctx, standalone_path, stage.name, aggregate_collision=colliding_aggregate)
                raise ChopperError(
                    f"F3 standalone stack path {standalone_path.as_posix()!r} collides with "
                    f"an existing file decision or the aggregate stack path; rename the stage, "
                    f"remove the colliding files.* entry, or unset standalone_stack"
                )
            file_decisions[standalone_path] = FileTreatment.GENERATED
            provenance[standalone_path] = _make_provenance(standalone_path)

        if emit_aggregate and not stage.command:
            _emit_vw23(ctx, stage.name)

    if aggregate_path is not None:
        if aggregate_path in file_decisions:
            _emit_ve28(ctx, aggregate_path)
            raise ChopperError(
                f"F3 aggregate stack path {aggregate_path.as_posix()!r} collides with "
                f"an existing file decision; rename the domain root, exclude the colliding "
                f"files.* entry, or disable options.generate_stack"
            )
        file_decisions[aggregate_path] = FileTreatment.GENERATED
        provenance[aggregate_path] = _make_provenance(aggregate_path)

    _resort_by_posix(file_decisions)
    _resort_by_posix(provenance)


def _emit_ve28(ctx: ChopperContext, aggregate_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-28",
            phase=Phase.P3_COMPILE,
            message=(
                f"Aggregate F3 stack path {aggregate_path.as_posix()!r} (from options.generate_stack) "
                f"collides with an existing files.* entry"
            ),
            path=aggregate_path,
            hint=("Rename the domain root, exclude the colliding files.* entry, or disable options.generate_stack"),
        )
    )


def _emit_ve29(ctx: ChopperContext, standalone_path: Path, stage_name: str, *, aggregate_collision: bool) -> None:
    cause = "the aggregate stack path" if aggregate_collision else "an existing files.* entry"
    ctx.diag.emit(
        Diagnostic.build(
            "VE-29",
            phase=Phase.P3_COMPILE,
            message=(
                f"Standalone F3 stack path {standalone_path.as_posix()!r} for stage {stage_name!r} "
                f"collides with {cause}"
            ),
            path=standalone_path,
            hint=("Rename the stage, remove the colliding files.* entry, or unset standalone_stack on this stage"),
        )
    )


def _emit_vw23(ctx: ChopperContext, stage_name: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VW-23",
            phase=Phase.P3_COMPILE,
            message=(
                f"Stage {stage_name!r} is in the aggregate stack but has no command; the record will omit its J line"
            ),
            hint="Author a command on the stage or accept the J-less record if the scheduler tolerates it",
        )
    )


def _resort_by_posix(mapping: dict) -> None:
    sorted_items = sorted(mapping.items(), key=lambda kv: kv[0].as_posix())
    mapping.clear()
    mapping.update(sorted_items)


def _build_short_to_canonical(parsed_file) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Map every short and qualified name in ``parsed_file`` to its canonical name."""

    out: dict[str, str] = {}
    for proc in parsed_file.procs:
        out[proc.short_name] = proc.canonical_name
        out[proc.qualified_name] = proc.canonical_name
    return out


# ---------------------------------------------------------------------------
# Per-layer fact extraction
# ---------------------------------------------------------------------------


def _build_source_facts(
    loaded: LoadedConfig, parsed: ParseResult
) -> tuple[list[_SourceRef], dict[_SourceRef, _SourceFacts]]:
    """Iterate layers in declared order (base then features)."""
    parsed_paths = frozenset(parsed.files.keys())
    all_surface_paths: frozenset[Path] = frozenset(loaded.surface_files) | parsed_paths

    sources: list[_SourceRef] = []
    facts: dict[_SourceRef, _SourceFacts] = {}

    base_ref = _SourceRef(key="base", source_path=loaded.base.source_path)
    sources.append(base_ref)
    facts[base_ref] = _extract_facts(base_ref, loaded.base, all_surface_paths)

    for feature in loaded.features:
        f_ref = _SourceRef(key=f"feature:{feature.name}", source_path=feature.source_path)
        sources.append(f_ref)
        facts[f_ref] = _extract_facts(f_ref, feature, all_surface_paths)

    return sources, facts


def _extract_facts(
    ref: _SourceRef,
    source: BaseJson | FeatureJson,
    surface_paths: frozenset[Path],
) -> _SourceFacts:
    """Distill one layer into literal/glob FI buckets, FE hits, and PI/PE by file."""
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

    fe_hits: set[Path] = {p for p in fe_literal_set if p in surface_paths}
    fe_glob_unmatched: list[str] = []
    for pattern in fe_glob_patterns:
        matches = _match_glob(pattern, surface_paths)
        if matches:
            fe_hits.update(matches)
        else:
            fe_glob_unmatched.append(pattern)

    fi_glob_matches: set[Path] = set()
    for pattern in fi_glob_patterns:
        fi_glob_matches.update(_match_glob(pattern, surface_paths))
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
        fi_glob_matched=frozenset(fi_glob_matches),
        fi_glob_surviving=frozenset(fi_glob_surviving),
        fe_literal=frozenset(fe_hits),
        pi_by_file={k: frozenset(v) for k, v in pi_by_file.items()},
        pe_by_file={k: frozenset(v) for k, v in pe_by_file.items()},
        fe_glob_unmatched=tuple(fe_glob_unmatched),
    )


def _collect_universe(parsed: ParseResult, facts_iter: Iterable[_SourceFacts]) -> list[Path]:
    """Universe of files the manifest reasons over -- lex-sorted by POSIX."""
    paths: set[Path] = set(parsed.files.keys())
    for facts in facts_iter:
        paths.update(facts.fi_literal)
        paths.update(facts.fi_glob_surviving)
    return sorted(paths, key=lambda p: p.as_posix())


# ---------------------------------------------------------------------------
# Ordered fold -- apply one layer to the running set
# ---------------------------------------------------------------------------


def _apply_layer(  # noqa: PLR0915, PLR0912 -- algorithm body kept inline
    ctx: ChopperContext,
    src: _SourceRef,
    facts: _SourceFacts,
    running: dict[Path, _RunningSignal],
    contributed_by: dict[Path, str],
    shadow_events: dict[Path, list[ShadowEvent]],
    input_sources_by_file: dict[Path, set[str]],
    proc_winner: dict[tuple[Path, str], tuple[str, str]],
    last_reason_by_file: dict[Path, str],
    all_procs_by_file: dict[Path, frozenset[str]],
    short_to_canonical_by_file: dict[Path, dict[str, str]],
) -> None:
    """Apply layer ``src``'s signals to the running set, emitting same-layer
    warnings (VW-09/11/12/13), layer-transition warnings (VW-21), and
    no-op exclude errors (VE-27).
    """
    layer_key = src.key

    # Glob FE patterns that matched zero surface paths at this layer.
    for pattern in facts.fe_glob_unmatched:
        _emit_ve27_glob(ctx, src, pattern)

    files_touched: set[Path] = set()
    files_touched |= facts.fi_literal | facts.fi_glob_surviving | facts.fe_literal
    files_touched |= set(facts.pi_by_file.keys()) | set(facts.pe_by_file.keys())

    for file_path in sorted(files_touched, key=lambda p: p.as_posix()):
        is_fi_literal = file_path in facts.fi_literal
        # Use pre-prune glob membership here so same-layer FI+FE on the
        # same file is recognized as an intentional subtraction, not a
        # standalone FE remove (which would false-trigger VE-27).
        is_fi_glob = file_path in facts.fi_glob_matched
        fi_any = is_fi_literal or is_fi_glob
        is_fe = file_path in facts.fe_literal
        pi_short = facts.pi_by_file.get(file_path, frozenset())
        pe_short = facts.pe_by_file.get(file_path, frozenset())

        all_procs = all_procs_by_file.get(file_path, frozenset())
        s2c = short_to_canonical_by_file.get(file_path, {})
        pi_cn = frozenset(s2c[s] for s in pi_short if s in s2c)
        pe_cn = frozenset(s2c[s] for s in pe_short if s in s2c)

        # PE short-names that don't resolve to any canonical proc in the file
        # are typo no-ops (VE-27). File presence is verified by VE-06 at P1.
        for unmapped in sorted(pe_short - set(s2c.keys())):
            _emit_ve27_pe_proc(ctx, src, file_path, unmapped)

        # ---- Same-layer authoring warnings (unchanged from prior model) --
        if fi_any and pi_short:
            _emit_vw09(ctx, src, file_path, pi_procs=pi_short)
        if is_fe and pe_short and not fi_any and not pi_short:
            _emit_vw11(ctx, src, file_path, pe_procs=pe_short)
        if pi_short and pe_short and not fi_any:
            _emit_vw12(ctx, src, file_path, pi_procs=pi_short, pe_procs=pe_short)
        if pe_short and not pi_short and not fi_any and not is_fe:
            if all_procs and not (all_procs - pe_cn):
                _emit_vw13(ctx, src, file_path, pe_procs=pe_short)
        if fi_any and pe_short:
            keep_after = all_procs - pe_cn
            if all_procs and not keep_after:
                _emit_vw13(ctx, src, file_path, pe_procs=pe_short)

        intent = _classify_layer_intent(is_fi_literal, is_fi_glob, is_fe, pi_short, pe_short, pi_cn, pe_cn, all_procs)

        if intent[0] == "none":
            continue

        prev = running.get(file_path)
        prior_layer = contributed_by.get(file_path)

        if intent[0] == "remove":
            if prev is None:
                # Literal FE that no earlier layer (or same-layer FI) contributed.
                _emit_ve27_fe_literal(ctx, src, file_path)
                continue
            shadow_events.setdefault(file_path, []).append(
                ShadowEvent(layer=layer_key, prior_layer=prior_layer or layer_key, action="remove")
            )
            _emit_vw21(ctx, file_path, layer_key, prior_layer or layer_key, "remove")
            running.pop(file_path, None)
            contributed_by.pop(file_path, None)
            last_reason_by_file.pop(file_path, None)
            for key in [k for k in proc_winner if k[0] == file_path]:
                del proc_winner[key]
            continue

        if intent[0] == "whole":
            _, reason, json_field = intent
            _record_replace_transition(
                ctx,
                file_path,
                layer_key,
                prior_layer,
                prev,
                "whole",
                shadow_events,
            )
            running[file_path] = _Whole()
            contributed_by[file_path] = layer_key
            last_reason_by_file[file_path] = reason
            input_sources_by_file.setdefault(file_path, set()).add(f"{layer_key}:{json_field}")
            for cn in all_procs:
                proc_winner[(file_path, cn)] = (layer_key, json_field)
            continue

        if intent[0] == "trim-replace":
            _, new_keep, reason, json_field, _layer_pi, _layer_pe = intent
            _record_replace_transition(
                ctx,
                file_path,
                layer_key,
                prior_layer,
                prev,
                "trim",
                shadow_events,
                new_keep=frozenset(new_keep),
            )
            running[file_path] = _Trim(keep=set(new_keep))
            contributed_by[file_path] = layer_key
            last_reason_by_file[file_path] = reason
            input_sources_by_file.setdefault(file_path, set()).add(f"{layer_key}:{json_field}")
            for cn in new_keep:
                proc_winner[(file_path, cn)] = (layer_key, json_field)
            for key in [k for k in proc_winner if k[0] == file_path and k[1] not in new_keep]:
                del proc_winner[key]
            continue

        if intent[0] == "trim-pi":
            _, layer_pi, reason, json_field = intent
            if prev is None:
                running[file_path] = _Trim(keep=set(layer_pi))
                contributed_by[file_path] = layer_key
                last_reason_by_file[file_path] = reason
            elif isinstance(prev, _Whole):
                new_keep = set(all_procs) | set(layer_pi)
                shadow_events.setdefault(file_path, []).append(
                    ShadowEvent(
                        layer=layer_key,
                        prior_layer=prior_layer or layer_key,
                        action="downgrade-whole-to-trim",
                    )
                )
                _emit_vw21(
                    ctx,
                    file_path,
                    layer_key,
                    prior_layer or layer_key,
                    "downgrade-whole-to-trim",
                    final_keep=frozenset(new_keep),
                )
                running[file_path] = _Trim(keep=new_keep)
                contributed_by[file_path] = layer_key
                last_reason_by_file[file_path] = reason
            else:  # _Trim
                added = set(layer_pi) - prev.keep
                new_keep = prev.keep | set(layer_pi)
                if added and prior_layer != layer_key:
                    shadow_events.setdefault(file_path, []).append(
                        ShadowEvent(layer=layer_key, prior_layer=prior_layer or layer_key, action="add-proc")
                    )
                    _emit_vw21(
                        ctx,
                        file_path,
                        layer_key,
                        prior_layer or layer_key,
                        "add-proc",
                        added_procs=frozenset(added),
                        prior_keep=frozenset(prev.keep),
                        final_keep=frozenset(new_keep),
                    )
                running[file_path] = _Trim(keep=new_keep)
                if added:
                    contributed_by[file_path] = layer_key
                    last_reason_by_file[file_path] = reason
            input_sources_by_file.setdefault(file_path, set()).add(f"{layer_key}:{json_field}")
            for cn in layer_pi:
                proc_winner[(file_path, cn)] = (layer_key, json_field)
            continue

        if intent[0] == "trim-pe":  # pragma: no branch
            _, layer_pe, reason, json_field = intent
            if prev is None:
                new_keep = set(all_procs) - set(layer_pe)
                running[file_path] = _Trim(keep=new_keep)
                contributed_by[file_path] = layer_key
                last_reason_by_file[file_path] = reason
                for cn in new_keep:
                    proc_winner[(file_path, cn)] = (layer_key, json_field)
            elif isinstance(prev, _Whole):
                new_keep = set(all_procs) - set(layer_pe)
                shadow_events.setdefault(file_path, []).append(
                    ShadowEvent(
                        layer=layer_key,
                        prior_layer=prior_layer or layer_key,
                        action="downgrade-whole-to-trim",
                    )
                )
                _emit_vw21(
                    ctx,
                    file_path,
                    layer_key,
                    prior_layer or layer_key,
                    "downgrade-whole-to-trim",
                    removed_procs=frozenset(layer_pe),
                    final_keep=frozenset(new_keep),
                )
                running[file_path] = _Trim(keep=new_keep)
                contributed_by[file_path] = layer_key
                last_reason_by_file[file_path] = reason
                for cn in new_keep:
                    proc_winner[(file_path, cn)] = (layer_key, json_field)
            else:  # _Trim
                removed = set(layer_pe) & prev.keep
                new_keep = prev.keep - set(layer_pe)
                if removed and prior_layer != layer_key:
                    shadow_events.setdefault(file_path, []).append(
                        ShadowEvent(
                            layer=layer_key,
                            prior_layer=prior_layer or layer_key,
                            action="remove-proc",
                        )
                    )
                    _emit_vw21(
                        ctx,
                        file_path,
                        layer_key,
                        prior_layer or layer_key,
                        "remove-proc",
                        removed_procs=frozenset(removed),
                        prior_keep=frozenset(prev.keep),
                        final_keep=frozenset(new_keep),
                    )
                running[file_path] = _Trim(keep=new_keep)
                if removed:
                    contributed_by[file_path] = layer_key
                    last_reason_by_file[file_path] = reason
                for cn in removed:
                    proc_winner.pop((file_path, cn), None)
            input_sources_by_file.setdefault(file_path, set()).add(f"{layer_key}:{json_field}")
            continue


def _classify_layer_intent(
    is_fi_literal: bool,
    is_fi_glob: bool,
    is_fe: bool,
    pi_short: frozenset[str],
    pe_short: frozenset[str],
    pi_cn: frozenset[str],
    pe_cn: frozenset[str],
    all_procs: frozenset[str],
) -> tuple:
    """Distill one layer's per-file (FI/FE/PI/PE) signals into a single intent tuple."""
    fi_any = is_fi_literal or is_fi_glob

    if not (fi_any or is_fe or pi_short or pe_short):  # pragma: no cover - call sites only invoke on touched files
        return ("none",)

    # Same-layer FE+PE without FI/PI: contributes nothing (VW-11 contradiction).
    if is_fe and pe_short and not fi_any and not pi_short:
        return ("none",)

    # Same-layer FE only: layer wants the file removed.
    if is_fe and not fi_any and not pi_short and not pe_short:
        return ("remove",)

    # Glob FI pruned by same-layer FE, no PI/PE: contributes nothing.
    if is_fi_glob and not is_fi_literal and is_fe and not (pi_short or pe_short):
        return ("none",)

    # FI + PI + PE -> PI redundant, PE qualifies.
    if fi_any and pi_short and pe_short:
        if is_fi_glob and not is_fi_literal and is_fe:  # pragma: no cover - VW-09 surfaced first
            return ("none",)
        new_keep = all_procs - pe_cn
        return ("trim-replace", new_keep, "fi-and-pe", "procedures.exclude", pi_cn, pe_cn)

    # FI + PE (no PI) -> TRIM(all - pe).
    if fi_any and pe_short and not pi_short:
        if is_fi_glob and not is_fi_literal and is_fe:  # pragma: no cover - VW-09 surfaced first
            return ("none",)
        new_keep = all_procs - pe_cn
        reason = "fi-and-pe" if is_fi_literal else "pe-overlay"
        return ("trim-replace", new_keep, reason, "procedures.exclude", frozenset(), pe_cn)

    # FI + PI (no PE) -> WHOLE (PI redundant).
    if fi_any and pi_short and not pe_short:
        return ("whole", "fi-literal" if is_fi_literal else "fi-glob", "files.include")

    # FI alone.
    if fi_any and not pi_short and not pe_short:
        return ("whole", "fi-literal" if is_fi_literal else "fi-glob", "files.include")

    # PI + PE no FI: PI wins (VW-12). Treat as PI-only union.
    if pi_short and pe_short and not fi_any:
        return ("trim-pi", pi_cn, "pi-overlay", "procedures.include")

    # PI alone (no PE, no FI), with or without FE.
    if pi_short and not pe_short and not fi_any:
        return ("trim-pi", pi_cn, "pi-overlay", "procedures.include")

    # PE alone (no PI, no FI, no FE).
    if pe_short and not pi_short and not fi_any and not is_fe:
        return ("trim-pe", pe_cn, "pe-overlay", "procedures.exclude")

    raise AssertionError(  # pragma: no cover - defensive: schema + validator gate every reachable combination
        f"_classify_layer_intent: unhandled combination "
        f"FI_lit={is_fi_literal}, FI_glob={is_fi_glob}, FE={is_fe}, "
        f"PI={bool(pi_short)}, PE={bool(pe_short)}"
    )


def _record_replace_transition(
    ctx: ChopperContext,
    file_path: Path,
    layer_key: str,
    prior_layer: str | None,
    prev: _RunningSignal | None,
    new_kind: str,
    shadow_events: dict[Path, list[ShadowEvent]],
    *,
    new_keep: frozenset[str] | None = None,
) -> None:
    """Record a ShadowEvent + emit VW-21 when a layer wholesale-replaces a prior decision.

    Per ARCHITECTURE.md Sec.4 row 2 (and the prose at lines 452 / 770 / 835):
    ``VW-21`` fires only when a later layer **actually changes** an earlier
    layer's decision. A redundant re-affirmation (WHOLE->WHOLE, or
    TRIM->TRIM with an identical keep set) is a no-op transition and must
    not emit ``VW-21`` nor record a ``ShadowEvent``.
    """
    if prev is None or not prior_layer or prior_layer == layer_key:
        return
    # Same-state short-circuit: prior decision is unchanged -> no shadow.
    if isinstance(prev, _Whole) and new_kind == "whole":
        return
    if isinstance(prev, _Trim) and new_kind == "trim" and new_keep is not None and prev.keep == new_keep:
        return
    action: Literal["replace", "downgrade-whole-to-trim"]
    if isinstance(prev, _Whole) and new_kind == "trim":
        action = "downgrade-whole-to-trim"
    else:
        action = "replace"
    prior_keep = frozenset(prev.keep) if isinstance(prev, _Trim) else None
    shadow_events.setdefault(file_path, []).append(ShadowEvent(layer=layer_key, prior_layer=prior_layer, action=action))
    _emit_vw21(ctx, file_path, layer_key, prior_layer, action, prior_keep=prior_keep, final_keep=new_keep)


# ---------------------------------------------------------------------------
# Manifest derivation from the final running state
# ---------------------------------------------------------------------------


def _derive_manifest(
    universe: list[Path],
    running: dict[Path, _RunningSignal],
    contributed_by: dict[Path, str],
    shadow_events: dict[Path, list[ShadowEvent]],
    input_sources_by_file: dict[Path, set[str]],
    proc_winner: dict[tuple[Path, str], tuple[str, str]],
    last_reason_by_file: dict[Path, str],
    parsed: ParseResult,
) -> tuple[dict[Path, FileTreatment], dict[str, ProcDecision], dict[Path, FileProvenance]]:
    file_decisions: dict[Path, FileTreatment] = {}
    proc_decisions: dict[str, ProcDecision] = {}
    provenance: dict[Path, FileProvenance] = {}

    for file_path in universe:
        signal = running.get(file_path)
        sb = tuple(shadow_events.get(file_path, ()))
        input_sources = tuple(sorted(input_sources_by_file.get(file_path, ())))

        if signal is None:
            treatment = FileTreatment.REMOVE
            reason = "default-exclude" if not sb else (last_reason_by_file.get(file_path) or "default-exclude")
            pv = FileProvenance(
                path=file_path,
                treatment=treatment,
                reason=reason,
                input_sources=input_sources,
                contributed_by=None,
                shadowed_by=sb,
                proc_model=None,
            )
            file_decisions[file_path] = treatment
            provenance[file_path] = pv
            continue

        if isinstance(signal, _Whole):
            treatment = FileTreatment.FULL_COPY
            reason = last_reason_by_file.get(file_path, "fi-literal")
            pv = FileProvenance(
                path=file_path,
                treatment=treatment,
                reason=reason,
                input_sources=input_sources,
                contributed_by=contributed_by.get(file_path),
                shadowed_by=sb,
                proc_model=None,
            )
            file_decisions[file_path] = treatment
            provenance[file_path] = pv
            pf = parsed.files.get(file_path)
            if pf is not None:
                for p in pf.procs:
                    layer_field = proc_winner.get((file_path, p.canonical_name))
                    if layer_field is None:  # pragma: no cover - defensive fallback
                        layer_field = (contributed_by.get(file_path, "base"), "files.include")
                    proc_decisions.setdefault(
                        p.canonical_name,
                        ProcDecision(
                            canonical_name=p.canonical_name,
                            source_file=file_path,
                            selection_source=f"{layer_field[0]}:{layer_field[1]}",
                        ),
                    )
            continue

        # _Trim
        treatment = FileTreatment.PROC_TRIM
        reason = last_reason_by_file.get(file_path, "pi-overlay")
        pv = FileProvenance(
            path=file_path,
            treatment=treatment,
            reason=reason,
            input_sources=input_sources,
            contributed_by=contributed_by.get(file_path),
            shadowed_by=sb,
            proc_model="overlay",
        )
        file_decisions[file_path] = treatment
        provenance[file_path] = pv
        for cn in sorted(signal.keep):
            layer_field = proc_winner.get((file_path, cn))
            if layer_field is None:  # pragma: no cover - defensive fallback
                layer_field = (contributed_by.get(file_path, "base"), "procedures.include")
            proc_decisions.setdefault(
                cn,
                ProcDecision(
                    canonical_name=cn,
                    source_file=file_path,
                    selection_source=f"{layer_field[0]}:{layer_field[1]}",
                ),
            )

    sorted_proc_decisions = {k: proc_decisions[k] for k in sorted(proc_decisions)}
    return file_decisions, sorted_proc_decisions, provenance


# ---------------------------------------------------------------------------
# Diagnostic emit helpers
# ---------------------------------------------------------------------------


def _emit_vw09(ctx: ChopperContext, ref: _SourceRef, file_path: Path, *, pi_procs: frozenset[str]) -> None:
    procs_list = "[" + ", ".join(sorted(pi_procs)) + "]"
    ctx.diag.emit(
        Diagnostic.build(
            "VW-09",
            phase=Phase.P3_COMPILE,
            message=(
                f"{ref.key!r}: {file_path.as_posix()!r} is in files.include and procedures.include; "
                f"PI procs {procs_list} are redundant -- file will be FULL_COPY regardless"
            ),
            path=file_path,
            hint=(
                "Remove from files.include to enable selective proc inclusion, "
                "or remove the redundant procedures.include entries"
            ),
        )
    )


def _emit_vw11(ctx: ChopperContext, ref: _SourceRef, file_path: Path, *, pe_procs: frozenset[str]) -> None:
    procs_list = "[" + ", ".join(sorted(pe_procs)) + "]"
    ctx.diag.emit(
        Diagnostic.build(
            "VW-11",
            phase=Phase.P3_COMPILE,
            message=(
                f"{ref.key!r}: {file_path.as_posix()!r} is in both files.exclude and "
                f"procedures.exclude {procs_list} with no matching procedures.include; "
                f"this layer contributes nothing for this file"
            ),
            path=file_path,
            hint=(
                "Use files.exclude alone to drop the file, "
                "or procedures.exclude alone to keep it with some procs removed"
            ),
        )
    )


def _emit_vw12(
    ctx: ChopperContext,
    ref: _SourceRef,
    file_path: Path,
    *,
    pi_procs: frozenset[str],
    pe_procs: frozenset[str],
) -> None:
    pi_list = "[" + ", ".join(sorted(pi_procs)) + "]"
    pe_list = "[" + ", ".join(sorted(pe_procs)) + "]"
    ctx.diag.emit(
        Diagnostic.build(
            "VW-12",
            phase=Phase.P3_COMPILE,
            message=(
                f"{ref.key!r}: {file_path.as_posix()!r} has procs in both "
                f"procedures.include {pi_list} and procedures.exclude {pe_list}; "
                f"PI takes precedence -- keeping {pi_list}, PE ignored"
            ),
            path=file_path,
            hint="Choose one model per file at this layer: procedures.include or procedures.exclude, not both",
        )
    )


def _emit_vw13(ctx: ChopperContext, ref: _SourceRef, file_path: Path, *, pe_procs: frozenset[str]) -> None:
    procs_list = "[" + ", ".join(sorted(pe_procs)) + "]"
    ctx.diag.emit(
        Diagnostic.build(
            "VW-13",
            phase=Phase.P3_COMPILE,
            message=(
                f"{ref.key!r}: procedures.exclude removes all procs {procs_list} from "
                f"{file_path.as_posix()!r}; file survives as comment/blank-only"
            ),
            path=file_path,
            hint="Consider using files.exclude to remove the entire file instead",
        )
    )


def _emit_vw21(
    ctx: ChopperContext,
    file_path: Path,
    layer: str,
    prior_layer: str,
    action: str,
    *,
    added_procs: frozenset[str] | None = None,
    removed_procs: frozenset[str] | None = None,
    prior_keep: frozenset[str] | None = None,
    final_keep: frozenset[str] | None = None,
) -> None:
    posix = file_path.as_posix()

    def _fmt(procs: frozenset[str] | None) -> str:
        return "[" + ", ".join(sorted(procs)) + "]" if procs is not None else "[?]"

    if action == "add-proc" and added_procs is not None:
        msg = (
            f"{layer!r} added proc(s) {_fmt(added_procs)} to {posix!r} "
            f"(already kept by {prior_layer!r}: {_fmt(prior_keep)}); "
            f"combined keep-set: {_fmt(final_keep)}"
        )
        hint = "No action required if intentional; verify feature layer order in project.features[] if unexpected"
    elif action == "remove-proc" and removed_procs is not None:
        msg = (
            f"{layer!r} removed proc(s) {_fmt(removed_procs)} from {posix!r} "
            f"(were kept by {prior_layer!r}: {_fmt(prior_keep)}); "
            f"remaining keep-set: {_fmt(final_keep)}"
        )
        hint = (
            "No action required if intentional; to reinstate a proc, add it to "
            "procedures.include in a later feature layer"
        )
    elif action == "downgrade-whole-to-trim" and final_keep is not None:
        excluded = _fmt(removed_procs) if removed_procs is not None else "[?]"
        msg = (
            f"{layer!r} narrowed {posix!r} from FULL_COPY to PROC_TRIM "
            f"(prior: {prior_layer!r} included the whole file); "
            f"keeping: {_fmt(final_keep)}" + (f"; excluded: {excluded}" if removed_procs is not None else "")
        )
        hint = "No action required if intentional; verify layer order in project.features[] if unexpected"
    elif action == "remove":
        msg = f"{layer!r} excluded {posix!r} (was included by {prior_layer!r})"
        hint = "No action required if intentional; check layer order in project.features[] if unexpected"
    elif action == "replace":
        if prior_keep is not None and final_keep is not None:
            msg = (
                f"{layer!r} replaced the proc selection for {posix!r} "
                f"(prior {prior_layer!r} keep: {_fmt(prior_keep)}; "
                f"new keep: {_fmt(final_keep)})"
            )
        elif prior_keep is not None:
            msg = (
                f"{layer!r} replaced prior selection for {posix!r} "
                f"(prior {prior_layer!r} kept: {_fmt(prior_keep)}; "
                f"new: FULL_COPY)"
            )
        else:  # pragma: no cover - defensive: every replace caller supplies prior_keep or final_keep
            msg = f"{layer!r} shadowed prior layer {prior_layer!r} for {posix!r} (action={action})"
        hint = "No action required if intentional; verify layer order in project.features[] if unexpected"
    else:
        msg = f"{layer!r} shadowed prior layer {prior_layer!r} for {posix!r} (action={action})"
        hint = (
            "No action required if the layer order in project.features[] is intentional; "
            "verify the order if the shadow is unexpected"
        )

    ctx.diag.emit(
        Diagnostic.build(
            "VW-21",
            phase=Phase.P3_COMPILE,
            message=msg,
            path=file_path,
            hint=hint,
        )
    )


def _emit_ve27_fe_literal(ctx: ChopperContext, ref: _SourceRef, file_path: Path) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-27",
            phase=Phase.P3_COMPILE,
            message=(
                f"Layer {ref.key!r}: files.exclude entry {file_path.as_posix()!r} matches nothing "
                f"in the running set established by earlier layers (no-op)"
            ),
            path=file_path,
            hint=(
                "Verify the path; remove the entry if no earlier layer (base or preceding feature) "
                "contributes this file"
            ),
        )
    )


def _emit_ve27_glob(ctx: ChopperContext, ref: _SourceRef, pattern: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-27",
            phase=Phase.P3_COMPILE,
            message=(f"Layer {ref.key!r}: files.exclude glob {pattern!r} matched zero files at this layer (no-op)"),
            hint="Verify the glob; remove it if it cannot match any file in the domain surface",
        )
    )


def _emit_ve27_pe_proc(ctx: ChopperContext, ref: _SourceRef, file_path: Path, proc_name: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-27",
            phase=Phase.P3_COMPILE,
            message=(
                f"Layer {ref.key!r}: procedures.exclude proc {proc_name!r} in "
                f"{file_path.as_posix()!r} does not match any proc in the file (no-op)"
            ),
            path=file_path,
            hint="Verify the proc name (short or qualified); remove the entry if the proc no longer exists",
        )
    )


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, stateless)
# ---------------------------------------------------------------------------


_GLOB_METACHARS = frozenset("*?[")


def _is_glob(entry: str) -> bool:
    """Return True if ``entry`` contains glob metacharacters."""
    return any(ch in _GLOB_METACHARS for ch in entry)


def _match_glob(pattern: str, paths: frozenset[Path]) -> set[Path]:
    """Match ``pattern`` against every path in ``paths`` using POSIX semantics."""
    regex = _glob_to_regex(pattern)
    hits: set[Path] = set()
    for path in paths:
        posix = path.as_posix()
        full_match = getattr(PurePosixPath(posix), "full_match", None)
        if full_match is not None:  # pragma: no branch
            try:
                if full_match(pattern):
                    hits.add(path)
                    continue
            except ValueError:  # pragma: no cover - full_match never raises on schema-accepted patterns
                pass
        if regex is not None:
            if regex.fullmatch(posix):  # pragma: no cover - <3.13 fallback; Py 3.13+ uses full_match
                hits.add(path)
        elif fnmatchcase(posix, pattern):  # pragma: no cover - last-ditch fallback for malformed globs
            hits.add(path)
    return hits


def _glob_to_regex(pattern: str) -> Pattern[str] | None:
    """Thin re-export of :func:`chopper.core.globs.glob_to_regex`."""

    from chopper.core.globs import glob_to_regex  # noqa: PLC0415

    return glob_to_regex(pattern)
