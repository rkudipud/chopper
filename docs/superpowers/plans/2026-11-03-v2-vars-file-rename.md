# V2 Vars File Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the v2 `vars` pointer to `vars_file`, remove the v2 `procs` pointer and generated procs wrapper end-to-end, and keep the resulting v2 behavior, diagnostics, documentation, examples, and migration tooling consistent.

**Architecture:** Mutate the unreleased v2 contract in place. Keep base `vars_file` as a layer-local whole-file F1/R1 input, while feature `vars_file` contributes only the generated feature-vars wrapper plus its existing-file F1 keeps; remove the parallel procs-pointer path rather than leaving unreachable code. Update the schema/model/config/compiler/generator cascade first, then align tests, diagnostics, docs, example 16, and migration tooling.

**Tech Stack:** Python 3.13, pytest/pytest-cov, JSON Schema, Tcl source-wrapper emission, Makefile quality gates, Markdown documentation.

**Spec:** `docs/superpowers/specs/2026-11-03-v2-vars-file-rename-design.md`

## Global Constraints

- `base-v2` and `feature-v2` rename `vars` to `vars_file`; `project-v2` is unchanged.
- No compatibility alias, deprecation warning, or v3 schema is introduced.
- The v2 `procs` pointer, generated `<flow>_feature_procs.tcl`, executor load path, and code serving only that path are removed end-to-end.
- Base `vars_file` is loaded by the flow itself, is never listed in the generated wrapper, and participates as a layer-local whole-file include in normal R1/F2 so later `files.exclude` or `procedures.exclude` can win and reversals emit `VW-21`.
- Feature `vars_file` emits only `<flow>_feature_vars.tcl`, with authored, `tech_`, then `project_` basename entries in project feature order; duplicate entries are first-wins and emit `VW-29`.
- Proc libraries are trimmed only through `procedures.include` / `procedures.exclude`; no pointer-driven proc trimming or replacement behavior is added.
- `VW-30` and `VW-31` are reserved/inactive, while historical documentation entries remain available and registry/code-space counts stay correct.
- Do not modify `dist/`, `graphify-out/`, or `presentation/*.html`; do not commit changes.
- Preserve all pre-existing dirty-worktree edits. Treat only the approved design document and this plan as work for this request.
- Keep the builder call from the design: update version/changelog/revision history to `4.12.0` only if the implementation confirms that release metadata is part of the accepted builder call.

## Review Focus

- A base `vars_file` must be kept as a whole file but omitted from the feature wrapper, and a later feature exclusion must remove it with `VW-21`; cover in `tests/unit/generators/test_vars_emitter.py` compiler-registration tests.
- Feature `vars_file` entries must preserve authored → `tech_` → `project_` order, project feature order, and first-wins deduplication with `VW-29`; cover in `tests/integration/test_feature_vars.py` and config-service tests.
- A v2 document using legacy `vars` or any v2 `procs` pointer must fail schema validation while v1 behavior remains unchanged; cover in `tests/unit/generators/test_vars_emitter.py`, `tests/unit/config/test_sourcing_paths.py`, and schema tests.
- No generated procs wrapper, procs manifest field, procs stack input, or procs migration preview may survive; cover in sourcing, stack-emitter, generator, and `check_v2` tests.
- Historical `VW-30`/`VW-31` references must remain documentation-only while active registry entries and totals exclude them; cover in diagnostic-registry/docs-gate tests and the final forbidden-token scan.

---

### Task 1: Specify the v2 contract and update schemas/models

**Files:**
- Modify first: `technical_docs/ARCHITECTURE.md` (Sec.3.12 and FR-57)
- Modify: `schemas/base-v2.schema.json`
- Modify: `schemas/feature-v2.schema.json`
- Modify: `src/chopper/core/models_config.py`
- Modify: `src/chopper/config/loaders.py`
- Test: `tests/unit/config/test_schema.py`
- Test: `tests/unit/config/test_sourcing_paths.py`
- Test: `tests/unit/config/test_loaders.py`

**Interfaces:**
- Consumes: Existing v1/v2 JSON loader and schema-validation contracts.
- Produces: `BaseJson.vars_file`, `FeatureJson.vars_file`, `vars_keep` fields, and no v2 `procs` model fields; `LoadedConfig` carries only `feature_vars`.

