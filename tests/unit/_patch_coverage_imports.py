"""Post-redistribution patch: add common imports missing from fleet files.

The original ``test_coverage_98.py`` / ``test_coverage_99.py`` had a
shared preamble that imported ``pytest``, ``Path``, ``MagicMock`` /
``patch``, ``io``, ``sys`` etc.  Those imports were not captured as
"section imports" by the redistribution script because they lived
above the first section header.  This script appends a standard
imports block to every redistributed coverage file when those names
are referenced in the file body.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "tests" / "unit"

# Each entry: (regex-pattern in body text, import line to add if missing)
COMMON_IMPORTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpytest\."), "import pytest"),
    (re.compile(r"\bpytest\b"), "import pytest"),
    (re.compile(r"\bPath\("), "from pathlib import Path"),
    (re.compile(r"\bMagicMock\b"), "from unittest.mock import MagicMock"),
    (re.compile(r"\bpatch\("), "from unittest.mock import patch"),
    (re.compile(r"\bpatch\.object\b"), "from unittest.mock import patch"),
    (re.compile(r"\bio\.StringIO\b"), "import io"),
    (re.compile(r"\bio\.BytesIO\b"), "import io"),
    (re.compile(r"\bsys\.stdout\b"), "import sys"),
    (re.compile(r"\bsys\.modules\b"), "import sys"),
    (re.compile(r"\bsys\.stderr\b"), "import sys"),
    (re.compile(r"\bsys\.argv\b"), "import sys"),
    (re.compile(r"\bjson\.dumps\b"), "import json"),
    (re.compile(r"\bjson\.loads\b"), "import json"),
    (re.compile(r"\bjson\.load\b"), "import json"),
    (re.compile(r"\bjson\.dump\b"), "import json"),
    (re.compile(r"\bos\."), "import os"),
    (re.compile(r"\bMonkeyPatch\b"), "from _pytest.monkeypatch import MonkeyPatch"),
    (re.compile(r"\bInMemoryFS\b"), "from chopper.adapters.fs_memory import InMemoryFS"),
    (re.compile(r"\bChopperContext\b"), "from chopper.core.context import ChopperContext"),
    (re.compile(r"\bRunConfig\b"), "from chopper.core.context import RunConfig"),
    (re.compile(r"\bDiagnostic\b"), "from chopper.core.diagnostics import Diagnostic"),
    (re.compile(r"\bDiagnosticSummary\b"), "from chopper.core.diagnostics import DiagnosticSummary"),
    (re.compile(r"\bPhase\."), "from chopper.core.diagnostics import Phase"),
    (re.compile(r"\bSeverity\."), "from chopper.core.diagnostics import Severity"),
    (re.compile(r"\bsubprocess\."), "import subprocess"),
    (re.compile(r"\btempfile\."), "import tempfile"),
    (re.compile(r"\bdataclasses\."), "import dataclasses"),
    (re.compile(r"\bcontextlib\."), "import contextlib"),
    (re.compile(r"\btextwrap\."), "import textwrap"),
    (re.compile(r"\binspect\."), "import inspect"),
    (re.compile(r"\bre\.compile\b"), "import re"),
    (re.compile(r"\bre\.match\b"), "import re"),
    (re.compile(r"\bre\.search\b"), "import re"),
    (re.compile(r"\bdatetime\."), "import datetime"),
    (re.compile(r"\bsimple_namespace\b|\bSimpleNamespace\b"), "from types import SimpleNamespace"),
    (re.compile(r"\bargparse\.Namespace\b"), "import argparse"),
]


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "from tests.unit._coverage_helpers" not in text:
        return False
    lines = text.splitlines()

    # Locate import block end: between docstring/future import and the
    # _coverage_helpers import block.
    helpers_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("from tests.unit._coverage_helpers"):
            helpers_idx = i
            break
    if helpers_idx is None:
        return False

    body = "\n".join(lines[helpers_idx:])
    existing_imports = "\n".join(lines[:helpers_idx])

    needed: list[str] = []
    seen: set[str] = set()
    for pat, imp in COMMON_IMPORTS:
        if imp in seen:
            continue
        if imp in existing_imports:
            seen.add(imp)
            continue
        if pat.search(body):
            needed.append(imp)
            seen.add(imp)

    if not needed:
        return False

    # Insert needed imports right before the helpers import.
    new_lines = lines[:helpers_idx] + needed + ["", ""] + lines[helpers_idx:]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    patched = 0
    for p in sorted(UNIT_DIR.rglob("test_*_coverage.py")):
        if patch_file(p):
            patched += 1
    print(f"Patched imports in {patched} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
