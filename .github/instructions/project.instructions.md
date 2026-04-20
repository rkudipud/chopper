---
applyTo: '**'
---

# Project Instructions

Authoritative conventions and guardrails for working in this codebase. Read this file at the start of every task. Add new rules here as patterns are discovered; never scatter project-level conventions across ad-hoc comments or other docs.

**Chopper v2** is a Python CLI tool that surgically trims VLSI EDA tool domains via JSON feature selection. It executes a 7-phase compilation pipeline: parse JSON → parse Tcl → merge & trace dependencies → apply decisions → generate output → validate → audit. The codebase is **docs-first, spec-driven** — all implementation details are pre-specified.

---

## Quick Setup

First time? Set up your environment with a platform-agnostic script:

| Platform | Shell | Command |
|----------|-------|----------|
| Unix/Linux/macOS | tcsh (PRIMARY) | `source setup.csh` |
| Unix/Linux/macOS | bash/zsh (fallback) | `source setup.sh` |
| Windows | PowerShell 5.1+ | `. .\setup.ps1` |
| Windows | cmd.exe | `setup.bat` |

tcsh is the primary Unix shell for this system. bash/zsh support is available as a fallback.

This creates `.venv`, activates it, and installs dev dependencies. See [SETUP_GUIDE.md](SETUP_GUIDE.md) for auto-activation and troubleshooting.

---

## Essential Commands

| Command | Purpose |
|---------|---------|
| `make install-dev` | Install dev dependencies (pytest, ruff, mypy) |
| `make check` | Fast gate: lint + format-check + type-check + unit tests |
| `make ci` | Full CI: all code quality + all test suites |
| `make test` / `make test-all` | Run all tests (unit, integration, golden, property) |
| `make lint` | Ruff linter |
| `make format` | Auto-format with Ruff |
| `make type-check` | mypy static type check |

**Coverage Requirement:** Minimum 78% line coverage (parser 85%, compiler 80%, trimmer 80%, enforced via pytest).

**Pre-Commit Gate:**

```bash
make check  # Lint + format-check + type-check + unit tests
make ci     # Full gate: all code quality + all test suites
```

---

## Architecture Overview

The codebase executes a **7-phase pipeline**:

```
F1 (Parse JSON)  →  F2 (Parse Tcl)  →  F3 (Merge & Trace)  →  F4 (Flow Actions)
   ↓
F5 (Run File Gen)  →  F6 (Validate Post)  →  F7 (Write & Audit)
```

**Core Modules** in `src/chopper/`:

| Module | Responsibility | Key Files | Phase |
|--------|-----------------|-----------|-------|
| `parser/` | Tcl static analysis; tokenize, extract proc defs, track namespaces | `parse.py`, `tokenizer.py` | F2 |
| `compiler/` | Merge JSON, trace proc dependencies (breadth-first), apply feature selections | `merge.py`, `trace.py`, `compiler.py` | F3–F4 |
| `trimmer/` | State machine to delete marked files/procs, rewrite Tcl | `trimmer.py` | F5 |
| `validator/` | Pre- and post-trim validation (schema, structure, brace balance, dangling refs) | `validator.py` | F1, F6 |
| `config/` | JSON/TOML schema loading and validation | `loaders.py`, `settings.py` | F1 |
| `cli/` | Command-line interface layer | `main.py`, `commands.py`, `render.py` | User layer |
| `core/` | Shared models (frozen dataclasses), errors, diagnostics, protocols, serialization | `models.py`, `errors.py`, `diagnostics.py`, `protocols.py`, `serialization.py` | All |
| `audit/` | Backup, restore, audit trail artifacts | `audit.py` | F7 |
| `generators/` | Run file generation | `run_file.py` | F5 |

**`tests/` layout:**

- `unit/` — Fast, isolated, no side effects
- `integration/` — End-to-end with `ChopperRunner` + fixtures
- `property/` — Hypothesis-based property tests
- `golden/` — Output contract tests (pytest-regressions)
- `fixtures/mini_domain/`, `namespace_domain/`, `tracing_domain/`, `edge_cases/` — Known test domains

