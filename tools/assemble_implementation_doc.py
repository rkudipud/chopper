"""Assemble technical_docs/IMPLEMENTATION.md from four source documents.

Stage-2 of the doc consolidation. Merges:
  - TCL_PARSER_SPEC.md            -> Section 1 (Parser)
  - IMPLEMENTATION_DECISION_LOG.md -> inlined as "Decision: ..." callouts in section 1
  - RISKS_AND_PITFALLS.md          -> per-module pitfalls + Section 12 quick-ref
  - FUTURE_PLANNED_DEVELOPMENTS.md -> Appendices A (OOS) and B (FD)

This is a one-shot transformation; running it again on the consolidated file would
fail because the source files no longer exist. Kept under tools/ for git history.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "technical_docs"

PARSER = (DOCS / "TCL_PARSER_SPEC.md").read_text(encoding="utf-8")
RISKS = (DOCS / "RISKS_AND_PITFALLS.md").read_text(encoding="utf-8")
DLOG = (DOCS / "IMPLEMENTATION_DECISION_LOG.md").read_text(encoding="utf-8")
FUTURE = (DOCS / "FUTURE_PLANNED_DEVELOPMENTS.md").read_text(encoding="utf-8")


def slice_between(text: str, start_marker: str, end_marker: str | None) -> str:
    """Return the substring starting at start_marker up to (but not including) end_marker.

    If end_marker is None, returns to end of string. Raises if start_marker missing.
    """
    s_idx = text.find(start_marker)
    if s_idx < 0:
        raise ValueError(f"start_marker not found: {start_marker[:80]!r}")
    if end_marker is None:
        return text[s_idx:]
    e_idx = text.find(end_marker, s_idx + len(start_marker))
    if e_idx < 0:
        raise ValueError(f"end_marker not found after start: {end_marker[:80]!r}")
    return text[s_idx:e_idx]


# ---------------------------------------------------------------------------
# Extract reusable blocks from sources
# ---------------------------------------------------------------------------

# Parser body (skip the original H1 + Purpose; we re-introduce them at section 1)
parser_purpose = slice_between(PARSER, "## 1. Purpose", "## 2. Input Contract")
parser_input = slice_between(PARSER, "## 2. Input Contract", "## 3. Tokenization Rules")
parser_tokenization = slice_between(PARSER, "## 3. Tokenization Rules", "## 4. Proc Detection")
parser_proc_detection = slice_between(PARSER, "## 4. Proc Detection", "## 5. Call Extraction (For Tracing)")
parser_call_extraction = slice_between(PARSER, "## 5. Call Extraction (For Tracing)", "## 6. Output: Proc Index Entry")
parser_output = slice_between(PARSER, "## 6. Output: Proc Index Entry", "## 7. Edge Cases and Adversarial Inputs")
parser_edge_cases = slice_between(PARSER, "## 7. Edge Cases and Adversarial Inputs", "## 8. Parser Architecture")
parser_architecture = slice_between(PARSER, "## 8. Parser Architecture", "## 9. Test Strategy")
parser_test_strategy = slice_between(PARSER, "## 9. Test Strategy", "## 10. References")
parser_references = slice_between(PARSER, "## 10. References", "## 11. Revision History")

# Risks per-module
risks_overview = slice_between(RISKS, "## Overview", "## PARSER MODULE")
risks_parser = slice_between(RISKS, "## PARSER MODULE", "## COMPILER MODULE")
risks_compiler = slice_between(RISKS, "## COMPILER MODULE", "## TRIMMER MODULE")
risks_trimmer = slice_between(RISKS, "## TRIMMER MODULE", "## VALIDATOR MODULE")
risks_validator = slice_between(RISKS, "## VALIDATOR MODULE", "## AUDIT & DIAGNOSTICS")
risks_audit = slice_between(RISKS, "## AUDIT & DIAGNOSTICS", "## BACKUP & RECOVERY")
risks_backup = slice_between(RISKS, "## BACKUP & RECOVERY", "## CONFIGURATION & PATHS")
risks_config = slice_between(RISKS, "## CONFIGURATION & PATHS", "## CLI & PRESENTATION")
risks_cli = slice_between(RISKS, "## CLI & PRESENTATION", "## HOOK FILES")
risks_hooks = slice_between(RISKS, "## HOOK FILES", "## PROJECT JSON")
risks_project = slice_between(RISKS, "## PROJECT JSON", "## TESTING STRATEGY")
risks_testing = slice_between(RISKS, "## TESTING STRATEGY", "## Quick Reference: Common Mistakes by Module")
risks_quickref = slice_between(
    RISKS, "## Quick Reference: Common Mistakes by Module", "## STANDALONE RISK ITEMS"
)
risks_standalone = slice_between(RISKS, "## STANDALONE RISK ITEMS", "## PROCESS ANALYSIS")

# Decision log entries (parser only — all D-xx are stage 1b/1c/1d/1e)
dlog_1b = slice_between(DLOG, "## Stage 1b — Tokenizer", "## Stage 1c — NamespaceTracker")
dlog_1c = slice_between(DLOG, "## Stage 1c — NamespaceTracker", "## Stage 1d — ProcExtractor")
dlog_1d = slice_between(DLOG, "## Stage 1d — ProcExtractor", "## Stage 1e — CallExtractor")
dlog_1e = slice_between(DLOG, "## Stage 1e — CallExtractor", None)
# Strip the trailing horizontal rule from dlog_1e if present
dlog_1e = dlog_1e.rstrip().rstrip("-").rstrip()

# Future doc — OOS table and FD-xx entries
oos_block = slice_between(FUTURE, "## Permanently Out of Scope", "## Parser Enhancements")
fd_parser = slice_between(FUTURE, "## Parser Enhancements", "## Compiler / Pipeline Enhancements")
fd_compiler = slice_between(FUTURE, "## Compiler / Pipeline Enhancements", "## CLI / UX Enhancements")
fd_cliux = slice_between(FUTURE, "## CLI / UX Enhancements", "## Documentation Enhancements")
fd_docs = slice_between(FUTURE, "## Documentation Enhancements", "## Summary")
fd_summary = slice_between(FUTURE, "## Summary", None)


# ---------------------------------------------------------------------------
# Helper: rewrite intra-doc cross-references to point at the new layout
# ---------------------------------------------------------------------------

def rewrite_internal_links(text: str) -> str:
    """Strip references to TCL_PARSER_SPEC, RISKS_AND_PITFALLS, IMPLEMENTATION_DECISION_LOG.

    These are now inlined sections of IMPLEMENTATION.md, so cross-doc links should
    become intra-doc references. We change "[`technical_docs/TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §X.Y"
    style markers into "this doc §X.Y" wording. Blunt but safe.
    """
    # Drop "[file.md](file.md)" style links to consolidated docs
    repls = [
        (r"\[`?technical_docs/TCL_PARSER_SPEC\.md`?\]\(\.\./?technical_docs/TCL_PARSER_SPEC\.md\)", "this doc"),
        (r"\[`?TCL_PARSER_SPEC\.md`?\]\(TCL_PARSER_SPEC\.md\)", "this doc"),
        (r"`technical_docs/TCL_PARSER_SPEC\.md`", "this doc"),
        (r"\bTCL_PARSER_SPEC\.md\b", "this doc (parser section)"),
        (r"\[`?technical_docs/RISKS_AND_PITFALLS\.md`?\]\([^)]+\)", "this doc"),
        (r"\[`?RISKS_AND_PITFALLS\.md`?\]\(RISKS_AND_PITFALLS\.md\)", "this doc"),
        (r"`RISKS_AND_PITFALLS\.md`", "this doc"),
        (r"\bRISKS_AND_PITFALLS\.md\b", "this doc (pitfalls section)"),
        (r"\[`?technical_docs/IMPLEMENTATION_DECISION_LOG\.md`?\]\([^)]+\)", "this doc"),
        (r"\[`?IMPLEMENTATION_DECISION_LOG\.md`?\]\(IMPLEMENTATION_DECISION_LOG\.md\)", "this doc"),
        (r"\bIMPLEMENTATION_DECISION_LOG\.md\b", "this doc (parser decisions)"),
        (r"\[`?technical_docs/FUTURE_PLANNED_DEVELOPMENTS\.md`?\]\([^)]+\)", "this doc Appendix B"),
        (r"\bFUTURE_PLANNED_DEVELOPMENTS\.md\b", "this doc Appendix B"),
    ]
    for pat, sub in repls:
        text = re.sub(pat, sub, text)
    # chopper_description.md is renamed in stage 4; for now keep links pointing at it
    return text


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------

HEADER = """# Chopper — Implementation Reference

