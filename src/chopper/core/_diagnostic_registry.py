"""Diagnostic-code registry — single Python-side source of truth.

Mirrors the active rows of the diagnostic registry documentation. Every
addition to the docs registry is accompanied by an addition here; the
``scripts/check_diagnostic_registry.py`` CI gate enforces the mirror.

Structured so that no line contains the literal substrings
``Diagnostic(`` or ``code=``, keeping it invisible to the per-line
gate scanner that would otherwise flag the registry as an unregistered
use site.

Usage is internal to :mod:`chopper.core.diagnostics`. External callers
reference diagnostics by numeric code only; slug / severity / source
are looked up here so they cannot drift from emitted output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):  # noqa: UP042 — str mixin required so the value is JSON-emitted as the string.
    """Diagnostic severity.

    Mirrors the three-letter family suffix (``E``/``W``/``I``). The
    string value is what appears in ``diagnostics.json`` and in
    rendered CLI output. Subclassing :class:`str` makes ``json.dumps``
    serialise the enum as the lowercase string value directly.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class _Entry:
    """A single row of the registry.

    * ``slug`` — kebab-case human-readable label (used in verbose CLI output).
    * ``severity`` — the severity baked into the code's family letter.
    * ``phase`` — the *canonical* phase where the code is emitted, per the
      registry. The phase actually stamped on a :class:`Diagnostic` is set
      by the caller at emission time; this field is here so callers that
      don't pass an explicit phase can default to the registered one.
    * ``source`` — the subsystem that owns the code (``parser``,
      ``compiler``, ``validator``, ``trimmer``, ``schema``, ``cli``).
        * ``exit_code`` — the process exit code the CLI selects when this code
            is the highest-severity outcome of the run.
    """

    slug: str
    severity: Severity
    phase: int
    source: str
    exit_code: int