---

## Critical Principles

### 1. Shared Models (Single Source of Truth)

All data models must live in `src/chopper/core/models.py` as frozen `dataclass`es. **Never create local copies.** Every module imports from core:

```python
from chopper.core.models import ProcEntry, CompiledManifest, FileTreatment
```

Example frozen dataclass:

```python
@dataclass(frozen=True)
class ProcEntry:
    name: str
    namespace: str
    line_no: int
    defined_in: Path
```

### 2. Diagnostic Codes (Authoritative Registry)

All diagnostic codes **must** be registered in [docs/DIAGNOSTIC_CODES.md](../../docs/DIAGNOSTIC_CODES.md) before use. See the **Diagnostic Codes** section below for the full contract (single source of truth, reference style, adding new codes, naming).

### 3. Path Handling

**Always use `pathlib.Path`** and POSIX-normalize:

```python
from pathlib import Path
p = Path("src/some/file.tcl").resolve()
```

**Never** hardcode paths or mix forward/backslashes.

### 4. Service Layer Discipline

- **No `print()` in library code.** Use structlog for logging.
- **Return typed objects** from service methods; let the CLI layer render.
- **Example:** A parser should return `ParserResult` (frozen dataclass), not print diagnostics.
- **Serialization:** All models must be JSON-serializable via `src/chopper/core/serialization.py`.

### 5. Determinism Required

Traces must be **breadth-first and reproducibly sorted**:

```python
# After BFS traversal, sort frontier lexicographically
frontier.sort(key=lambda x: x.name)
```

This ensures reproducible output across runs.

### 6. Explicit Include Wins

The merge algorithm's core rule: Explicit include **always** overrides exclude. Later features override earlier ones. See [docs/chopper_description.md](../../docs/chopper_description.md) §4 (Rule R1) for the rationale.

### 7. Trace Is Reporting-Only (Never Copies)

P4 BFS trace expansion (PI → PI+) produces `dependency_graph.json`, `TW-*` diagnostics, and the traced-only (PT) set **for visibility only**. Traced callees are **never** copied into the trimmed domain. Only procs named in `procedures.include` (directly or via whole-file `files.include`) survive.

- Example: JSON lists `foo`; `foo` calls `bar`. Trimmed output contains `foo`; `bar` appears in the call tree log and `dependency_graph.json` but is **not** copied.
- To keep `bar`, add it explicitly to `procedures.include`.
- Cycles emit `TW-04` and terminate safely via the BFS visited-set.

See [docs/chopper_description.md](../../docs/chopper_description.md) §5.4 for the authoritative contract and worked example.

---

## Documentation (Read These First)

All authoritative documentation lives under [docs/](../../docs/). Before implementing, consult these in order:

1. **[docs/chopper_description.md](../../docs/chopper_description.md)** — Single source of truth for product behavior, the 7-phase pipeline, R1 merge rules, and requirements (FR-xx / NFR-xx).
2. **[docs/TCL_PARSER_SPEC.md](../../docs/TCL_PARSER_SPEC.md)** — Parser engineering baseline: Tcl grammar rules, edge cases, tokenizer state machine, namespace resolution.
3. **[docs/RISKS_AND_PITFALLS.md](../../docs/RISKS_AND_PITFALLS.md)** — Technical risks (TC-01–TC-10) and implementation pitfalls (P-01–P-36) mapped to modules and test fixtures.
4. **[docs/DIAGNOSTIC_CODES.md](../../docs/DIAGNOSTIC_CODES.md)** — Authoritative diagnostic code registry (the `<FAMILY><SEV>-<NN>` scheme).
5. **[docs/CLI_HELP_TEXT_REFERENCE.md](../../docs/CLI_HELP_TEXT_REFERENCE.md)** — Complete CLI subcommand reference: `validate`, `trim`, `cleanup`, flags, examples.

Other key docs:

