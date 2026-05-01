"""Compiler and tracer model records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from chopper.core.models_common import FileTreatment

__all__ = [
    "CompiledManifest",
    "DependencyGraph",
    "Edge",
    "FileProvenance",
    "ProcDecision",
    "StageSpec",
]


@dataclass(frozen=True)
class ProcDecision:
    """One surviving proc recorded in the compiled manifest."""

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
    """Per-file provenance record written into the compiled manifest."""

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
    """One resolved F3 stage in the compiled manifest."""

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
    """Frozen output of :class:`~chopper.compiler.CompilerService` (P3)."""

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


@dataclass(frozen=True)
class Edge:
    """One caller to callee edge recorded by :class:`TracerService` (P4)."""

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
    """Frozen output of :class:`~chopper.compiler.TracerService` (P4)."""

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
