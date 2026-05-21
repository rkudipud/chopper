"""Generators package — P5b F3 run-file emission.

Emits one ``<stage>.tcl`` per resolved :class:`StageSpec`. Runs after
:class:`TrimmerService`; generated files live alongside normal domain
files and are subject to post-trim validation at P6.

Outputs are flat-file, plain-string: every step is rendered verbatim,
one step per line. No interpretation, no templating.
"""

from __future__ import annotations

from chopper.generators.service import GeneratorService

__all__ = ["GeneratorService"]