- [docs/chopper-gui-readiness-plan.md](../../docs/chopper-gui-readiness-plan.md) — GUI-readiness plan: typed results, JSON serialization, service-layer discipline.
- [docs/FUTURE_PLANNED_DEVELOPMENTS.md](../../docs/FUTURE_PLANNED_DEVELOPMENTS.md) — Roadmap items explicitly out of v1 scope.
- [docs/SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md](../../docs/SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md) — SNORT comparison and absorbed guardrails.
- [json_kit/docs/JSON_AUTHORING_GUIDE.md](../../json_kit/docs/JSON_AUTHORING_GUIDE.md) and [json_kit/schemas/](../../json_kit/schemas/) — Domain-owner authoring surface for base / feature / project JSONs.

---

## Documentation Conventions

- **No Addendum / Errata / "Clarifications" sections.** When a production review surfaces a clarification, inline the content into the section that owns the topic (the invariants, the algorithm step, the diagnostic table). Readers encounter docs in section order; appending trailing addendums fragments the reading model and lets the main body drift out of date.
- **Appendix sections are reserved for reference data tables** (file statistics, registries, mapping tables) — not for spec clarifications. If you find yourself writing prose in an appendix, it belongs in the main body.
- **Revision History is a log of conscious design decisions**, not a changelog of typo fixes or policy edicts. Each row must record the decision made and the alternative rejected so later readers understand the choice, not only the outcome.
- **No `Status:` / `Author:` / `Last Updated:` banners** at the top of spec files. The revision-history section is the living record of authorship and currency.

---

## Code Style

Enforced by Ruff:

- Line length: 120 characters
- `snake_case` functions/variables, `CamelCase` classes, `UPPER_CASE` constants
- Type hints on **all** public functions
- 4-space indentation

**Data Structures:**

- Frozen `dataclass` for records (immutable, hashable)
- `Enum` for vocabularies (e.g., `FileTreatment`, `Severity`)
- `Protocol` for alternate implementations (e.g., `ProgressSink`, `TableRenderer`)

---

## Module-Specific Guidance

### Parser — `src/chopper/parser/`

High-risk area. See [docs/TCL_PARSER_SPEC.md](../../docs/TCL_PARSER_SPEC.md) and pitfalls P-01, P-02, P-03.

- **P-01:** Quote context inside braced Tcl bodies → Only track quotes in non-braced words
- **P-02:** Backslash line continuation → Count lines separately, don't physically join
- **P-03:** Namespace stack not persisted → Use LIFO stack per block, pop on `namespace eval` exit
- **P-04:** Computed proc names silently ignored → Log WARNING, gracefully skip

Test fixtures: `tests/fixtures/edge_cases/` (14 adversarial Tcl inputs).

### Compiler — `src/chopper/compiler/`

Merge algorithm + breadth-first dependency tracing.

- Key constraint: Explicit include always wins
- Key constraint: Traces must be deterministically sorted
- See [docs/chopper_description.md](../../docs/chopper_description.md) §4 (R1) for merge semantics
- Test fixtures: `tests/fixtures/tracing_domain/` (cyclic procs, transitive closures)

### Trimmer — `src/chopper/trimmer/`

State machine to delete marked files and procs.

- Highest risk for partial deletes, dangling references
- Pitfalls P-08 to P-20 apply
- Must re-validate post-trim (F6)

### Validator — `src/chopper/validator/`

Pre-trim (F1) and post-trim (F6) validation.

- Pre-trim: schema, structure, file existence
- Post-trim: brace balance, dangling proc refs, namespace consistency
- See pitfalls P-21 to P-31

### Config — `src/chopper/config/`

JSON/TOML schema loading.

- Uses `jsonschema` library
- Schemas defined in `json_kit/schemas/base-v1.schema.json`, `feature-v1.schema.json`, `project-v1.schema.json`

---

## Testing Strategy

Full details in [tests/TESTING_STRATEGY.md](../../tests/TESTING_STRATEGY.md).

**Testing Standards:**

