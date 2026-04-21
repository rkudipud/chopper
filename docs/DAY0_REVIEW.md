# Day-0 Review — Devil's-Advocate Pass on the Pre-Implementation Docs

This is a review memo, not a spec. It challenges the current doc set against the user's stated intent:

> "All I care about is F1, F2, F3 working. Core is the Tcl parsing algorithms that identify procs for deletion/copy and a call tree. Final codebase is a trimmed version of the original based on logical superposition of base + feature JSONs. Simple as that. Do not over-complicate. Hard No's stay Hard No's."

Where "F1/F2/F3" = the three capability classes in the bible §2.1 (file-level, proc-level, stage-level) — **not** pipeline phases.

Each finding has a proposed action and a decision line. Bible / architecture-plan / registry edits do **not** land until you sign off — see [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) §2.

---

## Verdict at a glance

| Area | State |
|---|---|
| Scope lock (closed decisions for locks, plugins, MCP, AI, hand-edit stash, scan mode) | **Solid.** Keep as-is. |
| Bible §3 capability model, R1 L1/L2/L3 merge rules | **Correct.** Matches the "superposition of base + features" mental model. |
| Parser spec (Tcl 12-rule grounding, SNORT-absorbed suppression, P-01..P-07, P-32) | **Correct.** Needs concrete test-vector and state-diagram additions. |
| Architecture plan (hexagonal + pipeline, single-threaded, no locks) | **Shape is right.** But ports and adapters have crept — see findings A1–A9. |
| Diagnostic-code registry | **Authoritative.** One code-reassignment to fix (VW-10). |
| Implementation roadmap | **Missing operational detail** — see [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) (new). |
| 11 JSON examples in `json_kit/` | **Good.** Already the concrete contract. |
| Docs hygiene | `docs_old/` still exists; one dangling reference to a `docs/TECHNICAL_IMPLEMENTATION.md` that never got written. |

Bottom line: the spec is usable for handoff after the edits below. None are structural rewrites — they are **subtractions** to match the user's simplicity constraint, plus gaps to close before Stage 0 begins.

---

## A. Scope creep inside the architecture plan (must cut)

These items do nothing for F1/F2/F3 and should either be removed or punted to `FUTURE_PLANNED_DEVELOPMENTS.md` as FD-xx entries.

### A1. `PresentationConfig` is a 5-flag × 5-adapter UX matrix

**What exists today** (ARCHITECTURE_PLAN §6.1):

- Flags: `--verbose`, `--debug`, `--plain`, `--no-color`, `--json`.
- Adapter variants: `RichTable`, `PlainTable`, `JsonRenderer`, `RichProgress`, `PlainProgress`, `JsonlProgress`, `JsonlSink`.

**Cost.** Five flags × adapter variants × interaction matrix ("`--json` wins over `--plain` for rendering but `--plain` still disables Rich imports") = a surface area that doesn't advance trimming.

**Proposed cut for v1.**

| Flag | Keep / cut | Reason |
|---|---|---|
| `-v / --verbose` | **Keep** | Needed to debug stage-by-stage. `INFO` default, `DEBUG` with `-v`. |
| `-q / --quiet` | **Keep** | Silent progress for CI / grid. |
| `--plain` | **Cut → FD** | Rich handles no-tty automatically; no demand from a CLI user. |
| `--no-color` | **Cut → FD** | Same. Rich honors `NO_COLOR` env var for free. |
| `--json` | **Cut → FD** | `diagnostics.json` in `.chopper/` is already machine-readable. Two output surfaces competing for correctness is an anti-pattern. |
| `--debug` | **Cut** | Exit-code-3 handling already dumps `.chopper/internal-error.log`; that is the debug artifact. |

**Adapter implications.** `PlainTable`, `JsonRenderer`, `PlainProgress`, `JsonlProgress`, `JsonlSink` all go to FD. The CLI has exactly one output path: Rich (or no-tty-Rich if stdout is not a terminal), plus `diagnostics.json`.

