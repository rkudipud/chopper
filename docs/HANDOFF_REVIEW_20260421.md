<!-- markdownlint-disable-file -->

# Chopper v2 — Final Handoff Review (Devil's Advocate Sign-Off)

**Date:** 2026-04-21
**Reviewer stance:** Python/compiler-specialist skeptic. Bias: assume the first implementer will pick the *wrong* interpretation of any ambiguous contract.
**Scope:** End-to-end review of plan, architecture, technical implementation spec, diagnostic registry, fixtures, and tooling before assigning Stage 0 to build agents.
**Verdict:** **CONDITIONAL SIGN-OFF.** Seven must-fix doc-level items (H-1..H-7), nine residual sharp edges agents must be warned about (S-1..S-9), and four process concerns (PR-1..PR-4). Zero new design work required.

**How to use this file.**

- Each finding has **Reviewer Finding**, **Suggested Fix**, and a blank **Owner Decision / Notes** block.
- Fill in the Owner Decision block with `APPROVED` / `REJECTED` / `MODIFIED:<your preference>` plus any extra guidance.
- When done, ask me to apply the approved fixes. I will cascade them into the authoritative docs and register follow-up agent prompts where applicable.

---

## Status Legend

| Severity | Meaning |
|---|---|
| **BLOCKER** | Must be resolved before Stage 0 is assigned to an agent. Doc-level edits only. |
| **SHARP EDGE** | Not blocking, but agents will coin-flip on interpretation. Add to per-stage agent prompt. |
| **PROCESS** | Workflow / tooling / assignment concern. |

---

## 1. What is already bulletproof (no action needed)

| Area | Why it passes |
|---|---|
| **Scope lock** | Clean. Forbidden-identifier grep returns zero hits in living docs. [`docs/DAY0_REVIEW.md`](DAY0_REVIEW.md) CLOSED. |
| **Bible as single authority** | [`docs/chopper_description.md`](chopper_description.md) §5.11 (GUI surface) and §5.12 (Python standards) are the source of truth; subordinate docs reference up. |
| **Diagnostic registry** | Renumbered cleanly pre-release. 68 active + 37 reserved. VE-16 at exit 3. VE-23..VE-26 trimmer codes active. VW-10 RETIRED marker preserved. |
| **Parser spec** | §3.0 state-machine table, §2.1.1 per-PE-* return contract, §4.3 canonical-name test vectors, DPA/banner rules pinned. 17 edge-case fixtures on disk, 1:1 with catalog. |
| **R1 merge model** | Provenance-aware L1/L2/L3. Cross-source `VW-18`/`VW-19` vetoes. Deterministic iteration order pinned (base first, then `project.features[]` order, then lex-sorted files). |
| **Ports minimalism** | Three ports only: `FileSystemPort`, `DiagnosticSink`, `ProgressSink`. Clock/serializer/audit/renderer ports correctly cut per DAY0 A2–A5. |
| **Phase gates** | P0 none, P1 gate VE-*, P2 gate PE-* (fixed from research), P3 gate VE-*, P4 none (TW-* are warnings by def), P5 gate VE-*, P6 gate errors-only, P7 always in `finally`. |
| **Rollback model** | No staging, no atomic promotion. Case-2 re-trim rebuilds from intact `<domain>_backup/`. Bible §2.8 and CLI help are consistent. |
| **`src/` cleanliness** | Only `__init__.py` with `__version__`. Zero legacy code; zero scaffolding drift. |

---

## 2. BLOCKERS — must fix before Stage 0 handoff (doc-level only)

### H-1 — `TrimRequest` references remain in subordinate docs

