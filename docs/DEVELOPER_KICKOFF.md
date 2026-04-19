# Chopper — Developer Kickoff Guide

> **Status:** Pre-Implementation Reference
> **Audience:** AI agents and developers starting implementation

---

## 1. Pre-Implementation Checklist

Before writing any code for a module, the agent or developer MUST:

- [ ] Read `docs_old/ARCHITECTURE.md` (Rev 22) — product behavior and decisions
- [ ] Read `docs_old/TECHNICAL_REQUIREMENTS.md` (Rev 11) — implementation contracts
- [ ] Read `docs/DIAGNOSTIC_CODES.md` — authoritative code registry
- [ ] Read the module-specific spec section (see Module Reference below)
- [ ] Read `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` — common mistakes to avoid
- [ ] Create `src/chopper/core/models.py` with shared dataclasses (Day 0 task — not yet implemented)

---

## 2. Module Reference — What to Read Per Assignment

| Module | Primary Spec | Pitfalls | Key Sections |
|---|---|---|---|
| **Core/Foundation** | docs_old/TECHNICAL_REQUIREMENTS.md §3, §4, §5 | — | Models, errors, serialization, protocols |
| **Parser** | docs/TCL_PARSER_SPEC.md (full document) | P-01 through P-07 | Tokenizer §3, Proc detection §4, Call extraction §5 |
| **Compiler** | docs_old/TECHNICAL_REQUIREMENTS.md §7.1.1 | P-08, P-09, P-10, P-11, P-12 | Compilation algorithm (7 phases) |
| **Tracer** | docs_old/ARCHITECTURE.md §4.3 | P-08 | Trace expansion, namespace resolution |
| **Trimmer** | docs_old/ARCHITECTURE.md §2.8, TRQ §7.3, §7.4 | P-13, P-15, P-20 | Backup detection, staging, proc deletion |
| **Validator** | docs_old/TECHNICAL_REQUIREMENTS.md §8.3 | P-16 | Phase 1 + Phase 2 check matrices |
| **Audit** | docs_old/TECHNICAL_REQUIREMENTS.md §7.2 | — | Artifact contracts, field requirements |
| **CLI** | docs_old/TECHNICAL_REQUIREMENTS.md §9.1 | — | Argparse, service layer, renderers |
| **Scanner** | docs_old/ARCHITECTURE.md §3.7, §5.6 | — | Scan pipeline, draft generation |

---

## 3. Shared Data Models — DO NOT DUPLICATE

> **Status:** Day 0 task — `src/chopper/core/` does not yet exist. The Day 0 agent must create all files below before any other module begins.

These files are the single source of truth. All modules import from them:

| File | Status | Contents |
|---|---|---|
| `src/chopper/core/models.py` | **Pending** | ALL frozen dataclasses: `ProcEntry`, `FileEntry`, `CompiledManifest`, `Diagnostic`, `StageDefinition`, `TrimStats`, `RunSelection`, enums (`ExitCode`, `FileTreatment`, `KeepReason`, `Severity`, `DiagnosticSource`, `TrimMode`) |
| `src/chopper/core/errors.py` | **Pending** | `ChopperError` hierarchy with exit codes |
| `src/chopper/core/diagnostics.py` | **Pending** | Diagnostic code constants (V-xx, TRACE-xx, PARSER-xx) |
| `src/chopper/core/protocols.py` | **Pending** | Protocol interfaces: `ProgressSink`, `ProgressEvent`, `TableRenderer`, `DiagnosticRenderer` |
| `src/chopper/core/serialization.py` | **Pending** | `ChopperEncoder`, `serialize()` function |

**Rule:** NEVER create a local copy of these models. If a model needs a new field, update the shared file and coordinate.

---

## 4. First Commit Acceptance Criteria

Every commit must pass:

- [ ] `ruff check src/ tests/` — no lint errors
- [ ] `ruff format --check src/ tests/` — formatting compliant
- [ ] `mypy src/chopper/` — type check passes
- [ ] `pytest tests/unit/` — unit tests for the module pass
- [ ] No bare `print()` or `logging.basicConfig()` calls in library code
- [ ] All public functions have type hints
- [ ] All diagnostic codes used are registered in `docs/DIAGNOSTIC_CODES.md`
- [ ] All file paths use `pathlib.Path`, not raw strings

---

## 5. Code Review Checklist

| Check | Why |
|---|---|
| Decision 5 (include wins) correctly implemented | Core product correctness |
| Trace expansion is breadth-first with sorted frontier | Determinism requirement |
| All file operations use `pathlib.Path` + POSIX normalization | Cross-platform safety |
| Diagnostic codes match `DIAGNOSTIC_CODES.md` | Registry consistency |
| No hardcoded paths or OS-specific handling | Portability |
| No `print()` in library code | Logging contract |
| Frozen dataclasses for compiled state | Immutability contract |
| `tuple` instead of `list` for frozen dataclass fields | Hashability |
| Service layer returns typed results, never prints | GUI readiness |

