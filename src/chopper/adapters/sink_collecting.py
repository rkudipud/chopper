"""Production :class:`DiagnosticSink` adapter.

Collects :class:`Diagnostic` emissions in insertion order and
deduplicates on :attr:`Diagnostic.dedupe_key` (last-write-wins within
a bucket). Single-threaded; no locking.
"""

from __future__ import annotations

from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Severity

__all__ = ["CollectingSink"]


class CollectingSink:
    """Insertion-ordered, dedupe-aware diagnostic sink.

    ``emit`` appends; if an earlier emission shares the same
    :attr:`Diagnostic.dedupe_key`, the later one replaces it in place
    (last-write-wins). ``snapshot`` returns the preserved insertion
    order.
    """

    def __init__(self) -> None:
        self._emissions: list[Diagnostic] = []
        # Map dedupe_key -> index in self._emissions.
        self._index: dict[tuple[object, ...], int] = {}

    def emit(self, diagnostic: Diagnostic) -> None:
        key = diagnostic.dedupe_key
        existing = self._index.get(key)
        if existing is None:
            self._index[key] = len(self._emissions)
            self._emissions.append(diagnostic)
        else:
            self._emissions[existing] = diagnostic

    def snapshot(self) -> tuple[Diagnostic, ...]:
        return tuple(self._emissions)

    def finalize(self) -> DiagnosticSummary:
        errors = sum(1 for d in self._emissions if d.severity is Severity.ERROR)
        warnings = sum(1 for d in self._emissions if d.severity is Severity.WARNING)
        infos = sum(1 for d in self._emissions if d.severity is Severity.INFO)
        return DiagnosticSummary(errors=errors, warnings=warnings, infos=infos)
