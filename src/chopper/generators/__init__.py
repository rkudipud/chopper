"""Generators package — P5b of the Chopper pipeline.

Emits F3 run-files (``<stage>.tcl``) per resolved
:class:`~chopper.core.models.StageSpec`. Bible §§3.6, 5.3, 6.7.

:class:`GeneratorService` runs after :class:`~chopper.trimmer.TrimmerService`
and writes its outputs into the rebuilt ``<domain>/`` — generated files
live alongside normal domain files and are subject to post-trim
validation at P6 (bible §P5b).

Generator outputs are flat-file, plain-string emissions per bible §R4
("plain strings by design"): every step is rendered verbatim, one
step per line. No interpretation, no templating.
"""

from __future__ import annotations

from chopper.generators.service import GeneratorService

__all__ = ["GeneratorService"]