**Severity:** BLOCKER
**Files affected:** [`docs/RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) (P-30, 5 hits), [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](FUTURE_PLANNED_DEVELOPMENTS.md) (FD-10, 1 hit)

**Reviewer Finding.**
Decision B-1 collapsed `TrimService`/`TrimRequest`/`TrimResult` into `ChopperContext` + `RunResult`. Grep shows 8 live hits still naming `TrimRequest` as a Python class. A Stage-5 implementer will either invent a rival `TrimRequest` dataclass (contract drift) or leave it ambiguous (agent confusion).

**Suggested Fix.**

- [`docs/RISKS_AND_PITFALLS.md`](RISKS_AND_PITFALLS.md) P-30: replace `TrimRequest` with `ChopperContext`/`RunConfig` in the five affected paragraphs; update the "CLI layer: populate all project fields" phrasing to "CLI layer: populate all `RunConfig` project fields before constructing `ChopperContext`".
- [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](FUTURE_PLANNED_DEVELOPMENTS.md) FD-10: keep the wire-protocol JSON envelope preserved (owner requires GUI-readiness), but add one clarifying sentence: *"The wire-level JSON payload is conventionally called a 'TrimRequest' envelope; on the Python side it deserializes into `RunConfig` + `PresentationConfig` consumed by `ChopperRunner.run(ctx)`. There is no Python class named `TrimRequest`."*

**Owner Decision / Notes:**

```
i agree with your suiggestion; however scan rest of docs for these references and iron them out to a single sourtce of tuth. 
yes, gui readiness is a must however do not change the architecture to allow for gui; gui is  at lowest priority.




```

---

### H-2 — Tracing fixtures don't match the roadmap's canonical six

**Severity:** BLOCKER
**Files affected:** `tests/fixtures/tracing_domain/`, [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) Stage 2b, [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md)

**Reviewer Finding.**
Roadmap Stage 2b expects six canonical fixtures: `direct_call`, `bracketed_call`, `namespace_qualified`, `cycle`, `ambiguous`, `dynamic` — one per TW-0x code plus a baseline. On disk we have: `chain.tcl`, `cross_file.tcl`, `cycle.tcl`, `diamond.tcl`, `dynamic.tcl`, `ns_calls.tcl`. Rough coverage overlap but **no `ambiguous` fixture** — that's the one that forces `TW-02` emission. Stage-2b agents writing `test_trace_bfs.py` against roadmap names will fail to find fixtures.

**Suggested Fix (two options, pick one).**

- **Option A (recommended).** Rename/regenerate to the six canonical names. Author a new `ambiguous/` sub-fixture: two files defining the same short proc name in different namespaces, a caller using the short form. Map each sub-fixture to its target TW code (`direct_call` → baseline, `bracketed_call` → `[foo]`-style, `namespace_qualified` → `::ns::proc`, `cycle` → TW-04, `ambiguous` → TW-02, `dynamic` → TW-03).
- **Option B.** Update [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) Stage 2b + [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md) to match the six actual names, and audit that TW-01/TW-02/TW-03/TW-04 each have at least one fixture emitting them.

**Owner Decision / Notes:**

```
Option A. and add more fixtures. use fev_formality for code inspirations




```

---

### H-3 — `--plain` adapter wiring is underspecified

**Severity:** BLOCKER
**Files affected:** [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §5, [`docs/CLI_HELP_TEXT_REFERENCE.md`](CLI_HELP_TEXT_REFERENCE.md)

**Reviewer Finding.**
CLI reference advertises `--plain` = "disable Rich rendering and ANSI colors; plain text output." Ports table lists only `RichProgress` and `SilentProgress` as `ProgressSink` adapters. With `-q` off and `--plain` on, no adapter is specified. Agents will either invent a new `PlainProgress` class (scope creep) or default to `RichProgress` (contradicting the flag).

**Suggested Fix (two options, pick one).**

- **Option 1 (fewer adapters, recommended).** Keep only `RichProgress` + `SilentProgress`. Under `--plain`, initialize `RichProgress` with `no_color=True, force_terminal=False`. Document in [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §5 ports table: *"`RichProgress` handles both styled and plain text; `--plain` configures it to emit ASCII without ANSI."*
- **Option 2.** Add `PlainProgress` as a third adapter alongside `RichProgress`/`SilentProgress` in §5, and specify CLI dispatch: `-q` → `SilentProgress`, `--plain` → `PlainProgress`, else → `RichProgress`.

**Owner Decision / Notes:**

```
plain will help in normal console print. if plain is not used RICH wil be used. its a simple print switch logic. no need to create a new class for plain. just use the existing rich class and configure it to emit ascii without ansi when plain is used. this will keep the architecture simpler and avoid unnecessary complexity.




```

---

### H-4 — Dry-run P6 check set listed inconsistently in three places

**Severity:** BLOCKER
**Files affected:** [`docs/chopper_description.md`](chopper_description.md) §5.7–§5.8, [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2, [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md)

**Reviewer Finding.**
Three documents list slightly different rosters for "which VW-* codes run in dry-run P6":

- Research doc G-11: `VW-05, VW-06, VW-14, VW-15, VW-16, VW-17`
- [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md): `VW-05, VW-06, VW-08`
- [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2 comment: `VW-05, VW-06, VW-14..VW-17`

Agent implementing `validate_post(..., rewritten=())` will pick whichever doc they read last.

**Suggested Fix.**
Canonicalize one list in bible §5.7 (dry-run contract). Reference it from all subordinate docs. Recommended roster: **`VW-05, VW-06, VW-14, VW-15, VW-16, VW-17`** (VW-08 `file-empty-after-trim` needs actually-rewritten output to observe; skip in dry-run).

**Owner Decision / Notes:**

```
agree. also only maintain diag_cosdes doc a bible and refer to them from different otyther ocds, so not reinvent new codes in different docs. this will avoid confusion and maintain consistency across the documentation.perform a deep scan and establish relationships.




```

---

### H-5 — `options.cross_validate` implementation contract is prose-only

**Severity:** BLOCKER
**Files affected:** [`docs/chopper_description.md`](chopper_description.md) §3.1 and §5.8

**Reviewer Finding.**
Bible §3.1 table says `options.cross_validate` defaults to `true` and emits `VW-14`/`VW-15`/`VW-16`. But:

1. **Where does the check run?** P5b (after `GeneratorService`) or P6 (`validate_post`)? Both plausible. Agents will split.
2. **Against which set?** Filesystem re-scan of surviving tree, or `CompiledManifest.file_decisions` (manifest-only)? Dry-run forces this answer because filesystem checks can't run there.

**Suggested Fix.**
Add one paragraph in bible §5.8 immediately after the post-validate contract:

> "Cross-validate is part of P6 (`validate_post`) and uses `CompiledManifest` as the surviving-set source of truth — never the filesystem. For each step string in every surviving stage, classify by syntax: file-path literal with `.tcl`/`.pl`/`.py`/`.csh` extension → check `manifest.file_decisions` and emit `VW-14` on miss; bare proc token (no path separator, no extension) → check `manifest.proc_decisions` and emit `VW-15` on miss; `source <path>` / `iproc_source <path>` command → check `manifest.file_decisions` and emit `VW-16` on miss. Because the check is manifest-derivable, it runs identically in dry-run and live modes. When `options.cross_validate` is `false`, the three warnings are suppressed entirely."

**Owner Decision / Notes:**

```
add it to validate post. also add a note that cross validation is an expensive check and may increase the runtime, so it can be disabled with options.cross_validate = false. this will give users the flexibility to choose between thorough validation and faster runtime based on their needs. also clarify that cross validation is a crucial step for ensuring the integrity of the surviving set and should be used whenever possible, but can be skipped in cases where performance is a concern and the user is confident in the trimming results. and i agree with your suggestion to maintain a single source of truth for diagnostic codes in the bible, and refer to them from different docs to avoid confusion and maintain consistency across the documentation. perform a deep scan and establish relationships.




```

---

### H-6 — `import-linter` contract file does not exist

**Severity:** BLOCKER
**Files affected:** [`pyproject.toml`](../pyproject.toml)

**Reviewer Finding.**
[`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) Stage-0 DoD requires *"`import-linter --config pyproject.toml` passes against a sample contract."* There is no `[tool.importlinter]` section in [`pyproject.toml`](../pyproject.toml) and no `importlinter.ini`. Stage-0 agent has nothing to base their import contract on; the `cli → orchestrator → services → core` rule lives only in prose.

