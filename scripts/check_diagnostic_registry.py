"""Fail CI if any ``Diagnostic(code="XX-NN")`` literal in ``src/chopper/``
references a code that is not an Active row in ``technical_docs/DIAGNOSTIC_CODES.md``.

This is the doc↔code single-source-of-truth gate described in
``technical_docs/FINAL_HANDOFF_REVIEW.md`` PR-4. Agents that invent new diagnostic codes
without registering them in the architecture doc registry fail this check.

The script is intentionally tiny and dependency-free so it can run in the
earliest CI stages before the project itself is importable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "technical_docs" / "DIAGNOSTIC_CODES.md"
SOURCE_ROOT = ROOT / "src" / "chopper"

# Matches VE-06, PW-11, TW-02, etc. The two-letter family + severity letter
# pattern is fixed by technical_docs/DIAGNOSTIC_CODES.md §Naming Convention.
CODE_RE = re.compile(r"\b([VTP][EWI]-\d{2})\b")

# Matches registry rows of the shape "| VE-06 | `slug` | ..." — active rows
# only; RETIRED rows have a different cell pattern and must be ignored.
REGISTRY_ROW_RE = re.compile(r"^\|\s*([VTP][EWI]-\d{2})\s*\|\s*`[^`]+`")


def load_active_codes() -> set[str]:
    """Return the set of diagnostic codes registered as Active in the architecture doc."""
    if not REGISTRY.is_file():
        print(f"ERROR: registry not found: {REGISTRY}", file=sys.stderr)
        sys.exit(2)
    codes: set[str] = set()
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        match = REGISTRY_ROW_RE.match(line)
        if match:
            codes.add(match.group(1))
    return codes


def collect_code_references() -> dict[str, list[tuple[Path, int]]]:
    """Find every ``Diagnostic(code="XX-NN")`` reference under src/chopper/."""
    refs: dict[str, list[tuple[Path, int]]] = {}
    if not SOURCE_ROOT.is_dir():
        # Source tree not yet materialised — nothing to check.
        return refs
    for py_file in SOURCE_ROOT.rglob("*.py"):
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            # Only consider lines that look like they construct a Diagnostic
            # or explicitly reference a `code=` kwarg; avoids matching
            # documentation examples or unrelated identifiers.
            if "Diagnostic(" not in line and "code=" not in line:
                continue
            for code in CODE_RE.findall(line):
                refs.setdefault(code, []).append((py_file, lineno))
    return refs


def main() -> int:
    active = load_active_codes()
    refs = collect_code_references()
    unknown = {code: sites for code, sites in refs.items() if code not in active}
    if not unknown:
        print(f"OK: {len(refs)} code references; all registered in DIAGNOSTIC_CODES.md")
        return 0
    print("ERROR: unregistered diagnostic codes in source:", file=sys.stderr)
    for code in sorted(unknown):
        print(f"  {code}", file=sys.stderr)
        for path, line in unknown[code]:
            rel = path.relative_to(ROOT)
            print(f"    {rel}:{line}", file=sys.stderr)
    print(
        "\nRegister the code in technical_docs/DIAGNOSTIC_CODES.md (see "
        ".github/instructions/project.instructions.md §Diagnostic Codes) "
        "before using it in source.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