- [ ] **Step 1: Add failing schema/model tests** asserting `base-v2` and `feature-v2` accept `vars_file`, reject legacy `vars` and v2 `procs`, preserve v1 rejection/acceptance behavior, and retain literal-path validation for the renamed pointer.
- [ ] **Step 2: Run focused schema tests**
  - Run: `.venv/bin/python -m pytest tests/unit/config/test_schema.py::test_v2_preserves_every_v1_schema_field_except_version_and_pointers tests/unit/config/test_schema.py::test_v2_accepts_vars_file_and_rejects_old_pointer_names tests/unit/config/test_sourcing_paths.py tests/unit/config/test_loaders.py::TestLoadBase::test_v2_vars_file_hydrates_without_procs_pointer tests/unit/config/test_loaders.py::TestLoadFeature::test_v2_vars_file_hydrates_without_procs_pointer --no-cov -q`
  - Expected: initially fails on the old v2 schema and missing `vars_file` model fields; passes after Steps 3–5.
- [ ] **Step 3: Update the architecture contract before implementation** so v2 defines `vars_file` only, base pointers are whole-file layer-local keeps merged through existing F1/F2 semantics, feature pointers feed only `<flow>_feature_vars.tcl`, and aggregate-stack inputs include only that wrapper. Remove the procs-wrapper behavior from FR-57 and Sec.3.12 without rewriting historical revision entries.
- [ ] **Step 4: Replace schema properties/descriptions** with `vars_file` in both v2 schemas, remove v2 `procs`, and leave `project-v2` untouched.
- [ ] **Step 5: Rename the typed fields and loader hydration** from `vars` to `vars_file`; remove `procs`, `procs_keep`, and `feature_procs` from config models and update docstrings/exported contracts without changing v1 fields or procedures include/exclude records.
- [ ] **Step 6: Run the focused tests again** and require all schema/path tests to pass.
  - Run: the Step 2 command above, plus `.venv/bin/python -m pytest tests/unit/config/test_loaders.py --no-cov -q`
  - Expected: all tests pass; the full schema corpus is checked after example JSONs are updated in Task 5.

### Task 2: Collapse config resolution to feature vars only

**Files:**
- Modify: `src/chopper/config/service.py`
- Modify: `src/chopper/config/loaders.py` (resolver-facing documentation/calls if still required)
- Test: `tests/unit/config/test_service.py`
- Test: `tests/unit/config/test_service_feature_vars.py`
- Test: `tests/property/test_feature_sourcing.py`

**Interfaces:**
- Consumes: `BaseJson.vars_file`, `FeatureJson.vars_file`, `expand_vars_entry(entry: str) -> tuple[str, str, str]`.
- Produces: one feature-vars resolution path returning `(BaseJson, list[FeatureJson], tuple[tuple[str, ...], ...])`; missing authored entries use `VW-27`, duplicate expanded entries use `VW-29`, and no `kind` switch remains.

- [ ] **Step 1: Add failing resolver tests** for base `vars_file` whole-file keep, feature wrapper-only blocks, authored/`tech_`/`project_` order, first-wins duplicate handling, and absence of procs resolution/fields.
- [ ] **Step 2: Run the focused resolver/property tests**
  - Run: `.venv/bin/python -m pytest tests/unit/config/test_service.py tests/unit/config/test_service_feature_vars.py tests/property/test_feature_sourcing.py --no-cov -q`
  - Expected: FAIL while the implementation still branches on `vars`/`procs`.
- [ ] **Step 3: Remove the procs resolver call and `kind` branch** from `ConfigService.run` and `_resolve_feature_vars`; resolve only `vars_file`, retaining the base-name `VW-28` check and feature block construction.
- [ ] **Step 4: Preserve F1 surface collection for `vars_keep`** but remove `procs_keep`; ensure base keep data is layer-local and feature keep data covers only existing expanded vars files.
- [ ] **Step 5: Run the focused tests** and require the exact diagnostic codes/order and feature block tuples to pass.
  - Run: the Step 2 command above.
  - Expected: all resolver/property tests pass; the end-to-end wrapper test runs in Task 3 after its compiler/generator consumers are updated.

### Task 3: Remove procs wrapper/compiler/generator paths

**Files:**
- Modify: `src/chopper/core/models_compiler.py`
- Modify: `src/chopper/compiler/merge_service.py`
- Modify: `src/chopper/generators/service.py`
- Modify: `src/chopper/generators/vars_emitter.py`
- Modify: `src/chopper/config/service.py` or stack-input callers discovered by the existing tests
- Delete: `tests/integration/test_feature_procs.py`
- Delete: `tests/unit/config/test_service_feature_procs.py`
- Test: `tests/unit/generators/test_vars_emitter.py`
- Test: `tests/unit/generators/test_stack_emitter.py`
- Test: `tests/integration/test_feature_sourcing_options.py`
- Test: `tests/integration/test_feature_vars.py`

