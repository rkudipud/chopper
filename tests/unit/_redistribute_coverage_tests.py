"""One-shot redistribution script: dismantle test_coverage_98.py and
test_coverage_99.py into fleet-local test files under tests/unit/<fleet>/.

Strategy
========
1. Tokenize each omnibus file into "sections".  A section starts at the
   first ``# <header>`` line of an ``# --- ... ---`` comment block whose
   header names a source file (e.g. ``# core/fs_walk.py`` or
   ``# src/chopper/core/fs_walk.py``).  The section runs until the next
   such block (or EOF).

2. Each section's target source file determines the fleet directory
   (``parser/`` -> ``tests/unit/parser/``, etc.) and the fleet filename
   (``parser/proc_extractor.py`` -> ``tests/unit/parser/test_proc_extractor_coverage.py``).

3. Sections targeting the same source file across both omnibus files are
   concatenated into a single fleet file.  Each fleet file gets a small
   preamble:

       from __future__ import annotations
       <de-duplicated imports collected from contributing sections>
       from tests.unit._coverage_helpers import _Sink, _Progress, _ctx, _codes, DOMAIN, BACKUP, AUDIT

4. The original two files are deleted at the end.

5. After running, ``pytest tests/unit/`` must report the same number of
   passing tests and the same per-file coverage.

Run with:  ``python tests/unit/_redistribute_coverage_tests.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "tests" / "unit"

# Header pattern matches lines like:
#   # core/fs_walk.py ...
#   # src/chopper/core/fs_walk.py ...
#   # cli/commands.py  lines ...
HEADER_RE = re.compile(
    r"^#\s+(?:src/chopper/)?"
    r"(adapters|audit|cli|compiler|config|core|generators|orchestrator|parser|trimmer|validator)"
    r"/([a-z_][a-z0-9_]*)\.py\b"
)

# A "section divider" is a `# ----...----` line.  We treat any HEADER line
# that is immediately preceded (within the prior ~3 lines) by a divider
# as a true section start.  Inline `# parser/foo.py` comments inside a
# test body do not match because they aren't preceded by a divider.
DIVIDER_RE = re.compile(r"^#\s*-{10,}\s*$")

# Lines that look like `# ===...===` are top-level dividers in the 99
# file; treat them the same way.
TOP_DIVIDER_RE = re.compile(r"^#\s*={10,}\s*$")


def _split_into_sections(text: str) -> list[tuple[str, str, list[str]]]:
    """Yield ``(fleet, source_file_stem, body_lines)`` tuples.

    Body lines exclude the leading divider/header lines so the caller
    can prepend its own preamble.
    """
    lines = text.splitlines()
    sections: list[tuple[str, str, list[str]]] = []

    # Detect section starts.  A section starts when:
    #  - The current line matches HEADER_RE
    #  - AND it is preceded within the last 3 lines by a DIVIDER_RE or
    #    TOP_DIVIDER_RE line (this guards against comments inside
    #    test bodies that happen to mention a source path).
    i = 0
    n = len(lines)
    starts: list[tuple[int, str, str]] = []  # (line_idx, fleet, stem)
    while i < n:
        line = lines[i]
        m = HEADER_RE.match(line)
        if m:
            # Look back up to 4 lines for a divider; allow blank lines
            # between the divider and the header.
            ok = False
            for j in range(max(0, i - 4), i):
                if DIVIDER_RE.match(lines[j]) or TOP_DIVIDER_RE.match(lines[j]):
                    ok = True
                    break
            if ok:
                starts.append((i, m.group(1), m.group(2)))
        i += 1

    # Carve out body lines for each section.
    for k, (start_idx, fleet, stem) in enumerate(starts):
        end_idx = starts[k + 1][0] if k + 1 < len(starts) else n
        # Trim leading divider lines: walk back to the divider that
        # introduced this section so we DON'T include it in the body.
        # Likewise, the next section's leading divider is at end_idx-1
        # (or close to it), so we trim trailing dividers too.
        body_start = start_idx
        # consume the header line + its trailing divider/comment block
        # body_start moves PAST the header and any continuation comment
        # lines that start with `# ` until we hit the next divider or
        # blank line.
        body_start = start_idx + 1
        while body_start < end_idx and (
            lines[body_start].startswith("# ")
            or DIVIDER_RE.match(lines[body_start])
            or TOP_DIVIDER_RE.match(lines[body_start])
            or lines[body_start].strip() == ""
        ):
            # Stop as soon as we see actual code (def, import, from, etc.)
            stripped = lines[body_start].lstrip()
            if stripped.startswith(("def ", "import ", "from ", "@", "class ")):
                break
            body_start += 1

        # Walk back from end_idx to strip the next section's leading
        # divider block.
        body_end = end_idx
        while body_end > body_start and (
            DIVIDER_RE.match(lines[body_end - 1])
            or TOP_DIVIDER_RE.match(lines[body_end - 1])
            or lines[body_end - 1].strip() == ""
        ):
            body_end -= 1

        body = lines[body_start:body_end]
        sections.append((fleet, stem, body))

    return sections


def _collect_imports(body: list[str]) -> tuple[set[str], list[str]]:
    """Find module-level import statements in body lines.

    Returns ``(import_lines, rest)``.  Indented imports inside functions
    are left in place.
    """
    imports: set[str] = set()
    rest: list[str] = []
    for ln in body:
        # Module-level import: starts at column 0 with "import" or "from"
        if ln.startswith(("import ", "from ")) and not ln.startswith(("import_", "from_")):
            imports.add(ln.rstrip())
        else:
            rest.append(ln)
    return imports, rest


def _build_fleet_file(fleet: str, stem: str, contributions: list[list[str]]) -> str:
    """Render the final fleet test-file content."""

    all_imports: set[str] = set()
    bodies: list[str] = []
    for body in contributions:
        imps, rest = _collect_imports(body)
        all_imports |= imps
        # strip leading blank lines from rest
        while rest and rest[0].strip() == "":
            rest.pop(0)
        bodies.append("\n".join(rest).rstrip())

    # Filter out re-imports of helper names we'll provide via
    # ``_coverage_helpers``.
    filtered_imports: list[str] = []
    for imp in sorted(all_imports):
        # Drop imports that pull in the helpers we expose ourselves.
        if "chopper.adapters.fs_memory" in imp and "InMemoryFS" in imp:
            filtered_imports.append(imp)
        elif "chopper.core.context" in imp:
            filtered_imports.append(imp)
        elif "chopper.core.diagnostics" in imp:
            filtered_imports.append(imp)
        else:
            filtered_imports.append(imp)

    header = (
        f'"""Per-file coverage tests for src/chopper/{fleet}/{stem}.py.\n\n'
        "Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and\n"
        "``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``\n"
        "for shared fixtures.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
    )
    body_sep = "\n\n\n"
    imports_block = "\n".join(filtered_imports) + "\n\n"
    helpers_import = (
        "from tests.unit._coverage_helpers import (  # noqa: F401\n"
        "    AUDIT,\n"
        "    BACKUP,\n"
        "    DOMAIN,\n"
        "    _Progress,\n"
        "    _Sink,\n"
        "    _codes,\n"
        "    _ctx,\n"
        ")\n\n\n"
    )
    return header + imports_block + helpers_import + body_sep.join(bodies) + "\n"


