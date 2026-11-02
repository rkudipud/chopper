"""Shared emitter for v2 feature vars/procs sourcing files.

Pure value function (no I/O). Layout (ARCHITECTURE.md Sec.3.12)::

    <Intel header>

    # Feature vars.tcl sourcing file for <flow>

    iproc_source -file <entry> -optional      (one line per entry,
    ...                                        one blank line between
                                               feature blocks)

With no blocks the file is the header and the title line only.
"""

from __future__ import annotations

from pathlib import Path

from chopper.core.header import intel_header_lines
from chopper.core.models_trimmer import GeneratedArtifact

__all__ = ["emit_feature_vars"]

_TCL_WORD_ESCAPES = str.maketrans(
    {
        **{char: f"\\{char}" for char in ' \\"{}[]$;'},
        "\t": r"\t",
        "\r": r"\r",
        "\n": r"\n",
        "\v": r"\v",
        "\f": r"\f",
    }
)


def emit_feature_vars(flow_name: str, blocks: tuple[tuple[str, ...], ...], *, procs: bool = False) -> GeneratedArtifact:
    """Render a feature vars/procs sourcing file from per-feature entry blocks."""
    kind = "procs" if procs else "vars"
    parts = ["\n".join(intel_header_lines()), f"# Feature {kind}.tcl sourcing file for {flow_name}"]
    parts.extend(
        "\n".join(f"iproc_source -file {entry.translate(_TCL_WORD_ESCAPES)} -optional" for entry in block)
        for block in blocks
    )
    return GeneratedArtifact(
        path=Path(f"{flow_name}_feature_{kind}.tcl"),
        kind="tcl",
        content="\n\n".join(parts) + "\n",
        source_stage=flow_name,
    )
