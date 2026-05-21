"""Round-trip parse of every ``tests/fixtures/edge_cases/parser_*.tcl`` fixture.

Closes Q-03 from the 2026-04-23 spec-conformance audit. The fixtures under
``tests/fixtures/edge_cases/`` are catalogued in
`tests/FIXTURE_AUDIT.md` §2 as the canonical adversarial parser input set
(P-01 through P-04 pitfall coverage plus the namespace / EDA-complex
vectors). Before this test existed, those ``.tcl`` files were only
referenced as spec-review artifacts — no production test exercised them,
so a drift in a fixture went unnoticed.

What this test guarantees:

* Every ``parser_*.tcl`` file under ``tests/fixtures/edge_cases/`` is
  fed to :func:`chopper.parser.service.parse_file`.
* The parser does not crash (no uncaught exception).
* Any diagnostics emitted carry registered codes — the registry
  bidirectional gate in ``schemas/scripts/check_diagnostic_registry.py`` already
  guarantees registration at the source-code level, but running the
  parser against real fixtures proves no *emitted* code is a typo.

This is deliberately a thin guard. Behavioural assertions (what
specific diagnostic each fixture should emit, in which order) already
live beside the relevant parser unit tests; duplicating them here would
break the "regression guards co-located with the code" principle
([tests/FIXTURE_AUDIT.md](../../FIXTURE_AUDIT.md) §1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.diagnostics import Diagnostic
from chopper.parser.service import parse_file

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "edge_cases"


def _parser_fixtures() -> list[Path]:
    """Return every ``parser_*.tcl`` fixture; sorted for deterministic IDs."""
    return sorted(FIXTURES_DIR.glob("parser_*.tcl"))


@pytest.mark.parametrize("fixture", _parser_fixtures(), ids=lambda p: p.name)
def test_edge_case_fixture_parses_without_crashing(fixture: Path) -> None:
    """Each fixture parses; any emitted diagnostics have registered codes."""
    # Decode with UTF-8 first, Latin-1 fallback — mirrors
    # :class:`chopper.parser.service.ParserService` encoding policy (see
    # ``parser_encoding_latin1_fallback.tcl``).
    raw = fixture.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    emitted: list[Diagnostic] = []
    # parse_file must not raise. Any failure here is the test failure.
    result = parse_file(fixture, text, on_diagnostic=emitted.append)

    # ProcEntry list is well-formed.
    assert isinstance(result, list)
    # Diagnostic.__post_init__ already validates each code against the
    # registry; reaching this point means every emission is a registered
    # code. We assert the invariant explicitly as a readability win.
    for diag in emitted:
        assert diag.code, "emitted diagnostic has empty code"
        assert diag.slug, f"diagnostic {diag.code!r} has empty slug"


def test_every_parser_fixture_is_covered() -> None:
    """Guard: the glob above finds at least the count documented in FIXTURE_AUDIT.md §2."""
    fixtures = _parser_fixtures()
    # FIXTURE_AUDIT.md §2 enumerates 17 adversarial parser fixtures; the
    # guard tolerates additions but flags accidental deletions.
    assert len(fixtures) >= 17, (
        f"expected at least 17 parser_*.tcl fixtures under {FIXTURES_DIR.as_posix()}, "
        f"found {len(fixtures)}. Has a fixture been deleted without updating "
        f"tests/FIXTURE_AUDIT.md?"
    )
