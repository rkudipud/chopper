"""Source, tests, and technical docs stay ASCII-only.

Em dashes, arrows, and section signs pasted from spec text once shipped
inside ``src/`` to a CTH ward and rendered as mojibake there. The one
exemption is the fixture that exists to exercise the parser's Latin-1
decoding fallback.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUFFIXES = {".py", ".md", ".tcl", ".json", ".txt", ".csv", ".stack", ".commands"}
EXEMPT = {"tests/fixtures/edge_cases/parser_encoding_latin1_fallback.tcl"}


def _text_files() -> list[Path]:
    return sorted(
        path
        for top in ("src", "tests", "technical_docs")
        for path in (ROOT / top).rglob("*")
        if path.suffix in SUFFIXES
        and path.is_file()
        and not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(ROOT).parts)
        and path.relative_to(ROOT).as_posix() not in EXEMPT
    )


def test_tree_is_ascii_only() -> None:
    offenders = []
    for path in _text_files():
        for line_no, line in enumerate(path.read_bytes().splitlines(), 1):
            if any(byte > 127 for byte in line):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}")
    assert offenders == [], f"non-ASCII bytes: {offenders[:20]}"


def test_scan_covers_the_tree() -> None:
    scanned = {path.relative_to(ROOT).as_posix() for path in _text_files()}
    assert "src/chopper/orchestrator/runner.py" in scanned
    assert "technical_docs/ARCHITECTURE.md" in scanned
    assert not scanned & EXEMPT