**Interfaces:**
- Consumes: `CompiledManifest.feature_vars`.
- Produces: exactly one `emit_feature_vars(flow_name, blocks)` artifact at `<flow>_feature_vars.tcl`; aggregate stack `I` inputs include only that path; no `feature_procs` field or `procs` emitter switch.

- [ ] **Step 1: Add/adjust failing generator and stack assertions** requiring one vars artifact, no procs artifact, no `procs` argument, and no procs stack input; retain Tcl literal escaping coverage for vars entries.
- [ ] **Step 2: Run focused generator/stack/sourcing tests**
  - Run: `pytest tests/unit/generators/test_vars_emitter.py tests/unit/generators/test_stack_emitter.py tests/integration/test_feature_sourcing_options.py -q`
  - Expected: FAIL because the current manifest and generator emit both wrappers.
- [ ] **Step 3: Remove `feature_procs` from `CompiledManifest` and all compiler registration/return paths**; retain the single generated-vars registration and its existing `VE-40` collision/provenance behavior.
- [ ] **Step 4: Simplify `emit_feature_vars`** to the vars-only signature/path/title and update `GeneratorService` to emit one wrapper; pass only that wrapper to aggregate stack `extra_inputs`.
- [ ] **Step 5: Run focused tests** and verify generated artifact order, manifest provenance, stack input lines, and no-wrapper behavior for v1.

### Task 4: Reconcile active diagnostics and documentation registry

**Files:**
- Modify: `src/chopper/core/_diagnostic_registry.py`
- Modify: `technical_docs/DIAGNOSTIC_CODES.md`
- Modify: `technical_docs/ENGINEERING.md`
- Modify: `technical_docs/JSON_AUTHORING_GUIDE.md`
- Modify: `user_docs/01_OVERVIEW.md`
- Modify: `user_docs/02_CLI_GUIDE.md`
- Modify: `tests/TESTING_STRATEGY.md`
- Test: existing registry/docs gate tests discovered by `make docs-gate`

**Interfaces:**
- Consumes: Current diagnostic registry mirror and historical documentation conventions.
- Produces: active diagnostics for `vars_file` only, reserved `VW-30`/`VW-31` slots, corrected active/historical/code-space counts, and wording that does not describe a live procs pointer/wrapper.

- [ ] **Step 1: Update docs and registry tests/fixtures** to assert active `VW-27`/`VW-29` wording uses `vars_file`, `VW-30`/`VW-31` are not active emitters, and historical entries remain explicitly retained.
- [ ] **Step 2: Run the documentation/registry gate before implementation**
  - Run: `make docs-gate`
  - Expected: FAIL until registry, table, historical notes, and counts agree.
- [ ] **Step 3: Update diagnostic registry source/table/counts** and revise `VE-40`/`VE-42` wording only as required by the approved design so no active text claims a generated feature-procs wrapper.
- [ ] **Step 5: Run `make docs-gate`** and require the registry mirror and counts to pass.

### Task 5: Update migration checker, skill guidance, agent instructions, and example 16

**Files:**
- Modify: `.github/skills/migrate-v1-to-v2/scripts/check_v2.py`
- Modify: `.github/skills/migrate-v1-to-v2/SKILL.md`
- Modify: `.github/skills/migrate-v1-to-v2/references/check_v2.md`
- Modify: `.github/skills/migrate-v1-to-v2/references/interview.md`
- Modify: `.github/agents/chopper-agent.agent.md`
- Modify: `.github/instructions/project.instructions.md`
- Modify: `AGENTS.md`
- Modify: `examples/16_feature_vars/README.md`
- Modify: `examples/16_feature_vars/jsons/apr_fc.json`
- Modify: `examples/16_feature_vars/jsons/features/dop.feature.json`
- Modify: `examples/16_feature_vars/jsons/features/fdr.feature.json`
- Delete: any example-16 procs-pointer assets that become unused, only when confirmed unused by the updated tests
- Test: `tests/integration/test_v2_check_script.py`
- Test: example command coverage in `tests/integration/test_feature_sourcing_options.py`

**Interfaces:**
- Consumes: The updated v2 schema and audit manifest containing only `apr_fc_feature_vars.tcl`.
- Produces: Migration guidance/checks that identify `vars_file`, never require/adopt `procs`, preview only the vars wrapper, and retain historical migration explanations without active forbidden references.

- [ ] **Step 1: Update checker tests/scenarios** so `_good_layers`, flawed cases, adoption gates, expected preview, delta, and counts exercise `vars_file` and contain no generated procs preview.
- [ ] **Step 2: Run the checker tests**
  - Run: `pytest tests/integration/test_v2_check_script.py tests/integration/test_feature_sourcing_options.py -q`
  - Expected: FAIL against the current checker’s `_KINDS`, procs preview, and adoption logic.
