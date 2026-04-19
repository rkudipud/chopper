# Chopper — Implementation Action Plan

> **Status:** Active — Sprint Execution Guide
> **Created:** 2026-04-05
> **Methodology:** AI-Assisted Sprint Development (days, not weeks)
> **Agents:** 2 parallel agents per day

---

## Engineering Constraints (Owner-Declared)

These constraints are authoritative and override any conflicting spec guidance:

| # | Constraint | Impact on Implementation |
|---|---|---|
| **1** | **Codebase ≤ 1 GB always** | No streaming I/O, no chunked processing, no memory-mapped files. Simple in-memory `file.read_text()` for all domain files. |
| **2** | **3–5 min runtime acceptable** | No performance optimization. No C extensions, no parallel workers, no caching layers. Bulk string ops are fine. |
| **3** | **No over-engineering / scope creep** | Implement what the spec says. Do not add features, abstractions, or "improvements" beyond requirements. Practical internal tool, not a public framework. |
| **4** | **Modularity is core** | Clean module boundaries, service layer, typed contracts. Each module independently testable and replaceable. |
| **5** | **Tcl parser can have bugs** | Namespace support is value-add, not absolute must. If implemented per spec, keep it. Don't rip it out. Expect edge-case bugs and handle gracefully with diagnostics. |
| **6** | **Locking is lowest priority** | If something goes wrong, user deletes dir, renames backup, restarts. Don't gold-plate the locking solution. If finalized in docs, leave intact but don't waste cycles perfecting it. |
| **7** | **Simplify interfaces** | Fewer options, fewer modes, fewer knobs. Keep CLI clean and minimal. |
| **8** | **GUI readiness required** | Typed result objects, structured progress events, JSON-serializable models, no `print()` in library code. Service layer returns data, presentation layer renders it. |

---

## What NOT to Stress About

- Performance optimization beyond reasonable bounds
- Perfect Tcl namespace resolution for all edge cases
- Bulletproof locking and crash recovery for every scenario
- 100% coverage of adversarial Tcl inputs
- Enterprise-grade plugin architecture
- Making it "production perfect" — good enough that works is the goal

---

## Pre-Implementation Artifacts (Day 0)

These files must exist before Day 1 coding begins:

| Artifact | Status | Purpose |
|---|---|---|
| `docs/ARCHITECTURE.md` (Rev 22) | ✅ Done | Product behavior source of truth |
| `docs/TECHNICAL_REQUIREMENTS.md` (Rev 11) | ✅ Done | Implementation contracts + integrated clarification updates |
| `docs/TCL_PARSER_SPEC.md` (Rev 6) | ✅ Done | Parser engineering baseline + Addendum A |
| `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` | ✅ Done | Common mistakes to avoid |
| `docs/DIAGNOSTIC_CODES.md` | ✅ Done | Authoritative code registry |
| `docs/DEVELOPER_KICKOFF.md` | ✅ Done | Test order, acceptance criteria, agent sync |
| `docs/CLI_HELP_TEXT_REFERENCE.md` | ✅ Done | Canonical help text phrasing |
| `docs/FINAL_PRODUCTION_REVIEW.md` | ✅ Done | Go/no-go verdict + findings |
| `schemas/base-v1.schema.json` | ✅ Done | Base JSON schema |
| `schemas/feature-v1.schema.json` | ✅ Done | Feature JSON schema |
| `schemas/project-v1.schema.json` | ✅ Done | Project JSON schema |
| `tests/fixtures/mini_domain/` | ✅ Done | F1+F2 test domain with base.json + feature_a.json |
| `tests/fixtures/namespace_domain/` | ✅ Done | Namespace stress tests (nested, sequential, absolute, control flow) |
| `tests/fixtures/tracing_domain/` | ✅ Done | Trace scenarios (chain, diamond, cycle, dynamic, cross-file, ns-calls) |
| `tests/fixtures/edge_cases/` | ✅ Done | 14 parser adversarial input files |
| `tests/FIXTURE_CATALOG.md` | ✅ Done | Fixture index with expected outcomes |

---

## Day 0: Foundation Sprint

**Goal:** Shared infrastructure that all modules depend on.

**Single agent. Complete before any Day 1 work begins.**

### Tasks

