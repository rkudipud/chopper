"""JSON hydration — raw dicts → frozen dataclasses.

This module provides three public ``load_*`` functions that, after a
document has been declared valid by :func:`~chopper.config.schema.validate_json`,
turn its raw ``dict`` into the typed frozen dataclasses declared in
:mod:`chopper.core.models`.

It also provides :func:`topo_sort_features`, which orders a list of
:class:`~chopper.core.models.FeatureJson` records by their ``depends_on``
graph (Kahn's algorithm — O(V+E), deterministic, stable sort within each
rank level).  A cycle emits ``VE-22`` and returns the original input order.

Diagnostic emission:

* ``VE-03`` — ``procEntry`` with empty ``procs`` array.
* ``VE-14`` — duplicate ``name`` across selected features.
* ``VE-15`` — ``depends_on`` names a feature not present in the selection.
* ``VE-22`` — ``depends_on`` forms a cycle.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import (
    AddStageAction,
    AddStepAction,
    BaseJson,
    BaseOptions,
    FeatureJson,
    FeatureMetadata,
    FilesSection,
    FlowAction,
    LoadFromAction,
    ProceduresSection,
    ProcEntryRef,
    ProjectJson,
    RemoveStageAction,
    RemoveStepAction,
    ReplaceStageAction,
    ReplaceStepAction,
    StageDefinition,
)

__all__ = [
    "load_base",
    "load_feature",
    "load_project",
    "topo_sort_features",
]

DiagnosticEmitter = Callable[[Diagnostic], None]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_files_section(raw: dict[str, Any]) -> FilesSection:
    """Hydrate a ``files`` object from raw JSON."""
    return FilesSection(
        include=tuple(raw.get("include") or []),
        exclude=tuple(raw.get("exclude") or []),
    )


def _load_procedures_section(
    raw: dict[str, Any],
    source_path: Path,
    on_diagnostic: DiagnosticEmitter,
) -> ProceduresSection:
    """Hydrate a ``procedures`` object; emits ``VE-03`` for empty procs arrays."""
    include: list[ProcEntryRef] = []
    for entry in raw.get("include") or []:
        procs = tuple(entry.get("procs") or [])
        if not procs:
            on_diagnostic(
                Diagnostic.build(
                    "VE-03",
                    phase=Phase.P1_CONFIG,
                    message=(f"procedures.include entry for file {entry.get('file')!r} has an empty procs array"),
                    path=source_path,
                    hint="Remove the entry or add at least one proc name",
                )
            )
            continue
        include.append(ProcEntryRef(file=Path(entry["file"]), procs=procs))

    exclude: list[ProcEntryRef] = []
    for entry in raw.get("exclude") or []:
        procs = tuple(entry.get("procs") or [])
        if not procs:
            on_diagnostic(
                Diagnostic.build(
                    "VE-03",
                    phase=Phase.P1_CONFIG,
                    message=(f"procedures.exclude entry for file {entry.get('file')!r} has an empty procs array"),
                    path=source_path,
                    hint="Remove the entry if you have nothing to exclude",
                )
            )
            continue
        exclude.append(ProcEntryRef(file=Path(entry["file"]), procs=procs))

    return ProceduresSection(include=tuple(include), exclude=tuple(exclude))


def _load_stage_def(raw: dict[str, Any]) -> StageDefinition:
    """Hydrate a ``stageDefinition`` object."""
    return StageDefinition(
        name=raw["name"],
        load_from=raw.get("load_from") or "",
        steps=tuple(raw.get("steps") or []),
        dependencies=tuple(raw.get("dependencies") or []),
        exit_codes=tuple(raw.get("exit_codes") or []),
        command=raw.get("command") or None,
        inputs=tuple(raw.get("inputs") or []),
        outputs=tuple(raw.get("outputs") or []),
        run_mode=raw.get("run_mode", "serial"),  # type: ignore[arg-type]
        language=raw.get("language", "tcl"),  # type: ignore[arg-type]
    )


def _load_flow_action(raw: dict[str, Any]) -> FlowAction:
    """Hydrate one flow-action entry from raw JSON.

    The schema's ``oneOf`` guarantees structural validity before this
    function is called; we dispatch purely on ``action``.
    """
    action: str = raw["action"]

    if action in ("add_step_before", "add_step_after"):
        return AddStepAction(
            action=action,  # type: ignore[arg-type]
            stage=raw["stage"],
            reference=raw["reference"],
            items=tuple(raw["items"]),
        )

    if action in ("add_stage_before", "add_stage_after"):
        # The new stage fields are inline in the action object, not nested.
        stage_def = StageDefinition(
            name=raw["name"],
            load_from=raw.get("load_from") or "",
            steps=tuple(raw.get("steps") or []),
            dependencies=tuple(raw.get("dependencies") or []),
            exit_codes=tuple(raw.get("exit_codes") or []),
            command=raw.get("command") or None,
            inputs=tuple(raw.get("inputs") or []),
            outputs=tuple(raw.get("outputs") or []),
            run_mode=raw.get("run_mode", "serial"),  # type: ignore[arg-type]
            language=raw.get("language", "tcl"),  # type: ignore[arg-type]
        )
        return AddStageAction(
            action=action,  # type: ignore[arg-type]
            reference=raw["reference"],
            stage=stage_def,
        )

    if action == "remove_step":
        return RemoveStepAction(
            action="remove_step",
            stage=raw["stage"],
            reference=raw["reference"],
        )

    if action == "remove_stage":
        return RemoveStageAction(action="remove_stage", reference=raw["reference"])

    if action == "load_from":
        return LoadFromAction(action="load_from", stage=raw["stage"], reference=raw["reference"])

    if action == "replace_step":
        return ReplaceStepAction(
            action="replace_step",
            stage=raw["stage"],
            reference=raw["reference"],
            replacement=raw["with"],
        )

    if action == "replace_stage":
        return ReplaceStageAction(
            action="replace_stage",
            reference=raw["reference"],
            replacement=_load_stage_def(raw["with"]),
        )

    # Unreachable if schema validation ran first.
    raise AssertionError(f"unmapped flow action kind: {action!r}")


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_base(
    raw: dict[str, Any],
    source_path: Path,
    on_diagnostic: DiagnosticEmitter,
) -> BaseJson:
    """Hydrate a validated ``chopper/base/v1`` dict into :class:`BaseJson`.

    :param raw: Already-validated dict (caller invoked
        :func:`~chopper.config.schema.validate_json` and got ``True``).
    :param source_path: Path of the JSON file — for provenance on
        ``VE-03`` diagnostics.
    :param on_diagnostic: Diagnostic callback for ``VE-03`` only;
        schema errors are the schema layer's responsibility.
    :returns: Populated :class:`BaseJson` instance.
    """
    options_raw = raw.get("options") or {}
    options = BaseOptions(cross_validate=options_raw.get("cross_validate", True))

    stages = tuple(_load_stage_def(s) for s in (raw.get("stages") or []))
    files = _load_files_section(raw.get("files") or {})
    procs = _load_procedures_section(raw.get("procedures") or {}, source_path, on_diagnostic)

    return BaseJson(
        source_path=source_path,
        domain=raw["domain"],
        owner=raw.get("owner"),
        vendor=raw.get("vendor"),
        tool=raw.get("tool"),
        description=raw.get("description"),
        options=options,
        files=files,
        procedures=procs,
        stages=stages,
    )


def load_feature(
    raw: dict[str, Any],
    source_path: Path,
    on_diagnostic: DiagnosticEmitter,
) -> FeatureJson:
    """Hydrate a validated ``chopper/feature/v1`` dict into :class:`FeatureJson`."""
    meta_raw = raw.get("metadata") or {}
    metadata = FeatureMetadata(
        owner=meta_raw.get("owner"),
        tags=tuple(meta_raw.get("tags") or []),
        wiki=meta_raw.get("wiki"),
        related_ivars=tuple(meta_raw.get("related_ivars") or []),
        related_appvars=tuple(meta_raw.get("related_appvars") or []),
    )

    files = _load_files_section(raw.get("files") or {})
    procs = _load_procedures_section(raw.get("procedures") or {}, source_path, on_diagnostic)
    actions = tuple(_load_flow_action(a) for a in (raw.get("flow_actions") or []))

    return FeatureJson(
        source_path=source_path,
        name=raw["name"],
        domain=raw.get("domain"),
        description=raw.get("description"),
        depends_on=tuple(raw.get("depends_on") or []),
        metadata=metadata,
        files=files,
        procedures=procs,
        flow_actions=actions,
    )


def load_project(raw: dict[str, Any], source_path: Path) -> ProjectJson:
    """Hydrate a validated ``chopper/project/v1`` dict into :class:`ProjectJson`.

    No diagnostics are emitted here — structural errors were caught by the
    schema validator; semantic errors (VE-17, VE-18) are the
    ``ValidatorService``'s responsibility after the full load.
    """
    return ProjectJson(
        source_path=source_path,
        project=raw["project"],
        domain=raw["domain"],
        base=raw["base"],
        owner=raw.get("owner"),
        release_branch=raw.get("release_branch"),
        features=tuple(raw.get("features") or []),
        notes=tuple(raw.get("notes") or []),
    )


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------


def topo_sort_features(
    features: list[FeatureJson],
    source_path: Path,
    on_diagnostic: DiagnosticEmitter,
) -> list[FeatureJson]:
    """Return ``features`` in dependency-first order (Kahn's algorithm).

    Features that have no mutual dependency relationship preserve their
    original relative order (stable). The sort is O(V + E).

    Emits:

    * ``VE-14`` once per duplicate ``name`` field (first occurrence wins;
      duplicates are dropped before sorting).
    * ``VE-15`` for each ``depends_on`` name that is not present in the
      selection.
    * ``VE-22`` if a cycle is detected; returns the original order so
      the caller can continue loading (and the pipeline gate will abort
      cleanly after the phase).

    :param features: Feature list from the project selection (or the
        direct ``--features`` CLI flag); order is preserved within
        equal-rank groups.
    :param source_path: Used for diagnostic provenance (project JSON
        path when project-driven; the first feature path otherwise).
    :param on_diagnostic: Diagnostic callback.
    :returns: Re-ordered (or original-on-error) list.
    """
    # --- VE-14: deduplicate by name (first seen wins) ---
    seen_names: dict[str, int] = {}  # name → first index
    deduped: list[FeatureJson] = []
    for i, feat in enumerate(features):
        if feat.name in seen_names:
            on_diagnostic(
                Diagnostic.build(
                    "VE-14",
                    phase=Phase.P1_CONFIG,
                    message=(
                        f"Duplicate feature name {feat.name!r}: first at index "
                        f"{seen_names[feat.name]}, duplicate at index {i}"
                    ),
                    path=source_path,
                    hint="Rename one feature or remove the duplicate from the project",
                )
            )
        else:
            seen_names[feat.name] = i
            deduped.append(feat)

    name_to_feat: dict[str, FeatureJson] = {f.name: f for f in deduped}

    # --- VE-15: check all depends_on references are present ---
    has_missing = False
    for feat in deduped:
        for dep in feat.depends_on:
            if dep not in name_to_feat:
                has_missing = True
                on_diagnostic(
                    Diagnostic.build(
                        "VE-15",
                        phase=Phase.P1_CONFIG,
                        message=(f"Feature {feat.name!r} depends on {dep!r}, which is not in the project selection"),
                        path=source_path,
                        hint="Add the prerequisite feature to the project or remove the dependency",
                    )
                )

    if has_missing:
        # Can't sort a graph with dangling edges — return as-is; phase gate
        # will abort on the VE-15 errors.
        return deduped

    # --- Kahn's algorithm ---
    # Build adjacency: dep_name → set of names that depend on dep_name.
    dependents: dict[str, list[str]] = {f.name: [] for f in deduped}
    in_degree: dict[str, int] = {f.name: 0 for f in deduped}

    for feat in deduped:
        for dep in feat.depends_on:
            dependents[dep].append(feat.name)
            in_degree[feat.name] += 1

    # Seed the queue with zero-in-degree nodes, in *original* order to keep
    # equal-rank features stable.
    original_order = {f.name: i for i, f in enumerate(deduped)}
    queue: deque[str] = deque(sorted((n for n, d in in_degree.items() if d == 0), key=lambda n: original_order[n]))

    sorted_names: list[str] = []
    while queue:
        name = queue.popleft()
        sorted_names.append(name)
        # Release dependents; add newly zero-in-degree ones in original order.
        released: list[str] = []
        for dep in dependents[name]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                released.append(dep)
        released.sort(key=lambda n: original_order[n])
        queue.extend(released)

    if len(sorted_names) != len(deduped):
        # Cycle detected — VE-22.
        on_diagnostic(
            Diagnostic.build(
                "VE-22",
                phase=Phase.P1_CONFIG,
                message="Feature depends_on cycle detected; topological sort failed",
                path=source_path,
                hint="Break the cycle by removing or reordering depends_on declarations",
            )
        )
        return deduped

    return [name_to_feat[n] for n in sorted_names]
