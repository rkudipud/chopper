"""Stack emitter — renders a :class:`StageSpec` to ``<stage>.stack`` text.

Emits an N/J/L/D/I/O/R stack-file entry derived directly from the
resolved stage's authored fields. Pure value function; no I/O. The
:class:`~chopper.generators.GeneratorService` writes the content via
:attr:`ChopperContext.fs` when ``manifest.generate_stack`` is ``True``.

Output layout (lines omitted when the corresponding field is empty,
except ``N``, ``D``, and ``R`` which are always emitted)::

    # Chopper-generated stack: <name>
    N <name>
    J <command>
    L <code1> <code2> ...
    D <dependency>
    I <input>
    O <output>
    R <run_mode>

**Dependency (D) derivation:**

1. If ``stage.dependencies`` is non-empty, emit one ``D <dep>`` line per
   entry in authored order.
2. Else if ``stage.load_from`` is non-empty, emit ``D <load_from>``.
3. Else, emit a bare ``D`` line (first stage, no predecessor).

``R <run_mode>`` is always emitted with ``"serial"`` (default) or
``"parallel"``.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.models_compiler import StageSpec
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = ["emit_stage_stack", "stack_output_path"]


def stack_output_path(stage: StageSpec) -> Path:
    """Return the domain-relative path at which the stack file is written."""

    return Path(f"{stage.name}.stack")


def emit_stage_stack(stage: StageSpec) -> GeneratedArtifact:
    """Render ``stage`` as a ``GeneratedArtifact`` of kind ``"stack"``."""

    lines: list[str] = [f"# Chopper-generated stack: {stage.name}", f"N {stage.name}"]

    if stage.command:
        lines.append(f"J {stage.command}")

    if stage.exit_codes:
        codes = " ".join(str(code) for code in stage.exit_codes)
        lines.append(f"L {codes}")

    # D-line derivation: dependencies > load_from > blank.
    if stage.dependencies:
        for dep in stage.dependencies:
            lines.append(f"D {dep}")
    elif stage.load_from:
        lines.append(f"D {stage.load_from}")
    else:
        lines.append("D")

    for value in stage.inputs:
        lines.append(f"I {value}")

    for value in stage.outputs:
        lines.append(f"O {value}")

    lines.append(f"R {stage.run_mode}")

    content = "\n".join(lines) + "\n"

    return GeneratedArtifact(
        path=stack_output_path(stage),
        kind="stack",
        content=content,
        source_stage=stage.name,
    )