**Suggested Fix.**
Add a `[tool.importlinter]` block to [`pyproject.toml`](../pyproject.toml) with three contracts, committed empty-passing (zero siblings yet):

1. **Layered:** `chopper.core` → services (`parser`, `config`, `compiler`, `trimmer`, `generators`, `validator`, `audit`) → `chopper.orchestrator` → `chopper.cli`. Each higher layer may import from lower layers only.
2. **Independence:** `chopper.core` imports only stdlib. Siblings (`parser`, `compiler`, etc.) do not import each other.
3. **Adapters:** `chopper.adapters` imports `chopper.core` and third-party libs only.

Add `import-linter` to the `dev` extras in [`pyproject.toml`](../pyproject.toml) and to the `make check` target.

**Owner Decision / Notes:**

```
add it. agree with your sugegstion to maintain a single source of truth for diagnostic codes in the bible, and refer to them from different docs to avoid confusion and maintain consistency across the documentation. perform a deep scan and establish relationships.




```

---

### H-7 — Diagnostic / RunResult JSON wire schemas are not published

**Severity:** BLOCKER
**Files affected:** [`json_kit/schemas/`](../json_kit/schemas/) (missing files)

**Reviewer Finding.**
Owner explicitly wants GUI-readiness via streamable JSON (B-1 decision). [`json_kit/schemas/`](../json_kit/schemas/) ships `base-v1.schema.json`, `feature-v1.schema.json`, `project-v1.schema.json` — the **input** contracts. There is no `diagnostic-v1.schema.json` or `run-result-v1.schema.json` — the **output** contracts. Without published schemas, the GUI/stdio wire format is "whatever Python's `asdict()` emits this month," which drifts silently and breaks the GUI without warning.