| # | Task | File | Description |
|---|---|---|---|
| 0.1 | Package scaffolding | `src/chopper/` tree | Create all `__init__.py` files for: `core/`, `cli/`, `parser/`, `compiler/`, `trimmer/`, `validator/`, `audit/`, `generators/`, `ui/`, `config/` |
| 0.2 | Core models | `src/chopper/core/models.py` | ALL frozen dataclasses from TRQ §7.1.2: `ProcEntry`, `FileEntry`, `ProcDecision`, `CompiledManifest`, `Diagnostic`, `StageDefinition`, `TrimStats`, `RunSelection`, `TrimRequest`, `TrimResult` + ALL enums: `ExitCode`, `FileTreatment`, `KeepReason`, `Severity`, `DiagnosticSource`, `TrimMode` |
| 0.3 | Error hierarchy | `src/chopper/core/errors.py` | `ChopperError` base + `SchemaValidationError`, `CompilationError`, `ParseError`, `TrimWriteError` — each with exit code |
| 0.4 | Diagnostic constants | `src/chopper/core/diagnostics.py` | All codes from `docs/DIAGNOSTIC_CODES.md` as string constants |
| 0.5 | Protocols | `src/chopper/core/protocols.py` | `ProgressSink`, `ProgressEvent`, `TableRenderer`, `DiagnosticRenderer`, `OutputFormatter`, `CustomValidator` |
| 0.6 | Serialization | `src/chopper/core/serialization.py` | `ChopperEncoder`, `serialize()` function per TRQ §5.2 |
| 0.7 | Logging setup | `src/chopper/__init__.py` | `__version__`, `NullHandler` on `chopper` logger |
| 0.8 | pyproject.toml update | `pyproject.toml` | Add all dependencies: `structlog>=24.1.0`, `jsonschema>=4.0`, `rich>=13.0` (optional), dev deps |
| 0.9 | Test scaffolding | `tests/unit/__init__.py`, etc. | Create test directory structure: `unit/`, `integration/`, `golden/`, `property/` |

### Gate

```bash
python -c "from chopper.core.models import ProcEntry, CompiledManifest, Diagnostic, ExitCode, FileTreatment"
python -c "from chopper.core.errors import ChopperError, ParseError"
python -c "from chopper.core.diagnostics import DiagnosticCodes"
ruff check src/
mypy src/chopper/core/
```

---

## Day 1: Parser Module

**Goal:** Parse all domain Tcl files into a ProcEntry index.

### Agent A: Tcl Parser

| # | Task | File | Spec Reference |
|---|---|---|---|
| 1A.1 | Tokenizer: brace tracking | `src/chopper/parser/tcl_parser.py` | TCL_PARSER_SPEC §3.1 |
| 1A.2 | Tokenizer: quote handling (pre-body only) | same | TCL_PARSER_SPEC §3.3.1, §3.3.2 |
| 1A.3 | Tokenizer: comment detection | same | TCL_PARSER_SPEC §3.4 |
| 1A.4 | Tokenizer: backslash continuation | same | TCL_PARSER_SPEC §3.2 |
| 1A.5 | Proc detection state machine | same | TCL_PARSER_SPEC §4.2 (context stack algorithm) |
| 1A.6 | Namespace eval detection | same | TCL_PARSER_SPEC §4.5, §4.5.1 |
| 1A.7 | Proc name resolution | same | TCL_PARSER_SPEC §4.3 |
| 1A.8 | Call extraction (Phase 2) | `src/chopper/parser/call_extractor.py` | TCL_PARSER_SPEC §5 |
| 1A.9 | Source/iproc_source extraction | same | TCL_PARSER_SPEC §5.4 |
| 1A.10 | Public API | `src/chopper/parser/__init__.py` | `parse_file(domain_path, file_path, on_diagnostic?) -> list[ProcEntry]` |

**Key pitfalls to avoid:** P-01 (quote context in braced body), P-02 (line continuation breaks numbering), P-03 (namespace stack persist), P-04 (computed names), P-05 (duplicate procs), P-06 (empty files valid), P-07 (comment braces inert)

### Agent B: Parser Tests + Remaining Fixtures

| # | Task | File | Notes |
|---|---|---|---|
| 1B.1 | Unit test: basic fixtures | `tests/unit/test_parser.py` | Fixtures 1–3 from FIXTURE_CATALOG |
| 1B.2 | Unit test: namespace fixtures | same | Fixtures 6, 7, 12 |
| 1B.3 | Unit test: edge case fixtures | same | Fixtures 4, 5, 8, 9, 10, 11, 13 |
| 1B.4 | Unit test: call extraction | same | Fixture 14 |
| 1B.5 | Property test: PB-01 (span consistency) | `tests/property/test_parser_properties.py` | All lines in span exist |
| 1B.6 | Property test: PB-02 (no overlap) | same | No two ProcEntry spans overlap |
| 1B.7 | Build hook_domain fixture | `tests/fixtures/hook_domain/` | For iproc_source -use_hooks testing |
| 1B.8 | Build encoding fixture | `tests/fixtures/edge_cases/parser_encoding_latin1_fallback.tcl` | Non-UTF8 content |

