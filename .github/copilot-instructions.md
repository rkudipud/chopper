# Chopper — Workspace Instructions

## Environment Bootstrap

**Always activate the venv before running any command:**

```tcsh
source setup.csh        # Creates .venv/, activates it, installs chopper[dev]
```

If already activated: `source .venv/bin/activate`

## Agent-First Development

This project is built with **agent-driven development**. Agents are primary contributors.

- **Read before writing** — consult the spec docs listed below before implementing any module
- **Run `make check` after every change** — lint + format + type-check + unit tests (fast gate)
- **Run `make ci` before pushing** — full test suite including integration, golden, property tests
- **One module at a time** — each module has a clear entry point, typed contracts, and self-contained test fixtures so agents can work independently
- **No `print()` in library code** — use `structlog` / `logging`; the codebase must stay GUI-ready
- **All public functions get type hints** — `mypy --strict`-ready, enforced via `make type-check`

## Build & Test Commands

| Command | Purpose |
|---------|---------|
| `make check` | Pre-commit gate: lint + format-check + type-check + unit tests |
| `make ci` | Full CI gate: all test suites |
| `make test-unit` | `pytest tests/unit/ -v` |
| `make test-integration` | `pytest tests/integration/ -v` |
| `make test-golden` | `pytest tests/golden/ -v` |
| `make test-property` | `pytest tests/property/ -v` |
| `make lint` | `ruff check src/ tests/` |
| `make format` | `ruff format src/ tests/` (auto-fix) |
| `make type-check` | `mypy src/` |
| `make clean` | Remove caches and build artifacts |

## Project Context

Chopper is a Python CLI tool that trims EDA TFM (Tool Flow Manager) codebases for the Cheetah R2G VLSI backend flow. It operates at the per-domain level, extracting only the needed Tcl procs and files based on JSON configuration.

## Architecture

See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for full architecture (Rev 22, source of truth).

| Module | Role | Spec Reference |
|--------|------|----------------|
| `src/chopper/core/` | Shared models, errors, diagnostics, protocols | TRQ §3–5 |
| `src/chopper/parser/` | Tcl proc parser + call extractor | [docs/TCL_PARSER_SPEC.md](../docs/TCL_PARSER_SPEC.md) |
| `src/chopper/compiler/` | JSON compilation (base+features merge, 7-phase) + trace expansion | TRQ §7.1.1 |
| `src/chopper/trimmer/` | File/proc extraction engine, state machine, backup lifecycle | TRQ §7.3–7.4 |
| `src/chopper/validator/` | V-01 through V-26 validation checks (phase 1 + phase 2) | TRQ §8.3 |
| `src/chopper/cli/` | CLI entry point (argparse), service layer, renderers | TRQ §9.1 |
| `src/chopper/generators/` | Scanner (scan pipeline, `draft_base.json`) | ARCH §3.7 |
| `tests/` | pytest: unit, integration, golden, property | [tests/TESTING_STRATEGY.md](../tests/TESTING_STRATEGY.md) |

## Code Style

- Python ≥3.9, <3.14
- Type hints on all public functions (`disallow_untyped_defs = true`)
- `pathlib.Path` for file paths — never raw strings
- `structlog` for logging — never bare `print()`
- Ruff: `line-length = 120`, select `["E", "F", "I", "N", "W", "UP"]`
- pytest with `--cov-fail-under=78` branch coverage

## Key Domain Terms

- **Base JSON** — bare minimum flow definition for a tool domain
- **Feature JSON** — extension that injects/overrides/removes procs from base
- **Domain** — a tool flow directory (e.g., `fev_formality/`, `sta_pt/`, `power/`)
- **iproc_source** — CTH's file sourcing command (like Tcl `source` but with hooks)
- **ivar** — Intel variable system used for flow configuration
- **Proc-level trimming** — extract individual `proc` definitions from Tcl files
- **Backup** — `domain_backup/` folder with the untouched original

## Hard Constraints

- Include wins over exclude when resolving proc conflicts
- Non-Tcl files (Perl, Python, csh) are file-level only, no proc-level extraction
- Backup folders are committed to the project branch
- Codebase ≤ 1 GB always — simple `file.read_text()`, no streaming/chunking
- No over-engineering — implement spec only, no extra abstractions
- Locking is lowest priority — simple recovery over bulletproof

## Key Specs & Docs

