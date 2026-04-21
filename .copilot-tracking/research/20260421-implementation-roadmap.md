<!-- markdownlint-disable-file -->

# Chopper v2 — Implementation Roadmap and Doc-Patch Plan

**Date:** 2026-04-21  
**Companion to:** [20260421-handoff-readiness-devils-advocate-research.md](20260421-handoff-readiness-devils-advocate-research.md)  
**Purpose:** Consolidate the owner's decisions on all 20 review findings, specify the exact doc patches required, and lay out the end-to-end implementation plan (arch → specs → code → tests → ship) so agents/engineers can code the system without ambiguity.

**Guiding principle (from owner):** *F1 (file selection) + F2 (proc selection) + F3 (flow actions) must work. The core is the Tcl parsing algorithm that identifies procs in files (mark-for-copy / mark-for-delete) plus a call-tree tracer that helps authors refine JSONs for inclusive coverage. The final trimmed codebase is a logical superposition of base + features. Python implementation can be robust, clean, modular, and maintainable — but never over-engineered for scenarios that do not exist in daily operation.*

**What is explicitly NOT being built** (hard-no, do not reintroduce under any pretext): locks, hand-edit preservation, scan subcommand, plugins, MCP, AI advisor, `X*` diagnostics, severity-rewriting `--strict`, parallelism, staging atomicity. Owner's rollback policy makes staging-with-atomic-promotion unnecessary; see Decision B-3.

---

## Part A — Reconciled Decisions (Owner-Approved)

The table below is the single decision record for the 9 blockers, 11 gaps, and 6 debt items. Use it to drive Part B patches.

### Blockers