### Sync: End of Day 1

- [ ] Parser produces correct ProcEntry for fixtures 1–15
- [ ] `pytest tests/unit/test_parser.py` all green
- [ ] Property tests PB-01, PB-02 pass

---

## Day 2: Compiler Module + Tracer

**Goal:** Compile base+features into a frozen manifest with traced proc dependencies.

### Agent A: Compiler

| # | Task | File | Spec Reference |
|---|---|---|---|
| 2A.1 | JSON loader + schema validation | `src/chopper/compiler/loader.py` | TRQ §6.3, schemas/ |
| 2A.2 | Phase 1–2: collect file/proc rules | `src/chopper/compiler/compiler.py` | TRQ §7.1.1 phases 1–2 |
| 2A.3 | Partition literal vs glob includes | same | TRQ §7.1.1 `partition_file_includes()` |
| 2A.4 | Glob expansion + dedup + sort | same | TRQ §6.4.1 |
| 2A.5 | Phase 4: Decision 5 (include wins) | same | ARCH §4.5, TRQ §7.1.1 phase 4 |
| 2A.6 | Phase 5: file treatment derivation | same | ARCH §4.5 (FI→FULL_COPY, PI+→PROC_TRIM, etc.) |
| 2A.7 | Phase 6: flow_actions application | same | ARCH §6.7 (9 actions, @n targeting) |
| 2A.8 | Phase 7: freeze CompiledManifest | same | TRQ §7.1.2 |
| 2A.9 | Public API | `src/chopper/compiler/__init__.py` | `compile_selection(base, features, domain, proc_index) -> CompiledManifest` |

**Key pitfalls:** P-08 (deterministic trace), P-09 (include wins), P-10 (feature order), P-11 (glob normalize), P-12 (reject absolute paths)

### Agent B: Tracer

| # | Task | File | Spec Reference |
|---|---|---|---|
| 2B.1 | Build domain proc index | `src/chopper/compiler/tracer.py` | ARCH §4.3 (parse all Tcl files in lex order) |
| 2B.2 | Breadth-first sorted-frontier expansion | same | ARCH §4.3 steps 1–12 |
| 2B.3 | Namespace resolution contract | same | TCL_PARSER_SPEC §5.3.1 |
| 2B.4 | TRACE-AMBIG-01 emission | same | Multiple candidates → warning, don't resolve |
| 2B.5 | TRACE-CROSS-DOMAIN-01 emission | same | No in-domain match → warning |
| 2B.6 | TRACE-UNRESOLV-01 emission | same | Dynamic dispatch → warning |
| 2B.7 | TRACE-CYCLE-01 emission | same | Cycle detected → warning, both procs included |
| 2B.8 | Unit tests | `tests/unit/test_tracer.py` | Chain, diamond, cycle, dynamic, ns-resolution |
| 2B.9 | Public API | same module | `trace_expand(seeds, proc_index) -> (traced_set, diagnostics)` |

### Sync: End of Day 2

- [ ] `compile_selection()` produces correct CompiledManifest from base+features
- [ ] Tracer resolves chain, diamond, and cycle correctly
- [ ] Decision 5 tests pass (explicit include beats exclude)
- [ ] `pytest tests/unit/test_compiler.py tests/unit/test_tracer.py` all green

---

## Day 3: Trimmer Module + Audit Trail

**Goal:** Write trimmed domain files and emit audit trail.

### Agent A: Trimmer + State Machine

| # | Task | File | Spec Reference |
|---|---|---|---|
| 3A.1 | Backup detection | `src/chopper/trimmer/backup.py` | ARCH §2.8.1: detect if `domain_backup/` exists, rebuild from it if present |
| 3A.2 | Backup creation (first trim) | same | `os.rename(domain, domain_backup)` |
| 3A.3 | Staging directory creation | `src/chopper/trimmer/staging.py` | TRQ §7.3 (`domain_staging/`) |
| 3A.4 | File FULL_COPY from backup | `src/chopper/trimmer/writer.py` | Byte-for-byte copy |
| 3A.5 | File PROC_TRIM: proc deletion | same | TRQ §7.4 (comment association, blank-line collapse) |
| 3A.6 | File GENERATED: F3 run-file output | `src/chopper/generators/f3_generator.py` | ARCH §3.6, stages→run files |
| 3A.7 | Atomic promotion (staging→domain) | `src/chopper/trimmer/staging.py` | TRQ §7.3.1 (`os.replace()`) |
| 3A.8 | Failure recovery | same | Restore pre-run state on crash |
| 3A.9 | TrimService.execute() | `src/chopper/trimmer/trimmer.py` | TRQ §5.3 |

