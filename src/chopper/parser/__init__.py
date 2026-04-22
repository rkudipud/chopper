"""Parser package — pure utilities for Tcl tokenization, namespace tracking,
proc extraction, and call extraction.

Public entry point is :class:`ParserService` in :mod:`chopper.parser.service`
(Stage 1f). The internal helpers in this package — :mod:`tokenizer`,
:mod:`namespace_tracker`, :mod:`proc_extractor`, :mod:`call_extractor` — are
consumed only by the service, but each is independently testable with the
fixtures in ``tests/fixtures/edge_cases/``.

The parser is stateless: no module-level globals, no singletons. Each call
creates fresh state.
"""

from __future__ import annotations