---

## 6. Test Execution Order — Critical Path

> **Current state:** Only smoke tests exist (`tests/unit/test_package_smoke.py`, `tests/integration/test_smoke.py`, `tests/property/test_smoke.py`). All test cases below are targets to be written as modules are implemented. Fixtures in `tests/fixtures/` are in place and ready.

### CRITICAL (Must pass before module is considered done)

**Parser:**
- `parser_basic_single_proc.tcl` — baseline
- `parser_basic_multiple_procs.tcl` — no overlapping spans
- `parser_empty_file.tcl` — empty index, no error
- `parser_nested_namespace_accumulates.tcl` — namespace resolution
- `parser_namespace_reset_after_block.tcl` — stack pop timing
- `parser_comment_with_braces_ignored.tcl` — brace tracking in comments

**Compiler:**
- Decision 5: explicit include wins over exclude
- Feature ordering: later features see earlier results
- Glob expansion + deduplication + sorting
- Trace expansion: deterministic breadth-first sorted frontier

**Trimmer:**
- Proc deletion: surrounding code preserved, comments associated

**Integration :**
- `chopper trim --dry-run` does not modify any files
- `chopper validate` returns exit 0/1 correctly
- `chopper trim` end-to-end on mini_domain

### BLOCKING (Must pass before release)

- Re-trim from backup produces identical output
- `--project` mode produces identical results to `--base`/`--features`
- All Phase 1 validation checks (V-01 through V-18) tested
- All Phase 2 validation checks (V-20 through V-26) tested
- Golden output comparison for mini_domain

### OPTIONAL (Nice to have for v0.1.0)

- Property-based tests (PB-01 through PB-06)
- Parser edge cases: computed name, encoding fallback, duplicate proc
- F3 flow actions: all 9 action types tested
- `chopper scan` on mini_domain produces valid artifacts

---

## 7. Multi-Agent Coordination

### Shared Contract Rule

`src/chopper/core/` is shared infrastructure. If two agents need to modify it:

1. **Day 0 agent** creates ALL shared files first
2. Subsequent agents IMPORT from `core/`, never redefine
3. If a model needs a new field, the change is made in `core/models.py` and tested before the module that needs it proceeds

### Daily Sync Points

| Day | Checkpoint | How to Verify |
|---|---|---|
| 0 | Foundation complete | `python -c "from chopper.core.models import ProcEntry, CompiledManifest, Diagnostic"` |
| 1 | Parser produces ProcEntry | Run parser unit tests: `pytest tests/unit/test_parser.py` |
| 2 | Compiler produces CompiledManifest | Run compiler unit tests: `pytest tests/unit/test_compiler.py` |
| 3 | Trimmer writes domain output | Run trimmer unit tests + mini_domain integration |
| 4 | CLI dispatches all subcommands | `chopper --help`, `chopper trim --dry-run --base tests/fixtures/mini_domain/jsons/base.json` |
| 5 | Full workflow passes | `pytest tests/integration/` |

### Commit Strategy

- Small, frequent commits (< 300 LOC per commit)
- Always include test coverage with feature code
- Commit message format: `<module>: <what changed>` (e.g., `parser: implement brace tracking`)
- Mark incomplete work as `WIP:` in commit message

---

## 8. Package Entry Points

> **Status:** Target API — no submodules are implemented yet. `src/chopper/` currently contains only `__init__.py`. After Day 0 these imports should become valid:

```python
# Core
from chopper.core.models import ProcEntry, CompiledManifest, Diagnostic
from chopper.core.errors import ChopperError, ParseError, CompilationError
from chopper.core.diagnostics import DiagnosticCodes

# Parser
from chopper.parser.tcl_parser import parse_file  # (domain_path, file_path, on_diagnostic?) -> list[ProcEntry]

# Compiler
from chopper.compiler.compiler import compile_selection  # (base, features, domain, proc_index) -> CompiledManifest
from chopper.compiler.tracer import trace_expand  # (seeds, proc_index) -> traced_set

# Trimmer
from chopper.trimmer.trimmer import TrimService  # .execute(TrimRequest) -> TrimResult
from chopper.trimmer.backup import detect_backup_exists  # (domain_path) -> bool

# Validator
from chopper.validator.phase1 import validate_phase1  # (inputs) -> list[Diagnostic]
from chopper.validator.phase2 import validate_phase2  # (domain, manifest) -> list[Diagnostic]

# CLI
from chopper.cli.main import main  # CLI entry point

# Scanner
from chopper.generators.scanner import ScanService  # .execute(ScanRequest) -> ScanResult
```

