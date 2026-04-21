<!-- markdownlint-disable-file -->

# Task Research Notes: Handoff Readiness — Devil's-Advocate Review of Chopper v2 Docs

**Date:** 2026-04-21
**Scope:** [`docs/chopper_description.md`](../../docs/chopper_description.md) (bible), [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) (plan), [`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md), [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md), [`docs/RISKS_AND_PITFALLS.md`](../../docs/RISKS_AND_PITFALLS.md), [`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md), [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](../../docs/FUTURE_PLANNED_DEVELOPMENTS.md), [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md), [`tests/FIXTURE_CATALOG.md`](../../tests/FIXTURE_CATALOG.md), [`pyproject.toml`](../../pyproject.toml).

**Verdict (one line):** Docs are unusually thorough and internally disciplined (scope-lock, frozen dataclass contracts, named diagnostic registry). **They are NOT yet code-ready.** There are ~20 concrete contradictions, gaps, or undefined edges that will generate design-by-first-implementer decisions the moment Stage 0 starts. All are fixable in-doc before a single line of `core/` is written.

---

## Research Executed

### File Analysis

- [`docs/chopper_description.md`](../../docs/chopper_description.md) — read §1–§11 end-to-end (2700 lines). Bible of product behavior; defines the 7-phase pipeline, R1 merge rules, F1/F2/F3 capability model, `.chopper/` audit contract, and the §5.11 GUI-readiness service layer.
- [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) — read fully (~900 lines). Defines `ChopperContext`/`RunConfig`, 10 phase services with `run()` signatures, ports/adapters, gate semantics, scope-lock, and §12 corner-case catalog.
- [`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md) — complete registry. 65 active / 40 reserved codes across VE/VW/VI/TW/PE/PW/PI families. Retired slots: VE-16, VE-24, VI-04, VI-05.
- [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md) — `validate` / `trim` / `cleanup` subcommands; top-level flags `-v`, `--debug`, `--plain`, `--no-color`, `--json`, `--strict`.
- [`docs/RISKS_AND_PITFALLS.md`](../../docs/RISKS_AND_PITFALLS.md) — TC-01..TC-10 plus P-01..P-36. Parser module (highest risk) has P-32..P-36 specifically pinning Synopsys/Intel EDA idioms (nested default-brace args, DPA blocks, banner comments, `foreach_in_collection`, DPA-arg false-dep suppression).
- [`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md) — tokenizer, context stack, `parse_file()` signature, DPA (§4.6) and comment (§4.7) lookahead rules.
- [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) — stage coverage gates, `ChopperRunner` subprocess harness, 21 named integration scenarios.
- [`tests/FIXTURE_CATALOG.md`](../../tests/FIXTURE_CATALOG.md) — 17 parser fixtures with pitfall mapping.
- [`pyproject.toml`](../../pyproject.toml) — Py3.9+; ruff, mypy, pytest-cov 78% floor, hypothesis 500 examples. structlog + jsonschema runtime deps; rich optional.

### Code Search / Workspace State