> **Scope.** Per-module engineering specifications, implementation pitfalls, and the recorded design decisions that shaped both. This document is the working reference for engineers writing or modifying any of Chopper's services. The architecture doc ([chopper_description.md](chopper_description.md)) defines the system contract; this doc describes how each module honors that contract in code.

> **What changed in this consolidation.** This file replaces four previous docs that drifted apart over time:
>
> - The Tcl parser engineering spec
> - The technical-risks and implementation-pitfalls ledger (P-01 … P-44 + TC-01 … TC-10)
> - The parser implementation decision log (D-1b-01 … D-1e-03)
> - The future-planned-developments ledger (OOS-01 … OOS-04 + FD-01 … FD-13)
>
> All content is preserved, but it is now organised **by module** rather than by document type, so the spec for a behaviour, the pitfalls that motivated it, and the decisions taken when implementing it sit next to each other. References that previously pointed at one of the four sources have been rewritten to point at the corresponding section of this doc.

## Contents

1. [Parser Module](#1-parser-module) — Tcl parser engineering spec, parser pitfalls (P-01 … P-07, P-32 … P-43), and parser decisions (D-1b-01 … D-1e-03)
2. [Compiler & Tracer Module](#2-compiler--tracer-module) — Merge algorithm and trace expansion (P-08 … P-12, P-41, P-42)
3. [Trimmer Module](#3-trimmer-module) — Backup / rebuild / write contract (P-13, P-15, P-37, P-44)
4. [Validator Module](#4-validator-module) — Pre/post-trim integrity checks (P-16, P-17)
5. [Audit & Diagnostics](#5-audit--diagnostics) — Diagnostic emission and audit-bundle invariants (P-18, P-19)
6. [Backup & Recovery](#6-backup--recovery) — Re-trim semantics (P-20)
7. [Configuration & Paths](#7-configuration--paths) — Path normalization, config-file resolution (P-21, P-22)
8. [CLI & Presentation](#8-cli--presentation) — Dry-run, project JSON path resolution, mutually-exclusive flags, --strict, cleanup (P-23, P-25, P-26, P-27, P-28)
9. [Hook Files](#9-hook-files) — `-use_hooks` discovery-only contract (P-29)
10. [Project JSON](#10-project-json) — Project-mode metadata flow and domain consistency (P-30, P-31)
11. [Testing Strategy](#11-testing-strategy) — Stage gating and edge-case timing (P-24)
12. [Quick Reference](#12-quick-reference-common-mistakes-by-module) — One-table-per-mistake summary
13. [Standalone Risk Items](#13-standalone-risk-items) — TC-06, TC-09 (no dedicated pitfall)
- [Appendix A: Out of Scope (OOS-01 … OOS-04)](#appendix-a-permanently-out-of-scope)
- [Appendix B: Deferred Work (FD-01 … FD-13)](#appendix-b-deferred-work-items)

---

"""

# Parser section: keep the spec's original structure but renumber as 1.X and inline
# the four parser decision-log stages at the right insertion points.

PARSER_INTRO = """## 1. Parser Module

The parser is the foundation of F2 (proc-level trimming) and transitive tracing. Every rule in this section is derived from the Tcl 8.6 Dodekalogue (the twelve rules that define Tcl syntax and semantics) and adapted for Chopper's static analysis context.

The architecture doc [chopper_description.md](chopper_description.md) §5.4 fixes the parser's role in the pipeline (P2). This section is the engineering specification: tokenization rules, proc-detection algorithm, call-extraction rules, the `ProcEntry` output shape, edge cases, the test-fixture catalog, and the design decisions taken during implementation.

**Risk statements covered by this section.**

> **TC-01 — Tcl Proc Boundary Detection.** Chopper must correctly find proc boundaries even with nested braces and namespace constructs. Without a reliable parser, F2 (proc-level trimming) is not viable.
>
> **TC-02 — Canonical Proc Naming.** Resolved to **file + proc name** with namespace-qualified synthesis. Canonical form: `file.tcl::proc_name`. Incorrect canonicalization breaks JSON stability and traceability. JSON authoring uses the short proc name; Chopper resolves the canonical form internally.

---

"""

# Renumber parser sub-sections to use 1.X
def renumber_parser(text: str) -> str:
    repls = [
        ("## 1. Purpose", "### 1.1 Purpose"),
        ("## 2. Input Contract", "### 1.2 Input Contract"),
        ("### 2.1 Public Function Signature", "#### 1.2.1 Public Function Signature"),
        ("### 2.1.1 Return-Value Contract on Diagnostics (D4)", "#### 1.2.2 Return-Value Contract on Diagnostics"),
        ("## 3. Tokenization Rules", "### 1.3 Tokenization Rules"),
        ("### 3.0 State-Machine Summary (D2)", "#### 1.3.0 State-Machine Summary"),
        ("### 3.1 Brace Matching (Tcl Rule 6)", "#### 1.3.1 Brace Matching (Tcl Rule 6)"),
        ("### 3.2 Backslash Continuation (Tcl Rule 9)", "#### 1.3.2 Backslash Continuation (Tcl Rule 9)"),
        ("### 3.3 Double Quotes (Tcl Endekas/Dodekalogue Rule 5)", "#### 1.3.3 Double Quotes (Tcl Endekas/Dodekalogue Rule 5)"),
        ("#### 3.3.1 Pre-Body Quote Rule (Outside Brace-Delimited Blocks)", "##### 1.3.3.1 Pre-Body Quote Rule (Outside Brace-Delimited Blocks)"),
        ("#### 3.3.2 In-Body Rule (Inside Brace-Delimited Blocks)", "##### 1.3.3.2 In-Body Rule (Inside Brace-Delimited Blocks)"),
        ("### 3.4 Comments (Tcl Rule 10)", "#### 1.3.4 Comments (Tcl Rule 10)"),
        ("### 3.5 Command Substitution (`[...]`) (Tcl Rule 7)", "#### 1.3.5 Command Substitution (`[...]`) (Tcl Rule 7)"),
        ("## 4. Proc Detection", "### 1.4 Proc Detection"),
        ("### 4.1 Proc Definition Pattern", "#### 1.4.1 Proc Definition Pattern"),
        ("### 4.2 Detection Algorithm", "#### 1.4.2 Detection Algorithm"),
        ("### 4.3 Proc Name Resolution", "#### 1.4.3 Proc Name Resolution"),
        ("#### 4.3.1 Canonical-Name Test Vectors (D3)", "##### 1.4.3.1 Canonical-Name Test Vectors"),
        ("#### 4.3.2 Source / `iproc_source` Edges (E2)", "##### 1.4.3.2 Source / `iproc_source` Edges"),
        ("### 4.4 Where Procs Are Recognized", "#### 1.4.4 Where Procs Are Recognized"),
        ("### 4.5 Namespace Eval Detection", "#### 1.4.5 Namespace Eval Detection"),
        ("#### 4.5.1 Namespace Stack Pop Timing — Worked Example", "##### 1.4.5.1 Namespace Stack Pop Timing — Worked Example"),
        ("### 4.6 define_proc_attributes (DPA) Detection", "#### 1.4.6 define_proc_attributes (DPA) Detection"),
        ("### 4.7 Structured Doc-Comment Block Detection", "#### 1.4.7 Structured Doc-Comment Block Detection"),
        ("## 5. Call Extraction (For Tracing)", "### 1.5 Call Extraction (For Tracing)"),
        ("### 5.1 What Chopper Extracts", "#### 1.5.1 What Chopper Extracts"),
        ("### 5.2 What Chopper Does NOT Extract", "#### 1.5.2 What Chopper Does NOT Extract"),
        ("### 5.3 Call Extraction Algorithm", "#### 1.5.3 Call Extraction Algorithm"),
        ("#### 5.3.0.1 Skip-Index Pre-Pass (Opaque Commands & `switch` Pattern Labels)", "##### 1.5.3.1 Skip-Index Pre-Pass (Opaque Commands & `switch` Pattern Labels)"),
        ("#### 5.3.0.2 Why First-WORD-After-LBRACE Heuristic Is Needed", "##### 1.5.3.2 Why First-WORD-After-LBRACE Heuristic Is Needed"),
        ("### 5.3.1 Deterministic Proc Name Resolution Contract", "#### 1.5.4 Deterministic Proc Name Resolution Contract"),
        ("### 5.4 Source/iproc_source Extraction", "#### 1.5.5 Source/iproc_source Extraction"),
        ("### 5.4.1 Trace Diagnostic and Call-Tree Alignment Contract", "#### 1.5.6 Trace Diagnostic and Call-Tree Alignment Contract"),
        ("### 5.5 Call Detection False-Positive Filter", "#### 1.5.7 Call Detection False-Positive Filter"),
        ("## 6. Output: Proc Index Entry", "### 1.6 Output: ProcEntry"),
        ("### 6.1 Invariants", "#### 1.6.1 Invariants"),
        ("### 6.2 Boundary Definitions for `body_start_line` / `body_end_line`", "#### 1.6.2 Boundary Definitions for `body_start_line` / `body_end_line`"),
        ("### 6.3 Duplicate Proc Validation Timing and Emission", "#### 1.6.3 Duplicate Proc Validation Timing and Emission"),
        ("## 7. Edge Cases and Adversarial Inputs", "### 1.7 Edge Cases and Adversarial Inputs"),
        ("## 8. Parser Architecture", "### 1.8 Parser Architecture"),
        ("### 8.1 Two-Phase Design", "#### 1.8.1 Two-Phase Design"),
        ("### 8.2 State Machine", "#### 1.8.2 State Machine"),
        ("### 8.3 Performance Target", "#### 1.8.3 Performance Target"),
        ("### 8.4 Diagnostic Emission Contract", "#### 1.8.4 Diagnostic Emission Contract"),
        ("### 8.5 Parser-to-Pipeline Integration", "#### 1.8.5 Parser-to-Pipeline Integration"),
        ("#### 8.5.1 Fields Used by the Trimmer (Phase 5)", "##### 1.8.5.1 Fields Used by the Trimmer (Phase 5)"),
        ("#### 8.5.2 Fields Used by the Compiler / Tracer (Phases 3–4)", "##### 1.8.5.2 Fields Used by the Compiler / Tracer (Phases 3–4)"),
        ("#### 8.5.3 Fields Used by `chopper trim --dry-run` (`dependency_graph.json`)", "##### 1.8.5.3 Fields Used by `chopper trim --dry-run` (`dependency_graph.json`)"),
        ("## 9. Test Strategy", "### 1.9 Test Strategy"),
        ("### 9.1 Fixture Categories", "#### 1.9.1 Fixture Categories"),
        ("### 9.2 Property-Based Invariants", "#### 1.9.2 Property-Based Invariants"),
        ("## 10. References", "### 1.10 References"),
        # Edge-case sub-sections inside §7 (now §1.7) — keep their numbering inline
        ("### 7.1 Brace in Quoted Text Inside a Braced Proc Body", "#### 1.7.1 Brace in Quoted Text Inside a Braced Proc Body"),
        ("### 7.2 Backslash Line Continuation", "#### 1.7.2 Backslash Line Continuation"),
        ("### 7.3 Empty File", "#### 1.7.3 Empty File"),
        ("### 7.4 Proc with No Body Braces (Theoretical)", "#### 1.7.4 Proc with No Body Braces (Theoretical)"),
        ("### 7.5 Deeply Nested Namespace", "#### 1.7.5 Deeply Nested Namespace"),
        ("### 7.6 Multiple Namespace Blocks", "#### 1.7.6 Multiple Namespace Blocks"),
        ("### 7.7 Mixed Encoding", "#### 1.7.7 Mixed Encoding"),
        ("### 7.8 Proc Inside If Block", "#### 1.7.8 Proc Inside If Block"),
        ("### 7.9 Computed Proc Name", "#### 1.7.9 Computed Proc Name"),
        ("### 7.10 Duplicate Proc Definition", "#### 1.7.10 Duplicate Proc Definition"),
        ("### 7.11 Proc Args with Default Values Containing Nested Braces", "#### 1.7.11 Proc Args with Default Values Containing Nested Braces"),
        ("### 7.12 define_proc_attributes Immediately After Proc Closing Brace", "#### 1.7.12 define_proc_attributes Immediately After Proc Closing Brace"),
        ("### 7.13 Structured Comment Banner Before Proc", "#### 1.7.13 Structured Comment Banner Before Proc"),
        ("### 7.14 foreach_in_collection (Synopsys EDA Iterator)", "#### 1.7.14 foreach_in_collection (Synopsys EDA Iterator)"),
    ]
    for old, new in repls:
        text = text.replace(old, new)
    return text


# Wrap each Stage-1x decision block as a callout subsection inside §1.X
def wrap_decisions(stage_text: str, header: str) -> str:
    # stage_text starts with "## Stage 1b — Tokenizer\n\n### D-..." — replace H2 with our context header.
    # Demote H3 D-xx entries to H5 so they nest under the H4 callout header without inverted nesting.
    body = re.sub(r"^## Stage 1[a-z] — [^\n]+\n+", "", stage_text)
    body = re.sub(r"^### (D-1[a-z]-\d{2}:)", r"##### \1", body, flags=re.MULTILINE)
    return f"{header}\n\n{body}\n"


parser_section = (
    PARSER_INTRO
    + renumber_parser(parser_purpose).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_input).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_tokenization).rstrip()
    + "\n\n"
    + wrap_decisions(dlog_1b, "#### 1.3.6 Tokenizer Implementation Decisions")
    + "\n---\n\n"
    + renumber_parser(parser_proc_detection).rstrip()
    + "\n\n"
    + wrap_decisions(dlog_1c, "#### 1.4.8 NamespaceTracker Implementation Decisions")
    + "\n"
    + wrap_decisions(dlog_1d, "#### 1.4.9 ProcExtractor Implementation Decisions")
    + "\n---\n\n"
    + renumber_parser(parser_call_extraction).rstrip()
    + "\n\n"
    + wrap_decisions(dlog_1e, "#### 1.5.8 CallExtractor Implementation Decisions")
    + "\n---\n\n"
    + renumber_parser(parser_output).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_edge_cases).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_architecture).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_test_strategy).rstrip()
    + "\n\n---\n\n"
    + renumber_parser(parser_references).rstrip()
    + "\n\n"
)

# Risks-derived sections (compiler/trimmer/validator/audit/backup/config/cli/hooks/project/testing)
# Renumber from "## PARSER MODULE" style to "## 2. Compiler ..." style.

def render_risks_section(num: int, title: str, body: str) -> str:
    """Wrap a per-module risks block under a new H2 number; strip its old MODULE banner."""
    # Strip the original "## XYZ MODULE — Risk: ..." line
    stripped = re.sub(r"^## [A-Z &/]+(?: MODULE)? — [^\n]+\n", "", body)
    # Promote H3 (### Pitfall ...) one level down to H4 ("#### Pitfall ...") so they sit under H2 + intro text
    return f"## {num}. {title}\n\n{stripped.strip()}\n\n"


compiler_section = render_risks_section(2, "Compiler & Tracer Module", risks_compiler)
trimmer_section = render_risks_section(3, "Trimmer Module", risks_trimmer)
validator_section = render_risks_section(4, "Validator Module", risks_validator)
audit_section = render_risks_section(5, "Audit & Diagnostics", risks_audit)
backup_section = render_risks_section(6, "Backup & Recovery", risks_backup)
config_section = render_risks_section(7, "Configuration & Paths", risks_config)
cli_section = render_risks_section(8, "CLI & Presentation", risks_cli)
hooks_section = render_risks_section(9, "Hook Files", risks_hooks)
project_section = render_risks_section(10, "Project JSON", risks_project)
testing_section = render_risks_section(11, "Testing Strategy", risks_testing)

# Quick-reference table
quickref_section = "## 12. Quick Reference: Common Mistakes by Module\n\n" + \
    re.sub(r"^## Quick Reference: Common Mistakes by Module\n+", "", risks_quickref).strip() + "\n\n"

# Standalone TC items
standalone_section = "## 13. Standalone Risk Items\n\n" + \
    re.sub(r"^## STANDALONE RISK ITEMS\n+", "", risks_standalone).strip() + "\n\n"

# Appendices A and B
appendix_a = "## Appendix A: Permanently Out of Scope\n\n" + \
    re.sub(r"^## Permanently Out of Scope\n+", "", oos_block).strip() + "\n\n"

appendix_b = (
    "## Appendix B: Deferred Work Items\n\n"
    "These items have been considered and **deferred** from the v1 release. They are recorded so future authors know what was thought about and why it was not built. An FD-xx entry is **not a TODO** — many will stay deferred indefinitely. Adding any of these requires re-entering the architecture-doc-first cascade specified in `.github/instructions/project.instructions.md`.\n\n"
    "### B.1 Parser Enhancements\n\n"
    + re.sub(r"^## Parser Enhancements\n+", "", fd_parser).strip() + "\n\n"
    "### B.2 Compiler / Pipeline Enhancements\n\n"
    + re.sub(r"^## Compiler / Pipeline Enhancements\n+", "", fd_compiler).strip() + "\n\n"
    "### B.3 CLI / UX Enhancements\n\n"
    + re.sub(r"^## CLI / UX Enhancements\n+", "", fd_cliux).strip() + "\n\n"
    "### B.4 Documentation Enhancements\n\n"
    + re.sub(r"^## Documentation Enhancements\n+", "", fd_docs).strip() + "\n\n"
    "### B.5 Summary Table\n\n"
    + re.sub(r"^## Summary\n+", "", fd_summary).strip() + "\n"
)


full_doc = (
    HEADER
    + parser_section
    + "\n---\n\n"
    + compiler_section
    + "\n---\n\n"
    + trimmer_section
    + "\n---\n\n"
    + validator_section
    + "\n---\n\n"
    + audit_section
    + "\n---\n\n"
    + backup_section
    + "\n---\n\n"
    + config_section
    + "\n---\n\n"
    + cli_section
    + "\n---\n\n"
    + hooks_section
    + "\n---\n\n"
    + project_section
    + "\n---\n\n"
    + testing_section
    + "\n---\n\n"
    + quickref_section
    + "\n---\n\n"
    + standalone_section
    + "\n---\n\n"
    + appendix_a
    + "\n---\n\n"
    + appendix_b
)

# Apply cross-reference rewrites globally
full_doc = rewrite_internal_links(full_doc)

# Also rewrite "§1.X" style references to use the new numbering scheme inside the parser
# section. Most §X references inside the parser content used the old numbering; the
# renumber_parser call only fixed headings, not in-prose mentions. Add forwarding map:
parser_xref_map = {
    "§3.0": "§1.3.0",
    "§3.1": "§1.3.1",
    "§3.2": "§1.3.2",
    "§3.3": "§1.3.3",
    "§3.3.1": "§1.3.3.1",
    "§3.3.2": "§1.3.3.2",
    "§3.4": "§1.3.4",
    "§3.5": "§1.3.5",
    "§4.1": "§1.4.1",
    "§4.2": "§1.4.2",
    "§4.3": "§1.4.3",
    "§4.3.1": "§1.4.3.1",
    "§4.3.2": "§1.4.3.2",
    "§4.4": "§1.4.4",
    "§4.5": "§1.4.5",
    "§4.5.1": "§1.4.5.1",
    "§4.6": "§1.4.6",
    "§4.7": "§1.4.7",
    "§5.1": "§1.5.1",
    "§5.2": "§1.5.2",
    "§5.3": "§1.5.3",
    "§5.3.1": "§1.5.4",
    "§5.4": "§1.5.5",
    "§5.4.1": "§1.5.6",
    "§5.5": "§1.5.7",
    "§6": "§1.6",
    "§6.1": "§1.6.1",
    "§6.2": "§1.6.2",
    "§6.3": "§1.6.3",
    "§7": "§1.7",
    "§7.14": "§1.7.14",
    "§8": "§1.8",
    "§8.5": "§1.8.5",
    "§9": "§1.9",
}
# Apply only in passages that came from the parser doc. The §X.Y syntax also appears
# in the architecture doc cross-refs and we must not rewrite those — apply with a guard.
# Crude but effective: rewrite only when "§4.6" etc. appear with no preceding "doc"/"architecture doc"/"chopper_description" in the same line.
def rewrite_parser_anchors(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        lower = line.lower()
        if "chopper_description" in lower or "architecture doc" in lower:
            out.append(line)
            continue
        new_line = line
        # Sort longest first so §4.5.1 is replaced before §4.5
        for old in sorted(parser_xref_map, key=len, reverse=True):
            new_line = new_line.replace(old, parser_xref_map[old])
        out.append(new_line)
    return "".join(out)


full_doc = rewrite_parser_anchors(full_doc)

# Final write
out_path = DOCS / "IMPLEMENTATION.md"
out_path.write_text(full_doc, encoding="utf-8")
print(f"Wrote {out_path} ({len(full_doc):,} bytes, {full_doc.count(chr(10)):,} lines)")
