# Chopper v2 — Implementation Roadmap

The Day-0 handoff for engineering agents and humans. Every stage has a clear goal, a fixed test gate, a definition of done, a demo checkpoint, and a hand-off criterion to the next stage. No stage begins until the previous stage's gate is green.

**Authority.** This document is subordinate to [`chopper_description.md`](chopper_description.md) (the bible) and [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md). Where they disagree, the bible wins and this roadmap is edited. This roadmap never adds behavior the bible does not mandate.

**Read this first.** Every engineer reads:

1. [`chopper_description.md`](chopper_description.md) §1–§5 (problem, scope, capability model, R1 rules, pipeline)
2. [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §1–§10 (modules, ports, services, sink, inter-service contract)
3. [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) (for any parser work)
4. [`RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) for the module being worked on
5. [`DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) before emitting any diagnostic
6. This document

Skip any of the above and the stage gate will fail.

---

## End-to-End Engineering Picture

**What Chopper does in one sentence:** Load base+feature JSONs → parse domain Tcl → compute what to keep (F1 files, F2 procs, F3 stages) → write trimmed domain to disk.

**The simplicity constraint:** The system is a local single-process Python CLI that reads ≤1 GB from disk, writes a trimmed domain, and exits. No locks. No concurrency. No network. No plugins. Three ports only (FileSystem, DiagnosticSink, ProgressSink). If a design decision requires more than that, stop and challenge it first.

**What "F1/F2/F3 working" means end-to-end:**

| Capability | Input | Core algorithm | Output |
|---|---|---|---|
| **F1** — file trimming | `files.include`/`exclude` globs in JSON | R1 L1/L2/L3 cross-source merge → `FULL_COPY`/`REMOVE` per file | Files copied or not copied into rebuilt domain |
| **F2** — proc trimming | `procedures.include`/`exclude` in JSON + parsed Tcl | Tokenizer → proc extractor → namespace tracker → R1 merge → `PROC_TRIM` | Files rewritten with unwanted proc bodies deleted |
| **F3** — run-file gen | `stages` in base JSON + `flow_actions` in feature JSONs | Stage merge algorithm → `<stage>.tcl` emitter | `<stage>.tcl` files written into rebuilt domain |

**The trace (call tree) is diagnostic only.** Traced callees appear in `dependency_graph.json` and `TW-*` warnings to help domain owners decide what to add to `procedures.include`. They are never automatically copied. This is an inviolable design decision.

**End-to-end journey of a `chopper trim` invocation:**

```
1. CLI parses args; resolves domain_root, backup_root, audit_root
2. P0 (DomainStateService): detect which of 4 backup/domain cases applies → DomainState
3. P1 (ConfigService): load + validate base JSON + feature JSONs → LoadedConfig
   → validate_pre() emits any VE-*/VW-* for bad files/procs/globs → abort if errors
4. P2 (ParserService): tokenize + proc-extract every .tcl in domain → ParseResult
   → PE-*/PW-*/PI-* diagnostics; abort if errors
5. P3 (CompilerService): apply R1 L1/L2/L3 across all sources → CompiledManifest
   → every file gets a treatment: FULL_COPY, PROC_TRIM, GENERATED, or REMOVE
   → every PROC_TRIM file gets a keep-set of proc names
6. P4 (TracerService): BFS from CompiledManifest.proc_decisions → DependencyGraph
   → TW-* warnings for ambiguous/unresolved/dynamic/cycle; reporting-only
7. P5a (TrimmerService): read from _backup, write to domain per manifest decisions
   → FULL_COPY: byte-identical copy; PROC_TRIM: rewrite with spans deleted; REMOVE: skip
8. P5b (GeneratorService): emit <stage>.tcl files per F3 stage specs
9. P6 (validate_post): re-tokenize rewritten files; emit VW-05/VW-06/VW-08 if dangling refs
10. P7 (AuditService): write .chopper/ bundle — always, even on failure
```

---

## Milestone Map

| Milestone | What ships | How to verify |
|---|---|---|
| **M0 — Foundation** | `core/` imports clean; serialization deterministic; diagnostic registry guarded | `make check` green; REPL demo from Stage 0 DoD |
| **M1 — Parser** | `parse_file()` handles all 17+ edge-case fixtures; `ParserService.run()` deterministic | Parser-fixture matrix green; golden snapshot committed |
| **M2 — Config+Compile** | All 11 `json_kit/examples/*/` load cleanly; compiled manifests byte-stable | `chopper validate` on all examples; golden manifests |
| **M3 — Trim** | `mini_domain` trimmed correctly; second trim is idempotent (Case 2) | Live trim + re-trim demo; `FULL_COPY` hash-equal to backup |
| **M4 — F3 + Audit** | `<stage>.tcl` files correct; `.chopper/` bundle present on success and failure | F3 example 10 run; forced-error audit test |
| **M5 — Validator** | All VE-*/VW-* codes fire exactly where specified | `chopper validate` on known-bad JSONs; post-trim dangling-ref test |
| **M6 — CLI + E2E** | All 28+ TESTING_STRATEGY.md scenarios pass; coverage thresholds met | `make ci` green; `fev_formality_real` live trim demo |

Each milestone = one stage gate green + demo checkpoint verified. No milestone is declared done until a second review pass confirms it.

---

## Cross-Stage Handoff Map

Use this table when assigning work. It shows which document is authoritative for each stage and where the main implementation risks live.

| Stage | Primary deliverable | Read first | Main risk / pitfall source |
|---|---|---|---|
| Stage 0 | Core models, diagnostics, context, serialization | `ARCHITECTURE_PLAN.md` §5–§10 | `IMPLEMENTATION_ROADMAP.md` phase contract + serialization rules |
| Stage 1 | Parser utility + parser service | `TCL_PARSER_SPEC.md` | `RISKS_AND_PITFALLS.md` TC-01, TC-02, P-01..P-18 |
| Stage 2a | Config loading and schema resolution | `chopper_description.md` §5.1, §6 | `RISKS_AND_PITFALLS.md` config / validation pitfalls |
| Stage 2b | Compiler merge + tracer BFS | `chopper_description.md` §5.3–§5.4 | `RISKS_AND_PITFALLS.md` compiler pitfalls + tracing fixtures |
| Stage 3a | Domain state + trimmer | `chopper_description.md` §2.8, §5.2.1 | `RISKS_AND_PITFALLS.md` trimmer pitfalls, especially P-13..P-20 |
| Stage 3b | F3 run-file generation | `chopper_description.md` F3 sections + flow-action rules | `RISKS_AND_PITFALLS.md` F3-related validation pitfalls |
| Stage 3c | Audit bundle | `chopper_description.md` audit artifact sections | `IMPLEMENTATION_ROADMAP.md` Stage 3c DoD + determinism tests |
| Stage 4 | Pre/post validation | `DIAGNOSTIC_CODES.md` + bible validation sections | `RISKS_AND_PITFALLS.md` validator pitfalls |
| Stage 5 | CLI + orchestrator + end-to-end wiring | `CLI_HELP_TEXT_REFERENCE.md` + `ARCHITECTURE_PLAN.md` §6 | `tests/TESTING_STRATEGY.md` named scenarios |

No stage should invent behavior locally. If the stage owner cannot find the contract in the docs above, the correct action is to update the docs before writing code.

---

## Stage-0 prerequisites (before any code)

### Scope lock sanity check

```powershell
# From repo root, Windows PowerShell
Select-String -Path docs\*.md, src\**\*.py -Pattern 'LockPort|preserve-hand-edits|chopper scan|PluginHost|MCPProgressBridge|EntryPointPluginHost|MCPDiagnosticSink|advisor/|XE-|XW-|XI-|mcp_server|\.chopper/\.lock|\.chopper/hand_edits'
```

Any match outside a negative-assertion sentence ("there is no ...") is a regression. Fix before starting.

### Fixture audit (owner: Stage 0 engineer)

Inventory against the required fixture lists and file gaps as a Stage-0 deliverable (not a Stage-1 prerequisite — because Stage 1 needs these green on day one).

| Fixture folder | Required content | Source of requirement |
|---|---|---|
| `tests/fixtures/edge_cases/` | Named fixtures for P-01..P-36 (where each pitfall has a "Test:" line) | [`RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) per-pitfall `Test:` lines |
| `tests/fixtures/mini_domain/` | 3 procs, 2 files, 1 feature — minimal valid end-to-end | [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md) |
| `tests/fixtures/namespace_domain/` | Multi-file namespace nesting, `namespace eval a::b { proc c ... }` | P-03, TC-02 |
| `tests/fixtures/tracing_domain/` | Six sub-fixtures: `direct_call`, `bracketed_call`, `namespace_qualified`, `cycle`, `ambiguous`, `dynamic` | Bible §5.4 trace expansion algorithm |
| `tests/fixtures/fev_formality_real/` | Real-world domain snapshot for acceptance | Acceptance, not unit |

**Action.** Produce `tests/FIXTURE_AUDIT.md` listing: ✅ present / ❌ missing per required fixture. File missing fixtures as Stage-0 issues.

### Tooling baseline

Verify:

- `make check` passes (lint + format-check + type-check + unit tests on current skeleton).
- `make ci` passes.
- Coverage threshold file enforces 78% overall (parser 85% / compiler 80% / trimmer 80%).
- `import-linter` config present at repo root (see Stage-0 deliverable below); if absent, author it per [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §3 dependency rule.

### Phase execution contract

Implementation follows the phase-gate policy in [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2. Engineers do not invent local error-handling rules.

| Phase | Primary owner | Errors gate? | Dry-run behavior |
|---|---|---|---|
| P0 Domain state | `DomainStateService` | No diagnostics gate here; CLI/domain-state failures surface before useful work starts | Same as live run |
| P1 Config + pre-validate | `ConfigService` + `validate_pre` | **Yes** — `VE-*` abort before parser | Same as live run |
| P2 Parse | `ParserService` | **Yes** — `ERROR`-severity parse diagnostics abort before P3 | Same as live run |
| P3 Compile | `CompilerService` | **Yes** — manifest contradictions must not reach trim | Same as live run |
| P4 Trace | `TracerService` | No — `TW-*` are reporting-only warnings | Same as live run |
| P5 Build output | `TrimmerService` + `GeneratorService` | **Yes** — trim/write failures abort success path | **Skipped for domain writes** |
| P6 Post-validate | `validate_post` | **Yes on errors only** — warnings remain warnings | Runs synthetic, manifest-derivable checks only |
| P7 Audit | `AuditService` | Never masks the primary failure | Still emits report artifacts |

`--strict` is an exit-code policy only. It does not rewrite warning severity.

---

## Stage 0 — `core/` foundation

**Goal.** Ship shared models, diagnostics, errors, protocols, context/config, and serialization. Nothing else depends on sibling modules; sibling modules will import from here.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/core/__init__.py` | Public re-exports: all dataclasses + `Diagnostic` + `Severity` + `Phase` + `ChopperContext` + `RunConfig` + `dump_model` |
| `src/chopper/core/models.py` | All frozen dataclasses from [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §9.1 (after `DAY0_REVIEW.md` A1–A9 cuts): `ProcEntry`, `CallSite`, `ParsedFile`, `ParseResult`, `LoadedConfig`, `BaseJson`, `FeatureJson`, `ProjectJson`, `FileTreatment` (enum), `Provenance`, `ProcDecision`, `CompiledManifest`, `StageSpec`, `Edge`, `DependencyGraph`, `FileOutcome`, `TrimReport`, `GeneratedArtifact`, `AuditArtifact`, `AuditManifest`, `DomainState`, `RunResult`, `FileStat`. **No `RunMode` enum** (cut per A7; CLI dispatches on subcommand). |
| `src/chopper/core/diagnostics.py` | `Severity`, `Phase`, `Diagnostic` (frozen, keeps `dedupe_bucket` per A6), `DiagnosticSummary`, compile-time code registry validator loaded from `DIAGNOSTIC_CODES.md` |
| `src/chopper/core/errors.py` | `ChopperError` (base), `ConfigurationError`, `ParserError`, `CompilerError`, `TrimmerError`, `AuditError` — programmer-error channel only (not user-facing) |
| `src/chopper/core/protocols.py` | The three port `Protocol` definitions per [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §5 (after `DAY0_REVIEW.md` cuts): `FileSystemPort`, `DiagnosticSink`, `ProgressSink`. **No `ClockPort` / `SerializerPort` / `AuditStore` / `TableRenderer`** (cut per A2–A5). |
| `src/chopper/core/context.py` | `RunConfig`, `PresentationConfig` (with `verbose` / `quiet` / `plain` only), `ChopperContext` (bundle of `config` + `fs` + `diag` + `progress`) per [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.1 |
| `src/chopper/core/result.py` | `RunResult` and any per-phase result aliases (may be folded into `models.py`) |
| `src/chopper/core/serialization.py` | `dump_model(obj) -> str`, `load_model(cls, data) -> obj`; uses deterministic recursive key-sort for mappings, preserves list order, encodes `Path` as POSIX strings and `Enum` as `.value`, and keeps `None` as JSON `null`. Replaces the removed `SerializerPort`. |
| `importlinter.ini` or `pyproject.toml` contract | Enforce: `cli → orchestrator → services → core`; `core` imports only stdlib; no circular imports |

**Definition of done (DoD).**

- All dataclasses import cleanly from `chopper.core`.
- `Diagnostic(code="XX-99")` with an unregistered code raises at construction (registry validation).
- `mypy --strict src/chopper/core` passes.
- `import-linter --config pyproject.toml` passes against a sample contract (even though sibling modules don't exist yet, the contract validates `core` has no sibling imports).
- `make check` green.
- Unit tests in `tests/unit/core/` achieve ≥ 90% coverage (core is small — easy to hit).

**Test gate.**

- `tests/unit/core/test_models_frozen.py` — every model is frozen (`dataclasses.FrozenInstanceError` on mutation).
- `tests/unit/core/test_serialization_roundtrip.py` — every public model round-trips through `dump_model / load_model`.
- `tests/unit/core/test_serialization_determinism.py` — serializing the same object twice produces byte-identical output.
- `tests/unit/core/test_diagnostic_registry.py` — valid codes construct; unknown codes raise; registry loading matches the `DIAGNOSTIC_CODES.md` active rows.
- `tests/unit/core/test_context_frozen.py` — `ChopperContext` and `RunConfig` reject field reassignment.

**Demo checkpoint.** Show a Python REPL session building a `ChopperContext` with stub adapters (even trivial ones like `pass`-body adapters) via a `make_test_context()` helper in `tests/support/context.py`. Emit a `Diagnostic`. Call `sink.snapshot()`. Serialize a `CompiledManifest` via `dump_model()`. Print. Quit.

**Exit criterion to Stage 1.** All sibling modules can `from chopper.core import ...` everything they need. Import-linter contract enforces sibling-free-from-sibling.

**Owner risk to watch.**

- Diagnostic registry loading at import time — cache it; do not re-parse `DIAGNOSTIC_CODES.md` on every `Diagnostic(...)` call.
- `dump_model()` must sort dict keys recursively for golden-stable output, preserve list order exactly, POSIX-normalize `Path`, encode `Enum` via `.value`, and serialize `None` as JSON `null`.

---

## Stage 1 — `parser/` (the crown jewel)

**Goal.** Ship the pure parser utility `parse_file(file_path, text, on_diagnostic)` returning `list[ProcEntry]`, and `ParserService.run(ctx, files)` wrapping it into `ParseResult` after reading file content through `ctx.fs`.

**This is the highest-risk module.** TC-01 (proc boundary), TC-02 (canonical naming), and 10+ pitfalls live here. Do not start without green fixtures.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/parser/__init__.py` | Re-export `parse_file`, `ParserService` |
| `src/chopper/parser/tokenizer.py` | Brace/quote/comment state machine per [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §3 |
| `src/chopper/parser/namespace_tracker.py` | LIFO namespace stack per P-03 |
| `src/chopper/parser/proc_extractor.py` | Proc detection algorithm per [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §4 |
| `src/chopper/parser/dpa_associator.py` | DPA / comment-banner association per [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §5 |
| `src/chopper/parser/call_extractor.py` | Raw call-token + source-ref extraction with SNORT suppression filters (bible §5.4.1 R3 hybrid) |
| `src/chopper/parser/parse_file.py` | The pure `parse_file(file_path, text, on_diagnostic)` utility |
| `src/chopper/parser/service.py` | `ParserService.run(ctx, files)` — reads via `ctx.fs`, fans out to `parse_file`, assembles global proc index |

**Parser service contract.**

`ParserService.run(ctx, files: Sequence[Path]) -> ParseResult` is the public parser API. It reads files via `ctx.fs`, calls `parse_file(file_path=..., text=..., on_diagnostic=ctx.diag.emit)`, preserves lexicographic POSIX order, and returns a deterministic `ParseResult`. `parse_file()` never performs filesystem I/O itself.

**DoD.**

- All P-01..P-36 pitfall fixtures produce the expected diagnostics and proc-entry spans.
- Duplicate-proc returns last-wins index entry + emits `PE-01`.
- Unbalanced-brace returns `[]` + emits `PE-02`.
- Line numbers in diagnostics match source positions (verify against `backslash_line_continuation` fixture).
- Latin-1 fallback path tied to `PW-02` fires only after UTF-8 decode exception.
- Namespace stack produces `utils.tcl::a::b::helper` canonical names per D3 test vectors.
- `ParserService.run()` iterates files in lexicographic POSIX order.
- `make check` green; `make test-parser` (new target) green; parser-module coverage ≥ 85%.

**Test gate.**

- `tests/unit/parser/test_tokenizer.py` — isolated state-machine tests per §3 rules.
- `tests/unit/parser/test_proc_extraction.py` — per-pitfall (P-01..P-36) test methods.
- `tests/unit/parser/test_canonical_names.py` — test-vector table from D3.
- `tests/unit/parser/test_return_contract.py` — `PE-01`/`PE-02` return values match bible §5.4.1.
- `tests/unit/parser/test_call_extraction_snort.py` — SNORT suppression cases (comments, log strings, metadata, variables).
- `tests/golden/parser/*.json` — `ProcEntry` list snapshot per fixture via `pytest-regressions`.

**Demo checkpoint.** Parse `tests/fixtures/fev_formality_real/` and print the canonical proc index length, top 10 procs by line span, and count of `PE-*` / `PW-*` / `PI-*` diagnostics. All numbers must match a prerecorded expected value.

**Exit criterion to Stage 2.** `ParserService.run()` produces a deterministic `ParseResult` for the real-world fixture. Golden snapshot of `ParseResult` is committed.

**Owner risks.**

- **P-01** (brace depth inside quoted strings): easy to misread the rule. Re-read [`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §3.3.1 / §3.3.2 before writing the tokenizer. The mnemonic is: *outside braces, quotes suppress braces; inside braces, nothing suppresses braces.*
- **P-02** (line continuation): do not physically join lines.
- **P-03** (namespace stack): LIFO, pop on `namespace eval` block exit, not on every `}`.
- **P-32** (proc args with nested brace defaults): body brace is the one at matching `brace_depth`, not the first `{` after the proc name.

---

## Stage 2a — `config/` + JSON loading

**Goal.** Load base, feature, and project JSONs through the three schemas in `json_kit/schemas/`, validate, topo-sort features by `depends_on`, resolve paths.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/config/schemas.py` | `jsonschema` Draft-07 validators for base/feature/project |
| `src/chopper/config/loaders.py` | `load_base(path)`, `load_feature(path)`, `load_project(path)` — raise `ConfigurationError` on schema failure |
| `src/chopper/config/resolver.py` | Path resolution: project-JSON mode vs `--base/--features` mode; enforce "no `..`, no absolute paths" at the schema boundary |
| `src/chopper/config/depends_on.py` | Topological sort over feature `depends_on`; detect cycles → `VE-22`; detect missing prerequisites → `VE-15` |
| `src/chopper/config/service.py` | `ConfigService.run(ctx, state) -> LoadedConfig` |

**DoD.**

- All three schemas validate all 11 `json_kit/examples/*/` fixtures successfully.
- Malformed JSON (trailing commas, BOM) → `VE-01 missing-schema` or schema error.
- `depends_on` cycle → `VE-22`.
- `depends_on` prerequisite missing from project selection → `VE-15` (order **not** enforced).
- Duplicate feature entries → `VE-18`; duplicate feature names → `VE-14`.
- `--project` path resolution failures → `VE-13` and the runner is never entered.
- CLI conflict (`--project` with `--base/--features`) → `VE-11` (handled by CLI, not here — but document the boundary).
- `LoadedConfig.features` is topo-sorted; `project.features[]` order is preserved as the tie-breaker.

**Test gate.**

- `tests/unit/config/test_schema_validation.py` — every `json_kit/examples/*/` fixture + malformed-JSON negatives.
- `tests/unit/config/test_depends_on.py` — cycles, missing prerequisites, out-of-order (allowed).
- `tests/unit/config/test_path_resolution.py` — `..` rejection, absolute rejection, project-domain basename match (case-insensitive).
- `tests/golden/config/loaded_config_*.json` — `LoadedConfig` golden snapshots.

**Demo checkpoint.** `chopper validate --project json_kit/examples/10_chained_features_depends_on/project.json` emits zero errors; the topo-sorted feature list in `.chopper/chopper_run.json` matches expected.

**Exit criterion to Stage 2b.** `LoadedConfig` is a deterministic, frozen, golden-stable object.

---

## Stage 2b — `compiler/` (merge + trace)

**Goal.** P3 (R1 L1/L2/L3 provenance-aware merge) and P4 (BFS trace expansion). Produces `CompiledManifest` and `DependencyGraph`.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/compiler/per_source.py` | Step 1–2 of bible §5.3: per-source file partition into `FI_literal`, `FI_glob`, `FE`, `PI`, `PE` and per-file L2 classification into `NONE` / `WHOLE` / `TRIM(keep_set)` |
| `src/chopper/compiler/aggregate.py` | Step 3 of bible §5.3: cross-source L1 + L3 aggregation, `VW-09`..`VW-13`, `VW-19`, `VW-18` |
| `src/chopper/compiler/provenance.py` | Per-file `input_sources`, `vetoed_entries`, `surviving_procs` |
| `src/chopper/compiler/merge_service.py` | `CompilerService.run(ctx, loaded, parsed) -> CompiledManifest` |
| `src/chopper/compiler/trace.py` | BFS expansion per bible §5.4: sorted frontier, namespace resolution candidates, `TW-01`..`TW-04` emission |
| `src/chopper/compiler/trace_service.py` | `TracerService.run(ctx, manifest, parsed) -> DependencyGraph` |
| `src/chopper/compiler/flow_actions.py` | F3 stage merge (add/remove/replace stage/step, `load_from`, `@n` suffix) |

**DoD.**

- Bible §4 R1 matrix rows 1–16 handled correctly (unit test per row).
- Cross-source `VW-19` / `VW-18` vetoes emitted exactly once per authoring conflict.
- BFS frontier is lex-sorted; cycles terminate via visited-set and emit `TW-04`.
- `PI+` is reporting-only; `CompiledManifest.file_decisions` and `proc_decisions` are frozen before `TracerService.run()` is called (enforced by order in `runner.py`).
- F3 `flow_actions` respect feature order in `project.features[]`.
- `compiled_manifest.json` and `dependency_graph.json` are byte-stable across runs.
- Coverage ≥ 80%.

**Test gate.**

- `tests/unit/compiler/test_r1_matrix.py` — 16 rows × matrix scenarios.
- `tests/unit/compiler/test_cross_source_veto.py` — `VW-19` / `VW-18` emissions.
- `tests/unit/compiler/test_trace_bfs.py` — frontier pop order, cycle, ambiguous, unresolved, dynamic (covers the 6 tracing_domain sub-fixtures).
- `tests/unit/compiler/test_flow_actions.py` — F3 action vocabulary.
- `tests/golden/compiler/compiled_manifest_*.json` — golden snapshots for each `json_kit/examples/*/` scenario.
- `tests/golden/compiler/dependency_graph_*.json` — golden snapshots.

**Demo checkpoint.** Run the pipeline end-to-end on `tests/fixtures/tracing_domain/` and dump both JSON artifacts. All `VW-*` and `TW-*` codes match expectations.

**Exit criterion to Stage 3.** `CompiledManifest` and `DependencyGraph` are deterministic, golden-stable, and provenance-complete. P3 never mutates after P4.

**Owner risks.**

- Order of iteration in aggregation (see DAY0_REVIEW F2): sources in project order, files in lex order.
- L2.2 vs L2.3 vs L2.5 in per-source classification is subtle; test each row of the single-source interaction matrix (bible §4 rows 1–16) individually.
- Trace's `reachable_from_includes` is `PI+` — reporting-only. Do not let it leak into `CompiledManifest.proc_decisions`.

---

## Stage 3a — `trimmer/` + domain-state machine

**Goal.** P0 (domain-state detection, backup/restore) and P5a (read backup, rewrite trimmed domain tree). Writes through `ctx.fs`. No staging.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/orchestrator/domain_state.py` | `DomainStateService.run(ctx) -> DomainState` — edge-case matrix from bible §2.8 (4 cases, `VE-21` for case 4; hand-edited domains on re-trim discard silently with fixed CLI pre-flight warning) |
| `src/chopper/trimmer/file_writer.py` | Write verbatim (`FULL_COPY`) or atomic-drop (`PROC_TRIM`) |
| `src/chopper/trimmer/proc_dropper.py` | Given proc spans (including DPA blocks and comment banners), rewrite file content with targeted procs removed; emit `VE-26` on span misalignment |
| `src/chopper/trimmer/service.py` | `TrimmerService.run(ctx, manifest, state) -> TrimReport` |

**DoD.**

- All four bible §2.8 cases handled.
- Dry-run does not call `ctx.fs.write_text` / `rename` / `remove`.
- `FULL_COPY` bytes are identical to source (hash-compare).
- `PROC_TRIM` removes exactly the specified procs + their DPA blocks + adjacent doc-comment banners; no trailing blank-line clutter.
- `VE-23` / `VE-24` / `VE-25` / `VE-26` fire exactly where specified in the registry.
- P5a failure leaves `<domain>_backup/` intact; re-invocation resumes from backup via Case 2.
- Coverage ≥ 80%.

**Test gate.**

- `tests/unit/trimmer/test_state_machine.py` — four domain-state cases.
- `tests/unit/trimmer/test_proc_drop.py` — single-proc drop, last-proc drop, multi-proc drop, DPA attached / orphaned / mismatched.
- `tests/integration/test_trim_roundtrip.py` — trim `mini_domain`, re-parse output, compare expected procs survived.
- `tests/golden/trimmer/trim_report_*.json`.

**Demo checkpoint.** Live-trim `mini_domain` against a feature JSON. Show `<domain>_backup/` + rebuilt `<domain>/` + `.chopper/trim_report.txt`. Re-run trim without changes — second run is idempotent (same output, Case 2).

**Exit criterion to Stage 3b.** Trim is deterministic and idempotent.

**Owner risks.**

- Proc-span atomic drop must align parser line ranges to byte offsets exactly. If parser output is stale relative to the file on disk, emit `VE-26` and abort — do not guess.
- First-trim backup copies **exclude** `.chopper/` — move pre-existing `.chopper/` aside, re-create fresh post-trim.

---

## Stage 3b — `generators/` (F3 run-file generation)

**Goal.** P5b emission of `<stage>.tcl` files and optional stack artifacts per F3 `stages` and `flow_actions`.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/generators/stage_emitter.py` | One `<stage>.tcl` per `StageSpec` after feature `flow_actions` applied |
| `src/chopper/generators/stack_emitter.py` | Optional stack-file entries (`N`, `J`, `L`, `D`, `I`, `O`, `R` lines) |
| `src/chopper/generators/service.py` | `GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]` — writes directly via `ctx.fs`; returned tuple is a manifest for audit |

**DoD.**

- Every `StageSpec.steps` string is emitted verbatim — no interpretation, no validation of content (R4 "plain strings by design").
- `flow_actions` sequencing respects `project.features[]` order.
- `@n` suffix resolution + `VE-10` / `VE-19` / `VE-20` emission works.
- Generated files are copied into the rebuilt `<domain>/`, not written to a staging tree.
- Coverage ≥ 80%.

**Test gate.**

- `tests/unit/generators/test_stage_emission.py` — stage order preserved, steps plain-string.
- `tests/unit/generators/test_flow_actions_ordering.py` — add_before / add_after / replace / remove / `@n`.
- `tests/golden/generators/generated_*.tcl`.

**Demo checkpoint.** F3 example 10 (`json_kit/examples/10_chained_features_depends_on/`) produces the expected `<stage>.tcl` files.

**Exit criterion to Stage 3c.** Generated run-files parse as syntactically valid Tcl (brace-balance check only — no semantic validation per R4).

---

## Stage 3c — `audit/` (P7)

**Goal.** Write `.chopper/` bundle on every run (success *and* failure). Bible §5.5.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/audit/service.py` | `AuditService.run(ctx, manifest, graph) -> AuditManifest` — writes seven named files per bible §5.5.1 |
| `src/chopper/audit/writers.py` | Individual writers: `write_chopper_run`, `write_compiled_manifest`, `write_dependency_graph`, `write_diagnostics`, `write_trim_report`, `write_trim_report_txt`, `write_trim_stats` |
| `src/chopper/audit/hashing.py` | SHA-256 over file contents for `AuditArtifact.sha256` |

**DoD.**

- Audit runs unconditionally from the `finally` block in `runner.py`, even on failure.
- `AuditService` tolerates `None` for `manifest` and `graph` (writes `chopper_run.json` + `diagnostics.json` only).
- `chopper_run.json.artifacts_present[]` lists exactly which files exist.
- All artifacts are JSON-serialized via `dump_model()` (sorted keys, deterministic).
- Internal error during audit itself is swallowed and logged to stderr only — never masks the primary failure.
- Coverage ≥ 80%.

**Test gate.**

- `tests/unit/audit/test_partial_audit.py` — audit with `manifest=None` succeeds, emits `chopper_run.json` + `diagnostics.json`.
- `tests/unit/audit/test_audit_manifest_complete.py` — happy path writes all seven files.
- `tests/integration/test_audit_on_failure.py` — force a P3 error; audit bundle still present.
- `tests/golden/audit/chopper_run_*.json`.

**Demo checkpoint.** Force a parse error in `mini_domain`; verify `.chopper/diagnostics.json` and `.chopper/chopper_run.json` are present; `exit_code == 1`.

**Exit criterion to Stage 4.** Every Chopper invocation — successful or not — leaves a complete, valid audit bundle.

---

## Stage 4 — `validator/` (pre + post)

**Goal.** P1 (schema beyond config) and P6 (post-trim integrity). Emits `VE-*` / `VW-*`.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/validator/pre.py` | `validate_pre(ctx, loaded) -> None` — file existence (`VE-06`), proc-in-file (`VE-07`), glob wellformedness (`VE-09`), empty-procs-array (`VE-03`), feature-domain-mismatch (`VW-04`) |
| `src/chopper/validator/post.py` | `validate_post(ctx, manifest, rewritten_paths) -> None` — re-parse rewritten files, check brace balance (`VE-17` internal error), dangling proc refs (`VW-05`), missing source targets (`VW-06`), empty-after-trim (`VW-08`) |

Whether these are free functions or service classes depends on DAY0_REVIEW A9 decision.

**DoD.**

- Pre-validation runs after config load, before parse; errors gate `P1 → P2`.
- Post-validation runs after trim (or in dry-run with manifest-derivable-only checks per [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2); errors gate `P6 → P7` as error-only.
- No side-effects beyond `ctx.diag.emit`.
- Coverage ≥ 80%.

**Test gate.**

- `tests/unit/validator/test_pre_checks.py`.
- `tests/unit/validator/test_post_checks.py`.
- `tests/integration/test_post_trim_validation.py` — trim with intentional dangling ref → `VW-05` present.

**Demo checkpoint.** Run `chopper validate` against a known-bad JSON (file not in domain); exits 1 with `VE-06` in the rendered output.

**Exit criterion to Stage 5.** All diagnostic emissions are stable; golden `diagnostics.json` passes.

---

## Stage 5 — `cli/` + end-to-end integration

**Goal.** Thin `argparse` (or `typer`) CLI surface with three subcommands: `validate`, `trim`, `cleanup`.

**Files to produce.**

| File | Contains |
|---|---|
| `src/chopper/cli/main.py` | Entry point — parses args, constructs `ChopperContext`, dispatches subcommand |
| `src/chopper/cli/commands.py` | `run_validate`, `run_trim`, `run_cleanup` — each constructs the context it needs |
| `src/chopper/cli/render.py` | End-of-run Rich-table summary (no live progress in v1 — see DAY0_REVIEW A1) |
| `src/chopper/orchestrator/runner.py` | `ChopperRunner.run(ctx) -> RunResult` — the phase loop from [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2 |
| `src/chopper/orchestrator/gates.py` | `_has_errors(ctx, phase)`; `_abort(ctx, ...)` helpers |

**DoD.**

- Three subcommands dispatch correctly; `--help` text matches [`CLI_HELP_TEXT_REFERENCE.md`](CLI_HELP_TEXT_REFERENCE.md).
- Exit codes match [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §8.2 rule 4: 0 / 1 / 2 / 3.
- `--strict` affects only the final exit-code computation (never rewrites severity).
- `--dry-run` skips domain-write work in P5, still runs synthetic P6 checks, and still emits audit artifacts.
- `--project` is mutually exclusive with `--base/--features` (→ `VE-11`).
- Unhandled exception → audit bundle + `.chopper/internal-error.log` + exit 3.
- No library code calls `print`. Rendering happens in `cli/render.py` only.

**Test gate.**

- `tests/integration/test_cli_validate.py` — all 11 `json_kit/examples/*/` scenarios exit 0.
- `tests/integration/test_cli_trim_mini_domain.py` — happy path end-to-end.
- `tests/integration/test_cli_trim_re_trim.py` — idempotency on second invocation.
- `tests/integration/test_cli_strict.py` — warnings present → exit 1 with `--strict`, exit 0 without.
- `tests/integration/test_cli_exit_codes.py` — 0 / 1 / 2 / 3 matrix.
- `tests/integration/test_cli_cleanup.py` — deletes `<domain>_backup/`, preserves `<domain>/`.

**Demo checkpoint.** End-to-end live trim of `fev_formality_real` with a realistic base + feature selection; show `.chopper/trim_report.txt` summary; show diff of `<domain>_backup/` vs `<domain>/` for sanity.

**Exit criterion — v1 release candidate.**

- All 33 corner-case scenarios in [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §12 have acceptance tests and pass (minus any removed under DAY0_REVIEW A8).
- Coverage thresholds met (78% overall, 85% parser, 80% compiler/trimmer).
- Golden snapshots exist for every public JSON artifact: `Diagnostic`, `RunResult`, `CompiledManifest`, `DependencyGraph`, `TrimReport`, `AuditManifest`.
- `make ci` green.
- Observational benchmark recorded on `fev_formality_real` for reference (not gating).

---

## Cross-stage contracts (never violate)

1. **Stage N cannot import from Stage N+1.** Enforced by `import-linter`.
2. **Services never call services.** Orchestrator composes. Enforced by `import-linter`.
3. **All I/O through `ctx.fs`.** Direct `Path.read_text` / `Path.rename` / `shutil.*` outside `adapters/` is a bug.
4. **All diagnostics through `ctx.diag.emit`.** No `print` in library code. No `raise` for user-facing errors.
5. **All models are frozen dataclasses.** Mutation is a bug.
6. **Determinism is non-negotiable.** Every iteration over user data is sorted; BFS frontier is lex-sorted; file walks use `sorted(Path.rglob)`.
7. **Register diagnostic codes before use.** Registry lookup at `Diagnostic(...)` construction fails fast.
8. **No new flags, phases, diagnostic families, or ports without a bible edit first.** See [`project.instructions.md`](../.github/instructions/project.instructions.md) §2.

---

## Per-stage gating rule

A stage is complete only when:

1. All files listed under "Files to produce" exist and are reviewed.
2. All "DoD" items are checked.
3. "Test gate" suite is green; coverage threshold met.
4. "Demo checkpoint" has been run once against the stated fixture.
5. "Exit criterion" has been verified by a second engineer (or second review pass if solo).

Do not start Stage N+1 before Stage N's gate is green. If a gate fails, stop and fix — do not stack new work on a broken foundation.

---

## Runbook for common stage-failure modes

| Symptom | First check | Likely root cause |
|---|---|---|
| Golden snapshot differs between runs | Sort keys in `dump_model()`? Iteration order in compiler aggregation? | Missing sort on set/dict iteration |
| Parser flakes on a new fixture | Tokenizer state re-check | P-01 quote context drift or P-07 comment braces |
| Trace cycle not caught | Visited-set updated **before** frontier append? | BFS visited-set bug |
| `VE-26 proc-atomic-drop-failed` fires in Stage 3a | Parser output stale vs file on disk? | Parser must be re-run from scratch on each invocation — cache only inside one run |
| Audit missing on failure | `AuditService` called from `finally`? | Runner wiring |
| Exit code 1 when `--strict` is off but warnings present | `--strict` gating in `finalize()` | `--strict` is exit-code-only policy |
| `import-linter` fails | Sibling-module import added? | Violation of dependency rule in §3 |

---

## Quick-reference cheat sheet

**Where code goes.** `src/chopper/<stage>/...`. Stage 0 → `core/`. Stage 1 → `parser/`. Stage 2 → `config/`, `compiler/`. Stage 3 → `trimmer/`, `generators/`, `audit/`. Stage 4 → `validator/`. Stage 5 → `cli/`, `orchestrator/`.

**Where tests go.** `tests/unit/<stage>/` (fast, isolated). `tests/integration/` (end-to-end). `tests/property/` (Hypothesis). `tests/golden/<stage>/` (regression snapshots).

**Where fixtures go.** `tests/fixtures/<category>/`. Each pitfall's `Test:` line names its fixture.

**When adding a diagnostic.** Register in [`DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) first. Lowest reserved slot. Then add constant in `core/diagnostics.py`. Then emit.

**When stuck.** [`RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) per-module section. Worked example in bible §5.4. Named integration scenarios in [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md) §5.