- [`src/chopper/__init__.py`](../../src/chopper/__init__.py) — **only file in src/**. Zero implementation; pure spec-driven repo. No legacy to contradict; no scaffolding drift.
- [`tests/fixtures/edge_cases/`](../../tests/fixtures/edge_cases/) — 17 parser `.tcl` fixtures already in place matching FIXTURE_CATALOG.md (1:1). [`tests/fixtures/mini_domain/`](../../tests/fixtures/mini_domain/) populated (main_flow, helper_procs, extra_utils, vars, utils.pl, jsons/). [`tests/unit/`](../../tests/unit/) has only `test_package_smoke.py`; [`tests/integration/`](../../tests/integration/) has `crash_harness.py` + `test_smoke.py`. No actual stage 0–5 tests yet.
- [`tests/fev_formality/`](../../tests/fev_formality/) — real Synopsys Formality domain source living **outside** `tests/fixtures/`. Unusual location; not referenced by testing strategy.
- [`snort/`](../../snort/), [`docs_old/`](../../docs_old/) — stale; not referenced from living docs.
- [`json_kit/`](../../json_kit/) — 11 example scenarios + 3 schemas. Already production-quality; independent of Chopper runtime.

### Project Conventions Referenced

- [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) — Scope Lock (§1 closed decisions), bible-first cascade, Stage 0–5 build model, diagnostic-code discipline.
- [`.github/instructions/memory-bank.instructions.md`](../../.github/instructions/memory-bank.instructions.md) — MemPalace MCP workflow (orthogonal to this review).

---

## Devil's-Advocate Findings

Findings are grouped **by severity for handoff**: **BLOCKERS** must be resolved before Stage 0 starts (otherwise the first implementer invents a contract the next implementer has to undo); **GAPS** are unspecified edges the first implementer will discover at test time; **DEBT** is cosmetic / registry-level and non-blocking.

### BLOCKERS (resolve in-doc before coding)

#### B-1. Two incompatible service contracts exist

The bible ([`docs/chopper_description.md`](../../docs/chopper_description.md) §5.11.2) specifies a **single** `TrimService` with `execute(request: TrimRequest, progress: ProgressSink | None) -> TrimResult` using `TrimRequest`, `TrimResult`, `TrimStats`, `ExitCode`, `TrimMode` as the public surface for CLI and future GUI.

The plan ([`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §4, §9.2) defines **ten** per-phase services (`DomainStateService`, `ConfigService`, `ParserService`, …, `AuditService`) each with `run(ctx, …) -> TypedResult`, composed by `ChopperRunner.run(ctx) -> RunResult`. `ChopperContext` replaces `TrimRequest`; `RunResult` replaces `TrimResult`; `ProgressSink` is rebound to `phase_started`/`phase_done`/`step` (vs bible's `on_progress`/`on_diagnostic`).

**Neither `TrimRequest` / `TrimResult` / `TrimService` / `TrimStats` nor `ExitCode`/`TrimMode` is mentioned anywhere in the plan.** Per project policy the bible wins and the plan should have been edited in place. It wasn't — the bible's §5.11 was left as a rival API. First implementer of Stage 5 (CLI) has to guess which one ships.

**Fix:** pick one. Recommended: keep the plan's `ChopperRunner` + per-phase services as the internal seam and collapse `TrimService.execute` down to a thin wrapper the CLI calls (`TrimService.execute(req) → build ctx from req → ChopperRunner.run(ctx) → map RunResult to TrimResult`). Then rewrite bible §5.11.2 to match, or delete §5.11.2's request/result shapes and keep only the *rules* (typed-in, typed-out, no prints, `--json` required).

--> I agree witrh your fix, however make sutreh the system is ready for GUI as well overt the streamable json or domwother protocol described in the older_docs. 


#### B-2. `ProgressSink` has two different protocols in two living docs

- Bible §5.11.6 lists `ProgressSink` with `on_progress()`, `on_diagnostic()`.
- Plan §5 port table lists `ProgressSink` with `phase_started()`, `phase_done()`, `step()`.

These are not compatible method sets. Adapters (`RichProgress`, `SilentProgress`) can only implement one. This is the same root as B-1 but hits Stage 0 directly because `core/protocols.py` is the very first file.

**Fix:** define `ProgressSink` once. The plan's `phase_started/phase_done/step` is closer to what the runner's 7-phase loop actually needs; the bible's `on_diagnostic` belongs on `DiagnosticSink` (where the plan already puts it). Remove the bible's duplicate.

-->  Agree with your fix- align them - give more priority to practically feasible and non over engineered approach

#### B-3. Bible and plan disagree on rollback mechanism

- [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md) `chopper trim` help: *"On failure: remove half cooked domain/ and replace domain_backup/ as domain/."* — i.e., **rename** backup → domain (destroying backup).
- Plan §12 scenario 29 (VE-26 filesystem-error-during-trim): *"rollback restores `<domain>_backup/` → `<domain>/`"* — worded as restore (implying copy, backup preserved).

Renaming vs copying matters:

| Mechanism | Next `chopper trim` invocation sees |
|---|---|
| Rename (destroys backup) | Case 1 (first trim) — no evidence a prior trim failed |
| Copy (preserves backup) | Case 2 (re-trim) — existing backup; continues normal flow |

Plan §2.8 matrix cases 1–4 don't cover "post-failed-trim" state either way. First implementer of `TrimmerService` will pick one and lock it in.

**Fix:** specify the rollback mechanism in the bible (§2.8 edge-case matrix) and reference from plan §12 and CLI help. Recommended: **copy + leave `_backup` in place**; the diagnostic log in `.chopper/` tells the operator a failure happened, and re-trim is idempotent from the preserved backup.

--> if trim fails show the trim failed ; either restore backupby (rm -rf domain; and mv domain_backup domain )  or leave it as it is, upon second restart from the domain folder the system detects backup is available and then does the modifications under the hood. by changing its cwd to domain_backup. this is a simple and clean approach fror every user by not complicating th UX.

#### B-4. `.chopper/` location survives `domain/` rebuild — ambiguous

`.chopper/` lives at `<domain>/.chopper/` ([bible §5.5.1](../../docs/chopper_description.md)). First-trim renames `<domain>/` → `<domain>_backup/`, meaning the backup captures any pre-existing `.chopper/` from *before Chopper was ever run*. On every subsequent re-trim, `<domain>/` is rebuilt from `<domain>_backup/`, which now contains the previous run's `.chopper/`.


**Three undefined behaviors:**

1. Does the trimmer copy `.chopper/` from backup into the fresh `<domain>/`? If yes, the new run's audit artifacts overwrite onto stale ones mid-run.
2. Can a `files.include` glob (e.g. `**` or `reports/**`) accidentally match under `.chopper/`?
3. Is `<domain>_backup/.chopper/` itself a candidate for parsing at P2? (No extension filter in [`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md) §2 says "don't recurse into `.chopper/`".)

**Fix:** add an explicit exclusion rule: `.chopper/` is reserved; never backed up, never copied, never parsed, never matched by globs. Put it in bible §2.4/§5.5 and in the plan's `FileSystemPort` write-scope paragraph.

--> I agree chopper is never backed up; it lives in domain only

#### B-5. `parse_file` error-handling contract is undefined

[`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md) §2.1 says the parser returns `list[ProcEntry]`. Plan §9.1 defines `ParsedFile` (no `parse_errors` field — errors go to `ctx.diag`). But **what does the parser return on `PE-01` / `PE-02` / `PE-03`?**

- `PE-02 unbalanced-braces` — spec says "file is skipped or yields partial results" ([`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md)). Which? Bible §5.4.1 shows the compiler iterates `parse_file()` results to build the global proc index. If the parser returns a partial list, the index contains half-parsed procs; if it returns `[]`, downstream file/proc resolution silently breaks.
- No phase gate exists at P2. Plan §6.2 gates only P1, P3, P6. An error-severity parser diagnostic will **not stop the pipeline** — the compiler proceeds against a corrupt index.

**Fix:** add a P2 phase gate (or state explicitly "P2 errors are captured but the run continues with the best-effort index; downstream `VE-07 proc-not-in-file` will catch the consequences"). Specify the return contract per code:

| Code | `parse_file()` returns |
|---|---|
| PE-01 duplicate proc | full list, last-definition's span used |
| PE-02 unbalanced braces | `[]` (file unusable for F2) |
| PE-03 ambiguous short name | full list |
| PW-* / PI-* | full list |

Also bible §5.4.1 iterator code uses `for entry in parse_file(...)` — in-place exception propagation semantics are undefined.

--> Agreed!

#### B-6. Post-trim validation sources are not specified

[`docs/chopper_description.md`](../../docs/chopper_description.md) §5.8 says P6 checks "brace balance, dangling proc refs, missing source targets." This requires:

1. Re-tokenizing or re-parsing the **trimmed** Tcl files to check balance → does P6 invoke `parse_file()` again? Against the staging tree? Under `--dry-run`, the staging tree doesn't exist — bible §5.7 says dry-run P6 runs "against the resolved sets" which cannot answer brace-balance questions.
2. For `VW-05 dangling-proc-call`: call extraction + resolution on surviving files → essentially re-running P2+P4 but only over kept files.

**Neither is specified.** `PostValidatorService` in plan §3/§9.2 has signature `run(ctx, manifest) -> None` but no mention of where the content comes from.

**Fix:** specify P6 inputs. Options: (a) add `manifest + parsed` to the signature and re-use P2 output on the unchanged subset, re-parse the rewritten subset via `ctx.fs`; (b) make `VE-17` / `VW-05` strictly pre-trim (derived from manifest + P4 graph, not filesystem re-read) and drop brace-balance from P6 entirely. Either is fine; the doc must pick. 

-->  Agreed. pre and post checks must hasv differences

#### B-7. Trimmer error-code coverage is one code

Plan §6.2: *"The registered codes covering this gate live in the `VE-*` trimmer range."* Only `VE-26 filesystem-error-during-trim` exists. Real P5a failures include:

- File disappeared from `<domain>_backup/` between P2 and P5
- Target directory exists but is a file (or vice versa)
- Atomic rename across filesystem boundary (EXDEV)
- Partial write: write succeeded but file size mismatch on re-stat
- Comment-banner + DPA atomic drop failed to locate DPA line

[`docs/RISKS_AND_PITFALLS.md`](../../docs/RISKS_AND_PITFALLS.md) P-33/P-34 identify the atomic-drop hazard without a dedicated code. One generic `VE-26` forces the implementer to either cram all cases into one message (bad UX, bad runbook) or invent `VE-27`+ ad-hoc.

**Fix:** reserve and name at minimum:

| Slot | Purpose |
|---|---|
| VE-27 | `backup-contents-missing` — file referenced in manifest not present in `_backup` |
| VE-28 | `staging-promotion-failed` — atomic rename of staging → domain failed |
| VE-29 | `proc-atomic-drop-failed` — DPA or banner lookahead can't align with parsed span |

(Registry currently shows VE-27..VE-30 reserved; good, just name them.)

--> Add them Agreed


#### B-8. CLI flags documented but un-sourced into `RunConfig`

[`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md) lists top-level global flags: `-v/--verbose`, `--debug`, `--plain`, `--no-color`, `--json`, `--strict`. Plan §6.1 `RunConfig` has only `strict` and `dry_run`.

Consequences for Stage 5 implementer:

- `--json` is a bible hard requirement (FR-38, §5.11.1 rule 7) but nothing in `ctx` tells any service to suppress non-JSON output. Plan says "CLI owns rendering" — but the service layer still uses `ProgressSink` which in `--json` mode should be `SilentProgress`. Who picks the adapter? CLI. Where does the flag live? Undefined.
- `--debug` semantics (full stack traces) imply the CLI re-raises from `RunResult` on exit code 3 — but the bible never says this.
- `-v`/`-vv` are not represented anywhere and structlog verbosity has no documented mapping.

**Fix:** either enumerate every CLI flag as a field on `RunConfig` + specify its effect per port, or add a `PresentationConfig` next to `RunConfig` and route all seven flags through it. The plan's "CLI has zero business logic" discipline collapses otherwise.

--> cli referene specified the arguments fo rthis script; run config is built after processing these input switches.  there is mo -vv; you ned to make sure you honor the switches privded in the cli reference as they controll the whole execition behaviour of this tool. why do we have progress sink in --json mode ? it must be in all modes. 

#### B-9. Phase gate does not cover P2 or P4

Plan §6.2 gates P1, P3, P6. P2 emits `PE-*` (errors) and has no gate (see B-5). P4 emits only warnings (`TW-*`), but if the tracer encounters a programmer error (index corruption from B-5, internal inconsistency) it can only raise — which hits exit code 3 (internal error) rather than a clean exit 1. Is that the intent? Undefined.

**Fix:** either state "P2 has no gate by design; PE-* warnings only aggregate" (which contradicts PE-* being severity=ERROR) or add a P2 gate. Similarly decide P4 policy explicitly.

-->   define them pease. and make sure they align with system behavior. if P2 has no gate, then PE-* are warnings and the system continues; if P4 raises on internal errors, document that and make sure the code does it.

---

### GAPS (will bite during implementation)

#### G-1. VE-13 emission source is ambiguous

Registry says `Source = validator`. Plan §8.2 rule 4 says "CLI / pre-pipeline fatal conditions the runner never even enters: `VE-11`, `VE-13`, `VE-23`." Plan §12 scenario 19 says "CLI / `ConfigService` pre-pass." Bible §5.1 is silent on where the check runs.

Decision: who owns `VE-13` — the CLI before building `ctx`, `ConfigService` after P1 entry, or a pre-P1 validator? All three have consequences (diagnostic sink may not exist yet if CLI owns it → where does the JSON output go?).

**Fix:** pin the owner. Recommended: CLI-layer pre-check **before** `ChopperRunner.run()` so no service has observed the bad input, and the bad path string is rendered by the CLI's `TableRenderer` directly.

--> I agree with your fix, CLI should own it and exit gracefully with the error message.

#### G-2. `DomainState.case` values 5 and 6 are synthetic

Plan §9.1: `case: Literal[1,2,3,4,5,6]`. Bible §2.8 matrix defines 6 cases, but case 5 ("cleanup was run previously") is behaviorally identical to case 2, and case 6 ("backup unreadable") is really a filesystem error that aborts before domain-state analysis completes. The `DomainStateService` emits no diagnostic for case 5 and no documented code for case 6 (probably `VE-26` or an OS exception).

**Fix:** collapse to `Literal[1,2,3,4]`; handle case 6 as a raise at the `FileSystemPort.stat()` boundary.

--> Agreed. the domain state should be about the domain, not about the trimmer's past actions or backup health. those are orthogonal concerns.

#### G-3. `project.domain` vs cwd basename casing

Bible §2.5 / §5.1 require `project.domain` to match "the basename of the current working directory." On Linux grid vs Windows authoring, case-fold may differ (`Fev_Formality` vs `fev_formality`). [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §12 scenario 30 says case-insensitive path collision is handled by `Path.resolve()` + POSIX normalization — but that's for *path* matching, not the `domain` **string field** match.

**Fix:** specify exact comparison (case-sensitive string equality? case-folded?). Put it next to VE-19 in the registry.

--> let go of case sensitivity, do not path comparisons in a case-sensitive way. normalize to lowercase and do the comparison. document this behavior clearly. and only coimpare the basenames, not the full paths.

#### G-4. Feature paths resolved from cwd, not project-JSON location

Bible §3.3 and §6.6 both say `base` and `features` paths in a project JSON resolve relative to **cwd**, not the project JSON's own location. That makes project JSONs portable, but it also means a project JSON **cannot** safely sit outside the domain without risking `..` traversal in its `base`/`features` strings — and §6.3.1 forbids `..`. So any project JSON stored under e.g. `configs/` at repo root **must** reference domain-relative paths like `jsons/base.json`, which the operator must navigate-into before running. This constraint isn't called out.

**Fix:** add an explicit note in bible §6.6: "The operator MUST `cd` into the domain root before running `chopper trim --project <anywhere>`." Currently only implied.

--> Agreed. do not allow `..` in project JSON paths. document the requirement to run from domain root.

#### G-5. `GeneratorService` return value is unused

Plan §9.2: `GeneratorService.run(ctx, manifest) -> tuple[GeneratedArtifact, ...]`. Plan §6.2 runner body calls `GeneratorService().run(ctx, manifest)` and discards the result. `GeneratedArtifact.content: str` has no writer. Two reads:

1. Generator writes via `ctx.fs.write_text()` internally and returns the tuple for audit/manifest → then who records it? Runner doesn't use it.
2. Generator returns content; runner writes. But runner §6.2 doesn't.

**Fix:** pick one. If (1), add a `generated: tuple[GeneratedArtifact, ...] = ()` field to `RunResult` and wire audit to it. If (2), the runner has to loop and write — add it.

--> do not waste efforts. if the generator can write directly to the fs, let it do so. the return value is redundant. if you want to keep it for audit/manifest, that's fine, but make sure it's not the only record of the generated artifact's existence. audit should be able to reconstruct it from the manifest and the filesystem state.


#### G-6. `VE-17 brace-error-post-trim` only reachable via trimmer bugs

PE-02 already rejects files with unbalanced braces in P2, so the only way P6 sees a brace-balance error is if the trimmer introduced one (e.g., deleted a proc body span that crossed a brace boundary). That's a programmer-error condition; it should probably be exit 3 (internal error) rather than exit 1. Registry says VE-17 exits 1.

**Fix:** either raise the exit to 3 and document it as an internal-consistency assertion, or remove VE-17 entirely and let trimmer pitfalls surface via the new VE-29 (see B-7).

--> Agreed. if the trimmer's own bugs can cause VE-17, it's not a user-facing error code; it's an internal assertion failure. raise exit code to 3 and document it as such.

#### G-7. Empty `procs` array on PE side

Bible §3.5: `procedures.include` with `"procs": []` is `VE-03`. The same shape on `procedures.exclude` is not specified — is it silently accepted? A no-op? An error? Implementer will guess.

**Fix:** add a single sentence: "Empty `procs` arrays in `procedures.exclude` are silently ignored (no-op)." Or mirror to VE-03 if the consensus is strictness.

--> Agreed. empty `procs` in `procedures.exclude` is a no-op. document it.

#### G-8. `AuditService` behavior on `None` inputs

Plan §6.2: `AuditService().run(ctx, manif, graph)` runs in `finally` and "tolerates `None` inputs." What does it actually write when `manif is None` (P1 aborted) vs when `graph is None` (P4 didn't run)? Bible §5.5.10 says every run emits `run_id` + `chopper_run.json` + `diagnostics.json`. The artifact emission table there has fixed ✓/— but no partial-run column.

**Fix:** add a column or note: "When a phase aborts before producing its artifact, the corresponding `.chopper/` file is omitted; `chopper_run.json` always records which artifacts are present." Stage 3 implementer will otherwise pick either "write partial" or "write empty stub" and both have review costs.

--> Agreed. if the manifest or graph is None, audit should write a stub with the run_id and an empty manifest/graph field, plus any diagnostics that exist. this way we have a complete record of what happened even in failure cases.

#### G-9. `chopper validate` file-existence check

Bible §5.8: *"`chopper validate` is the standalone Phase 1-only command (no domain source files needed — structural checks only)."* But `VE-06 file-not-in-domain` is Phase 1 and **does** require filesystem checks. Contradiction: either validate can check file existence (and therefore needs domain source files) or `VE-06` doesn't fire in `validate`.

**Fix:** state which Phase 1 checks `validate` runs and which it skips. Recommended: `validate` runs everything except `VE-06`/`VE-07` (those require filesystem + parse). Alternatively, run them when `--domain` is provided.

--> Agreed with your suggestion. `chopper validate` should run all Phase 1 checks except those that require filesystem access. Validate is json validation only., if the user provides a domain or user is in CWD of the domain, we can run the full set of checks including VE-06 and VE-07. document this behavior clearly.

#### G-10. Diagnostic dedupe key excludes `hint` and `context`

Plan §8.1: dedupe on `(code, path, line_no, message)`. If two services compute different *contexts* for the same logical issue (e.g., compiler says "feature_dft introduced this," and audit writes a JSON representation that needs the context), the second emit is dropped and the richer context is lost.

**Fix:** either state "last write wins on collision" (document it in §8.2 invariants) or expand the dedupe key to include a caller-specified `dedupe_bucket` so services that need multi-context emission opt in.

--> expand byy caller. but also give priroty to last call if the bucket is the same. this way we can have both deduplication and multi-context emission when needed.

#### G-11. Dry-run P6 without staging

Bible §5.7: dry-run still runs P6 "against resolved sets." P6 checks brace balance and dangling refs. Without staging, the trimmed bytes don't exist. Either P6 is reduced under dry-run (document which checks run) or dry-run needs an in-memory trim simulator. Currently undefined.

**Fix:** specify the dry-run P6 check set. Recommended: run only the manifest-based checks (`VW-05`, `VW-06`, `VW-14`, `VW-15`, `VW-16`, `VW-17`); skip filesystem checks (`VE-17`).

--> Agreed. dry-run should run only the manifest-based checks, not the filesystem checks that require the staging tree. document this behavior clearly.

---

### DEBT (cosmetic; doesn't block)

#### D-1. `VE-26` registry "phase 1" is wrong

Registry row for `VE-26 filesystem-error-during-trim` lists phase = 1. It's a P5 (trim) emission. Harmless label drift but every audit query filtering by phase is now off-by-four.

--> Fix: update registry.

#### D-2. Stale directories

[`docs_old/`](../../docs_old/), [`snort/`](../../snort/) are not referenced by any living doc. Removing them (or adding a README pointing to why they remain) prevents future agents from treating them as authoritative.

--> add history in read me. `docs_old/` is the old architecture decision record; `snort/` is the other tool where we took inspiration for this tcl parser and proc chasing tool. Both are frozen but not deleted for historical reference. Add a README in each pointing to the new docs and saying "frozen for historical reference; not authoritative for current design."

#### D-3. `tests/fev_formality/` location

Real domain source (`default_fm_procs.tcl`, `fev_fm_rtl2gate.tcl`, etc.) lives at `tests/fev_formality/` alongside `tests/fixtures/`. [`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) never references it; it's not in [`tests/FIXTURE_CATALOG.md`](../../tests/FIXTURE_CATALOG.md). Intent unclear: acceptance fixture? Benchmark seed? Move under `tests/fixtures/fev_formality_real/` or document what it's for.

-->can you pull in code from fev formality along with other fixture tests to mix fabricated, targeted and real code for testign and quality gating? if so, move it under `tests/fixtures/fev_formality_real/` and add a note in the testing strategy about how it's used.

#### D-4. `ChopperRunner` (integration harness) name collides with plan's `ChopperRunner` (orchestrator class)

[`tests/TESTING_STRATEGY.md`](../../tests/TESTING_STRATEGY.md) §4 defines an integration-test `ChopperRunner` class that subprocess-executes the CLI. [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §6.2 defines a production `ChopperRunner` class that sequences phases. Same name, different classes. Annoying in grep, imports, and error messages.

**Fix:** rename the test harness to `ChopperCli` or `ChopperSubprocess`.

--> Agreed with `ChopperSubprocess` — it's more descriptive and less likely to collide with future production classes.

#### D-5. §5.10 "see project.instructions.md" is circular

Bible §5.10 points at [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) for "Python coding standards, repo structure, package boundaries." The instructions file in turn points at the bible. Neither is the authoritative owner of, e.g., "which `Path.resolve()` mode to use" or "`pathlib.PurePosixPath` vs `pathlib.Path`." Minor but notable for first-implementer confusion.

--> Fix: move all Python coding standards into the bible (e.g., a new §5.12 "Python Coding Standards" with subsections for path handling, type annotations, logging, etc.) and have the instructions file point to that. The instructions can still have a "Python conventions summary" section that links to the bible for details.

#### D-6. `parse_file()` vs `ParserService` split is documented twice, slightly differently

[`docs/TCL_PARSER_SPEC.md`](../../docs/TCL_PARSER_SPEC.md) §2.1 gives one signature: `parse_file(domain_path, file_path, on_diagnostic) -> list[ProcEntry]`. Plan §9.2 gives a *compatible* but differently phrased version: "wraps the pure `parse_file()` utility" with the service doing the `ctx.fs.read_text()`. Both agree on facts but describe the split twice. Pick one canonical version and have the other doc link to it.


--> Fix: make the plan's `ParserService` the canonical version since it's more complete (includes the `ctx.fs` detail), and have the parser spec link to it. The parser spec can still describe the pure `parse_file()` as an internal utility, but the service signature is what implementers should follow.

---

## Scope-Lock Verification (Clean)

Grepped the repo for the forbidden identifiers from [`.github/instructions/project.instructions.md`](../../.github/instructions/project.instructions.md) §1 scope-lock table. No violations in living docs. The negative assertions in [`docs/ARCHITECTURE_PLAN.md`](../../docs/ARCHITECTURE_PLAN.md) §7 and §16 are doing their job.

--> Scope lock is clean. No forbidden identifiers found in living docs. The plan's negative assertions are intact and effective.

---

## Handoff-Readiness Summary

| Area | Ready? | Notes |
|---|---|---|
| Scope & constraints | ✅ Yes | Scope lock is crisp; closed decisions (Q1–Q3, Q6) well documented. |
| JSON schema + authoring | ✅ Yes | `json_kit/` is shippable today. 11 progressive examples + 3 schemas. |
| Diagnostic registry | ✅ Yes (1 bug) | 65 codes named; fix D-1 (VE-26 phase), reserve B-7 codes. |
| R1 merge algorithm | ✅ Yes | Provenance-aware, order-independent, worked examples + per-source matrix are precise. |
| Parser spec | ✅ Yes | §4.2 algorithm + P-32..P-36 pitfalls + 17 fixtures already on disk. High-confidence Stage 1 start. |
| Tracing spec | ✅ Yes | Deterministic lexical namespace resolution, BFS lex-sorted frontier, cycle handling, TW-01..TW-04 all pinned. |
| Pipeline phases (P0–P7) | ⚠️ Mostly | P1/P3/P6 gates defined; P2/P4 gates undefined (B-9). Post-trim inputs undefined (B-6). |
| Service contract | ❌ Blocked | B-1 (two rival APIs), B-2 (ProgressSink). Must reconcile before Stage 0. |
| Context / RunConfig | ❌ Blocked | B-8 (CLI flags not in RunConfig). |
| Trimmer contract | ⚠️ Gap | B-3 (rollback mechanism), B-7 (one error code), G-5 (generator output). |
| Audit contract | ⚠️ Gap | B-4 (.chopper/ survival), G-8 (partial-run artifacts). |
| Validation contract | ⚠️ Gap | B-5 (parse errors), B-6 (post-trim inputs), G-9 (validate vs VE-06). |
| Testing strategy | ✅ Yes | Coverage gates + 21 scenarios + parser fixtures ready. Minor D-4 naming clash. |

**Bottom line:** the corpus is ~92% handoff-ready. The remaining 8% is **9 blockers** that are all doc-edits (no new design work needed — just picking one of two already-articulated options in each case) and **11 gaps** that are each one-sentence-to-one-paragraph clarifications. None of the blockers requires implementing anything; all are "delete the losing option and say so." An afternoon of focused editing against this list unblocks Stage 0 entirely.

---

## Recommended Approach (Single Path Forward)

**Do not start Stage 0 coding yet.** Run one doc-reconciliation pass in the following order, one PR at a time so each change is reviewable:

1. **Reconcile service contract (B-1, B-2).** Edit bible §5.11.2 to point at the plan's `ChopperRunner` + per-phase `run()` surface. Drop `TrimService`/`TrimRequest`/`TrimResult` from §5.11 **or** keep them as a thin CLI-layer wrapper and add exactly one sentence saying so. Delete the duplicate `ProgressSink` shape from §5.11.6 and let the plan's §5 version stand.
2. **Pin CLI presentation flags (B-8).** Add a `PresentationConfig` frozen dataclass next to `RunConfig` in plan §6.1 with fields for every flag in [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md). Document which port each flag controls.
3. **Pin rollback, `.chopper/` survival, parse-error, post-trim input contracts (B-3, B-4, B-5, B-6).** Four short edits, mostly in bible §2.8, §5.5, §5.4.1, §5.8 respectively. Each is ≤1 paragraph.
4. **Reserve trimmer diagnostic codes (B-7).** Add VE-27/28/29 rows to [`docs/DIAGNOSTIC_CODES.md`](../../docs/DIAGNOSTIC_CODES.md) with phase=1 (trim, consistent with the spec's "phase 1 vs phase 2 = pre/post-trim" not to be confused with P0–P7 pipeline phases — and fix D-1 while you're in there).
5. **Close P2/P4 phase gates (B-9).** One-line edit in plan §6.2 runner body stating the policy for each.
6. **Add one sentence each for the 11 GAPS.** G-1..G-11 are independently applicable, so batch them into one "clarifications" PR that touches every affected doc exactly once.
7. **Housekeeping pass for D-1..D-6.** Separate low-priority PR, not blocking.

Only then, start Stage 0 (`core/`) — the existing [`tests/fixtures/edge_cases/`](../../tests/fixtures/edge_cases/) and `mini_domain/` make Stage 1 ready to begin immediately after.

---

## Implementation Guidance

- **Objectives:** lock every service-to-service contract in doc-form before Stage 0 so each stage's first implementer cannot invent a new seam.
- **Key Tasks:** seven doc PRs (sequenced above), each ≤ one day of editing, touching only documentation.
- **Dependencies:** item 1 (B-1/B-2) unblocks every downstream item. Items 2–7 can parallelize after that.
- **Success Criteria:**
  1. `grep -r "TrimService\|TrimRequest\|TrimResult" docs/` and `src/` returns either zero hits or only the single canonical definition.
  2. Every flag in [`docs/CLI_HELP_TEXT_REFERENCE.md`](../../docs/CLI_HELP_TEXT_REFERENCE.md) maps 1:1 to a `RunConfig` / `PresentationConfig` field.
  3. Every diagnostic code emitted by the trimmer module (plan §12 scenarios 21, 29) has a registered code.
  4. Every phase boundary (P0–P7) has a documented "on error" policy — gate, propagate, or ignore.
  5. `.chopper/` directory survival rules cover first-trim, re-trim, dry-run, and crashed-trim cases.
  6. `parse_file()` return value per-code is explicitly tabled.

When those six criteria are met, the corpus is green for implementation handoff.

