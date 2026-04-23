# Chopper — Technical Guide

Architecture overview for developers integrating, extending, or debugging Chopper. This is the short architectural map: use it to understand the system shape, major modules, ports, diagnostics, and runtime phases without reading every service in detail. For the code-level walkthrough, diagrams, and test-system explanation, see [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md). For the full specification, see [`../technical_docs/chopper_description.md`](../technical_docs/chopper_description.md) and [`../technical_docs/ARCHITECTURE_PLAN.md`](../technical_docs/ARCHITECTURE_PLAN.md).

---

## System Shape

Chopper is a single-process, single-threaded Python CLI. It reads JSON inputs and Tcl source files from disk, and produces a trimmed domain directory plus an audit bundle.

```text
                 ┌────────────────────────────────────┐
 JSON inputs ──► │  chopper [validate | trim | cleanup]│
 Tcl sources ──► │                                    │ ──► trimmed domain/
                 │  8-phase pipeline (P0 … P7)         │ ──► .chopper/ audit bundle
                 └────────────────────────────────────┘
```

No network, no daemon, no plugin host, no parallelism. Deterministic output byte-for-byte given the same inputs.

---

## The 8-Phase Pipeline

Every live `trim` run executes this sequence:

| Phase | Name | Responsibility |
| --- | --- | --- |
| **P0** | Domain state | Detect whether `<domain>/` and `<domain>_backup/` exist; classify first-trim vs re-trim vs recovery |
| **P1** | Config + pre-validate | Load base + feature JSONs, resolve `depends_on`, schema-validate, check file/proc existence |
| **P2** | Parse Tcl | Tokenize all `.tcl` files, extract `ProcEntry` records (definitions, calls, namespaces) |
| **P3** | Compile | Apply R1 merge rules across base + features; produce `CompiledManifest` with per-file treatments |
| **P4** | Trace | BFS from explicit proc includes; emit `dependency_graph.json` and `TW-*` diagnostics. **Reporting only — no auto-copy.** |
| **P5** | Build output | Execute file-level copies and proc-level rewrites. Emit F3 run scripts (`<stage>.tcl`). |
| **P6** | Post-validate | Re-parse trimmed output; check brace balance, dangling references, namespace consistency |
| **P7** | Audit | Write `.chopper/` bundle (always runs, even on prior failure) |

`validate` uses the same read-only front half of the engine: P0, P1, P2, P3, P4, then a manifest-only P6 pass. It skips P5 filesystem rebuild work and stage-file emission.

Phases are executed sequentially by `ChopperRunner.run(ctx)` in `src/chopper/orchestrator/`. Each phase is a service function with a typed input/output contract.

---

## Module Layout

```text
src/chopper/
├── core/            Shared frozen dataclasses, diagnostics, protocols, serialization
├── config/          JSON/TOML loading, schema validation, depends_on topo-sort       (P1)
├── parser/          Tcl tokenizer, proc extractor, namespace tracker, call extractor (P2)
├── compiler/        R1 merge algorithm, BFS trace, F3 flow-actions                   (P3, P4)
├── trimmer/         File copier, proc dropper, state machine                         (P5)
├── validator/       Pre- and post-trim validation (plain module functions)           (P1, P6)
├── generators/      F3 run-file emitter (`<stage>.tcl` only in v1)                   (P5)
├── audit/           .chopper/ bundle writers, SLOC counter, hashing                  (P7)
├── orchestrator/    ChopperRunner, phase-gate logic, domain-state detection          (all)
├── adapters/        Concrete port implementations (fs, sinks, progress)              (all)
└── cli/             argparse wiring, render helpers, three subcommand handlers       (user)
```

Each service package depends only on `core/` and its own submodules. No cross-service imports.

---

## Data Flow

### ChopperContext: the per-run container

```python
@dataclass(frozen=True)
class ChopperContext:
    config: RunConfig
    fs: FileSystemPort
    diag: DiagnosticSink
    progress: ProgressSink
```

`ChopperContext` is constructed once by the CLI layer. Services never construct adapters; they receive them via `ctx`. This makes every service unit-testable with in-memory filesystems and collecting sinks.

`PresentationConfig` exists in `core/context.py`, but it is CLI-local and is not carried on `ChopperContext`.

### RunResult: the structured output