**Suggested Fix.**

1. Author `json_kit/schemas/diagnostic-v1.schema.json` covering the on-wire shape of `Diagnostic` (code, severity, phase, source, path, line_no, message, hint, exit_code, dedupe_bucket).
2. Author `json_kit/schemas/run-result-v1.schema.json` covering the on-wire shape of `RunResult` (exit_code, run_id, artifacts_present, manifest_summary, graph_summary, diagnostics_summary — not the full manifest, that stays in `.chopper/compiled_manifest.json`).
3. Author `json_kit/schemas/progress-event-v1.schema.json` for `ProgressSink` JSONL events (`phase_started`/`phase_done`/`step`).
4. Add a Stage-0 round-trip test: serialize every `Diagnostic` / `RunResult` / progress event and validate against its schema. Failing schema validation fails the build.

**Owner Decision / Notes:**

```
alright i agree. you need to think to the extreme mode and consider all cases to ideate these jsons and make sure they are robust enough. also add a note that these schemas will serve as the contract between the CLI and any potential GUI, ensuring that both components can evolve independently while maintaining compatibility. by validating against these schemas in CI, we can catch any breaking changes early and maintain a stable interface for users and developers alike.




```

---

## 3. SHARP EDGES — agents must handle deliberately

Each of these is a coin-flip for the first implementer. Not a blocker on its own, but the specified prompt line should go into the per-stage agent briefing.

### S-1 — BFS frontier dedup semantics

**Stage:** 2b (tracer)
**Risk:** If proc `A` calls `B` three times, do three copies of `B` enter the frontier, or one? Determinism depends on answer.
**Suggested prompt line.** *"Frontier entries are unique per canonical name. Duplicates from multiple call sites collapse to a single BFS visit; the `Edge` record accumulates multiple `call_sites`. Before popping, lex-sort and deduplicate the frontier."*

**Owner Decision / Notes:**