- Minimum 78% line coverage (parser 85%, compiler 80%, trimmer 80%)
- Unit tests isolated, use `tmp_path` fixture
- Integration tests use fixtures from `tests/fixtures/`
- Property tests with hypothesis (500 examples)
- Golden files via pytest-regressions for output contracts

**Golden Files** (output regression tests):

- Stored in `tests/golden/`
- Use pytest-regressions (`assert_regressions.json()`)
- Example: Parser output contract tests in `tests/unit/parser/`

**Fixtures:**

- `tests/fixtures/mini_domain/` — Minimal valid domain (3 procs, 2 files, 1 feature)
- `tests/fixtures/namespace_domain/` — Namespace resolution test case
- `tests/fixtures/tracing_domain/` — Breadth-first trace validation
- `tests/fixtures/edge_cases/` — 14 adversarial Tcl inputs for parser

**Coverage Thresholds:**

- Overall: 78%
- Parser: 85%
- Compiler: 80%
- Trimmer: 80%

---

## Implementation Stages

Chopper is built stage-by-stage along module dependency boundaries. Each stage is gated by its own test scope and must be complete before the next begins.

| Stage | Module(s) | Deliverable |
|---|---|---|
| Stage 0 — Foundation | `core/` | Shared frozen models, errors, diagnostics, protocols, serialization |
| Stage 1 — Parser | `parser/` | `parse_file()` returning `list[ProcEntry]`; all fixtures in [tests/FIXTURE_CATALOG.md](../../tests/FIXTURE_CATALOG.md) pass |
| Stage 2 — Compiler & Trace | `config/`, `compiler/` | JSON loading, P3 provenance-aware merge, P4 BFS trace; `compiled_manifest.json` and `dependency_graph.json` are byte-stable |
| Stage 3 — Trimmer & Lifecycle | `trimmer/`, `generators/`, `audit/` | Trim state machine, domain backup/restore, crash recovery, F3 run-file generation, `trim_report.json` |
| Stage 4 — Validator | `validator/` | Pre- and post-trim validation, `--strict` escalation, VE/VW/VI emission |
| Stage 5 — CLI & Integration | `cli/` | `validate`, `trim`, `cleanup` subcommands; `--project` resolution; end-to-end scenarios in [tests/TESTING_STRATEGY.md](../../tests/TESTING_STRATEGY.md) pass |

Stage boundaries are hard: earlier stages must not depend on later ones, and a later stage cannot be declared started until the previous stage's test scope is green.

---

## Production Constraints

1. **≤1 GB codebase** — No streaming I/O; simple `file.read_text()`
2. **3–5 min runtime acceptable** — No performance optimization required
3. **No scope creep** — Implement spec only; no extra features
4. **Modularity is core** — Each module independently testable and replaceable
5. **Tcl parser can have bugs** — Graceful fallback via warnings/diagnostics
6. **Locking lowest priority** — Simple backup/restore; user handles crashes
7. **GUI readiness required** — Typed results, JSON-serializable, no bare `print()` in library

---

## Common Workflow

**New Implementation Task:**

1. Read specification from [docs/chopper_description.md](../../docs/chopper_description.md) for your phase and R1 merge rules
2. Check [docs/RISKS_AND_PITFALLS.md](../../docs/RISKS_AND_PITFALLS.md) for your module's risks and pitfalls
3. Write tests first in `tests/unit/<module>/` or `tests/integration/`
4. Reference shared models from `src/chopper/core/models.py` only
5. Register diagnostics in [docs/DIAGNOSTIC_CODES.md](../../docs/DIAGNOSTIC_CODES.md) before use
6. Run `make check` before commit

**When Stuck:**

- Check [docs/RISKS_AND_PITFALLS.md](../../docs/RISKS_AND_PITFALLS.md) for your module
- Review test fixtures in `tests/fixtures/` — they exemplify expected behavior
- Consult [docs/chopper_description.md](../../docs/chopper_description.md) for the phase contract and R1 rules
- Search test files for similar patterns

---

## Diagnostic Codes

### Single Source of Truth

`docs/DIAGNOSTIC_CODES.md` is the **only** file that houses diagnostic codes. It is the single source of truth for every code in the `VE`, `VW`, `VI`, `TW`, `PE`, `PW`, and `PI` families.

