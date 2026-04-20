# Chopper — Future Planned Developments

> **Status:** Living Document
> **Purpose:** Consolidated registry of deferred work items and permanently excluded scope items

---

## Permanently Out of Scope

These items have been evaluated and **permanently excluded**. They will not be implemented in any version of Chopper. Do not plan, design, or prototype any of these.

| ID | Item | Rationale |
|---|---|---|
| OOS-01 | Non-Tcl subroutine-level trimming | Non-Tcl files (Perl, Python, shell) are file-level only by design. Subroutine-level parsing for non-Tcl languages is not a requirement. |
| OOS-02 | Computed proc name extraction | Procs with dynamic names (`proc ${prefix}_helper`) are skipped with `PW-01`. Heuristic resolution adds complexity with no practical value. |
| OOS-03 | Pipeline checkpointing | No domain exceeds 200 MB. Full restart from Phase 1 is acceptable. The `compiled_plan.json` resumption idea is unnecessary. |
| OOS-04 | Auto-draft JSON / scan mode | Scan mode was considered and explicitly removed. Chopper does not generate draft JSONs. Domain owners author JSONs manually; `--dry-run` is the authoring iteration feedback loop. |

---

## Parser Enhancements

### FD-01: Advanced Namespace Resolution

The following Tcl namespace features are out of scope for v1 and are never guessed. They emit `TW-03` (unresolvable call form) when encountered:

- `namespace import`
- Command path lookup (`namespace path`)
- `namespace unknown` handlers
- Runtime aliasing / `interp alias`
- Runtime redefinition order across sourced files

**Source:** `docs/TCL_PARSER_SPEC.md` §6.3, `docs/chopper_description.md` §4.6

---

## Compiler / Pipeline Enhancements

### FD-02: Cross-Domain Dependency Awareness

v1 treats domains as fully isolated. Cross-domain proc calls are logged as `TW-02` (unresolved) but never traced. A future version could optionally accept a multi-domain manifest for read-only cross-domain call validation (not trimming).

**Source:** `docs/chopper_description.md` §2.2, Q1

---

## CLI / UX Enhancements

### FD-03: Interactive Feature Selection TUI

Provide a terminal-based interactive UI for browsing available features, previewing their effects, and composing a project JSON.

**Deferred because:** CLI-first approach is correct for v1. The service-layer and renderer-adapter architecture (`docs/chopper_description.md` §5.11) enables this without engine changes.

### FD-04: GUI Client

JSON-over-stdio wire protocol is now documented in `docs/chopper_description.md` §5.11.3. The Chopper engine will accept a `TrimRequest` as JSON on stdin and emit a `TrimResult` as JSON on stdout. Progress events will be emitted as JSON lines on stderr. Not implemented in v1 but architecturally enabled by the service-layer, serialization, and renderer-adapter contracts defined in §5.11.

GUI-relevant data surfaces (file selection, proc selection, dependency graph, trim stats, JSON viewing, diagnostics) are enumerated in §5.11.5. No additional data models or artifacts are needed — the v1 pipeline already produces everything a GUI would consume.

---

## Documentation Enhancements

### FD-05: Quick-Start Guide

Add a quick-start section to the architecture doc with a minimal end-to-end walkthrough.

**Source:** `docs/chopper_description.md` §13.4, DF-01

### FD-06: Example Diagnostic Messages

Add concrete example error/warning messages to the architecture doc for every diagnostic code.

**Source:** `docs/chopper_description.md` §13.4, DF-02

### FD-07: Terminology Glossary

Add a terminology note distinguishing "capability" (F1/F2/F3) from "feature JSON" (a JSON file that extends the base).

**Source:** `docs/chopper_description.md` §13.4, DF-03

---

### FD-09: Performance Benchmark Harness and Phase Budgets

v1 accepts a 5–10 minute runtime for a typical domain; optimization is explicitly deferred until the core pipeline is verified end-to-end. Post-v1, add:

- A `make bench` target that runs the `tests/fixtures/gen_large_domain.py` fixture through `chopper validate` and `chopper trim --dry-run` and records P50 / P95 wall-clock per phase.
- A phase-time budget table (% of total) kept next to the benchmark harness so regressions are visible at review time.
- Opt-in parser concurrency (`--jobs N`) using a bounded thread pool with sorted result merge to preserve determinism.
- Optional `slots=True` on hot frozen dataclasses if allocator pressure shows up in profiling.

**Deferred because:** premature optimization before correctness is verified risks locking in bugs. The determinism contract (§11 of the plan) is the prerequisite for any meaningful benchmarking.

**Source:** [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §11, §13.5

---

## Summary

| ID | Category | Item | Status |
|---|---|---|---|
| FD-01 | Parser | Advanced namespace resolution | Out of scope for v1 |
| FD-02 | Pipeline | Cross-domain dependency awareness | Out of scope for v1 |
| FD-03 | CLI/UX | Interactive feature selection TUI | Architecturally enabled, deferred |
| FD-04 | CLI/UX | GUI client via JSON-over-stdio | Architecturally enabled, deferred (§5.11) |
| FD-05 | Docs | Quick-start guide | Deferred until spec final |
| FD-06 | Docs | Example diagnostic messages | Deferred until spec final |
| FD-07 | Docs | Terminology glossary | Deferred until spec final |
| FD-09 | Performance | Benchmark harness and phase budgets | Deferred until core pipeline verified |