```
let 3 enter. the reason is that if we collapse them into one, we might miss some edge cases where the same proc is called from different places and has different behaviors based on the call site. allowing duplicates will give us a more accurate picture of the call graph and help us identify any potential issues that might arise from different call sites. it will also make our tracing more robust and comprehensive, as we will be able to see all the different contexts in which a proc is called. while it might introduce some redundancy in the frontier, it will ultimately lead to a more thorough analysis and better results.

```

---

### S-2 — DPA alignment drift between P2 and P5

**Stage:** 3a (trimmer)
**Risk:** If a file's mtime changes between parse and trim (grid NFS race), byte spans desync and trimming corrupts the file.
**Suggested prompt line.** *"TrimmerService must stat each file on read and compare against `ParsedFile.mtime` captured at P2. If mismatch, emit `VE-26 proc-atomic-drop-failed` and abort the file. Requires a new `mtime: float` field on `ParsedFile` in Stage 0."*
**Stage 0 action required.** Add `mtime: float` to `ParsedFile` frozen dataclass.

**Owner Decision / Notes:**

```
remove all timed events and locks. assumption is that teh system stays static when this process runs. do not over comoplicate with locks and timers. if the file changes during the process, it is a programmer error and should be fixed by the user. we can emit a warning or error message to inform the user about the change, but we should not try to handle it automatically as it can lead to unexpected behavior and further complications. instead, we should focus on providing clear documentation and guidance to users about the expected state of the system during the trimming process, and encourage them to ensure that files are not modified during this time to avoid any issues.its a nontrivial and make a note in hard nos section that this must never be implemented with timers or locks, and that the system is expected to be static during the trimming process. any change to files during this time is a programmer error and should be treated as such. we can emit a warning or error message to inform the user about the change, but we should not try to handle it automatically as it can lead to unexpected behavior and further complications. instead, we should focus on providing clear documentation and guidance to users about the expected state of the system during the trimming process, and encourage them to ensure that files are not modified during this time to avoid any issues.

```

---

### S-3 — Python 3.9 compatibility for PEP 585 generics

**Stage:** All
**Risk:** [`pyproject.toml`](../pyproject.toml) targets 3.9+. Models use `list[X]`/`dict[K,V]` (PEP 585, 3.9 runtime-only with `from __future__ import annotations`). A missing future-import on one module bites 3.9 at runtime.
**Suggested fix.** Add to bible §5.12 as mandatory: *"Every module in `src/chopper/` MUST begin with `from __future__ import annotations`. Enforced via ruff rule `FA102`."*

**Owner Decision / Notes:**

```
make it python 3.13 plus only. python 3.9 is too old and has reached end of life, and supporting it would require additional complexity and testing. by targeting python 3.13 and above, we can take advantage of the latest features and improvements in the language, while also simplifying our codebase and reducing maintenance overhead. this will allow us to focus on building a robust and efficient tool without worrying about compatibility issues with older versions of python. we can also provide clear documentation about the minimum python version required to run chopper, so that users are aware of the requirements before they start using the tool.

```

---

### S-4 — `.chopper/internal-error.log` referenced but unlisted

**Stage:** 3c (audit) + CLI exit-3 path
**Risk:** CLI help and architecture plan reference `.chopper/internal-error.log` on exit 3. Bible §5.5.10 audit-artifact table does not list it. Agent will either skip writing it or invent a path.
**Suggested fix.** Add a row to bible §5.5.10: *"`internal-error.log` — written only on exit 3 (programmer error). Contains `run_id`, timestamp, full traceback, and active diagnostic snapshot. Written by the CLI's exit-3 handler (not `AuditService`) because audit itself may have failed."*

**Owner Decision / Notes:**

```
add it to bible and make sure all the items are well defined and utilised. also add a note that this log file will serve as a crucial resource for debugging and troubleshooting any issues that arise during the execution of chopper, and should be carefully maintained and protected to ensure that it contains accurate and complete information about any internal errors that occur. we should also provide clear documentation about the format and contents of this log file, so that users and developers can easily understand and utilize it when needed.

```

---

### S-5 — Call-extraction vs regex temptation

