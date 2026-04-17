# Chopper — Future Planned Developments

> **Status:** Living Document  
> **Last Updated:** 2026-04-04  
> **Purpose:** Track potential improvements, enhancements, and deferred work items for post-v1 releases  

---

## Parser Enhancements

### FD-01: Quote Context Tracking at Depth > 0 (Extended Analysis)

**Origin:** Final Review Finding F-03

Inside a brace-delimited proc body (depth > 0), Tcl Rule 6 suppresses all substitution processing — meaning `"` characters are literal text and do not create quoted-string contexts. The current parser spec (TCL_PARSER_SPEC.md §3.3) has an implementation clarification that `in_quote` is not toggled inside brace-delimited blocks.

However, there is a subtle edge case at depth 0 where `proc` arguments are being parsed before the body brace opens. Consider:

```tcl
proc foo "arg1 arg2" {
    set x 1
}
```

Here the args word is double-quoted (not brace-delimited). The parser must correctly identify the body opening brace `{` that follows the quoted args, without being confused by any braces that might appear inside the quoted args.

**Future Enhancement:** If real-world domains contain quoted proc argument lists (extremely rare), extend the parser to handle this case. For v1, the spec correctly notes that Chopper only recognizes brace-delimited bodies and logs a WARNING for non-brace bodies.

---

## Schema Enhancements

### FD-02: Feature Dependency Graph

Support optional `depends_on` field in Feature JSON to declare inter-feature dependencies. When Feature B depends on Feature A, Chopper could validate that A is included whenever B is selected.

**Deferred because:** ARCHITECTURE.md §2.2 explicitly places hard-enforce feature dependency graphs out of scope for v1. Informational warnings are sufficient.

### FD-03: Conditional Feature Selection

Support `conditions` in Feature JSON that evaluate ivar expressions to determine whether a feature applies. This would reduce the number of project-specific feature combinations.

**Deferred because:** Evaluating runtime Tcl/ivar semantics is out of scope for v1.

---

## Trimmer Enhancements

### FD-04: Non-Tcl Subroutine-Level Trimming

Extend F2-style proc-level trimming to Perl subroutines and Python functions in non-Tcl files.

**Deferred because:** ARCHITECTURE.md §2.2 explicitly excludes partial trimming of non-Tcl languages at subroutine level for v1. File-level treatment is sufficient for the current domain structure.

---

## Validation Enhancements

### FD-05: Cross-Domain Reference Validation

Add a validation pass that detects cross-domain proc references (e.g., domain A calling a proc defined in domain B).

**Deferred because:** ARCHITECTURE.md §2.9 assumes cross-domain dependencies do not materially exist. If discovered later, this becomes a validation pass priority.

---

## CLI / UX Enhancements

### FD-06: Interactive Feature Selection TUI

Provide a terminal-based interactive UI for browsing available features, previewing their effects, and composing a project JSON.

**Deferred because:** CLI-first approach is correct for v1. The service-layer and renderer-adapter architecture (TECHNICAL_REQUIREMENTS.md §5) enables this without engine changes.

### FD-07: GUI Client

JSON-over-stdio wire protocol (TECHNICAL_REQUIREMENTS.md §5.2) enables a future GUI. Not implemented in v1 but architecturally enabled.

---

## Operational Enhancements

### FD-08: CI Integration for Trim and Validate

Provide CI pipeline templates (GitHub Actions, Jenkins) for automated trim-and-validate during the trim window.

**Deferred because:** Not a launch requirement. Chopper's CLI and exit codes are CI-compatible by design.

### FD-09: Branch Health Reporting

Aggregate trim status across all domains in a project branch to give release managers visibility into trim progress.

**Deferred because:** Per-domain isolation is the v1 boundary. Multi-domain awareness is post-v1.