- All other documentation and implementation code **must reference codes by their identifier** (e.g., `VE-06`), never by their prose description.
- If a description changes, the identifier stays stable — all cross-references remain accurate automatically.
- No other file may define, duplicate, or restate code metadata such as severity, phase, source, exit behavior, slug, description, or recovery hint.
- Diagnostic code tables outside `docs/DIAGNOSTIC_CODES.md` are not allowed.

### Reference Style (Required Outside the Registry)

When any file outside `docs/DIAGNOSTIC_CODES.md` mentions diagnostics:

- Use the exact code token only (for example: `PE-01`, `PW-11`, `TW-02`).
- Link or refer to the registry using a workspace-relative path: `docs/DIAGNOSTIC_CODES.md`.
- Use section-level references when needed (for example: "see `docs/DIAGNOSTIC_CODES.md`, Parse Warnings").
- Keep wording behavioral and local (for example: "emit `PW-11` in this branch"), not definitional.

Forbidden outside the registry:

- Rewriting what a code means (description, severity, hint, exit code, slug, etc.).
- Recreating code catalogs, mapping tables, or expanded code glossaries.
- Introducing aliases or ad-hoc variants (for example: `TRACE-AMBIG-01`).

### Adding a New Code

1. **Pick the lowest available reserved slot** in the correct `<FAMILY><SEV>` band from the Code Space Summary table in `docs/DIAGNOSTIC_CODES.md`.
2. **Fill in the row** following the exact column structure of the existing table — code, phase, source, exit, description, recovery hint.
3. **Update the Active / Reserved counts** in the Code Space Summary table.
4. **Implement the constant** in `src/chopper/core/diagnostics.py` before any code references it.
5. **Reference it by code only** in any documentation or test assertions.

Do not invent ad-hoc codes or reuse retired slots. Reserved rows exist precisely so new codes have a home — use them in sequence.

### Naming Convention (recap)

Codes follow `<FAMILY><SEV>-<NN>`: family (`V`, `T`, `P`) + severity (`E`, `W`, `I`) + two-digit sequence. Example: `VE-06` = Validation Error #6, `PW-04` = Parse Warning #4.

### Diagnostic Workflow

When adding a new diagnostic:

1. Assign code from the correct `<FAMILY><SEV>` band using the lowest available reserved slot (never renumber existing rows).
2. Register in [docs/DIAGNOSTIC_CODES.md](../../docs/DIAGNOSTIC_CODES.md) with slug, phase, source, exit code, description, and recovery hint.
3. Create `Diagnostic` instance using `src/chopper/core/diagnostics.py`.
4. Add test in appropriate test file (unit, integration, or golden).
5. Run `make ci` to ensure coverage and linting pass.

Example:

```python
# In your module
from chopper.core.diagnostics import Diagnostic

# In tests
def test_parser_undefined_proc():
    diag = Diagnostic(code="PW-05", severity="warning", message="Unresolvable proc call: foo", line_no=42)
    assert diag.code == "PW-05"
```

---

## Editing Conventions

### No Addendums

Never append a change as an addendum at the end of a document. Make the edit **in place**, in the section where the content belongs. If a document is out of date, update it directly — do not accumulate footnotes or trailing corrections.

### Cascading Updates

When content changes in one document, scan for all documents that reference or depend on that content and update them in the same pass. A change is only complete when every related reference is consistent. Leaving supporting documents stale causes misinformation and erodes the single-source-of-truth principle.

This applies to:

- Diagnostic code descriptions (registry → implementation constants → test assertions → docs)
- Architecture decisions (design doc → technical requirements → risks and pitfalls guide)
- CLI flag names or schema fields (spec → help text → user reference manual)

### Targeted, In-Place Edits

Every edit must be made at the correct location in the correct document. Do not make a change in one place and leave related content elsewhere outdated. Always consider the broader impact of a change before committing it.

---

<!-- Add new sections below as project conventions grow. -->