**Stage:** 1 (parser)
**Risk:** §5.4.1 R3 "hybrid SNORT suppression" is a token-stream filter, not a grammar. Regex-per-line implementations leak false calls from comments/strings inside proc bodies.
**Suggested prompt line.** *"Call extraction (`call_extractor.py`) consumes the already-tokenized command-position token stream from `tokenizer.py`, filtered to tokens whose context-stack top is `PROC_BODY`. Do NOT re-scan raw text with regex. Comments and quoted strings are already excluded by tokenizer state flags."*

**Owner Decision / Notes:**

```
agreed. we need best of both worlds. we can use the token stream from the tokenizer to accurately identify command positions and their contexts, while also leveraging regex patterns to extract specific information from those tokens when necessary. this approach allows us to maintain the precision and reliability of the token-based parsing, while also providing the flexibility and power of regex for more complex extraction tasks. by combining these two methods, we can ensure that we are accurately capturing the relevant information from the source code without being misled by comments or strings that may contain similar patterns. SNORT has been proven and tested. 

```

---

### S-6 — `PYTHONHASHSEED` determinism leakage

**Stage:** All that emit JSON
**Risk:** `dict`/`set` iteration order leaks into golden files. Manifests and dependency graphs golden-fail randomly in CI.
**Suggested fix.** Two-step CI guard:

1. Every boundary serialization calls `sorted(...)` on dict keys and set members explicitly.
2. CI runs the test suite twice on each commit — once with `PYTHONHASHSEED=0`, once with a random seed. Any diff = determinism bug.

**Owner Decision / Notes:**

```
I need your input on this one. am lost on how to implement it without adding too much complexity to the CI pipeline. running the test suite twice with different `PYTHONHASHSEED` values could potentially double the testing time, which might not be ideal. however, ensuring determinism is crucial for the reliability of our tests and the stability of our golden files. one possible solution could be to set `PYTHONHASHSEED=0` for all CI runs to maintain consistency and avoid any non-deterministic behavior. this way, we can ensure that our tests are reliable and our golden files remain stable without introducing additional complexity to our CI pipeline. what do you think about this approach?

```

---

### S-7 — Empty-domain and single-empty-file fixtures missing

**Stage:** 3c (audit) and 5 (CLI render)
**Risk:** Div-by-zero in statistics rendering and empty-index lookups.
**Suggested fix.** Add two fixtures to `tests/fixtures/edge_cases/`:

- `domain_empty/` — valid JSON, zero `.tcl` files.
- `domain_single_empty_file/` — one `.tcl` file containing only a comment; zero procs.

Golden-file both: expected `RunResult.exit_code=0`, `stats.files_out=0` or `1`, `stats.procs_out=0`.

**Owner Decision / Notes:**

```
Add them. these edge cases are important to test because they can reveal potential issues with our handling of empty domains and files, which could lead to unexpected behavior or errors in our statistics rendering and index lookups. by including these fixtures in our test suite, we can ensure that our code is robust and can gracefully handle these scenarios without crashing or producing incorrect results. it's crucial to have comprehensive test coverage that includes edge cases like these to maintain the reliability and stability of our tool.

```

---

### S-8 — `CompiledManifest` immutability at the P3→P4→P5 handoff

**Stage:** 2b → 3a/3b handoff
**Risk:** If `CompiledManifest` isn't frozen between P3 and P4, the tracer can accidentally promote traced callees into `proc_decisions` (which would violate the "trace is reporting-only" invariant). Same risk between P4 and P5 for `GeneratorService`.
**Suggested prompt line.** *"`CompiledManifest` is a `@dataclass(frozen=True)` and is constructed exactly once by `CompilerService.run()`. `TracerService` and `GeneratorService` hold read-only references and return new tuples. Any attempt to mutate raises `FrozenInstanceError` — treat that as a programmer error (exit 3)."*

**Owner Decision / Notes:**

