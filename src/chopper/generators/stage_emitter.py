"""Stage emitter -- renders a :class:`StageSpec` to ``<stage>.tcl`` text.

Plain strings by design: each step is emitted verbatim on its own line,
in declaration order. No templating, no variable expansion, no Tcl
parsing -- the authoring contract is that steps already contain valid
Tcl (or the target language).

The only interpretation performed:

* the Intel-standard copyright header (see :mod:`chopper.core.header`)
  is prepended with the current calendar year -- unless the steps own
  their header (line-1 ``#!`` shebang or a leading copyright notice),
  in which case the file is exactly the steps (ARCHITECTURE.md Sec.6.6.1);
* a single-line provenance banner, emitted with the header, so audit
  consumers can correlate a generated file back to its source stage
  without opening ``compiled_manifest.json``;
* steps joined with ``"\n"`` and file terminated with a trailing newline.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.header import intel_header_lines, needs_header
from chopper.core.models_compiler import StageSpec
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = ["emit_stage_tcl", "stage_output_path"]


def stage_output_path(stage: StageSpec) -> Path:
    """Return the domain-relative path at which the stage is written."""

    return Path(f"{stage.name}.tcl")


def emit_stage_tcl(stage: StageSpec) -> GeneratedArtifact:
    """Render ``stage`` as a ``GeneratedArtifact`` of kind ``"tcl"``.

    The returned artifact is purely a value record -- no filesystem I/O
    is performed here. :class:`~chopper.generators.GeneratorService`
    writes the content via :attr:`ChopperContext.fs`.
    """

    path = stage_output_path(stage)
    lines: list[str] = []
    if needs_header(path, stage.steps):
        lines.extend(intel_header_lines())
        lines.append(f"# Chopper-generated stage: {stage.name}")
        if stage.load_from:
            lines.append(f"# load_from: {stage.load_from}")
    lines.extend(stage.steps)
    content = "\n".join(lines) + "\n"

    return GeneratedArtifact(
        path=path,
        kind="tcl",
        content=content,
        source_stage=stage.name,
    )
