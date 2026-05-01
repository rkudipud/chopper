"""Diagnostic / RunResult rendering for the CLI.

Services never render; the CLI does. This module takes a
:class:`RunResult` (returned by :class:`ChopperRunner.run`) plus the
diagnostic snapshot and writes a human-readable summary to
``stderr``.

Rendering is a pure consumer of data. No side effects beyond writing
to the provided text stream.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from chopper.core.diagnostics import Diagnostic, Severity
from chopper.core.models_audit import RunResult

__all__ = ["render_cleanup_message", "render_diagnostics", "render_result"]


_SEVERITY_LABEL = {
    Severity.ERROR: "ERROR",
    Severity.WARNING: "WARN ",
    Severity.INFO: "INFO ",
}


def render_diagnostics(
    diagnostics: Sequence[Diagnostic],
    stream: TextIO | None = None,
) -> None:
    """Write each diagnostic as a one-line ``LEVEL CODE: message`` row."""

    out = stream if stream is not None else sys.stderr
    for d in diagnostics:
        label = _SEVERITY_LABEL[d.severity]
        location = ""
        if d.path is not None:
            location = f" [{d.path.as_posix()}"
            if d.line_no is not None:
                location += f":{d.line_no}"
            location += "]"
        out.write(f"{label} {d.code}:{location} {d.message}\n")


def render_result(
    result: RunResult,
    diagnostics: Sequence[Diagnostic],
    stream: TextIO | None = None,
) -> None:
    """Render diagnostics followed by a one-line summary."""

    render_diagnostics(diagnostics, stream=stream)
    out = stream if stream is not None else sys.stderr
    s = result.summary
    out.write(f"Summary: {s.errors} error(s), {s.warnings} warning(s), {s.infos} info(s); exit {result.exit_code}\n")


def render_cleanup_message(message: str, stream: TextIO | None = None) -> None:
    """Write a user-facing ``chopper cleanup`` status line to ``stdout``.

    Cleanup is a direct filesystem operation — it does not enter
    :class:`~chopper.orchestrator.runner.ChopperRunner`, so there are no
    diagnostics to render. The caller provides the prose; this helper
    centralises the output channel (``stdout``) so ``cli/render.py``
    remains the single place library code talks to the user.
    """

    out = stream if stream is not None else sys.stdout
    out.write(f"{message}\n")