```python
@dataclass(frozen=True)
class RunResult:
    exit_code: int
    summary: DiagnosticSummary
    state: DomainState | None
    loaded: LoadedConfig | None
    parsed: ParseResult | None
    manifest: CompiledManifest | None
    graph: DependencyGraph | None
    trim_report: TrimReport | None
    generated_artifacts: tuple[GeneratedArtifact, ...]
```

The CLI renderer consumes `RunResult` plus the diagnostic snapshot from the sink. Missing later-phase fields stay `None` when a run aborts early.

---

## Ports and Adapters

Chopper uses a narrow hexagonal layout. Three ports live in `src/chopper/core/protocols.py`:

| Port | Purpose | Adapters |
| --- | --- | --- |
| `FileSystemPort` | Read/write files | `LocalFS` (prod), `InMemoryFS` (tests) |
| `DiagnosticSink` | Collect `Diagnostic` records | `CollectingSink` |
| `ProgressSink` | User-facing progress output | `RichProgress` (prod), `SilentProgress` (tests / `--quiet`) |

Services depend only on the `Protocol` types, not the concrete adapters.

### What is **not** a port

By design, these are direct calls, not ports:

- **Clock / time** — services call `datetime.now()` directly
- **Serialization** — `core/serialization.dump_model()` is a plain helper
- **Audit storage** — writers use `ctx.fs` directly
- **CLI rendering** — `rich` is a CLI-local concern
- **JSON schema** — `jsonschema` is called directly

This keeps the port surface narrow and the project free of speculative abstractions.

---

## Diagnostics

Every user-visible outcome goes through `ctx.diag.emit(Diagnostic(...))`. Every diagnostic has a stable code from the registry in [`../technical_docs/DIAGNOSTIC_CODES.md`](../technical_docs/DIAGNOSTIC_CODES.md).

Code families:

| Prefix | Phase | Example |
| --- | --- | --- |
| `VE-`, `VW-`, `VI-` | Validation (P1 / P6) | `VE-17 project-domain-mismatch` |
| `PE-`, `PW-`, `PI-` | Parser (P2) | `PW-01 dynamic-proc-name` |
| `TW-` | Trace (P4) | `TW-04 cycle-in-call-graph` |

Codes are registered exclusively in the registry file; the code constants in `src/chopper/core/_diagnostic_registry.py` mirror it 1:1. A CI check (`scripts/check_diagnostic_registry.py`) enforces the mirror.

### Severity and exit codes

| Severity | Exit code | `--strict` effect |
| --- | --- | --- |
| Error | 1 | — |
| Warning | 0 | Becomes exit 1 |
| Info | 0 | No change |
| Internal error (uncaught) | 3 | No change |

`--strict` is **exit-code policy only** — it never rewrites `Diagnostic.severity`.

---

## Determinism Contract

Chopper guarantees byte-identical output for identical inputs. This is enforced by:

| Mechanism | Where |
| --- | --- |
| Sorted BFS frontier | `compiler/trace_service.py` — frontier sorted lexicographically each iteration |
| Sorted map keys in JSON writers | `audit/writers.py` — all `json.dumps(..., sort_keys=True)` |
| Stable insertion order in diagnostic sink | `adapters/sink_collecting.py` — preserves emission order |
| POSIX path normalization | Paths serialized as forward-slashed, domain-relative strings |
| No `set()` iteration in output paths | Use `sorted(set(...))` or `dict.fromkeys(...)` |

Property tests in `tests/property/` assert determinism by running the same inputs twice and comparing outputs.

---

## Testing Layout

```text
tests/
├── unit/         Fast, isolated, in-memory filesystem, no side effects
├── integration/  End-to-end ChopperRunner + real fixtures
├── golden/       Output regression tests via pytest-regressions
├── property/     Hypothesis-based (500 examples per test)
└── fixtures/     Known test domains + 17 parser edge cases
```

**Coverage floor:** 78% overall, 85% parser, 80% compiler, 80% trimmer. Enforced via pytest.

Run:

```powershell
make check   # lint + format + type-check + unit
make ci      # full: all quality gates + all test suites
```

---

## Build and Quality Gates

### Makefile targets

| Target | Purpose |
| --- | --- |
| `make install-dev` | Install dev dependencies (pytest, ruff, mypy, hypothesis, pytest-regressions) |
| `make lint` | Ruff linter |
| `make format` | Ruff formatter |
| `make type-check` | mypy (strict on `core/`, no-`Any` elsewhere) |
| `make test` | All test suites |
| `make check` | lint + format-check + type-check + unit |
| `make ci` | Full gate: every quality check + every test suite |