| ID | Decision (approved) |
|---|---|
| **B-1** Service contract | Keep plan's `ChopperRunner` + per-phase services as the only contract. Delete the rival `TrimService` / `TrimRequest` / `TrimResult` classes from bible §5.11.2. Preserve the §5.11.3 JSON-over-stdio wire protocol unchanged — that IS the GUI-readiness surface. GUI speaks JSON on stdin/stdout, engine emits JSONL on stderr. No extra wrapper class. |
| **B-2** ProgressSink shape | One `ProgressSink` with `phase_started / phase_done / step` (plan's version). `DiagnosticSink` owns `emit / snapshot / finalize`. `ProgressSink` is active in ALL modes (text, JSON, silent); only the adapter behind it changes. Remove bible §5.11.6's `on_progress / on_diagnostic` duplicate. |
| **B-3** Rollback mechanism | Simple, no staging. On trim failure: log the failure, stop. Leave `<domain>/` half-cooked and `<domain>_backup/` intact. On next invocation, `DomainStateService` detects both directories present → treats `<domain>_backup/` as authoritative source and rebuilds `<domain>/` from it (equivalent to re-trim Case 2). User may also manually run `rm -rf <domain> && mv <domain>_backup <domain>` to reset to pristine. No atomic promotion, no fsync dance, no temp staging tree. |
| **B-4** `.chopper/` survival | `.chopper/` lives only at `<domain>/.chopper/`. Never backed up, never copied into `<domain>_backup/`, never parsed, never matched by `files.include` globs, never walked during P2 file discovery. It is a reserved path. First-trim and re-trim both move/ignore it explicitly. |
| **B-5** Parse-error contract | Codified: `PE-01` → full list, last-def's span wins; `PE-02` → returns `[]`, file marked unusable; `PE-03` → full list. Add a P2 phase gate identical in shape to P1/P3/P6 gates — if any `PE-*` with severity `ERROR` is emitted, runner aborts before P3. No exception propagation from parser; all parse errors surface as diagnostics. |
| **B-6** Pre-trim vs post-trim validation | Split: **pre-trim** (P1b `PreValidatorService`) runs schema + structural + manifest-derived checks (empty-procs, conflicting options, unresolvable `--project`, missing files/procs at JSON level). **Post-trim** (P6 `PostValidatorService`) runs filesystem-level checks on the rebuilt `<domain>/` tree: brace balance via re-tokenization of *rewritten* files only, and dangling-proc-call scan across the surviving proc set. In dry-run, P6 runs only the manifest-derivable subset (skips filesystem checks). |
| **B-7** Trimmer error codes | Activate VE-27 (`backup-contents-missing`), VE-28 (`domain-write-failed` — fold "staging-promotion" into this since there is no staging), VE-29 (`proc-atomic-drop-failed`). Fix VE-26 phase label. All four exit at `1`. |
| **B-8** CLI flags → config | CLI reference ([`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md)) is the source of truth for user-facing switches. CLI parses them, produces a `RunConfig` for behavior (`strict`, `dry_run`, `domain_root`, `backup_root`, `audit_root`, `mode`) AND a `PresentationConfig` for UX (`verbose`, `debug`, `plain`, `no_color`, `json`). `ProgressSink` is always present; the CLI chooses the adapter (`RichProgress`, `PlainProgress`, `JsonlProgress`, `SilentProgress`) per these flags. No `-vv`; only `-v` and `--debug`. |
| **B-9** P2 and P4 gates | Plan §6.2 runner body gets explicit gates after every phase. Policy: P0 no gate (never errors), P1 gate on `VE-*`, P2 gate on `PE-*`, P3 gate on `VE-*` compiler, P4 no gate (reporting-only, `TW-*` are warnings by definition), P5 gate on `VE-*` trimmer, P6 gate on `VE-*` post-validator. P4 internal invariant violations raise → exit 3 (programmer error). |

### Gaps

| ID | Decision |
|---|---|
| **G-1** VE-13 owner | CLI owns it. Pre-runner check; CLI renders the error via `TableRenderer` and exits 2 directly. Diagnostic is emitted to stderr-JSONL only when `--json` is active; otherwise to stderr text. |
| **G-2** DomainState cases | Collapse to `Literal[1,2,3,4]`. Case 5 folds into 2 (re-trim). Case 6 raises at `FileSystemPort.stat()`; CLI catches and emits `VE-26`. |
| **G-3** Domain basename compare | Case-insensitive, basename-only (`Path.cwd().name.casefold() == project.domain.casefold()`). Documented next to VE-19. Full path comparison remains case-sensitive. |
| **G-4** Project JSON portability | Forbid `..` in `base` / `features` strings (already in §6.3.1; restate in §6.6). Require operator to `cd` to domain root before `chopper trim --project <path>`. Document once in §6.6. |
| **G-5** Generator write path | `GeneratorService` writes directly via `ctx.fs.write_text()`. Return value is `tuple[GeneratedArtifact, ...]` for audit/manifest record only; runner does not re-write. |
| **G-6** VE-17 exit code | Raise VE-17 to exit `3` (internal-consistency assertion). Documented as "emitted only when post-trim re-tokenization finds brace imbalance introduced by the trimmer itself". |
| **G-7** Empty `procs` in exclude | No-op. Silently accepted. One sentence added to bible §6.4 exclude description. |
| **G-8** Audit on partial run | Always emit `chopper_run.json` + `diagnostics.json`. Other artifacts emit only when their producing phase completed. `chopper_run.json` includes an `artifacts_present: string[]` field listing which files were written. |
| **G-9** `chopper validate` scope | Default: JSON-only validation (all `VE-*` codes that do not require filesystem or parser). When `--domain .` is provided or cwd matches `project.domain`, also run `VE-06`/`VE-07` (filesystem existence) and `VE-07`/`PE-*` (parse-time). |
| **G-10** Dedupe with buckets | `Diagnostic` gains an optional `dedupe_bucket: str` field. Sink dedupes on `(code, path, line_no, message, dedupe_bucket)`; last-write-wins within a bucket (replaces the prior entry). Callers that need multi-context emission set distinct buckets. Default bucket is `""` (empty). |
| **G-11** Dry-run P6 scope | Manifest-based checks only: `VW-05`, `VW-06`, `VW-14`, `VW-15`, `VW-16`, `VW-17`. Skip filesystem re-read checks (`VE-17`, `VE-29`). |

### Debt

| ID | Decision |
|---|---|
| **D-1** VE-26 phase bug | Registry row updated to `phase = 5`. |
| **D-2** `docs_old/`, `snort/` | Keep. Add README in each: `docs_old/README.md` states "archived architecture decision record from pre-bible era; frozen for historical reference; not authoritative." `snort/README.md` states "inspiration source — prior Tcl proc-chasing tool; kept for algorithm reference only." |
| **D-3** `tests/fev_formality/` | Move to `tests/fixtures/fev_formality_real/`. Update [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) §6 and [`tests/FIXTURE_CATALOG.md`](../../tests/FIXTURE_CATALOG.md) to catalog it as a real-world integration fixture used for end-to-end acceptance scenarios alongside fabricated fixtures. |
| **D-4** `ChopperRunner` name clash | Rename test harness to `ChopperSubprocess` in [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) §4 (and any integration test that uses it). Production `ChopperRunner` keeps its name. |
| **D-5** Python standards home | Move Python coding standards, path-handling rules, logging policy, and GUI-readiness into a new bible §5.12. [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) keeps a brief summary pointing to §5.12. No forward-declared circularity. |
| **D-6** Parser signature canonicalization | `ParserService.run()` (plan §9.2) is the canonical public API. `parse_file()` (parser spec §2.1) remains the pure internal utility. The spec links to the service for the authoritative signature. |

---

## Part B — Doc-Patch Plan (Sequenced)

Each patch is ≤ one paragraph of editing. Apply in the listed order; each PR is self-contained and reviewable in under 10 minutes.

### PR-1 — Reconcile service contract (B-1, B-2)

**File:** [`docs/chopper_description.md`](../../docs/chopper_description.md)

- **§5.11.2 Service Layer Contract:** Delete the `TrimRequest` / `TrimResult` / `TrimService` code block. Replace with one paragraph pointing at [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §6 (`ChopperContext`, `ChopperRunner.run()`) and §9.2 (per-phase service signatures). State explicitly: "The CLI builds `ChopperContext` from parsed args and calls `ChopperRunner.run(ctx) -> RunResult`. `RunResult` is the JSON payload emitted by `--json`. A future GUI builds `ChopperContext` the same way and calls the same runner."
- **§5.11.3 JSON-over-stdio Wire Protocol:** Keep intact. This IS the GUI-readiness contract.
- **§5.11.6 Extension Points:** Remove the `on_progress / on_diagnostic` row from the `ProgressSink` table. Replace with `phase_started / phase_done / step`. Add a separate `DiagnosticSink` row with `emit / snapshot / finalize`.

### PR-2 — Presentation vs RunConfig split (B-8)

**File:** [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §6.1

Add a `PresentationConfig` frozen dataclass next to `RunConfig`:

```python
@dataclass(frozen=True)
class PresentationConfig:
    verbose: bool = False        # -v
    debug: bool = False          # --debug: re-raise on exit 3, full traceback
    plain: bool = False          # --plain: no rich, no colors, ASCII-only
    no_color: bool = False       # --no-color
    json: bool = False           # --json: machine-readable stdout + JSONL stderr
```

Reword §6.1 to clarify: `RunConfig` is for engine behavior; `PresentationConfig` controls CLI-side adapter selection (which `ProgressSink`, which `TableRenderer`). Services depend only on `ctx.config` (i.e. `RunConfig`); the CLI reads `PresentationConfig` to pick adapters before constructing `ctx`. Neither config is mutated after construction.

### PR-3 — Rollback, `.chopper/`, parse errors, post-validate (B-3, B-4, B-5, B-6)

**Files:** [`docs/chopper_description.md`](../../docs/chopper_description.md), [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md), [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md)

- **Bible §2.8 (Edge-case matrix):** Replace Case 5 and Case 6 rows. Keep 1–4. Add a "Failure recovery" paragraph after the matrix: "If a trim run aborts between P5 and P7, `<domain>/` is left in whatever half-rebuilt state the failure produced, and `<domain>_backup/` is untouched. On next invocation, `DomainStateService` observes both directories and selects Case 2 (re-trim); `TrimmerService` treats `<domain>_backup/` as the source of truth, overwrites any stale content in `<domain>/`, and proceeds normally. Operators who want a pristine restart may run `rm -rf <domain> && mv <domain>_backup <domain>` manually. Chopper does not perform atomic-promotion; failures are recoverable by re-invocation."
- **Bible §2.4 + §5.5:** Add: "`.chopper/` is reserved. It lives only at `<domain>/.chopper/`. It is never backed up, never copied into `<domain>_backup/`, never parsed at P2, and never matched by `files.include` globs. When `DomainStateService` renames `<domain>/` to `<domain>_backup/`, it first moves `.chopper/` aside and re-creates it fresh under the rebuilt `<domain>/`."
- **Bible §5.4.1:** Add the three-row PE-* return-contract table (see Decision B-5).
- **Bible §5.7 (Dry-run):** Clarify: "Dry-run P6 runs only manifest-derivable checks (`VW-05`, `VW-06`, `VW-14`–`VW-17`). Filesystem-re-read checks (`VE-17`, `VE-29`) are skipped because there is no rewritten tree to re-tokenize."
- **Bible §5.8 (Post-validation):** Split inputs explicitly: pre-validator gets `(ctx, loaded_config, manifest_draft)`; post-validator gets `(ctx, manifest, rewritten_paths: Sequence[Path])` and re-tokenizes only files listed in `rewritten_paths`.
- **Plan §6.2 runner body:** Add explicit gate lines for P2 (`if _has_errors(ctx, Phase.P2_PARSE): return _abort(...)`) and note P4 has no gate by design.
- **Plan §12 scenario 29:** Reword rollback explanation to match bible §2.8.
- **CLI reference `chopper trim` help-text:** Replace the line "*On failure: remove half cooked domain/ and replace domain_backup/ as domain/*" with "*On failure: leave state as-is and exit non-zero; re-run to resume, or manually `rm -rf <domain> && mv <domain>_backup <domain>` to reset.*"

### PR-4 — Activate trimmer diagnostic codes (B-7, G-6, D-1)

**File:** [`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md)

- Fix VE-26 `phase = 5` (it was `1`).
- Change VE-17 exit code to `3`; update description to "post-trim brace imbalance (internal-consistency assertion; emitted only when trimmer introduced an imbalance)".
- Activate VE-27 `backup-contents-missing` (phase 5, exit 1).
- Activate VE-28 `domain-write-failed` (phase 5, exit 1).
- Activate VE-29 `proc-atomic-drop-failed` (phase 5, exit 1).
- Update the Code Space Summary counts.

### PR-5 — Clarifications cluster (all G-1..G-11 except those resolved above)

Single PR covering eight one-liner clarifications:

- **Bible §5.1 + diagnostic registry row for VE-13:** "Owner: CLI (pre-runner check)."
- **Plan §9.1 DomainState:** `case: Literal[1,2,3,4]`.
- **Bible §2.5 / §5.1:** "Domain-name comparison is case-insensitive, basename only: `Path.cwd().name.casefold() == project.domain.casefold()`."
- **Bible §6.6:** Add: "`..` is forbidden in `base` / `features` strings (§6.3.1 rule restated here). The operator must `cd` into the domain root before invoking `chopper trim --project <path>`; paths resolve against cwd, not against the project JSON's own location."
- **Plan §9.2 `GeneratorService`:** "Writes directly to `ctx.fs`. Return value is the manifest record for audit; the runner does not re-write."
- **Bible §6.4 `procedures.exclude`:** Add: "An empty `procs` array is a silent no-op (unlike `procedures.include`, where an empty array is `VE-03`)."
- **Plan §8.1 `Diagnostic`:** Add `dedupe_bucket: str = ""`. Update §8.2 rule 2 to: "Dedupe key is `(code, path, line_no, message, dedupe_bucket)`; within a bucket, last write replaces the prior entry."
- **Bible §5.8:** "`chopper validate` runs JSON-only structural checks by default. If `--domain .` is provided or cwd matches `project.domain`, validate additionally runs filesystem-existence checks (`VE-06`, `VE-07`) and parse-time checks (`PE-*`)."

### PR-6 — Fixture reorg and naming (D-3, D-4)

- Move `tests/fev_formality/` to `tests/fixtures/fev_formality_real/`.
- Rename test harness class from `ChopperRunner` to `ChopperSubprocess` in [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) §4.
- Update [`tests/FIXTURE_CATALOG.md`](../../tests/FIXTURE_CATALOG.md) with a new section "Real-world fixtures" describing how `fev_formality_real/` feeds end-to-end acceptance tests.

### PR-7 — Python standards home + historical READMEs (D-2, D-5)

- Add new bible §5.12 "Python Coding Standards" — pathlib rules, type annotations, logging (structlog), no prints, public API surface, module boundaries.
- Shrink [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) "Code Style" section to a bullet summary pointing to §5.12.
- Create `docs_old/README.md` — "Archived architecture decision record from pre-bible era. Frozen. Not authoritative for current design."
- Create `snort/README.md` — "Inspiration source: prior Tcl proc-chasing tool. Kept for algorithm reference only."

### PR-8 — Parser canonical signature pointer (D-6)

[`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md) §2.1: add one line: "`ParserService.run()` (plan §9.2) is the canonical public API. `parse_file()` below is the pure internal utility the service wraps."

---

## Part C — Implementation Roadmap (Stage 0 → Stage 5)

Stages strictly gate each other. Each stage has **entry criteria** (docs must be in this state), **deliverables** (code + tests + artifacts), **checkpoints** (verifiable during the stage), and **exit criteria** (verifiable at stage end). No stage begins before the previous one's exit criteria are green on CI.

### Stage 0 — Foundations (`core/` + `adapters/` skeleton)

**Entry criteria:**

- PR-1, PR-2, PR-3, PR-4, PR-5, PR-8 have landed (all blockers, all gaps that touch contracts). PR-6 and PR-7 may follow in parallel.
- `grep -r "TrimService\|TrimRequest\|TrimResult" docs/` returns zero.
- Diagnostic registry has VE-27/28/29 active, VE-26 at phase 5, VE-17 at exit 3.

**Deliverables** (under `src/chopper/core/` and `src/chopper/adapters/`):

| File | Content |
|---|---|
| `core/models.py` | All frozen dataclasses used in ≥2 modules: `FileEntry`, `ProcEntry`, `StageDefinition`, `FlowAction`, `CompiledManifest`, `DependencyGraph`, `TrimStats`, `GeneratedArtifact`, `RunResult`, `ParseResult`, `ParsedFile`, `LoadedConfig`, `DomainState`, `Severity`, `Phase`, `FileTreatment`, `TrimMode`, `ExitCode`. Enums for severity, phase, file treatment, trim mode, exit code. |
| `core/diagnostics.py` | `Diagnostic` dataclass + registry load from [`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md) at import time (parse the markdown table); `Diagnostic.__post_init__` validates `code ∈ registry`. |
| `core/errors.py` | `ChopperError` (base), `ProgrammerError`, `UnknownDiagnosticCodeError`. All other exceptions inherit. Never thrown for user errors — those go through `DiagnosticSink`. |
| `core/protocols.py` | `FileSystemPort`, `DiagnosticSink`, `ProgressSink`, `AuditStore`, `ClockPort`, `SerializerPort`, `TableRenderer`, `DiagnosticRenderer`, `ProgressRenderer`. Python `Protocol` classes only — no `abc.ABC`. |
| `core/context.py` | `RunConfig`, `PresentationConfig`, `ChopperContext`. |
| `core/result.py` | `RunResult` (with `exit_code`, `manifest`, `graph`, `diagnostics`, `run_id`, `artifacts_present`). |
| `core/serialization.py` | `ChopperEncoder`, `dumps()`, `loads()`; round-trip test for every model in `models.py`. |
| `adapters/fs_local.py` | `LocalFS` implementing `FileSystemPort`. |
| `adapters/fs_memory.py` | `InMemoryFS` for tests. |
| `adapters/sink_collecting.py` | `CollectingSink` (default `DiagnosticSink`; implements dedupe-bucket logic). |
| `adapters/sink_jsonl.py` | `JsonlSink` — writes each diagnostic as one JSON line. |
| `adapters/progress_silent.py` | `SilentProgress` — no-op. |
| `adapters/progress_plain.py` | `PlainProgress` — text lines on stderr. |
| `adapters/progress_jsonl.py` | `JsonlProgress` — JSONL events on stderr (GUI wire protocol). |
| `adapters/progress_rich.py` | `RichProgress` — Rich-based; optional import guarded by `try/except`. |
| `adapters/clock_system.py`, `adapters/clock_frozen.py` | Clock ports. |
| `adapters/audit_dotchopper.py` | `DotChopperAuditStore` writes to `.chopper/` under `<domain>/`. |

**Checkpoints (during the stage):**

1. `core/models.py` has zero imports from any sibling module.
2. Every model has a `test_models.py::test_<model>_roundtrip` that serializes → deserializes → `==`.
3. `Diagnostic("VE-99", ...)` raises `UnknownDiagnosticCodeError` (registry enforcement works).
4. `DiagnosticSink` dedupe test: same `(code, path, line_no, message, dedupe_bucket)` twice → one entry; same but different bucket → two entries; same bucket, different message → two entries.

**Exit criteria:**

- `make check` green (ruff + mypy + pytest unit).
- Coverage on `core/` ≥ 80%.
- All ports importable; all adapters instantiable in `make_test_context()`.
- `RunResult` JSON round-trip is byte-identical (after canonical-key sort).

### Stage 1 — Parser (P2)

**Entry criteria:** Stage 0 green. 17 parser fixtures in [`tests/fixtures/edge_cases/`](../../tests/fixtures/edge_cases/) present (they are). `docs/TCL_PARSER_SPEC.md` §2.1 points to `ParserService.run()` (PR-8).

**Deliverables:**

| File | Content |
|---|---|
| `parser/tokenizer.py` | Character-by-character tokenizer honoring Tcl Rules [1][6][9][10]; brace depth; quote state; comment state; `\`-continuation. |
| `parser/namespace_tracker.py` | Context stack: `FILE_ROOT`, `NAMESPACE_EVAL`, `CONTROL_FLOW`, `PROC_BODY`. `foreach_in_collection` treated as control-flow (P-36). |
| `parser/proc_extractor.py` | Given token stream + context stack, extract `ProcEntry` (name, namespace, file, line_no, span). Handles DPA (§4.6 of parser spec) and comment-banner (§4.7). |
| `parser/call_extractor.py` | Given a proc body, extract candidate call tokens for later tracing. Conservative: emits only names that look like proc references (no `$cmd $args` resolution). |
| `parser/service.py` | `ParserService.run(ctx, files: Sequence[Path]) -> ParseResult`. Iterates files in sorted order; calls pure `parse_file()`; aggregates `ParsedFile` entries; emits `PE-*` diagnostics per Decision B-5. |

**Checkpoints:**

1. Each of the 17 fixtures has a golden file in `tests/golden/parser/` (json: list of `ProcEntry`).
2. `parser_basic_single_proc.tcl` → exactly 1 `ProcEntry`.
3. `parser_duplicate_proc_definition_error.tcl` → 2 `ProcEntry` + 1 `PE-01` diagnostic.
4. `parser_computed_proc_name_skipped.tcl` → 0 `ProcEntry` + 1 `PW-04` diagnostic.
5. Property test (hypothesis): generate random balanced-brace Tcl; parser never raises.
6. DPA fixture: the proc span excludes the DPA block.

**Exit criteria:**

- All 17 fixtures green against their golden files.
- Coverage on `parser/` ≥ 85%.
- No `print` in `parser/`.
- `ParserService.run()` signature matches plan §9.2 exactly.

### Stage 2 — Config + Compile + Trace (P1, P3, P4)

**Entry criteria:** Stage 1 green. [`json_kit/schemas/`](../../json_kit/schemas/) in place (they are).

**Deliverables:**

| File | Content |
|---|---|
| `config/loaders.py` | Load + schema-validate base/feature/project JSONs via `jsonschema`. `VE-01`/`VE-02`/`VE-04`/`VE-12`/`VE-13` diagnostics. |
| `config/service.py` | `ConfigService.run(ctx, state) -> LoadedConfig`. Resolves project JSON if present; applies G-3 basename compare; forbids `..` per G-4. |
| `validator/pre.py` | `PreValidatorService.run(ctx, loaded) -> None`. Structural checks (`VE-03` empty-include, `VE-06` file-not-in-domain when domain present, `VE-07` proc-not-in-file, etc.). Per G-9: skip filesystem checks if validate-only mode without domain. |
| `compiler/provenance.py` | Per-source include/exclude tracking (R1 rule). |
| `compiler/merge_service.py` | `CompilerService.run(ctx, loaded, parsed) -> CompiledManifest`. Implements F1 (file set) + F2 (proc set) + F3 (flow_actions) via the algorithm in bible §5.4.1. Explicit include always wins. Lex-sorted keys. |
| `compiler/trace_service.py` | `TracerService.run(ctx, manifest, parsed) -> DependencyGraph`. BFS from `procedures.include`; lex-sorted frontier; TW-01..TW-04 diagnostics; **reporting-only** (never promotes procs into the manifest). |

**Checkpoints:**

1. `mini_domain` fixture compiles byte-identically twice (determinism gate, NFR-03).
2. Worked examples from bible §5.3 produce the expected `CompiledManifest` (golden file).
3. Cyclic proc fixture from `tests/fixtures/tracing_domain/` → 1 `TW-04` + successful termination.
4. Explicit include of a file wins over feature's exclude of same file (R1 test).
5. Feature order affects F3 output but NOT F1/F2 output (determinism on reorder).

**Exit criteria:**

- Coverage on `config/` ≥ 85%, `compiler/` ≥ 80%.
- `CompiledManifest` JSON output is byte-identical on repeated runs.
- Every FR-01..FR-10, FR-31 has ≥1 test.

### Stage 3 — Trimmer + Generator + Audit (P5, P7)

**Entry criteria:** Stage 2 green.

**Deliverables:**

| File | Content |
|---|---|
| `trimmer/service.py` | `TrimmerService.run(ctx, manifest, state) -> TrimmerResult`. State machine: (a) if `state.case == 2`, rebuild `<domain>/` from `<domain>_backup/`; (b) for each file in manifest, copy or rewrite; (c) for each rewritten file, delete dropped proc spans atomically (full-span, no mid-brace cuts). Emits VE-27/28/29. |
| `generators/service.py` | `GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]`. Writes run-files directly via `ctx.fs`; returns artifact records for audit (per G-5). |
| `validator/post.py` | `PostValidatorService.run(ctx, manifest, rewritten_paths) -> None`. Re-tokenize only `rewritten_paths` to check brace balance (`VE-17` → exit 3 per G-6). Dangling-ref scan across surviving procs. |
| `audit/service.py` | `AuditService.run(ctx, manifest, graph)`. Writes `.chopper/chopper_run.json`, `diagnostics.json`, `compiled_manifest.json` (if manifest present), `dependency_graph.json` (if graph present), `trim_report.json`, `trim_report.txt`. Records `artifacts_present` list (per G-8). Never masks primary failure. |

**Checkpoints:**

1. Trim the `mini_domain` fixture; `<domain>/` matches golden tree byte-for-byte.
2. Re-trim: no change, idempotent.
3. Fault-injection test: kill trimmer mid-write; next run detects half-cooked state and rebuilds from `<domain>_backup/`.
4. `.chopper/` is never present in `<domain>_backup/`.
5. `audit_present=['chopper_run.json','diagnostics.json']` when P1 aborts; full list when run completes.
6. Property test: for any manifest where `proc P` is kept, final file contains `proc P` body verbatim; for any manifest where `proc P` is dropped, final file does not contain `proc P` definition.

**Exit criteria:**

- Coverage on `trimmer/` ≥ 80%.
- All 21 testing-strategy integration scenarios pass.
- No data loss in any fault-injection run (backup always intact or manually recoverable).

### Stage 4 — Validator CLI subcommand + cleanup (P1 standalone, G-9)

**Entry criteria:** Stage 3 green.

**Deliverables:**

| File | Content |
|---|---|
| `cli/validate.py` | Thin wrapper: build ctx with `dry_run=True, mode=VALIDATE`, run `ConfigService` + `PreValidatorService`, return result. Per G-9: if `--domain .` or cwd matches project.domain, also run `ParserService` + filesystem existence checks. |
| `cli/cleanup.py` | Removes `<domain>_backup/` and `.chopper/`. Interactive confirmation unless `--yes`. |

**Exit criteria:**

- `chopper validate jsons/base.json` works without a domain.
- `chopper validate --domain . --project jsons/project.json` runs full pre-check.
- `chopper cleanup` prompts, removes backup, removes `.chopper/`.

### Stage 5 — CLI integration + end-to-end acceptance

**Entry criteria:** Stages 0–4 green. PR-6 landed (fev_formality_real moved).

**Deliverables:**

| File | Content |
|---|---|
| `cli/main.py` | Argparse; parses all top-level flags into `PresentationConfig`; parses subcommand args into `RunConfig`; picks `ProgressSink` adapter and `TableRenderer` per flags; constructs `ChopperContext`; dispatches to `ChopperRunner.run()`; renders `RunResult` via `TableRenderer`; exits with `RunResult.exit_code`. |
| `cli/render.py` | `TableRenderer` implementations (rich + plain). |

**Checkpoints:**

1. `chopper trim --project jsons/project.json --dry-run` against `fev_formality_real/` produces the 4 dry-run artifacts under `.chopper/`.
2. Live trim against `fev_formality_real/` produces a rebuilt domain whose `TrimStats.files_out`, `procs_out`, `sloc_out` match golden values.
3. `--json` emits a single valid JSON object to stdout and JSONL to stderr, with no interleaving.
4. `--strict` on a run with warnings exits 1; without `--strict`, same run exits 0.
5. `--debug` on an induced programmer error prints traceback and exits 3.

**Exit criteria:**

- All 21 integration scenarios from [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) §5 pass via `ChopperSubprocess`.
- Overall coverage ≥ 78%.
- `make ci` green.
- GUI wire protocol smoke test: pipe `TrimRequest` JSON into stdin, capture JSON from stdout, JSONL from stderr; round-trip through `RunResult`.

---

## Part D — Global Quality Gates

Applied on every PR, every stage, continuously:

| Gate | Tool | Threshold |
|---|---|---|
| Lint | `ruff` | zero errors |
| Format | `ruff format --check` | zero diffs |
| Types | `mypy` | zero errors (strict mode in `core/`) |
| Unit coverage | `pytest-cov` | overall 78%, parser 85%, compiler 80%, trimmer 80%, config 85%, core 80% |
| Property | `hypothesis` | 500 examples, zero failures |
| Golden files | `pytest-regressions` | zero diffs |
| Determinism | custom | byte-identical outputs across 2 runs on `mini_domain` and `fev_formality_real` |
| No-print | `grep` in CI | zero `print(` in `src/chopper/{parser,compiler,trimmer,validator,core,config,audit,generators}` |
| Registry integrity | CI script | every `Diagnostic(code=...)` in code ↔ row in `docs/DIAGNOSTIC_CODES.md` |
| Scope-lock grep | CI script | forbidden tokens list (see [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) §1) returns zero outside negative-assertion contexts |

---

## Part E — Pre-Coding Checklist (before Stage 0)

Owner signs off once all rows are ✅.

- [ ] PR-1 merged — bible §5.11.2 points at plan; `TrimService/TrimRequest/TrimResult` deleted.
- [ ] PR-2 merged — `PresentationConfig` in plan §6.1.
- [ ] PR-3 merged — rollback, `.chopper/`, parse-errors, post-validate all pinned in bible + plan + CLI reference.
- [ ] PR-4 merged — VE-26 phase fixed, VE-27/28/29 active, VE-17 at exit 3.
- [ ] PR-5 merged — 8 clarifications applied.
- [ ] PR-6 merged — `fev_formality_real/` in place, test harness renamed.
- [ ] PR-7 merged — bible §5.12 exists, historical READMEs in place.
- [ ] PR-8 merged — parser spec points at service.
- [ ] `make ci` runs clean against the empty scaffold (ruff + mypy + package smoke test).
- [ ] CI workflow enforces scope-lock grep and registry integrity.

Once the checklist is green, Stage 0 begins.

---

## Implementation Guidance

- **Objectives:** produce a single-process Python CLI that deterministically trims a VLSI Tcl domain based on JSON-driven selection, with F1/F2/F3 capabilities, Tcl proc identification, and call-tree tracing as the core value.
- **Key tasks:** apply the 8 sequenced doc patches (Part B), then build Stages 0–5 in order (Part C), gated by the quality thresholds in Part D.
- **Dependencies:** PR-1 through PR-5 unblock Stage 0. PR-6 unblocks Stage 5. PR-7 and PR-8 are housekeeping; they can land any time before their referenced stages.
- **Success criteria:** the six exit criteria in Part C Stage 5, plus every row in Part D green.

When Stages 0–5 are all green and the `fev_formality_real/` end-to-end acceptance run is byte-identical on two back-to-back invocations, v1 is shippable.