```
add this! trace is for log only. it should never be used for decision making. if we want to use it for decision making, we need to make sure that it is deterministic and does not leak any implementation details. by keeping the trace as a log only, we can ensure that it serves its intended purpose without introducing any unintended consequences or complexities into our implementation.users will look at trace and will modify jsons. 

```

---

### S-9 — Hypothesis runtime budget

**Stage:** 1 (parser property tests)
**Risk:** 500 examples × 17 fixtures × tokenizer state machine can push CI past 10 minutes.
**Suggested fix.** Start parser property tests at `max_examples=200`. Raise to 500 only after profiling confirms CI budget is met. Mark long tests with `@settings(deadline=None, max_examples=100)` where appropriate.

**Owner Decision / Notes:**

```
alright cap examples for testing. we can start with a lower number of examples to ensure that our tests run efficiently within our CI budget, and then gradually increase the number of examples as we optimize our tests and confirm that they can run within the desired time frame. by using the `@settings` decorator from the `hypothesis` library, we can also set a deadline for our tests to prevent them from running indefinitely, while still allowing for a sufficient number of examples to be generated for thorough testing. this approach will help us maintain a balance between test coverage and efficiency in our CI pipeline.

```

---

## 4. PROCESS CONCERNS

### PR-1 — `.copilot-tracking/research/` drift risk

**Severity:** PROCESS
**Files affected:** [`.copilot-tracking/research/20260421-implementation-roadmap.md`](../.copilot-tracking/research/20260421-implementation-roadmap.md), [`.copilot-tracking/research/20260421-handoff-readiness-devils-advocate-research.md`](../.copilot-tracking/research/20260421-handoff-readiness-devils-advocate-research.md)

**Reviewer Finding.**
The research-tracking docs contain a wider `PresentationConfig` (`--debug`, `--no-color`, `--json`) than the published [`docs/CLI_HELP_TEXT_REFERENCE.md`](CLI_HELP_TEXT_REFERENCE.md) (which has only `-v`, `-q`, `--plain`, `--strict`). Agents reading both will hallucinate flags that don't exist.

**Suggested Fix.**
Either (a) delete the research docs now that their decisions are cascaded, or (b) add a banner to the top of each: *"SUPERSEDED. Decisions cascaded to `docs/chopper_description.md` / `docs/ARCHITECTURE_PLAN.md` / `docs/DIAGNOSTIC_CODES.md`. Do not read for implementation guidance. Kept only for provenance."*

**Owner Decision / Notes:**

```
delete this direcorty

```

---

### PR-2 — Milestone scenario count drift

**Severity:** PROCESS
**Files affected:** [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) M6, [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md)

**Reviewer Finding.**
Roadmap M6 says "28+ TESTING_STRATEGY scenarios"; research doc says "21". Testing strategy doc itself needs to be the source of truth.
**Suggested Fix.**
Count actual named scenarios in [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md) §5 and update M6 to that number. Lock the count in CI (test named `test_testing_strategy_scenario_count` asserting `len(scenarios) == N`).

**Owner Decision / Notes:**

```
realign them!

```

---

### PR-3 — No agent-assignment matrix

**Severity:** PROCESS

**Reviewer Finding.**
User signalled "I'll assign the task to agents for actual tool buildout." No mapping exists from stage to preferred agent profile. Suboptimal assignments waste agent turns.