Before implementing a module, read its spec:

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) | Architecture source of truth (Rev 22) |
| [docs/TECHNICAL_REQUIREMENTS.md](../docs/TECHNICAL_REQUIREMENTS.md) | Full requirements (Rev 10) |
| [docs/TCL_PARSER_SPEC.md](../docs/TCL_PARSER_SPEC.md) | Parser rules (Rev 6) |
| [docs/DIAGNOSTIC_CODES.md](../docs/DIAGNOSTIC_CODES.md) | All E-xx, V-xx, TRACE-xx codes |
| [docs/IMPLEMENTATION_PITFALLS_GUIDE.md](../docs/IMPLEMENTATION_PITFALLS_GUIDE.md) | P-01 through P-16 pitfalls |
| [docs/DEVELOPER_KICKOFF.md](../docs/DEVELOPER_KICKOFF.md) | Module assignments + sync checkpoints |
| [docs/ACTION_PLAN.md](../docs/ACTION_PLAN.md) | Sprint plan (Day 0–5) |
| [tests/TESTING_STRATEGY.md](../tests/TESTING_STRATEGY.md) | Coverage targets, test harness, fixtures |
| [tests/FIXTURE_CATALOG.md](../tests/FIXTURE_CATALOG.md) | Test fixture inventory |

## Test Fixtures

Pre-built fixtures in `tests/fixtures/`:
- `mini_domain/` — 8-file domain with base+feature JSONs (compiler/trimmer tests)
- `namespace_domain/` — 5 files for namespace eval scenarios
- `tracing_domain/` — 6 files for call tracing (chain, cycle, diamond, cross-file)
- `edge_cases/` — 14 adversarial Tcl parser inputs

## Agent Handoff Protocol

### Before Starting Any Module

1. Read the module's spec (see Module Reference below)
2. Read `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` for that module's pitfalls
3. Verify `src/chopper/core/models.py` exists — import shared models, never duplicate them
4. Read test fixtures for the module from `tests/FIXTURE_CATALOG.md`

### Module Reference — What to Read Per Assignment

| Module | Primary Spec | Pitfalls | Entry Point |
|--------|-------------|----------|-------------|
| Core | TRQ §3–5 | — | `src/chopper/core/models.py` |
| Parser | `docs/TCL_PARSER_SPEC.md` (full) | P-01 – P-07 | `parse_file(domain_path, file_path, on_diagnostic?) -> list[ProcEntry]` |
| Compiler | TRQ §7.1.1 | P-08 – P-12 | `compile_selection(base, features, domain, proc_index) -> CompiledManifest` |
| Tracer | ARCH §4.3 | P-08 | `trace_expand(seeds, proc_index) -> (traced_set, diagnostics)` |
| Trimmer | ARCH §2.8, TRQ §7.3–7.4 | P-13 – P-15 | `TrimService.execute(TrimRequest) -> TrimResult` |
| Validator | TRQ §8.3 | P-16 | `validate_phase1(inputs) -> list[Diagnostic]` |
| CLI | TRQ §9.1 | — | `src/chopper/cli/main.py::main` |
| Scanner | ARCH §3.7, §5.6 | — | `ScanService.execute(ScanRequest) -> ScanResult` |

### Shared Contracts — DO NOT DUPLICATE

All modules import from `src/chopper/core/`. If a new field is needed, update the shared file:

| File | Contents |
|------|----------|
| `core/models.py` | ALL frozen dataclasses + enums (`ProcEntry`, `CompiledManifest`, `Diagnostic`, `ExitCode`, `FileTreatment`, etc.) |
| `core/errors.py` | `ChopperError` hierarchy with exit codes |
| `core/diagnostics.py` | Diagnostic code constants (V-xx, TRACE-xx, PARSER-xx) |
| `core/protocols.py` | Protocol interfaces (`ProgressSink`, `DiagnosticCollector`, `TableRenderer`, etc.) |
| `core/serialization.py` | `ChopperEncoder`, `serialize()` function |

### Module Independence for Parallel Work

Each module has a clear I/O contract for parallel agent sessions:

```
Parser:     Tcl file path              → list[ProcEntry]  (diagnostics via on_diagnostic callback)
Compiler:   JSONs + proc_index         → CompiledManifest  (diagnostics embedded in manifest)
Trimmer:    CompiledManifest + domain  → trimmed files      (diagnostics in TrimResult)
Validator:  JSONs or domain            → list[Diagnostic]
CLI/Audit:  service results            → user-facing artifacts
```

