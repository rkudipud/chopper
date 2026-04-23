"""Diagnostic data shape and registry façade.

Every user-visible outcome is a :class:`Diagnostic`. This module
exposes the public data type, the :class:`Phase` and :class:`Severity`
enums, and the :class:`DiagnosticSummary` returned by
:meth:`DiagnosticSink.finalize`.

The registry lives in :mod:`chopper.core._diagnostic_registry`; importing
this module pulls the registered codes into scope. Construction of a
:class:`Diagnostic` validates the code against the registry — unknown
codes raise :class:`UnknownDiagnosticCodeError` immediately, so typos
never reach the sink.

Key invariants:

* ``slug`` / ``severity`` / ``source`` are **derived** from the registry.
  Callers may not override them; attempting to pass a mismatching value
  raises. This prevents callers from silently drifting the human-facing
  label or severity away from the registry.
* ``phase`` is supplied by the caller at emission time. The phase field
  on :class:`Diagnostic` reflects *where* the code was emitted, which
  the orchestrator uses for gate decisions.
* :class:`Diagnostic` is immutable and hashable (frozen dataclass).
* ``context`` values must be JSON-serializable; enforcement is left to
  :mod:`chopper.core.serialization` at dump time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from chopper.core._diagnostic_registry import Severity, all_codes, lookup

__all__ = [
    "Diagnostic",
    "DiagnosticSummary",
    "Phase",
    "Severity",
    "all_codes",
]


class Phase(IntEnum):
    """The eight pipeline phases.

    ``IntEnum`` so gate comparisons (``diag.phase == Phase.P3_COMPILE``)
    work directly against the integer values the registry carries in its
    ``phase`` column.
    """

    P0_STATE = 0
    P1_CONFIG = 1
    P2_PARSE = 2
    P3_COMPILE = 3
    P4_TRACE = 4
    P5_TRIM = 5
    P6_POSTVALIDATE = 6
    P7_AUDIT = 7


@dataclass(frozen=True)
class Diagnostic:
    """A single user-facing outcome.

    Callers construct diagnostics with :meth:`Diagnostic.build` — a
    classmethod that takes only the fields the caller genuinely owns
    (``code``, ``phase``, ``message``, and optional location/hint
    context). ``slug``, ``severity``, and ``source`` are filled in from
    the registry to guarantee the in-memory diagnostic matches the
    registry row exactly.

    The direct constructor is also callable but validates that any
    caller-supplied ``slug`` / ``severity`` / ``source`` match the
    registry — equivalent to :meth:`build` with explicit redundant
    arguments, so tests and audit deserialisers that reconstitute a
    :class:`Diagnostic` from JSON still work.
    """

    code: str
    slug: str
    severity: Severity
    phase: Phase
    source: str
    message: str
    path: Path | None = None
    line_no: int | None = None
    hint: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)
    dedupe_bucket: str = ""

    def __post_init__(self) -> None:
        entry = lookup(self.code)
        if self.slug != entry.slug:
            raise ValueError(
                f"Diagnostic {self.code!r}: slug {self.slug!r} does not match registry slug {entry.slug!r}"
            )
        if self.severity != entry.severity:
            raise ValueError(
                f"Diagnostic {self.code!r}: severity {self.severity!r} does not "
                f"match registry severity {entry.severity!r}"
            )
        if self.source != entry.source:
            raise ValueError(
                f"Diagnostic {self.code!r}: source {self.source!r} does not match registry source {entry.source!r}"
            )
        if "\n" in self.message:
            # Messages must be single-line.
            raise ValueError(f"Diagnostic {self.code!r}: message must be single-line")

    @classmethod
    def build(
        cls,
        diagnostic_code: str,
        *,
        phase: Phase,
        message: str,
        path: Path | None = None,
        line_no: int | None = None,
        hint: str | None = None,
        context: Mapping[str, object] | None = None,
        dedupe_bucket: str = "",
    ) -> Diagnostic:
        """Construct a :class:`Diagnostic`, filling derived fields from the registry.

        This is the preferred construction path for services. The direct
        dataclass constructor is used only when rehydrating from JSON, where
        every field is already known.

        ``phase`` is required and reflects the actual emission phase. Services
        generally set it to their own phase (for example, ``ParserService``
        always emits with ``phase=Phase.P2_PARSE``); the registry's
        ``phase`` column is the *canonical* phase for the code and is used
        as a sanity check only in tests — services are free to emit the
        same code from a different phase if the spec requires.
        """
        entry = lookup(diagnostic_code)
        return cls(
            code=diagnostic_code,
            slug=entry.slug,
            severity=entry.severity,
            phase=phase,
            source=entry.source,
            message=message,
            path=path,
            line_no=line_no,
            hint=hint,
            context=dict(context) if context else {},
            dedupe_bucket=dedupe_bucket,
        )

    @property
    def dedupe_key(self) -> tuple[str, Path | None, int | None, str, str]:
        """Key used by :class:`CollectingSink` to deduplicate emissions.

        Shape: ``(code, path, line_no, message, dedupe_bucket)``.
        ``hint`` and ``context`` are intentionally excluded so a later
        emit with richer context replaces the earlier one.
        """
        return (self.code, self.path, self.line_no, self.message, self.dedupe_bucket)


@dataclass(frozen=True)
class DiagnosticSummary:
    """Aggregated counts returned by :meth:`DiagnosticSink.finalize`.

    The CLI uses the summary to compute the process exit code: exit 1
    if any ``ERROR``; exit 1 if ``--strict`` and any ``WARNING``;
    exit 0 otherwise. ``AuditService`` uses the same summary to
    populate ``diagnostic_counts`` in ``chopper_run.json``.
    """

    errors: int
    warnings: int
    infos: int

    @property
    def total(self) -> int:
        return self.errors + self.warnings + self.infos

    @property
    def has_error(self) -> bool:
        return self.errors > 0

    @property
    def has_warning(self) -> bool:
        return self.warnings > 0
