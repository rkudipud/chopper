"""Stack emitter -- F3 scheduler-stack artifact rendering.

Two emission modes, exposed as two pure value functions (no I/O):

* :func:`emit_flow_stack` -- renders the aggregate ``<domain>.stack``
  file produced when ``options.generate_stack: true``. The file contains
  a single Intel header followed by one N/J/L/I/O/D/(R) record per
  stage, with records separated by a single blank line and the Intel
  header appearing exactly once at the top.

* :func:`emit_standalone_stack` -- renders a per-stage ``<stage>.stack``
  file produced when the stage sets ``standalone_stack: true``. The
  body is the Intel header followed by a single blank line and then
  the authored ``steps`` joined by ``"\\n"`` verbatim -- no record
  derivation, no field interpretation.

Per-record line order in the aggregate is fixed::

    # Chopper-generated stack: <name>
    N <name>
    J <command>          (omitted when command is empty)
    L <code1> <code2>    (omitted when exit_codes is empty)
    I <input>            (one line per entry; omitted when empty)
    O <output>           (one line per entry; omitted when empty)
    D <dependency>       (always; see derivation below)
    R parallel           (only when run_mode == "parallel"; serial implicit)

**Dependency (D) derivation:**

1. If ``stage.dependencies`` is non-empty, emit one ``D <dep>`` line per
   entry in authored order.
2. Else if ``stage.load_from`` is non-empty, emit ``D <load_from>``.
3. Else, emit a bare ``D`` line (first stage, no predecessor).

The ``R`` line is omitted entirely for the default ``serial`` mode --
matches the production stack-file convention.

See ARCHITECTURE.md Sec.3.6 for the authoritative behavior spec.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.header import intel_header_lines
from chopper.core.models_compiler import StageSpec
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = ["aggregate_stack_path", "emit_flow_stack", "emit_standalone_stack", "standalone_stack_path"]


def aggregate_stack_path(domain_name: str) -> Path:
    """Return the domain-relative path at which the aggregate stack is written."""

    return Path(f"{domain_name}.stack")


def standalone_stack_path(stage: StageSpec) -> Path:
    """Return the domain-relative path at which a standalone stage stack is written."""

    return Path(f"{stage.name}.stack")


def _render_record(stage: StageSpec) -> list[str]:
    """Render one aggregate-stack record (no header). See module docstring for line order."""

    lines: list[str] = []
    lines.append(f"# Chopper-generated stack: {stage.name}")
    lines.append(f"N {stage.name}")

    if stage.command:
        lines.append(f"J {stage.command}")

    if stage.exit_codes:
        codes = " ".join(str(code) for code in stage.exit_codes)
        lines.append(f"L {codes}")

    for value in stage.inputs:
        lines.append(f"I {value}")

    for value in stage.outputs:
        lines.append(f"O {value}")

    # D-line derivation: dependencies > load_from > blank.
    if stage.dependencies:
        for dep in stage.dependencies:
            lines.append(f"D {dep}")
    elif stage.load_from:
        lines.append(f"D {stage.load_from}")
    else:
        lines.append("D")

    # R line is emitted only for parallel; serial is implicit.
    if stage.run_mode == "parallel":
        lines.append("R parallel")

    return lines


def emit_flow_stack(
    stages: tuple[StageSpec, ...],
    domain_name: str,
    stack_order: tuple[str, ...] = (),
) -> GeneratedArtifact:
    """Render the aggregate ``<domain_name>.stack`` for all stages.

    When ``stack_order`` is empty, records are emitted in ``stages``
    order. When non-empty, ``stack_order`` must be a permutation of
    ``{s.name for s in stages}`` (typically the topological order
    computed by :func:`chopper.compiler.stack_graph.compute_stack_order`)
    and records are emitted by name lookup in that order.

    ``stages`` must be non-empty; the aggregate stack is only requested
    when at least one stage is in scope, and the caller is responsible
    for that guard.
    """

    if stack_order:
        by_name = {s.name: s for s in stages}
        ordered_stages: tuple[StageSpec, ...] = tuple(by_name[n] for n in stack_order)
    else:
        ordered_stages = stages

    parts: list[str] = ["\n".join(intel_header_lines())]
    parts.extend("\n".join(_render_record(stage)) for stage in ordered_stages)
    content = "\n\n".join(parts) + "\n"

    return GeneratedArtifact(
        path=aggregate_stack_path(domain_name),
        kind="stack",
        content=content,
        source_stage=domain_name,
    )


def emit_standalone_stack(stage: StageSpec) -> GeneratedArtifact:
    """Render a per-stage ``<stage>.stack`` with verbatim steps.

    Body layout::

        <Intel header>
        <blank line>
        <step1>
        <step2>
        ...

    No record derivation; ``command``, ``exit_codes``, ``dependencies``,
    ``inputs``, ``outputs``, ``load_from``, and ``run_mode`` are
    ignored.
    """

    header = "\n".join(intel_header_lines())
    body = "\n".join(stage.steps)
    content = f"{header}\n\n{body}\n"

    return GeneratedArtifact(
        path=standalone_stack_path(stage),
        kind="stack",
        content=content,
        source_stage=stage.name,
    )