### Daily Sync Gates

| Day | Gate | Verify With |
|-----|------|-------------|
| 0 | Foundation | `python -c "from chopper.core.models import ProcEntry, CompiledManifest, Diagnostic"` |
| 1 | Parser | `pytest tests/unit/test_parser.py` |
| 2 | Compiler + Tracer | `pytest tests/unit/test_compiler.py tests/unit/test_tracer.py` |
| 3 | Trimmer + Audit | Full lifecycle: VIRGIN → BACKUP → STAGING → TRIMMED |
| 4 | Validator + CLI | `chopper --help` and `chopper trim --dry-run` |
| 5 | Scanner + E2E | `make ci` all pass |

### Commit Rules

- < 300 LOC per commit, always include tests with feature code
- Format: `<module>: <what changed>` (e.g., `parser: implement brace tracking`)
- Every commit must pass: `ruff check`, `ruff format --check`, `mypy src/`, `pytest tests/unit/`

### Code Review Checklist

- Decision 5 (include wins) correctly implemented
- Trace expansion is breadth-first with sorted frontier (determinism)
- All file operations use `pathlib.Path` + POSIX normalization
- Diagnostic codes match `docs/DIAGNOSTIC_CODES.md`
- No `print()` in library code — service layer returns typed results
- Frozen dataclasses for compiled state; `tuple` not `list` for frozen fields
- `--dry-run` never modifies files

## Doc-Driven Development Lifecycle

Specs and docs are living documents. They MUST be consulted and updated throughout the coding lifecycle — not just at project start.

### Before Writing Code

1. **Read the module's spec** from the table in "Module Reference" above
2. **Read `docs/IMPLEMENTATION_PITFALLS_GUIDE.md`** for that module's pitfall section
3. **Read `docs/DIAGNOSTIC_CODES.md`** to verify any diagnostic codes you emit are registered
4. **Read `tests/FIXTURE_CATALOG.md`** to find pre-built test data for your module

### During Implementation

- If you discover a spec gap or ambiguity, **update the spec doc** with the resolution — do not leave it ambiguous for the next agent
- If you add a new diagnostic code, **register it in `docs/DIAGNOSTIC_CODES.md` first**, then add the constant to `core/diagnostics.py`
- If you change a module's public API signature, **update all references**: copilot-instructions.md module table, ACTION_PLAN.md, DEVELOPER_KICKOFF.md
- If you add a new test fixture, **register it in `tests/FIXTURE_CATALOG.md`**

### After Implementation

- **Update `docs/ENGINEERING_HANDOFF_CHECKLIST.md`** — check off completed items for your module
- **Update `docs/ACTION_PLAN.md`** — mark completed tasks
- If you resolved a pitfall scenario, **annotate `docs/IMPLEMENTATION_PITFALLS_GUIDE.md`** with the resolution

### Key Doc References (Always Kept Current)

| Doc | What to Check/Update |
|-----|---------------------|
| [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) | Module boundaries, Decision 5, trace algorithm, state machine |
| [docs/TECHNICAL_REQUIREMENTS.md](../docs/TECHNICAL_REQUIREMENTS.md) | Service contracts, compilation algorithm, validation phases, CLI spec |
| [docs/TCL_PARSER_SPEC.md](../docs/TCL_PARSER_SPEC.md) | Parser rules, diagnostic emission, edge cases |
| [docs/DIAGNOSTIC_CODES.md](../docs/DIAGNOSTIC_CODES.md) | Registry of all diagnostic codes — update BEFORE implementing new codes |
| [docs/IMPLEMENTATION_PITFALLS_GUIDE.md](../docs/IMPLEMENTATION_PITFALLS_GUIDE.md) | Known traps — annotate when resolved |
| [docs/ENGINEERING_HANDOFF_CHECKLIST.md](../docs/ENGINEERING_HANDOFF_CHECKLIST.md) | Progress tracking — check off items as completed |
| [docs/ACTION_PLAN.md](../docs/ACTION_PLAN.md) | Sprint tasks — mark done |
| [tests/FIXTURE_CATALOG.md](../tests/FIXTURE_CATALOG.md) | Test data inventory — add new fixtures here |
| [schemas/](../schemas/) | JSON schemas — update if adding/changing JSON fields |
