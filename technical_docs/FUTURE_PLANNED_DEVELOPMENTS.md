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

**Source:** `technical_docs/TCL_PARSER_SPEC.md` §6.3, `technical_docs/chopper_description.md` §4.6

---

## Compiler / Pipeline Enhancements

### FD-02: Cross-Domain Dependency Awareness

v1 treats domains as fully isolated. Cross-domain proc calls are logged as `TW-02` (unresolved) but never traced. A future version could optionally accept a multi-domain manifest for read-only cross-domain call validation (not trimming).

**Source:** `technical_docs/chopper_description.md` §2.2, Q1

---

## CLI / UX Enhancements

### FD-03: Interactive Feature Selection TUI

Provide a terminal-based interactive UI for browsing available features, previewing their effects, and composing a project JSON.

**Deferred because:** CLI-first approach is correct for v1. The service-layer and renderer-adapter architecture (`technical_docs/chopper_description.md` §5.11) enables this without engine changes.

### FD-04: GUI Client

A machine-readable stdio wire protocol for a future GUI client is documented in `technical_docs/chopper_description.md` §5.11.3 and in [`FD-10`](#fd-10-machine-readable-cli-output). The wire-level JSON payload is conventionally called a "TrimRequest" envelope; on the Python side it deserializes into `RunConfig` + `PresentationConfig` consumed by `ChopperRunner.run(ctx) -> RunResult`. There is no Python class named `TrimRequest` — the engine boundary is `ChopperContext` in, `RunResult` out (see [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6). Progress events will be emitted as JSON lines on stderr. Not implemented in v1 but architecturally enabled by the service-layer, serialization, and renderer-adapter contracts defined in §5.11.

GUI-relevant data surfaces (file selection, proc selection, dependency graph, trim stats, JSON viewing, diagnostics) are enumerated in §5.11.5. No additional data models or artifacts are needed — the v1 pipeline already produces everything a GUI would consume.

---

## Documentation Enhancements

### FD-05: Quick-Start Guide

Add a quick-start section to the architecture doc with a minimal end-to-end walkthrough.

**Source:** `technical_docs/chopper_description.md` §13.4, DF-01

### FD-06: Example Diagnostic Messages

Add concrete example error/warning messages to the architecture doc for every diagnostic code.

**Source:** `technical_docs/chopper_description.md` §13.4, DF-02

### FD-07: Terminology Glossary

Add a terminology note distinguishing "capability" (F1/F2/F3) from "feature JSON" (a JSON file that extends the base).

**Source:** `technical_docs/chopper_description.md` §13.4, DF-03

---

### FD-09: Performance Benchmark Harness and Phase Budgets

v1 accepts a 5–10 minute runtime for a typical domain; optimization is explicitly deferred until the core pipeline is verified end-to-end. Post-v1, add:

- A `make bench` target that runs the `tests/fixtures/gen_large_domain.py` fixture through `chopper validate` and `chopper trim --dry-run` and records P50 / P95 wall-clock per phase.
- A phase-time budget table (% of total) kept next to the benchmark harness so regressions are visible at review time.
- Opt-in parser concurrency (`--jobs N`) using a bounded thread pool with sorted result merge to preserve determinism.
- Optional `slots=True` on hot frozen dataclasses if allocator pressure shows up in profiling.

**Deferred because:** premature optimization before correctness is verified risks locking in bugs. The determinism contract (§11 of the plan) is the prerequisite for any meaningful benchmarking.

**Source:** [`technical_docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §11, §13.5

---

### FD-10: Machine-Readable CLI Output

v1's CLI emits human-readable table output only. A `--json` or `--jsonl` mode would emit `RunResult` (and progress events) as structured lines on stdout so downstream tooling (CI dashboards, a future GUI, ad-hoc scripts) can consume them without scraping tables.

Post-v1, this is ~50 lines of code in `cli/render.py` plus a test fixture — `RunResult` already serializes via `core/serialization.py` and `PresentationConfig` already has a rendering seam. The deferral is solely to keep v1's user surface minimal and let the table renderer bed in before committing to a machine-output contract.

**Deferred because:** v1 is a push-button tool for one operator on one domain; structured output solves a problem (programmatic consumption) that no v1 user has. Shipping it now would freeze the JSON shape before the core pipeline has proved itself.

**Source:** `DAY0_REVIEW.md` A1 (CLI flag inventory decision).

---

### FD-11: Multi-Platform Domain Support

Chopper v1 runs on Linux grid nodes against domains authored on Windows. Authoring happens on either OS, trimming runs only on Linux. The `project.domain` field is case-folded for this reason (bible §5.1, `VE-17`).

A future version might support trimming domains that live on Windows filesystems directly (case-insensitive, different path semantics, CRLF line endings). That would require a canonical internal path representation across OSes, a line-ending policy for the trimmer, and cross-OS golden fixtures.

**Deferred because:** the v1 operator runs one command on one Linux grid node. Adding a cross-OS trim mode would double the fixture matrix and require contractual decisions about CRLF handling that have no v1 user.

**Source:** `DAY0_REVIEW.md` response to case-fold discussion.

---

### FD-12: Template-Script Generation

Some domains may want Chopper to execute a domain-specific post-trim script that generates derived artifacts (lint reports, project-level `run.tcl` wrappers, tool-specific setup files). Earlier spec drafts carried an `options.template_script` schema field and a `VE-18` diagnostic for path-safety validation, with the intent that v1 would validate the path but not execute the script ("reserved seam").

Per the scope-lock policy in [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md), reserved seams with registered diagnostics are not allowed. The field and the diagnostic have been removed. If a future version wants template generation, it will file this FD-12 entry as the starting point and re-enter the architecture through the bible-first cascade: spec the execution contract (sandbox? arguments? failure mode?), then reintroduce the schema field and diagnostic in a new code slot.

**Deferred because:** domain owners today can run their generation scripts before or after `chopper trim` themselves. Baking an executor into Chopper commits the tool to a security surface (what paths are allowed? what exit-code policy?) that has no v1 caller demanding it.

**Source:** `DAY0_REVIEW.md` G2; scope-lock policy (`.github/instructions/project.instructions.md` §1).

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
| FD-10 | CLI/UX | Machine-readable CLI output (`--json` / `--jsonl`) | Deferred; v1 is table-only |
| FD-11 | Platform | Multi-platform domain support (trim on Windows) | Deferred; v1 is Linux-only |
| FD-12 | Generator | Template-script generation (post-trim executor) | Deferred; scope-lock removed the reserved seam |