"""Stage 3 rename: ARCHITECTURE_PLAN.md -> ENGINEERING.md and align §16 with scope-lock.

Run from anywhere. Uses git mv for the rename, in-place rewrites for cross-refs and
the §16 Q1 narrowed-MCP fold-in.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(r"c:\personal\projects\chopper")
OLD = "ARCHITECTURE_PLAN.md"
NEW = "ENGINEERING.md"
OLD_PATH = ROOT / "technical_docs" / OLD
NEW_PATH = ROOT / "technical_docs" / NEW

FILES_TO_REWRITE = [
    ".github/agents/chopper-buildout.agent.md",
    ".github/agents/chopper-stage-builder.agent.md",
    ".github/instructions/project.instructions.md",
    ".github/prompts/buildout-commands.md",
    "CONTRIBUTING.md",
    "README.md",
    "doc/TECHNICAL_GUIDE.md",
    "pyproject.toml",
    "schemas/diagnostic-v1.schema.json",
    "schemas/progress-event-v1.schema.json",
    "schemas/run-result-v1.schema.json",
    "schemas/scripts/check_service_signatures.py",
    "technical_docs/DIAGNOSTIC_CODES.md",
    "technical_docs/IMPLEMENTATION.md",
    "technical_docs/ARCHITECTURE.md",
]


def run(*args: str, cwd: Path = ROOT) -> str:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return res.stdout


# ---------------------------------------------------------------------------
# Step 1: git mv
# ---------------------------------------------------------------------------
def rename_file() -> None:
    if NEW_PATH.exists():
        print(f"[skip] {NEW} already exists")
        return
    if not OLD_PATH.exists():
        raise SystemExit(f"[error] {OLD} not found")
    run("git", "-C", str(ROOT), "mv", f"technical_docs/{OLD}", f"technical_docs/{NEW}")
    print(f"[git mv] {OLD} -> {NEW}")


# ---------------------------------------------------------------------------
# Step 2: rewrite in-doc title and §16 Q1 narrowed MCP fold-in
# ---------------------------------------------------------------------------
def rewrite_engineering_doc() -> None:
    text = NEW_PATH.read_text(encoding="utf-8")
    original = text

    # Title: "Chopper — Modular Service Architecture Plan" -> "Chopper — Engineering Plan"
    text = text.replace(
        "# Chopper — Modular Service Architecture Plan",
        "# Chopper — Engineering Plan",
    )

    # Internal self-reference: "this plan" wording is fine; but the §16 Q1 MCP
    # paragraph is stale. Replace the entire Q1 block with a version that
    # acknowledges the narrowed read-only stdio MCP closure (per
    # `.github/instructions/project.instructions.md` §1.1 and architecture doc §3.8).
    old_q1 = (
        "### Q1 — Plugin host / MCP / AI advisor (CLOSED — permanently out of scope)\n"
        "\n"
        "**Chopper has no plugin system, no MCP driver, no AI advisor, and no reserved extension seams.** "
        "There is no `PluginHost`, no `X*` diagnostic family, no `plugins/`, `mcp_server/`, or `advisor/` module, "
        'and no "stage 6" on the roadmap for any of these. Previous drafts reserved these concepts '
        '"for future use"; that reservation is now withdrawn.\n'
        "\n"
        "**Rationale.** Reserving extension points that nobody is committed to building invites drift: "
        'an agent reading "reserved" treats it as "TODO", a contributor fills in the TODO, and a '
        "surface the project never approved ships. The cost of *not* reserving is near zero — if a future "
        "release ever genuinely needs a plugin mechanism, it will start with a fresh design doc "
        "(updating [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) first) rather than "
        "resurrecting stubs from this plan. PRs that add plugin / MCP / advisor scaffolding are rejected at review.\n"
    )
    new_q1 = (
        "### Q1 — Plugin host / AI advisor / destructive MCP (CLOSED) — read-only stdio MCP (NARROWED)\n"
        "\n"
        "**Closed permanently.** Chopper has no plugin system, no AI advisor, and no reserved "
        "extension seams. There is no `PluginHost`, no `X*` diagnostic family, no `plugins/` or "
        '`advisor/` module, and no "stage 6" on the roadmap for any of these. Previous drafts '
        'reserved these concepts "for future use"; that reservation is withdrawn. PRs that add '
        "plugin or advisor scaffolding are rejected at review.\n"
        "\n"
        "**Closed permanently — destructive MCP surface.** No `MCPDiagnosticSink`, no "
        "`MCPProgressBridge`, no `adapters/mcp_*.py`, no MCP client code inside Chopper, no "
        "HTTP/TCP/WebSocket MCP transports, no MCP tool exposing `chopper.trim` or "
        "`chopper.cleanup`, no MCP-driven filesystem mutation.\n"
        "\n"
        "**Narrowed (permitted) — read-only stdio MCP.** The `chopper mcp-serve` subcommand and "
        "the `src/chopper/mcp/` package are permitted: a stdio-only JSON-RPC server (no TCP, no "
        "HTTP, no WebSocket, no daemon) exposing read-only tools "
        "(`chopper.validate`, `chopper.explain_diagnostic`, `chopper.read_audit`). Specified in the "
        "architecture doc at [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) §3.8; "
        "the canonical scope-lock list lives in "
        "[`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) §1.1.\n"
        "\n"
        "**Rationale.** Reserving open-ended extension points (plugins, advisors, destructive MCP) "
        'invites drift: an agent reading "reserved" treats it as "TODO", a contributor fills in '
        "the TODO, and a surface the project never approved ships. The narrowed read-only MCP, by "
        "contrast, is a concrete, bounded surface with a fixed tool list and a single transport — "
        "the open-ended scope was the problem, not MCP itself.\n"
    )
    if old_q1 not in text:
        raise SystemExit("[error] Q1 anchor block not found verbatim — manual review required")
    text = text.replace(old_q1, new_q1)

    if text != original:
        NEW_PATH.write_text(text, encoding="utf-8")
        print(f"[rewrite] {NEW} (title + §16 Q1 fold-in)")
    else:
        print(f"[noop] {NEW} unchanged")


# ---------------------------------------------------------------------------
# Step 3: bulk rewrite all cross-refs across the workspace
# ---------------------------------------------------------------------------
LINK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Markdown links: [text](path/ARCHITECTURE_PLAN.md...)
    (re.compile(r"\]\(([^)]*?)ARCHITECTURE_PLAN\.md"), r"](\1ENGINEERING.md"),
    # Bare path mentions in prose
    (re.compile(r"`([^`]*?)ARCHITECTURE_PLAN\.md`"), r"`\1ENGINEERING.md`"),
    # Plain "ARCHITECTURE_PLAN.md" without backticks/parens
    (re.compile(r"\bARCHITECTURE_PLAN\.md\b"), "ENGINEERING.md"),
]


def rewrite_external_refs() -> None:
    for rel in FILES_TO_REWRITE:
        path = ROOT / rel
        if not path.exists():
            print(f"[skip] {rel} (missing)")
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for pat, repl in LINK_PATTERNS:
            text = pat.sub(repl, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            print(f"[rewrite] {rel}")
        else:
            print(f"[noop] {rel}")


# ---------------------------------------------------------------------------
def main() -> None:
    rename_file()
    rewrite_engineering_doc()
    rewrite_external_refs()


if __name__ == "__main__":
    main()