---

## 9. Environment Setup

```bash
# Clone and setup
cd /path/to/chopper

# Bash shells
source setup.sh

# tcsh shells (from the repo root)
source setup.csh

# If the venv already exists, activate it directly:
#   bash/zsh: source .venv/bin/activate
#   tcsh:     source .venv/bin/activate.csh

# Verify
make check  # lint + type-check + unit tests
```

Required dev dependencies (in `pyproject.toml`):
- `pytest >= 7.0`
- `pytest-cov`
- `hypothesis >= 6.0` (property-based testing)
- `ruff >= 0.4.0`
- `mypy >= 1.8`
- `structlog >= 24.1.0`
- `jsonschema >= 4.0`
- `rich >= 13.0` (optional, for TTY rendering)

---

## 10. Current Repo Layout (April 2026)

> This reflects the actual directory state. Modules listed as **Pending** do not yet exist and are Day 0 deliverables.

```
chopper_v2/
├── AGENTS.md                         # Agent instructions (authoritative)
├── Makefile                          # make check / make ci / make test
├── pyproject.toml                    # Package metadata + dev dependencies
├── setup.csh / setup.sh / setup.ps1  # Environment setup scripts
│
├── docs/                             # ACTIVE specification documents
│   ├── CLI_HELP_TEXT_REFERENCE.md
│   ├── DIAGNOSTIC_CODES.md           # Authoritative diagnostic code registry
│   ├── FUTURE_PLANNED_DEVELOPMENTS.md
│   ├── IMPLEMENTATION_PITFALLS_GUIDE.md
│   ├── SNORT_ANALYSIS_AND_CHOPPER_COMPARISON.md
│   └── TCL_PARSER_SPEC.md
│
├── docs_old/                         # ARCHIVED pre-implementation specs
│   ├── ARCHITECTURE.md               # Rev 22 — primary design reference
│   ├── DEVELOPER_KICKOFF.md          # This file
│   ├── ENGINEERING_HANDOFF_CHECKLIST.md
│   ├── TECHNICAL_REQUIREMENTS.md     # Rev 11 — phase contracts
│   ├── TECHNICAL_PRESENTATION_DECK.md
│   └── USER_REFERENCE_MANUAL.md
│
├── schemas/                          # JSON schemas (root-level, authoritative)
│   ├── base-v1.schema.json
│   ├── feature-v1.schema.json
│   └── project-v1.schema.json
│
├── chopper_json_kit/                 # JSON authoring aid and examples
│   ├── AGENTS.md
│   ├── README.md
│   ├── schemas/                      # Mirror of root schemas
│   └── examples/                     # 11 annotated JSON examples (01–11)
│
├── src/chopper/                      # IMPLEMENTATION ROOT
│   └── __init__.py                   # Package stub only — all below are PENDING
│   # core/        ← Pending: models, errors, diagnostics, protocols, serialization
│   # parser/      ← Pending: tcl_parser, tokenizer
│   # compiler/    ← Pending: merge, trace, compiler
│   # trimmer/     ← Pending: trimmer, lifecycle
│   # validator/   ← Pending: phase1, phase2
│   # audit/       ← Pending: audit
│   # generators/  ← Pending: run_file, scanner
│   # cli/         ← Pending: main, commands, render
│
└── tests/
    ├── unit/
    │   ├── test_package_smoke.py     # Package import smoke test only
    │   └── __init__.py
    ├── integration/
    │   ├── test_smoke.py             # Smoke test only
    │   ├── crash_harness.py
    │   └── __init__.py
    ├── property/
    │   ├── test_smoke.py             # Smoke test only
    │   └── __init__.py
    ├── fixtures/
    │   ├── mini_domain/              # 3 procs, 2 files, 1 feature
    │   ├── namespace_domain/         # Namespace resolution test case
    │   ├── tracing_domain/           # BFS trace validation
    │   └── edge_cases/               # 14 adversarial Tcl inputs
    └── golden/                       # Output regression snapshots (empty)
```

### Documentation Navigation

| Need | Location |
|---|---|
| Architecture decisions (D-1 to D-9) | `docs_old/ARCHITECTURE.md` |
| Phase-by-phase implementation contracts | `docs_old/TECHNICAL_REQUIREMENTS.md` |
| Tcl grammar and parser edge cases | `docs/TCL_PARSER_SPEC.md` |
| All known pitfalls by module | `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` |
| Diagnostic code registry | `docs/DIAGNOSTIC_CODES.md` |
| JSON authoring reference | `chopper_json_kit/docs/JSON_AUTHORING_GUIDE.md` |
| CLI flags and help text | `docs/CLI_HELP_TEXT_REFERENCE.md` |
