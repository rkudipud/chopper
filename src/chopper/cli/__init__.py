"""Thin argparse-based CLI for Chopper.

No business logic lives here. The CLI:

1. Parses arguments into :class:`argparse.Namespace`.
2. Dispatches to the appropriate :mod:`chopper.cli.commands` handler.
3. Builds a :class:`ChopperContext` and calls
   :meth:`ChopperRunner.run`.
4. Renders the returned :class:`RunResult` via
   :func:`chopper.cli.render.render_result`.
5. Returns a process exit code.

See :mod:`chopper.cli.main` for the entrypoint.
"""

from __future__ import annotations

from chopper.cli.main import main

__all__ = ["main"]
