"""Config-loader and JSON-authoring model records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

__all__ = [
    "AddStageAction",
    "AddStepAction",
    "BaseJson",
    "BaseOptions",
    "FeatureJson",
    "FeatureMetadata",
    "FilesSection",
    "FlowAction",
    "LoadFromAction",
    "LoadedConfig",
    "ProcEntryRef",
    "ProceduresSection",
    "ProjectJson",
    "RemoveStageAction",
    "RemoveStepAction",
    "ReplaceStageAction",
    "ReplaceStepAction",
    "StageDefinition",
]


@dataclass(frozen=True)
class ProcEntryRef:
    """A proc-level include/exclude reference: ``{file, procs[]}``."""

    file: Path
    procs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.procs:
            raise ValueError("ProcEntryRef.procs must be non-empty (VE-03 at loader)")


@dataclass(frozen=True)
class FilesSection:
    """``files`` block in base / feature JSON."""

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProceduresSection:
    """``procedures`` block in base / feature JSON."""

    include: tuple[ProcEntryRef, ...] = ()
    exclude: tuple[ProcEntryRef, ...] = ()


@dataclass(frozen=True)
class StageDefinition:
    """One stage entry from ``base.stages[]`` or a feature flow action."""

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
    """``add_stage_before`` / ``add_stage_after``."""

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
    """``load_from``: retarget a stage's predecessor."""

    action: Literal["load_from"]
    stage: str
    reference: str


@dataclass(frozen=True)
class ReplaceStepAction:
    """``replace_step``."""

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


@dataclass(frozen=True)
class BaseOptions:
    """``options`` block in base JSON."""

    cross_validate: bool = True
    generate_stack: bool = False


@dataclass(frozen=True)
class BaseJson:
    """Hydrated ``base-v1`` JSON."""

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
    """Optional ``metadata`` block on a feature JSON."""

    owner: str | None = None
    tags: tuple[str, ...] = ()
    wiki: str | None = None
    related_ivars: tuple[str, ...] = ()
    related_appvars: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureJson:
    """Hydrated ``feature-v1`` JSON."""

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
    """Hydrated ``project-v1`` JSON."""

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
    """Aggregate returned by :class:`ConfigService`."""

    base: BaseJson
    features: tuple[FeatureJson, ...] = ()
    project: ProjectJson | None = None
    surface_files: tuple[Path, ...] = ()
    tool_command_pool: frozenset[str] = frozenset()
    domain_file_cache: tuple[tuple[Path, str], ...] = ()

    def __post_init__(self) -> None:
        names = [f.name for f in self.features]
        if len(set(names)) != len(names):
            raise ValueError(f"LoadedConfig.features contains duplicate names: {names!r}")
        posix = [p.as_posix() for p in self.surface_files]
        if posix != sorted(posix):
            raise ValueError("LoadedConfig.surface_files must be sorted by POSIX form")