### Layered architecture enforcement

`pyproject.toml` configures `import-linter` contracts that enforce:

- `core/` has no dependencies on other Chopper packages
- Services import only from `core/` and their own submodules
- `cli/` is the only package allowed to construct adapters

A CI script (`scripts/check_service_signatures.py`) also verifies that service signatures in source match the documented §9.2 contracts.

---

## Performance Envelope

| Dimension | Target |
| --- | --- |
| Domain size | ≤ 1 GB |
| Runtime | 3–5 minutes acceptable |
| Memory | Whole-file reads (no streaming) |
| Parallelism | Single-threaded |

Performance was deliberately deprioritized in v1 in favor of correctness and determinism. A `make bench` harness is deferred (`FD-09`).

---

## Error Handling Model

Three layers:

1. **User-visible outcomes** — always a `Diagnostic` emitted via `ctx.diag`. Exit codes 0, 1, 2.
2. **Programmer errors** — raise a `ChopperError` subclass from `core/errors.py`. Caught by the runner's final `except`, surfaced as exit 3.
3. **Unexpected exceptions** — same path as (2).

No bare `print()` in library code. No bare `except:`. Every error path is typed.

---

## The `.chopper/` Audit Bundle

Written by `audit/service.py` in P7. Always runs, even on prior phase failure (inputs may be `None`; each writer tolerates missing data).

| Artifact | Writer | Always written? |
| --- | --- | --- |
| `run_id` | `render_run_id` | Yes |
| `chopper_run.json` | `render_chopper_run` | Yes |
| `compiled_manifest.json` | `render_compiled_manifest` | Yes |
| `dependency_graph.json` | `render_dependency_graph` | Yes |
| `trim_report.json` | `render_trim_report_json` | Yes |
| `trim_report.txt` | `render_trim_report_txt` | Yes |
| `trim_stats.json` | `render_trim_stats` | Yes |
| `diagnostics.json` | `render_diagnostics` | Yes |
| `input_base.json` | `AuditService._copy_inputs` | If config load succeeded |
| `input_features/NN_name.json` | `AuditService._copy_inputs` | If features were selected |

Earlier-phase data may be missing, but the renderers still emit valid JSON shells with empty or `null` fields so audit output exists even after partial failure.

All JSON written with deterministic key order, UTF-8, and a trailing newline.

---

## Extension Points (for Contributors)

### Adding a diagnostic code

1. Open [`../technical_docs/DIAGNOSTIC_CODES.md`](../technical_docs/DIAGNOSTIC_CODES.md) and claim the lowest reserved slot in the appropriate family.
2. Fill in the registry row.
3. Mirror in `src/chopper/core/_diagnostic_registry.py`.
4. Reference by code (e.g., `VE-42`) from services and tests.
5. `make check` — the registry-mirror CI check will catch any drift.

### Adding a capability

Not allowed without a spec edit. See `.github/instructions/project.instructions.md` §1 ("Closed Decisions") and §2 ("Single Authority: The Bible") for the scope-lock policy. Proposals go to [`../technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md`](../technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md) as `FD-xx` entries.

### Hot spots for future work

Tracked in [`../technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md`](../technical_docs/FUTURE_PLANNED_DEVELOPMENTS.md):

- `FD-09` — optional parallelism (post-correctness)
- `FD-10` — machine-readable CLI output (for GUI client)
- `FD-11` — multi-platform domain support

---

## Where to Go Next

- **Day-to-day operator reference** → [`USER_MANUAL.md`](USER_MANUAL.md)
- **JSON authoring patterns and FAQ** → [`BEHAVIOR_GUIDE.md`](BEHAVIOR_GUIDE.md)
- **Full specification** → [`../technical_docs/chopper_description.md`](../technical_docs/chopper_description.md)
- **Architecture plan** → [`../technical_docs/ARCHITECTURE_PLAN.md`](../technical_docs/ARCHITECTURE_PLAN.md)
- **Parser spec** → [`../technical_docs/TCL_PARSER_SPEC.md`](../technical_docs/TCL_PARSER_SPEC.md)
- **Risks and pitfalls** → [`../technical_docs/RISKS_AND_PITFALLS.md`](../technical_docs/RISKS_AND_PITFALLS.md)