def main() -> int:
    cov98 = UNIT_DIR / "test_coverage_98.py"
    cov99 = UNIT_DIR / "test_coverage_99.py"
    if not cov98.exists() and not cov99.exists():
        print("Both omnibus files already removed; nothing to do.", file=sys.stderr)
        return 0

    grouped: dict[tuple[str, str], list[list[str]]] = {}
    seen_test_names: set[str] = set()

    for src in [cov98, cov99]:
        if not src.exists():
            continue
        sections = _split_into_sections(src.read_text(encoding="utf-8"))
        for fleet, stem, body in sections:
            # Skip empty sections defensively.
            if not any(ln.strip() for ln in body):
                continue
            # Detect duplicate test names within a target stem and
            # rename collisions with a numeric suffix.
            renamed_body: list[str] = []
            for ln in body:
                m = re.match(r"^def (test_[a-zA-Z0-9_]+)\(", ln)
                if m:
                    name = m.group(1)
                    fq = f"{fleet}/{stem}::{name}"
                    if fq in seen_test_names:
                        suffix = 2
                        while f"{fleet}/{stem}::{name}_v{suffix}" in seen_test_names:
                            suffix += 1
                        new_name = f"{name}_v{suffix}"
                        seen_test_names.add(f"{fleet}/{stem}::{new_name}")
                        renamed_body.append(ln.replace(f"def {name}(", f"def {new_name}(", 1))
                    else:
                        seen_test_names.add(fq)
                        renamed_body.append(ln)
                else:
                    renamed_body.append(ln)
            grouped.setdefault((fleet, stem), []).append(renamed_body)

    # Make sure each fleet dir exists with an __init__.py.
    written: list[Path] = []
    for (fleet, stem), contribs in sorted(grouped.items()):
        fleet_dir = UNIT_DIR / fleet
        fleet_dir.mkdir(parents=True, exist_ok=True)
        init_py = fleet_dir / "__init__.py"
        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")
        # File name: test_<stem>_coverage.py to avoid colliding with
        # any existing fleet test file like test_<stem>.py.
        out_path = fleet_dir / f"test_{stem}_coverage.py"
        out_path.write_text(_build_fleet_file(fleet, stem, contribs), encoding="utf-8")
        written.append(out_path)

    # Remove the originals.
    for src in [cov98, cov99]:
        if src.exists():
            src.unlink()

    print(f"Wrote {len(written)} fleet files:")
    for p in written:
        print(f"  {p.relative_to(REPO_ROOT)}")
    print(f"Removed: {cov98.relative_to(REPO_ROOT)}, {cov99.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