**Cascade.** Update `ARCHITECTURE_PLAN.md` §6.1 table, `CLI_HELP_TEXT_REFERENCE.md` flag list. File `FD-10 machine-readable-cli-output` in `FUTURE_PLANNED_DEVELOPMENTS.md`.

- [ ] **Decision:** Cut A1 as proposed? (yes / no / different subset)

### A2. `TableRenderer` as a port with three adapters

There is exactly one output today: CLI status at end-of-run. Three renderer adapters (`RichTable`, `JSONTable`, `MarkdownTable`) with a Protocol are scaffolding for a need that doesn't exist.

**Proposed cut.** Remove `TableRenderer` from the port catalog. CLI calls `rich.print` directly in `cli/render.py`. Services continue to emit diagnostics only; they never render.

- [ ] **Decision:** Cut A2? (yes / no)

### A3. `SerializerPort` as a port

It's `json.dumps(asdict(model), sort_keys=True)` under every adapter. There is no alternate serializer planned (not YAML, not msgpack — `$schema` fields explicitly declare JSON). A port abstraction around a one-liner is machinery without value.

**Proposed cut.** Replace the port with a single helper `core/serialization.py::dump_model(obj) -> str`. All services and audit use it directly. No `ctx.serde`.

- [ ] **Decision:** Cut A3? (yes / no)

### A4. `AuditStore` port + `DotChopperAuditStore` + `EphemeralAuditStore`

`AuditService.run()` writes exactly seven named files under `<domain>/.chopper/`. This is a concrete list, not an abstraction. Swapping implementations is not imagined anywhere.

**Proposed cut.** Remove `AuditStore` port. `AuditService` calls `ctx.fs.write_text()` directly for each of its seven files. The `audit_root` path already lives on `RunConfig`. `EphemeralAuditStore` for tests is replaced by pointing `audit_root` at an `InMemoryFS` path (same `ctx.fs` already handles that).

- [ ] **Decision:** Cut A4? (yes / no)

### A5. `ClockPort` + `SystemClock` + `FrozenClock`

Chopper uses clocks in exactly two places: `chopper_run.json.timestamp_start/_end` and `run_id` derivation. That is 2 `datetime.utcnow()` calls.

**Proposed cut.** Remove `ClockPort`. `AuditService` calls `datetime.now(timezone.utc)` directly. Tests that need frozen time use `freezegun` or `monkeypatch` on the function. One less port, no observable loss.

- [ ] **Decision:** Cut A5? (yes / no)

### A6. `dedupe_bucket` field on `Diagnostic` + last-write-wins

Premature flexibility. None of the 33 corner-case scenarios in §12 require multi-bucket emission or last-write-wins refinement. First-write-wins dedupe on `(code, path, line_no, message)` is simpler and sufficient.

**Proposed cut.** Remove the `dedupe_bucket` field and the last-write-wins rule. Sink stores the first emission, silently drops duplicates.

- [ ] **Decision:** Cut A6? (yes / no)

### A7. `RunMode = TRIM | VALIDATE | CLEANUP` on `RunConfig`

The CLI already dispatches on the subcommand name — `chopper validate` calls `run_validate()`, `chopper trim` calls `run_trim()`, `chopper cleanup` calls `run_cleanup()`. Putting a redundant enum on the engine config means the runner branches internally on a value the CLI already consumed.

Also: `cleanup` doesn't go through the 7-phase pipeline at all — it's just `shutil.rmtree(<domain>_backup)`. Putting it in `RunMode` falsely suggests it enters `ChopperRunner.run()`.

**Proposed cut.** Drop `RunMode` from `RunConfig`. `cli/commands.py` keeps three explicit entry functions. The runner only knows about `dry_run: bool` (which it already does).

- [ ] **Decision:** Cut A7? (yes / no)

### A8. Corner-case scenarios 30, 31, 32 (Windows case-collision, symlink cycles, non-ASCII paths)