- [ ] **Step 3: Change `check_v2.py` and its references** from vars/procs pointer pairs to the single vars-file contract; remove procs-only suggestions/preview/gates while preserving baseline/history interpretation and `VW-29` guidance.
- [ ] **Step 4: Convert example 16** to `vars_file`, remove procs keys and generated-procs claims/assets, and update expected output/stack input/CLI narrative to one wrapper.
- [ ] **Step 5: Update agent/instruction guidance** so v2 additions, migration advice, and forbidden-token rules describe `vars_file` and procedures include/exclude rather than a procs pointer.
- [ ] **Step 6: Run focused integration/example tests** and require all four CLI commands, audit output, and migration report expectations to pass.

### Task 6: Apply the accepted release metadata call

**Files:**
- Modify: `README.md`
- Modify: `technical_docs/ARCHITECTURE.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: The design’s accepted builder call for version `4.12.0`.
- Produces: Matching version/changelog/revision-history metadata at `4.12.0`.

- [ ] **Step 1: Check the current version source and release-history conventions** without changing product code.
- [ ] **Step 2: Update `pyproject.toml`, README changelog, and the ARCHITECTURE revision row together** to `4.12.0`, preserving unrelated existing edits.
- [ ] **Step 3: Run the focused version/docs checks** and ensure no unrelated dirty-worktree lines were altered.

### Task 7: Run focused regression and full verification gates

**Files:**
- Test only; no additional product-code files are expected.

**Interfaces:**
- Consumes: All implementation changes from Tasks 1–6.
- Produces: Evidence that the rename/removal is complete, ASCII-safe, forbidden-token-clean, and green under project gates.

- [ ] **Step 1: Run the focused contract suite**
  - Run:
    ```bash
    pytest tests/unit/config/test_schema.py \
      tests/unit/config/test_sourcing_paths.py \
      tests/unit/config/test_service.py \
      tests/unit/generators/test_vars_emitter.py \
      tests/unit/generators/test_stack_emitter.py \
      tests/integration/test_feature_vars.py \
      tests/integration/test_feature_sourcing_options.py \
      tests/integration/test_v2_check_script.py \
      tests/property/test_feature_sourcing.py -q
    ```
  - Expected: PASS with no feature-procs test files collected.
- [ ] **Step 2: Run ASCII and forbidden-token scans** over active source/schema/test/docs/agent/example files:
  - Run: `LC_ALL=C grep -RInP '[^\x00-\x7F]' src schemas tests technical_docs user_docs docs/superpowers examples/16_feature_vars .github AGENTS.md README.md`
  - Expected: no output (or only pre-approved historical material explicitly allowed by the design).
  - Run: `grep -RInE 'feature_procs|<flow>_feature_procs|\"procs\"[[:space:]]*:|procs pointer|procs/procs' src schemas tests technical_docs user_docs docs/superpowers examples/16_feature_vars .github AGENTS.md README.md`
  - Expected: no active references; historical entries may remain only where explicitly preserved and must be excluded from the active-token assertion.
- [ ] **Step 3: Run repository gates**
  - Run: `make check`
  - Expected: lint, formatting, typing, imports, docs gate, and unit tests pass.
  - Run: `make ci`
  - Expected: all checks plus the complete 100% line/branch coverage suite pass.
- [ ] **Step 4: Review the final diff/status** with `git diff -- docs/superpowers/plans/2026-11-03-v2-vars-file-rename.md` and `git status --short`; confirm only the plan and intended implementation files are ours, existing dirty edits remain intact, generated/out-of-scope artifacts are untouched, and no commit is created.

## Self-Review

- **Spec coverage:** Tasks 1–3 cover the `vars_file` rename, base/feature semantics, and complete procs-path removal; Task 4 covers diagnostics and all named technical/user docs; Task 5 covers example 16, migration checker/skill, and agent surfaces; Task 6 covers the conditional version/changelog/revision call; Task 7 covers focused tests, ASCII/forbidden-token checks, `make check`, and `make ci`.
- **Step scan:** Each task uses failing-test, implementation, focused-verification, or final-gate steps; no step asks an implementer to make an unspecified “appropriate” change.
- **Type consistency:** The only produced sourcing field is `feature_vars`; resolver output and `CompiledManifest` consumption use the same `tuple[tuple[str, ...], ...] | None` shape; `emit_feature_vars` accepts only `(flow_name, blocks)`.
- **Review focus:** Each of the five likely failure modes is pinned to a named test file and a final active-token/registry check.
- **Proportion:** The plan records file boundaries, interfaces, exact behavior, and commands without reproducing implementation bodies or the approved design.