# Derived from the diagnostic registry. Order follows the registry:
# VE-01..VE-26, VW-01..VW-19, VI-01..VI-02, TW-01..TW-04,
# PE-01..PE-04, PW-01..PW-11, PI-01..PI-04 — 69 active codes, matching the
# Code Space Summary table in the registry.
_REGISTRY: dict[str, _Entry] = {
    "VE-01": _Entry(slug="missing-schema", severity=Severity.ERROR, phase=1, source="schema", exit_code=1),
    "VE-02": _Entry(slug="missing-required-fields", severity=Severity.ERROR, phase=1, source="schema", exit_code=1),
    "VE-03": _Entry(slug="empty-procs-array", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-04": _Entry(slug="unsupported-flow-action", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-05": _Entry(slug="missing-action-target", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-06": _Entry(slug="file-not-in-domain", severity=Severity.ERROR, phase=1, source="validator", exit_code=1),
    "VE-07": _Entry(slug="proc-not-in-file", severity=Severity.ERROR, phase=1, source="validator", exit_code=1),
    "VE-08": _Entry(slug="duplicate-stage-names", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-09": _Entry(slug="malformed-glob", severity=Severity.ERROR, phase=1, source="validator", exit_code=1),
    "VE-10": _Entry(
        slug="occurrence-suffix-overflow", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1
    ),
    "VE-11": _Entry(slug="conflicting-cli-options", severity=Severity.ERROR, phase=1, source="cli", exit_code=2),
    "VE-12": _Entry(slug="project-schema-invalid", severity=Severity.ERROR, phase=1, source="schema", exit_code=1),
    "VE-13": _Entry(slug="project-path-unresolvable", severity=Severity.ERROR, phase=1, source="cli", exit_code=2),
    "VE-14": _Entry(slug="duplicate-feature-name", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-15": _Entry(
        slug="missing-depends-on-feature", severity=Severity.ERROR, phase=1, source="validator", exit_code=1
    ),
    "VE-16": _Entry(slug="brace-error-post-trim", severity=Severity.ERROR, phase=6, source="validator", exit_code=3),
    "VE-17": _Entry(slug="project-domain-mismatch", severity=Severity.ERROR, phase=1, source="validator", exit_code=1),
    "VE-18": _Entry(slug="duplicate-feature-entry", severity=Severity.ERROR, phase=1, source="validator", exit_code=1),
    "VE-19": _Entry(slug="occurrence-suffix-zero", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-20": _Entry(slug="ambiguous-step-target", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-21": _Entry(slug="no-domain-or-backup", severity=Severity.ERROR, phase=1, source="cli", exit_code=2),
    "VE-22": _Entry(slug="feature-depends-on-cycle", severity=Severity.ERROR, phase=1, source="compiler", exit_code=1),
    "VE-23": _Entry(
        slug="filesystem-error-during-trim", severity=Severity.ERROR, phase=5, source="trimmer", exit_code=1
    ),
    "VE-24": _Entry(slug="backup-contents-missing", severity=Severity.ERROR, phase=5, source="trimmer", exit_code=1),
    "VE-25": _Entry(slug="domain-write-failed", severity=Severity.ERROR, phase=5, source="trimmer", exit_code=1),
    "VE-26": _Entry(slug="proc-atomic-drop-failed", severity=Severity.ERROR, phase=5, source="trimmer", exit_code=1),
    "VW-01": _Entry(
        slug="file-in-both-include-lists", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0
    ),
    "VW-02": _Entry(
        slug="proc-in-include-and-exclude", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0
    ),
    "VW-03": _Entry(slug="glob-matches-nothing", severity=Severity.WARNING, phase=1, source="validator", exit_code=0),
    "VW-04": _Entry(
        slug="feature-domain-mismatch", severity=Severity.WARNING, phase=1, source="validator", exit_code=0
    ),
    "VW-05": _Entry(slug="dangling-proc-call", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-06": _Entry(slug="source-file-removed", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-07": _Entry(slug="run-file-step-trimmed", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-08": _Entry(slug="file-empty-after-trim", severity=Severity.WARNING, phase=5, source="trimmer", exit_code=0),
    "VW-09": _Entry(slug="fi-pi-overlap", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0),
    # VW-10 is a reserved slot in the registry — not populated.
    "VW-11": _Entry(
        slug="fe-pe-same-source-conflict", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0
    ),
    "VW-12": _Entry(slug="pi-pe-same-file", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0),
    "VW-13": _Entry(slug="pe-removes-all-procs", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0),
    "VW-14": _Entry(slug="step-file-missing", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-15": _Entry(slug="step-proc-missing", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-16": _Entry(slug="step-source-missing", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-17": _Entry(slug="external-reference", severity=Severity.WARNING, phase=6, source="validator", exit_code=0),
    "VW-18": _Entry(slug="cross-source-pe-vetoed", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0),
    "VW-19": _Entry(slug="cross-source-fe-vetoed", severity=Severity.WARNING, phase=1, source="compiler", exit_code=0),
    "VI-01": _Entry(slug="empty-base-json", severity=Severity.INFO, phase=1, source="validator", exit_code=0),
    "VI-02": _Entry(slug="top-level-tcl-only", severity=Severity.INFO, phase=5, source="trimmer", exit_code=0),
    "TW-01": _Entry(slug="ambiguous-proc-match", severity=Severity.WARNING, phase=4, source="compiler", exit_code=0),
    "TW-02": _Entry(slug="unresolved-proc-call", severity=Severity.WARNING, phase=4, source="compiler", exit_code=0),
    "TW-03": _Entry(slug="dynamic-call-form", severity=Severity.WARNING, phase=4, source="compiler", exit_code=0),
    "TW-04": _Entry(slug="cycle-in-call-graph", severity=Severity.WARNING, phase=4, source="compiler", exit_code=0),
    "PE-01": _Entry(slug="duplicate-proc-definition", severity=Severity.ERROR, phase=2, source="parser", exit_code=1),
    "PE-02": _Entry(slug="unbalanced-braces", severity=Severity.ERROR, phase=2, source="parser", exit_code=1),
    "PE-03": _Entry(slug="ambiguous-short-name", severity=Severity.ERROR, phase=2, source="parser", exit_code=1),
    "PE-04": _Entry(slug="mcp-protocol-error", severity=Severity.ERROR, phase=0, source="mcp", exit_code=4),
    "PW-01": _Entry(slug="computed-proc-name", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-02": _Entry(slug="utf8-decode-failure", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-03": _Entry(slug="non-brace-body", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-04": _Entry(slug="computed-namespace-name", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-05": _Entry(slug="backslash-continuation", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-06": _Entry(slug="multi-value-set", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-07": _Entry(slug="dynamic-array-index", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-08": _Entry(slug="deep-nesting", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-09": _Entry(slug="dynamic-variable-ref", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-10": _Entry(slug="proc-call-in-string", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PW-11": _Entry(slug="dpa-name-mismatch", severity=Severity.WARNING, phase=2, source="parser", exit_code=0),
    "PI-01": _Entry(slug="structured-comment-block", severity=Severity.INFO, phase=2, source="parser", exit_code=0),
    "PI-02": _Entry(slug="command-substitution-indexed", severity=Severity.INFO, phase=2, source="parser", exit_code=0),
    "PI-03": _Entry(slug="comment-separator-block", severity=Severity.INFO, phase=2, source="parser", exit_code=0),
    "PI-04": _Entry(slug="dpa-orphan", severity=Severity.INFO, phase=2, source="parser", exit_code=0),
}


def lookup(diagnostic_code: str) -> _Entry:
    """Return the registry entry for a code, or raise.

    Named :func:`lookup` (not ``get``) to keep the word ``code`` out of the
    identifier — the CI gate scanner treats ``code=`` as a heuristic for
    diagnostic construction sites, and this helper is called with a bare
    string positional argument.
    """
    try:
        return _REGISTRY[diagnostic_code]
    except KeyError as exc:
        from chopper.core.errors import UnknownDiagnosticCodeError

        raise UnknownDiagnosticCodeError(f"{diagnostic_code!r} is not a registered diagnostic code") from exc


def all_codes() -> frozenset[str]:
    """Return every registered code. Used by unit tests only."""
    return frozenset(_REGISTRY)