**Key pitfalls:** P-13 (atomic transitions), P-15 (preserve surrounding context)

### Agent B: Audit Trail

| # | Task | File | Spec Reference |
|---|---|---|---|
| 3B.1 | `.chopper/` directory creation | `src/chopper/audit/writer.py` | TRQ §7.2.1 |
| 3B.2 | `chopper_run.json` | same | TRQ §7.2 |
| 3B.3 | `compiled_manifest.json` | same | Serialize CompiledManifest |
| 3B.4 | `input_base.json` + `input_features/` | same | Exact copies of inputs |
| 3B.5 | `input_project.json` (optional) | same | When --project used |
| 3B.6 | `trim_report.json` + `trim_report.txt` | same | Summary with diagnostics |
| 3B.7 | `dependency_graph.json` | same | Proc/file edges |
| 3B.8 | `diagnostics.json` | same | All warnings/errors |
| 3B.9 | `trim_stats.json` | same | Before/after counts |
| 3B.10 | Determinism tests | `tests/unit/test_audit.py` | Same inputs → byte-identical outputs |

### Sync: End of Day 3

- [ ] Backup detection and re-trim from backup works
- [ ] Staging and atomic promotion complete successfully
- [ ] Proc deletion preserves surrounding code
- [ ] All audit artifacts written correctly
- [ ] `pytest tests/unit/test_trimmer.py tests/unit/test_audit.py` all green

---

## Day 4: Validator + CLI

**Goal:** All validation checks work. CLI parses and dispatches correctly.

### Agent A: Validator

| # | Task | File | Spec Reference |
|---|---|---|---|
| 4A.1 | Phase 1: V-01 through V-09 | `src/chopper/validator/phase1.py` | TRQ §8.3 |
| 4A.2 | Phase 1: V-10 through V-18 | same | TRQ §8.3 |
| 4A.3 | Phase 2: V-20 through V-26 | `src/chopper/validator/phase2.py` | TRQ §8.3 |
| 4A.4 | Standalone `validate` command | wired in CLI | Phase 1 only |
| 4A.5 | `--strict` mode escalation | same | Warnings → errors |
| 4A.6 | Unit tests per V-xx | `tests/unit/test_validator.py` | One test per diagnostic code |

### Agent B: CLI + Service Layer

| # | Task | File | Spec Reference |
|---|---|---|---|
| 4B.1 | Argparse: shared parent parser | `src/chopper/cli/main.py` | TRQ §9.1.1, CLI_HELP_TEXT_REFERENCE.md |
| 4B.2 | Subcommands: scan, validate, trim, cleanup | same | TRQ §9.1.3 |
| 4B.3 | Input mode parsing (--base/--features/--project) | same | TRQ §9.1.2 |
| 4B.4 | Service layer wiring | `src/chopper/cli/commands.py` | TrimService, ValidateService, etc. |
| 4B.5 | Logging setup (structlog) | `src/chopper/cli/logging_setup.py` | TRQ §3.5 |
| 4B.6 | Rich + Plain renderers | `src/chopper/ui/rich_renderer.py`, `plain_renderer.py` | TRQ §5.6 |
| 4B.7 | Exit code mapping | `src/chopper/cli/main.py` | TRQ §8.2 |
| 4B.8 | `--json` output mode | same | TRQ §11.3 |
| 4B.9 | Config loader (.chopper.config) | `src/chopper/config/loaders.py` | TRQ §6.1 |
| 4B.10 | Integration tests | `tests/integration/test_cli.py` | Each subcommand + error paths |

### Sync: End of Day 4

- [ ] `chopper --help` works
- [ ] `chopper validate --base tests/fixtures/mini_domain/jsons/base.json` exits 0
- [ ] `chopper trim --dry-run --base tests/fixtures/mini_domain/jsons/base.json` exits 0
- [ ] Invalid inputs produce correct exit codes (1 or 2)

---

## Day 5: Scanner + Full E2E Integration

