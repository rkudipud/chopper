"""Stage 4 rename: chopper_description.md -> ARCHITECTURE.md and sweep cross-refs.

Strategy:
- git mv the file.
- Section numbers (§N.M) inside the doc are preserved (no renumbering) so the
  ~10 src/ comment refs that cite specific anchors remain valid.
- Bulk rewrite of every reference across the workspace.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(r"c:\personal\projects\chopper")
OLD = "chopper_description.md"
NEW = "ARCHITECTURE.md"
OLD_PATH = ROOT / "technical_docs" / OLD
NEW_PATH = ROOT / "technical_docs" / NEW

# Files that reference chopper_description (collected via git grep).
FILES_TO_REWRITE = [
    ".github/agent_memory/chopper-buildout.md",
    ".github/agents/Thinking-Beast-Mode.agent.md",
    ".github/agents/chopper-buildout.agent.md",
    ".github/agents/chopper-stage-builder.agent.md",
    ".github/instructions/project.instructions.md",
    ".github/prompts/buildout-commands.md",
    "CONTRIBUTING.md",
    "README.md",
    "doc/TECHNICAL_GUIDE.md",
    "presentation/chopper_onboarding.html",
    "src/chopper/cli/commands.py",
    "src/chopper/core/context.py",
    "src/chopper/mcp/__init__.py",
    "src/chopper/mcp/server.py",
    "src/chopper/mcp/tools.py",
    "src/chopper/parser/service.py",
    "technical_docs/CLI_REFERENCE.md",
    "technical_docs/DIAGNOSTIC_CODES.md",
    "technical_docs/ENGINEERING.md",
    "technical_docs/IMPLEMENTATION.md",
    "tests/FIXTURE_CATALOG.md",
    "tests/fixtures/tracing_domain/ambiguous.tcl",
    "tests/property/test_determinism.py",
    "tests/unit/parser/test_service.py",
    "tools/assemble_implementation_doc.py",
    "tools/stage3_rename_engineering.py",
]


def run(*args: str, cwd: Path = ROOT) -> str:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return res.stdout


def rename_file() -> None:
    if NEW_PATH.exists():
        print(f"[skip] {NEW} already exists")
        return
    if not OLD_PATH.exists():
        raise SystemExit(f"[error] {OLD} not found")
    run(
        "git",
        "-C",
        str(ROOT),
        "mv",
        f"technical_docs/{OLD}",
        f"technical_docs/{NEW}",
    )
    print(f"[git mv] {OLD} -> {NEW}")


# Two patterns:
#   (1) Markdown link / inline path:    chopper_description.md
#   (2) Bare token mentions in prose:   chopper_description (no .md)
LINK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bchopper_description\.md\b"), "ARCHITECTURE.md"),
    # Bare-token mention only when not part of an identifier or path token
    (re.compile(r"\bchopper_description\b(?!\.md)"), "ARCHITECTURE"),
]


def rewrite_external_refs() -> None:
    for rel in FILES_TO_REWRITE:
        path = ROOT / rel
        if not path.exists():
            print(f"[skip] {rel} (missing)")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        original = text
        for pat, repl in LINK_PATTERNS:
            text = pat.sub(repl, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            print(f"[rewrite] {rel}")
        else:
            print(f"[noop] {rel}")


# Also rewrite intra-doc self-mentions so the new ARCHITECTURE.md doesn't
# advertise its own old name.
def rewrite_self() -> None:
    text = NEW_PATH.read_text(encoding="utf-8")
    original = text
    for pat, repl in LINK_PATTERNS:
        text = pat.sub(repl, text)
    if text != original:
        NEW_PATH.write_text(text, encoding="utf-8")
        print(f"[rewrite-self] {NEW}")


def main() -> None:
    rename_file()
    rewrite_self()
    rewrite_external_refs()


if __name__ == "__main__":
    main()