**Suggested Fix.** Recommended mapping (add to [`docs/IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) preamble):

| Stage | Recommended Agent | Rationale |
|---|---|---|
| Stage 0 — `core/` | `SWE` | Mechanical scaffolding; small surface; high discipline. |
| Stage 1 — parser | `Principal software engineer` | Highest-risk module; TC-01/TC-02 + P-01..P-36 depth. |
| Stage 2a — config | `SWE` | Schema-driven; mechanical. |
| Stage 2b — compiler + tracer | `Principal software engineer` | R1 merge algorithm + BFS + determinism; subtle. |
| Stage 3a — trimmer + state | `Principal software engineer` | Filesystem side-effects + fault injection matter. |
| Stage 3b — generators | `SWE` | Straight emission given manifest. |
| Stage 3c — audit | `SWE` | Fixed artifact list; mechanical. |
| Stage 4 — validator | `SWE` | Registry-driven. |
| Stage 5 — CLI + E2E | `SWE` + `Devils Advocate` review before merge | Integration-heavy; needs adversarial review. |

Every stage exit gate runs a **second-agent review** (different agent than the one that wrote it) against the stage's DoD.

**Owner Decision / Notes:**

```
Add it in the handoff document. this will help ensure that we are assigning the right tasks to the right agents based on their expertise and experience, which can lead to a more efficient and effective implementation process. by providing clear guidance on which agent profiles are best suited for each stage of the implementation, we can optimize our resources and increase the likelihood of a successful outcome. it's important to regularly review and update this mapping as needed to ensure that it remains accurate and relevant throughout the implementation process.

```

---

### PR-4 — No automated doc↔code consistency gate

**Severity:** PROCESS

**Reviewer Finding.**
Agents WILL misread one spec. Today there is no CI gate that catches "agent invented a new diagnostic code" or "agent changed a service signature."

**Suggested Fix.** Two scripts wired into `make ci`:

1. **Registry cross-check.** Grep every `Diagnostic(code="XX-NN")` literal in `src/chopper/` and assert each appears as an Active row in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md). Fail CI otherwise.
2. **Signature cross-check.** Parse every `class *Service:` in `src/chopper/` with `ast` and assert the `run(...)` signature matches the corresponding row in [`docs/ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §9.2 service table. Fail CI otherwise.

Both scripts trivially implementable (≤50 lines each) and catch the most common class of misinterpretation defect at review time.

**Owner Decision / Notes:**

```
Agree with your sggestions. we need to maintain consistuency and refer abck gating. also add a note that these gates will help ensure that our implementation remains consistent with our documentation and specifications, and will allow us to catch any discrepancies or deviations early in the development process. by automating these checks in our CI pipeline, we can maintain a high level of quality and reliability in our codebase, while also ensuring that our documentation remains accurate and up-to-date. it's important to regularly review and update these gates as needed to ensure that they continue to serve their intended purpose effectively throughout the implementation process.

```

---

## 5. What I am explicitly NOT worried about

Flagging these so reviewers do not pile on:

- **Single-threaded perf.** 1 GB synchronous `read_text()` is fine for 3–5 min budget. No async/threads/mmap.
- **Latin-1 fallback correctness.** `PW-02` is trivial; one test vector suffices.
- **Computed `namespace eval` names.** `PW-04` + skip is correct. Do not chase heuristic resolution.
- **Cross-domain references.** Bible §2.9 + `VW-17 external-reference` as advisory is correct; no cross-domain graph.
- **Cleanup complexity.** `chopper cleanup --confirm` is literally `shutil.rmtree(<domain>_backup)`. Do not route through the runner. Bible and plan both state this.
- **Scope-lock re-opening.** No forbidden tokens appear in living docs. Agents who try to reintroduce them will be caught by the grep gate.

---

## 6. Sign-off Criteria

I will sign off on agent handoff when **all blockers (H-1..H-7)** are resolved with approved fixes applied. Sharp edges (S-1..S-9) and process concerns (PR-1..PR-4) can land in parallel or be tracked as Stage-N prerequisites.

Estimated total editing effort once approvals are in: **half a working session**.

**Stage 0 can be assigned the moment H-1..H-7 are green.**

---

## 7. Overall Owner Sign-Off

When you finish filling in the individual decision blocks above, mark overall status here:

- [ ] All blockers reviewed and decisions recorded.
- [ ] All sharp edges reviewed and decisions recorded.
- [ ] All process concerns reviewed and decisions recorded.
- [ ] Ready to apply approved fixes. (Tell me: "apply the approved fixes from HANDOFF_REVIEW_20260421.md".)

**Overall Notes / Direction to Implementation Agents:**

```
(leave blank — to be filled by owner)




```