**Goal:** `chopper scan` works. Full workflow passes end-to-end.

### Agent A: Scanner

| # | Task | File | Spec Reference |
|---|---|---|---|
| 5A.1 | Scan pipeline: discover files | `src/chopper/generators/scanner.py` | ARCH §5.6 |
| 5A.2 | Classify files (Tcl/Perl/Python/csh) | same | ARCH §2.7 |
| 5A.3 | Parse Tcl files → proc inventory | same | Reuse parser module |
| 5A.4 | Build dependency graph | same | source/iproc_source + proc calls |
| 5A.5 | Generate draft_base.json (_draft: true) | same | ARCH §3.7 |
| 5A.6 | Generate file_inventory.json | same | TRQ §7.2.2 |
| 5A.7 | Generate proc_inventory.json | same | TRQ §7.2.2 |
| 5A.8 | Generate scan_report.json + .txt | same | TRQ §7.2.2 |
| 5A.9 | Generate diff_report.json (conditional) | same | TRQ §7.2.2.1, Addendum A.1 |
| 5A.10 | ScanService.execute() | same | TRQ §5.3 |

### Agent B: Polish + E2E

| # | Task | File | Spec Reference |
|---|---|---|---|
| 5B.1 | `--project` mode: load + resolve | `src/chopper/cli/commands.py` | TRQ §9.1.4 |
| 5B.2 | Project JSON audit recording | `src/chopper/audit/writer.py` | TRQ §9.1.4 |
| 5B.3 | `--dry-run`: full simulation | `src/chopper/trimmer/trimmer.py` | TRQ §8.3 Phase 3 |
| 5B.4 | `chopper cleanup --confirm` | `src/chopper/cli/commands.py` | TRQ §9.1.3 |
| 5B.5 | Template script execution | `src/chopper/trimmer/trimmer.py` | TRQ §5.5.1 |
| 5B.6 | Project JSON equivalence test | `tests/integration/test_project_mode.py` | --project == --base/--features |
| 5B.7 | Full E2E workflow test | `tests/integration/test_full_workflow.py` | scan → validate → dry-run → trim → cleanup |
| 5B.8 | Golden output comparison | `tests/golden/` | mini_domain expected output |
| 5B.9 | Signal handling (SIGINT/SIGTERM) | `src/chopper/cli/main.py` | TRQ §11.2 |
| 5B.10 | Final ruff + mypy + test gate | — | `make ci` passes |

### Sync: End of Day 5

- [ ] `chopper scan` produces all artifacts for mini_domain
- [ ] `chopper trim --project` == `chopper trim --base --features`
- [ ] Full workflow: scan → validate → dry-run → trim → re-trim → cleanup
- [ ] `make ci` passes (lint + type-check + all tests)
- [ ] v0.1.0 candidate ready for code review

---

## Success Criteria

| Criterion | How to Verify |
|---|---|
| Zero circular dependencies | Import test: each module imports only from `core/` and its own submodules |
| All proc boundaries correct | Parser passes all 15+ fixture files |
| Deterministic output | Same inputs → byte-identical manifests (SHA256 comparison) |
| Trace expansion correct | BFS sorted frontier produces expected PI+ |
| Crash recovery works | State machine tests pass at all transition points |
| All V-xx checks work | One unit test per diagnostic code |
| Dry-run is safe | No files modified during dry-run |
| Project mode equivalence | Identical output from both input modes |
| No print() in library | Grep check: `grep -r "print(" src/chopper/ --include="*.py" | grep -v cli/ | grep -v ui/` returns nothing |
| GUI readiness | All service methods return typed dataclasses, not strings |

---

## Quick Reference: Key File Locations

| What | Where |
|---|---|
| Architecture spec | `docs/ARCHITECTURE.md` |
| Technical requirements | `docs/TECHNICAL_REQUIREMENTS.md` |
| Parser spec | `docs/TCL_PARSER_SPEC.md` |
| Pitfalls guide | `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` |
| Diagnostic codes | `docs/DIAGNOSTIC_CODES.md` |
| Developer kickoff | `docs/DEVELOPER_KICKOFF.md` |
| CLI help text | `docs/CLI_HELP_TEXT_REFERENCE.md` |
| Production review | `docs/FINAL_PRODUCTION_REVIEW.md` |
| JSON schemas | `schemas/*.schema.json` |
| Shared models | `src/chopper/core/models.py` |
| Test fixtures | `tests/fixtures/` |
| Fixture catalog | `tests/FIXTURE_CATALOG.md` |
