"""Rewrite cross-references to the four consolidated source docs.

After IMPLEMENTATION.md is generated, this script updates every external file that
references the old doc names (TCL_PARSER_SPEC.md, RISKS_AND_PITFALLS.md,
IMPLEMENTATION_DECISION_LOG.md, FUTURE_PLANNED_DEVELOPMENTS.md) so they point at
IMPLEMENTATION.md instead.

Skipped:
  - The four source files themselves (will be deleted by `git rm`)
  - This script and the assembly script
  - Generated IMPLEMENTATION.md (already has correct anchors)
  - Anything under .git/, .venv/, node_modules/, __pycache__/
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "technical_docs"

# §X.Y -> §1.X.Y mapping for parser-spec section anchors (longest-first)
PARSER_ANCHOR_MAP = {
    "§4.3.1": "§1.4.3.1",
    "§4.3.2": "§1.4.3.2",
    "§4.5.1": "§1.4.5.1",
    "§3.3.1": "§1.3.3.1",
    "§3.3.2": "§1.3.3.2",
    "§5.3.0.1": "§1.5.3.1",
    "§5.3.0.2": "§1.5.3.2",
    "§5.3.1": "§1.5.4",
    "§5.4.1": "§1.5.6",
    "§8.5.1": "§1.8.5.1",
    "§8.5.2": "§1.8.5.2",
    "§8.5.3": "§1.8.5.3",
    "§3.0": "§1.3.0",
    "§3.1": "§1.3.1",
    "§3.2": "§1.3.2",
    "§3.3": "§1.3.3",
    "§3.4": "§1.3.4",
    "§3.5": "§1.3.5",
    "§4.1": "§1.4.1",
    "§4.2": "§1.4.2",
    "§4.3": "§1.4.3",
    "§4.4": "§1.4.4",
    "§4.5": "§1.4.5",
    "§4.6": "§1.4.6",
    "§4.7": "§1.4.7",
    "§5.1": "§1.5.1",
    "§5.2": "§1.5.2",
    "§5.3": "§1.5.3",
    "§5.4": "§1.5.5",
    "§5.5": "§1.5.7",
    "§6.1": "§1.6.1",
    "§6.2": "§1.6.2",
    "§6.3": "§1.6.3",
    "§7.14": "§1.7.14",
    "§8.1": "§1.8.1",
    "§8.2": "§1.8.2",
    "§8.3": "§1.8.3",
    "§8.4": "§1.8.4",
    "§8.5": "§1.8.5",
    "§9.1": "§1.9.1",
    "§9.2": "§1.9.2",
    # Single-digit (catch last so prefix-match fail is acceptable; only apply when
    # very near a parser-spec mention via the parser_anchor_lines logic below)
    "§2.1": "§1.2.1",
    "§2": "§1.2",
    "§3": "§1.3",
    "§4": "§1.4",
    "§5": "§1.5",
    "§6": "§1.6",
    "§7": "§1.7",
    "§8": "§1.8",
    "§9": "§1.9",
}

# Files / dirs to skip
SKIP_FILES = {
    "technical_docs/TCL_PARSER_SPEC.md",
    "technical_docs/RISKS_AND_PITFALLS.md",
    "technical_docs/IMPLEMENTATION_DECISION_LOG.md",
    "technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md",
    "technical_docs/IMPLEMENTATION.md",
    "tools/assemble_implementation_doc.py",
    "tools/rewrite_consolidation_refs.py",
}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "chopper.egg-info", "dom"}


def is_skipped(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & SKIP_DIRS:
        return True
    if str(rel).replace("\\", "/") in SKIP_FILES:
        return True
    return False


def rewrite_text(text: str) -> tuple[str, int]:
    """Return (new_text, num_changes)."""
    original = text

    # 1) Markdown link forms: [text](path) — rewrite path side.
    #    Keep the link text intact (it usually says something like "RISKS_AND_PITFALLS.md")
    #    so readers can still see the historical name; only the target gets retargeted.
    link_target_patterns = [
        # ../../technical_docs/X.md, ../technical_docs/X.md, technical_docs/X.md, X.md
        (r"(\]\(\.\./\.\./technical_docs/)TCL_PARSER_SPEC\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./technical_docs/)TCL_PARSER_SPEC\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(technical_docs/)TCL_PARSER_SPEC\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\()TCL_PARSER_SPEC\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./\.\./technical_docs/)RISKS_AND_PITFALLS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./technical_docs/)RISKS_AND_PITFALLS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(technical_docs/)RISKS_AND_PITFALLS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\()RISKS_AND_PITFALLS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./\.\./technical_docs/)IMPLEMENTATION_DECISION_LOG\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./technical_docs/)IMPLEMENTATION_DECISION_LOG\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(technical_docs/)IMPLEMENTATION_DECISION_LOG\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\()IMPLEMENTATION_DECISION_LOG\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./\.\./technical_docs/)FUTURE_PLANNED_DEVELOPMENTS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(\.\./technical_docs/)FUTURE_PLANNED_DEVELOPMENTS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\(technical_docs/)FUTURE_PLANNED_DEVELOPMENTS\.md(\))", r"\1IMPLEMENTATION.md\2"),
        (r"(\]\()FUTURE_PLANNED_DEVELOPMENTS\.md(\))", r"\1IMPLEMENTATION.md\2"),
    ]
    for pat, sub in link_target_patterns:
        text = re.sub(pat, sub, text)

    # 2) Plain mentions in prose / code comments / docstrings.
    #    These use bare filenames without markdown links.
    plain_subs = [
        # Inline-code `technical_docs/X.md` and `X.md`
        (r"`technical_docs/TCL_PARSER_SPEC\.md`", "`technical_docs/IMPLEMENTATION.md` (parser section)"),
        (r"`TCL_PARSER_SPEC\.md`", "`technical_docs/IMPLEMENTATION.md` (parser section)"),
        (r"`technical_docs/RISKS_AND_PITFALLS\.md`", "`technical_docs/IMPLEMENTATION.md` (pitfalls)"),
        (r"`RISKS_AND_PITFALLS\.md`", "`technical_docs/IMPLEMENTATION.md` (pitfalls)"),
        (r"`technical_docs/IMPLEMENTATION_DECISION_LOG\.md`", "`technical_docs/IMPLEMENTATION.md` (parser decisions)"),
        (r"`IMPLEMENTATION_DECISION_LOG\.md`", "`technical_docs/IMPLEMENTATION.md` (parser decisions)"),
        (r"`technical_docs/FUTURE_PLANNED_DEVELOPMENTS\.md`", "`technical_docs/IMPLEMENTATION.md` Appendix B"),
        (r"`FUTURE_PLANNED_DEVELOPMENTS\.md`", "`technical_docs/IMPLEMENTATION.md` Appendix B"),
        # Bare filename mentions (no backticks, no markdown link)
        (r"\btechnical_docs/TCL_PARSER_SPEC\.md\b", "technical_docs/IMPLEMENTATION.md (parser section)"),
        (r"\bTCL_PARSER_SPEC\.md\b", "IMPLEMENTATION.md (parser section)"),
        (r"\btechnical_docs/RISKS_AND_PITFALLS\.md\b", "technical_docs/IMPLEMENTATION.md (pitfalls)"),
        (r"\bRISKS_AND_PITFALLS\.md\b", "IMPLEMENTATION.md (pitfalls)"),
        (r"\btechnical_docs/IMPLEMENTATION_DECISION_LOG\.md\b", "technical_docs/IMPLEMENTATION.md (parser decisions)"),
        (r"\bIMPLEMENTATION_DECISION_LOG\.md\b", "IMPLEMENTATION.md (parser decisions)"),
        (r"\btechnical_docs/FUTURE_PLANNED_DEVELOPMENTS\.md\b", "technical_docs/IMPLEMENTATION.md Appendix B"),
        (r"\bFUTURE_PLANNED_DEVELOPMENTS\.md\b", "IMPLEMENTATION.md Appendix B"),
    ]
    for pat, sub in plain_subs:
        text = re.sub(pat, sub, text)

    # 3) Update parser-section anchors near a parser mention.
    #    Apply ONLY to lines that mention the parser doc in the original text;
    #    otherwise §X.Y references in architecture-doc context get clobbered.
    parser_keywords = (
        "TCL_PARSER_SPEC", "IMPLEMENTATION.md (parser",
        "parser section", "parser decisions",
    )
    new_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if any(kw in line for kw in parser_keywords):
            for old in sorted(PARSER_ANCHOR_MAP, key=len, reverse=True):
                line = line.replace(old, PARSER_ANCHOR_MAP[old])
        new_lines.append(line)
    text = "".join(new_lines)

    return text, sum(1 for a, b in zip(original, text) if a != b)


def main() -> None:
    changed: list[tuple[str, int]] = []
    skipped: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if is_skipped(rel):
            continue
        # Only process text-y extensions
        if path.suffix.lower() not in {".md", ".py", ".tcl", ".json", ".yaml", ".yml", ".txt", ".html", ".cfg", ".ini", ".toml"}:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(str(rel))
            continue
        # Quick filter: only touch files that actually mention any of the four names
        if not any(name in original for name in (
            "TCL_PARSER_SPEC", "RISKS_AND_PITFALLS",
            "IMPLEMENTATION_DECISION_LOG", "FUTURE_PLANNED_DEVELOPMENTS",
        )):
            continue
        new_text, _ = rewrite_text(original)
        if new_text != original:
            path.write_text(new_text, encoding="utf-8")
            changed.append((str(rel), len(new_text) - len(original)))

    print(f"Changed {len(changed)} files:")
    for rel, delta in sorted(changed):
        print(f"  {rel:60s}  ({delta:+d} bytes)")
    if skipped:
        print(f"\nSkipped {len(skipped)} non-utf8 files")


if __name__ == "__main__":
    main()