Bible §2 says the trim environment is Linux grid; JSON authoring may be on Windows. These three scenarios cover *runtime* on Windows, symlinked domain trees, and non-ASCII Tcl filenames.

None of these exist in the described workflow. They would require: case-insensitive `pathlib` support, symlink cycle detection with `lstat`, and UTF-8 path normalization tests. That's real work for zero real users.

**Proposed action.** Keep POSIX path normalization (it's already free via `pathlib.PurePosixPath`). Drop scenarios 30 / 31 / 32 from §12 acceptance catalog. Move to `FD-11 multi-platform-domain-support`.

- [ ] **Decision:** Drop A8 scenarios? (yes / no)

### A9. Two separate validator services (PreValidatorService, PostValidatorService)

Stylistic. The "every service has one `run()`" rule becomes a straitjacket when pre-validation and post-validation are literally two free functions against the same module.

**Proposed action (soft).** Combine into `validator/service.py` with two functions: `validate_pre(ctx, loaded) -> None` and `validate_post(ctx, manifest, rewritten_paths) -> None`. The runner calls them by name. No service class contortions.

Keep as two classes if the team genuinely prefers. Not a blocker.

- [ ] **Decision:** Collapse A9 into functions? (yes / no / keep as classes)

---

## B. Doc size and split

`ARCHITECTURE_PLAN.md` is ~2000 lines for a CLI that reads JSON, parses Tcl, writes trimmed files. Comparable tools (Ruff, Pylint, dbt-core) ship ~400 lines of design doc. The plan has absorbed:

- 33-row corner-case catalog (really a test plan).
- 5-reviewer multi-expert panel with per-reviewer objections and responses.
- Closed-decisions Q1–Q6 with multi-paragraph rationale each.
- Full diagnostic-sink contract + rules + invariants.
- Stage-by-stage roadmap.

Engineers reading this for the first time will drown. Splitting keeps each file single-purpose.

**Proposed split.**

| Current content | New home |
|---|---|
| §1–§10 (framing, modules, ports, services, context, sink, inter-service contract) | `ARCHITECTURE.md` (≤500 lines) |
| §11 (determinism + concurrency) | Fold into `ARCHITECTURE.md` §contracts |
| §12 (33-row corner-case catalog) | Move to [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md) — it *is* the acceptance test plan |
| §13 (multi-expert review panel) | Delete (served its purpose; findings now in §16 closed decisions and this review) |
| §14 (contributor playbook) | `CONTRIBUTING.md` at repo root |
| §15 (stage roadmap) | Move to [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) (new, this turn) |
| §16 (closed decisions) | Fold into `ARCHITECTURE.md` §closed-decisions |

Result: `ARCHITECTURE.md` ≈ 500 lines, no multi-expert panel, no test catalog, no contributor bits. Engineers skim it in 15 minutes.

- [ ] **Decision:** Approve the split? (yes / no / partial)

---

## C. Implementation roadmap gaps

Stages 0–5 are named but each stage lacks:

- **Definition of Done** (what green state marks the stage complete?).
- **Demo checkpoint** (what can be shown to the user?).
- **Exit criteria to next stage** (what must be verified before Stage N+1 starts?).
- **Fixture and test gate** (which `tests/fixtures/*` must pass?).

Also: **Stage 3 bundles trimmer + generators + audit into one stage**. That's three separate modules, each with non-trivial risk. Split into 3a / 3b / 3c.

**Deliverable.** This is filled in by `IMPLEMENTATION_ROADMAP.md` (new doc, next file). No decision needed — it's pure addition.

---

## D. Parser spec gaps (core risk area)

The parser is the highest-risk module. Findings:

### D1. Concrete test-fixture list matched to P-01..P-36 pitfalls

`RISKS_AND_PITFALLS.md` names fixtures (`brace_in_string_literal`, `backslash_line_continuation`, `nested_namespace_accumulates`, etc.) but `tests/fixtures/edge_cases/` is not audited. Before Stage 1 begins:

- [ ] **Action:** Audit `tests/fixtures/edge_cases/` against the pitfall list. File any missing fixture as a Stage-1 prerequisite.

### D2. Parser state-machine table

[`TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §3 describes rules in prose. Engineers will re-derive the transition table. Add an explicit table:

```
State      : (brace_depth, in_quote, in_comment, context_stack_top)
Transitions: char / token -> next state / side-effect
```

One concrete table prevents every engineer from inventing their own.

- [ ] **Decision:** Add the state-machine table to `TCL_PARSER_SPEC.md` §3? (yes / no)

### D3. Canonical-name test-vector table

Contract says `"<relative-path>::<qualified_name>"` but the namespace composition is a code rule from pitfall P-03. Need:

```
(file, namespace_stack, proc_short_name) -> canonical_name

("utils.tcl", [],          "helper")     -> "utils.tcl::helper"
("utils.tcl", ["a"],       "helper")     -> "utils.tcl::a::helper"
("utils.tcl", ["a","b"],   "helper")     -> "utils.tcl::a::b::helper"
("utils.tcl", [],          "::abs::x")   -> "utils.tcl::abs::x"      (leading :: stripped)
("utils.tcl", ["a"],       "::abs::x")   -> "utils.tcl::abs::x"      (absolute wins over nesting)
```

One table, ten rows, end of debate.

- [ ] **Decision:** Add test-vector table to `TCL_PARSER_SPEC.md` §4.3 and the bible §5.4.1? (yes / no)

### D4. `PE-01` vs `PE-02` return-value contract cross-reference

Bible §5.4.1 has the authoritative table (PE-02 → `[]`, PE-01 → full list with last-wins). Parser spec §2.1 mentions it in prose but doesn't show the table. Duplicate the table in `TCL_PARSER_SPEC.md` §2.1 (or add a direct cross-ref).

- [ ] **Decision:** Add the table to parser spec? (yes / no / cross-ref only)

---

## E. Tracer (F2 core) gaps

### E1. Worked BFS example is missing

Bible §5.4 specifies the algorithm, §5.4.1 explains the handoff. No concrete walk-through exists. Add one worked example with ~6 procs, one cycle, one ambiguous match, one unresolved, one dynamic-call token. Show the frontier pop-by-pop. This is 30 lines and saves engineers a week of TW-01/02/03/04 edge-case debate.

- [ ] **Decision:** Add worked example to bible §5.4? (yes / no)

### E2. `source` / `iproc_source` edges — survival effect clarification

§5.4 talks about proc edges. §3.4 mentions `source_refs`. Nowhere does it bluntly state: **`source` edges are reporting-only, identical to proc edges — they never copy files**. Add one sentence in §5.4 R3 and §3.4 hook semantics to make this non-negotiable.

- [ ] **Decision:** Add clarification? (yes / no)

### E3. Fixture `tests/fixtures/tracing_domain/` specification

Existing directory is listed but contents unknown. Needs 6 named sub-fixtures: `direct_call`, `bracketed_call`, `namespace_qualified`, `cycle`, `ambiguous`, `dynamic`. Each is 2–3 Tcl files plus an expected `dependency_graph.json`.

- [ ] **Action (Stage 1 pre-req):** Audit and author missing tracing-domain fixtures.

---

## F. R1 merge-rule fixes

### F1. `VW-10` reassignment is a registry violation

The registry rule (from `project.instructions.md`): *"Do not invent ad-hoc codes or reuse retired slots."* Bible §3.2 "Retired codes" admits openly: `VW-10` was retired, then un-retired and reassigned to `cross-source-fe-vetoed`. That reassignment conflicts with the stated policy.

**Problem.** Any residual test fixture, git history, log, or developer memory that recalls the old meaning will silently mis-interpret the new code. This is the exact failure mode the "never renumber" rule exists to prevent.

**Proposed fix.**

1. `VW-10` → **permanently retired** (treat identically to VE-16, VE-24, VI-04, VI-05).
2. Assign `cross-source-fe-vetoed` to **`VW-19`** (currently reserved — lowest available).
3. Update all ~20 references across `chopper_description.md`, `ARCHITECTURE_PLAN.md`, `DIAGNOSTIC_CODES.md`.
4. Add a "retired — do not reuse" row for VW-10 in the registry.

This is a mechanical rename and I can do it in one pass once approved.

- [ ] **Decision:** Retire VW-10, promote to VW-19? (yes / no / keep reassignment)

### F2. L3 aggregation iteration order

L3 is spec'd as a per-file algorithm but the compiler must iterate *across* files deterministically to produce stable diagnostic emission. Bible §5.3 doesn't pin this down. Add to §5.3:

> **Iteration order (emission determinism).** During P3 cross-source aggregation: iterate sources in (base, then features in `project.features[]` order); within each source, iterate files in lexicographic POSIX order; emit all per-file and cross-source warnings in that traversal order. Golden tests snapshot this ordering.

- [ ] **Decision:** Add iteration-order clause to bible §5.3? (yes / no)

---

## G. Spec bugs / reserved-seams

### G1. `options.cross_validate` (bible §3.1)

Mentioned once. Does nothing visibly. Either:

- Spec its exact behavior (what does "cross-validate F3 output against F1/F2" mean in P5 or P6?), or
- Remove the field from the base JSON table and the schema.

Current wording ("Default: `true`") reads like a reserved-but-unwired feature — exactly the pattern §7 and §16 Q1 forbid.

- [ ] **Decision:** Define behavior, or delete the field? (define / delete / defer to FD)

### G2. `options.template_script` + VE-18

`VE-18 template-script-path-escapes` validates path safety of a field that is "reserved and not executed in v1." That is a reserved seam with a registered diagnostic code. Per §7 scope-lock: no reserved seams.

**Proposed cut.** Remove `options.template_script` from the schema. Retire `VE-18`. If a template-script feature is ever wanted, file `FD-12 template-script-generation`.

- [ ] **Decision:** Cut VE-18 + field? (yes / no / define now)

### G3. `VI-03 domain-hand-edited` detection algorithm is unspecified

Bible §2.8 Case 2 says "If the existing `<domain>/` contents have been hand-edited, emit VI-03." How? No content hash is stored between runs. No comparison algorithm is specified.

**Options.**

- **(a) Content-hash checkpoint.** Write `.chopper/domain_tree_hash` at P7; compare at P0. Adds a file, an algorithm, and a failure mode.
- **(b) Always emit VI-03 on case-2.** Every re-trim tells the user "any manual edits are now gone." No detection, no false negatives. Loud but safe.
- **(c) Kill VI-03 entirely.** The CLI prints a one-liner on every re-trim: *"Re-trim rebuilds `<domain>/` from `<domain>_backup/`. Any manual edits in `<domain>/` will be discarded."* No diagnostic code, just help text.

User said "no ideal conditions, hand edits are the user's problem." **Option (c) or (b)** match that. (a) is over-engineering.

- [ ] **Decision:** (a) / (b) / (c)?

### G4. `RunMode` cleanup subcommand doesn't use the pipeline

Confirmed by scanning `cli/main.py` commands: `chopper cleanup --confirm` deletes `<domain>_backup/` and exits. It doesn't load JSON, parse Tcl, or run the 7-phase pipeline. Currently the `ARCHITECTURE_PLAN.md` suggests it is a mode of `ChopperRunner`. Clarify: `cleanup` is a standalone CLI action that never enters the runner. (Fixed automatically if A7 is approved.)

---

## H. Housekeeping

### H1. `docs_old/` exists with four stale docs

`docs_old/ACTION_PLAN.md`, `DEVELOPER_KICKOFF.md`, `ENGINEERING_HANDOFF_CHECKLIST.md`, `TECHNICAL_REQUIREMENTS.md`, `README.md`. Nothing in the active `docs/` references them. They confuse new contributors ("is this current? is it superseded?").

- [ ] **Decision:** Delete `docs_old/`? (yes / no / archive elsewhere)

### H2. Dangling reference to `docs/TECHNICAL_IMPLEMENTATION.md`

Bible §5.3.1 says *"the technical requirements document (see `docs/TECHNICAL_IMPLEMENTATION.md` once authored)"*. This doc was never authored and never will be — `TCL_PARSER_SPEC.md` + `ARCHITECTURE_PLAN.md` + the bible cover the territory.

**Proposed fix.** Replace the sentence with: *"The compilation contract is defined in §5.3 above; implementation detail lives in `src/chopper/compiler/` docstrings."*

- [ ] **Decision:** Apply the fix? (yes / no)

### H3. Fixture audit

Pre-Stage-0: audit `tests/fixtures/edge_cases/`, `mini_domain/`, `namespace_domain/`, `tracing_domain/`, `fev_formality_real/` against:

- P-01..P-36 named fixtures (RISKS_AND_PITFALLS.md).
- 33-row corner-case catalog (ARCHITECTURE_PLAN §12).
- E3 tracing sub-fixtures (above).

Produces a gap list. Fill the gap list before Stage 1.

### H4. `README.md` at repo root

Haven't read. Should be a 60-second onboarding: what chopper is, how to run it, where docs live. If already sufficient, note as such.

---

## Summary: one-glance decision list

Copy-paste your yes/no for each line. Everything marked "yes" I will apply in a single cascade edit in the next turn. Anything "no" stays as-is.

**Cuts (scope discipline):**

- [ ] A1 — Cut `--plain`, `--no-color`, `--json`, `--debug`; keep `-v` and `-q` only
- [ ] A2 — Remove `TableRenderer` port
- [ ] A3 — Remove `SerializerPort`, replace with `dump_model()` helper
- [ ] A4 — Remove `AuditStore` port, fold into `AuditService`
- [ ] A5 — Remove `ClockPort`
- [ ] A6 — Remove `dedupe_bucket` field, first-write-wins dedupe
- [ ] A7 — Remove `RunMode` from `RunConfig`
- [ ] A8 — Drop corner-case scenarios 30 / 31 / 32 (Windows / symlinks / non-ASCII paths)
- [ ] A9 — Collapse validator into two free functions (or keep as classes)

**Doc split:**

- [ ] B — Split `ARCHITECTURE_PLAN.md` per the table in §B

**Spec additions:**

- [ ] D2 — Parser state-machine table in `TCL_PARSER_SPEC.md` §3
- [ ] D3 — Canonical-name test-vector table
- [ ] D4 — `PE-01`/`PE-02` return-value table in parser spec
- [ ] E1 — Worked BFS trace example in bible §5.4
- [ ] E2 — `source` edges are reporting-only clarification
- [ ] F2 — L3 iteration-order clause in §5.3

**Registry / bible fixes:**

- [ ] F1 — Retire `VW-10` permanently, promote `cross-source-fe-vetoed` to `VW-19`
- [ ] G1 — `options.cross_validate`: define / delete / FD
- [ ] G2 — Cut `options.template_script` + retire `VE-18`
- [ ] G3 — VI-03 detection: pick (a) / (b) / (c)
- [ ] G4 — Clarify `cleanup` is outside the runner (implied by A7)

**Housekeeping:**

- [ ] H1 — Delete `docs_old/`
- [ ] H2 — Fix dangling `docs/TECHNICAL_IMPLEMENTATION.md` reference
- [ ] H3 — Fixture audit before Stage 1 (action, not a doc edit)
- [ ] H4 — Confirm or rewrite `README.md`

Once approved, the cascade edits land in one pass with updated cross-references across every affected doc.
