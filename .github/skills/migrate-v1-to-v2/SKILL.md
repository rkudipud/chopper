---
name: migrate-v1-to-v2
description: 'Use when a user wants to move Chopper base/feature/project JSONs from v1 (base-v1, feature-v1, project-v1) to v2, add vars/procs pointers, adopt the generated <flow>_feature_vars.tcl / <flow>_feature_procs.tcl files, asks whether a v2 migration is done or correct, wants v1 or v2 JSONs reviewed for better trim output, or asks why VE-41, VW-27..VW-31, VE-40 or VE-42 appeared after an upgrade.'
---

# Migrate Chopper JSONs from v1 to v2

v2 adds two optional pointer keys, `vars` and `procs`, to base and feature JSONs. In an all-v2 run Chopper generates `<flow>_feature_vars.tcl` and `<flow>_feature_procs.tcl` at the domain root, which the flow infrastructure loads after the base vars and procs. Nothing else changes.

**Core principle:** migrate in proven steps. Flipping `$schema` alone must change nothing except adding the two generated files. Every later change is one layer at a time, and each is proven with a dry-run diff against the v1 baseline.

**Proof is deterministic.** [`scripts/check_v2.py`](./scripts/check_v2.py) grades every snapshot. It runs a pass/fail gate, reports the adoption level, previews the generated files, classifies every change against the v1 baseline, and gives an exact JSON edit for each issue. Don't call a phase done, or the migration finished, without its `RESULT: PASS`. Reference: [check_v2.md](./references/check_v2.md).

There is no `chopper migrate` command. A migration is a set of hand edits to JSON, validated by the normal CLI.

## Iron rules

1. **Interview before editing.** Ask the user the Round 1 questions in [interview.md](./references/interview.md) (use the ask-user tool) before changing any file. Don't assume answers and continue.
2. **Dry-run only.** Never run a live `chopper trim`, even on a copy, unless the user asks for it in this conversation.
3. **Write only where agreed:** the domain's `jsons/`, the project JSON, and one scratch folder the user approves for baselines. Never write to the domain's Tcl or to `<domain>_backup/`.
4. **One change set per dry-run.** If a dry-run shows a delta you didn't predict, stop and explain it before making more edits.

## The v2 contract (what you're migrating to)

| Rule | Detail |
| --- | --- |
| One version per run | Project, base and every selected feature must all be v1 or all v2. A mix emits `VE-41`. `project-v2` differs from `project-v1` only in its `$schema` value. |
| Pointer shape | `vars` / `procs` hold one domain-relative file path: no globs, no `..`, no trailing `/`, no drive letter. Both are optional. |
| Base pointer | Kept as an F1 whole-file include, and **never** listed in the generated files (the infrastructure already loads it). `tech_`/`project_` variants are **not** expanded for the base. |
| Feature pointer | Expands to `X`, `<dir>/tech_<name>` and `<dir>/project_<name>`. Each becomes `iproc_source -file … -optional` in the generated file. Variants that exist are kept automatically; missing variants are silent. |
| Block order | Features in dependency-sorted project order; the first occurrence of an entry wins (`VW-29` / `VW-31` for duplicates). |
| Missing pointer file | `VW-27` (vars) / `VW-30` (procs). The block is still emitted. |
| Flow name | `<flow>` = the domain directory's name. A base JSON not named `jsons/<flow>.json` emits `VW-28`. |
| Reserved names | Don't list the generated names in `files.*`, and don't define a stage whose `<stage>.tcl` would collide with them (`VE-40`, `VE-42`). |
| Outputs | `GENERATED` in the manifest, listed in `files_kept.txt`, counted by `chopper loc`, given `p4 add`/`p4 edit` lines in `.chopper/p4_commands.txt`, and added as `I` inputs on aggregate-stack records when `options.generate_stack` is true. |
| Not automatic | Chopper never adds a stage step that sources the generated files. The infrastructure must load them. |

Field reference: [JSON_AUTHORING_GUIDE.md Sec.2.4](../../../technical_docs/JSON_AUTHORING_GUIDE.md). Worked example: [examples/16_feature_vars/](../../../examples/16_feature_vars/). Code meanings: [DIAGNOSTIC_CODES.md](../../../technical_docs/DIAGNOSTIC_CODES.md).

## Workflow

Track these as todos. Don't start a phase until the previous one is green.

### Phase 0 — Inventory and v1 baseline (read-only)

1. List the domain's JSONs: base, every feature, and the project JSON(s). Note any already on v2.
2. Run the v1 recipe exactly as the user runs it today. Run it from the domain's parent folder and always pass `--domain`. Without it Chopper takes the current directory as the domain and fails with `VE-13`:
   ```text
   chopper validate --domain <domain> --project <project.json>     # or --base ... --features ...
   chopper trim --dry-run --domain <domain> --project <project.json>
   ```
3. Snapshot the run: copy the **whole** `.chopper/` folder to `<scratch>/v1/`. The checker needs all of it (run record, input JSON copies, dependency graph). Every later step gets its own folder (`<scratch>/p2/`, `<scratch>/p4_dft/`, …), and `v1/` is the reference for every diff.
4. Grade the baseline: `python .github/skills/migrate-v1-to-v2/scripts/check_v2.py <scratch>/v1`. Its `pointer-candidate` rows pre-fill the interview. The `fix` rows are pre-existing problems (for example `traced-callee-dropped`, a project JSON outside `jsons/`); report them, but they are not migration regressions.

### Phase 1 — Interview

Ask the questions in [interview.md](./references/interview.md), Round 1 then Round 2. One ask-user form per round. Show the user the inventory first, so the questions are concrete: "Is `vars.tcl` your base vars file?", not "What is your vars file?".

### Phase 2 — Schema flip only

1. Change every `$schema` in the selected set **at once**: `base-v1` → `base-v2`, `feature-v1` → `feature-v2`, `project-v1` → `project-v2`. Unselected features that might be selected later need the flip too; otherwise a later run hits `VE-41`.
2. Dry-run, snapshot into `<scratch>/p2/`, then grade it against the baseline:
   ```text
   python .github/skills/migrate-v1-to-v2/scripts/check_v2.py <scratch>/p2 --baseline <scratch>/v1
   ```
   **Expected:** `RESULT: PASS`, adoption `schema-only`, and no `unexpected` delta. The `expected` rows are the two `generated` files (`<flow>_feature_vars.tcl`, `<flow>_feature_procs.tcl`) with their `kept` and `p4 add` lines; the only `review` row is `+ diag VW-28`, when the base JSON isn't named `jsons/<flow>.json`. With `generate_stack`, the two files also become `I` inputs. Anything else means the migration went wrong. Stop.

   For a raw diff between any two snapshots, `scripts/compare_manifests.py BEFORE AFTER` prints the same facts unclassified. Provenance labels (`contributed_by`, `selection_source`) are ignored on purpose: they move to whichever layer contributed last, without changing what is kept.
3. If you see `VW-28`, offer the rename (Phase 3). It's optional.

### Phase 3 — Optional base rename

Rename `jsons/base.json` to `jsons/<flow>.json`, and update `base` in every project JSON plus any scripts or CI that pass `--base`. In Perforce, use `p4 move`, not delete plus add, so the file keeps its history. Auto-discovery tries `jsons/base.json` first, then `jsons/<flow>.json`, so bare `--domain` runs keep working. Dry-run; the only delta against Phase 2 must be `- diag VW-28`.

### Phase 4 — Pointers, one layer at a time

Order: the base first, then each feature in project order. For each layer:

1. Add the pointer(s) the user confirmed.
2. Apply the **cleanup checklist** below, but only the items the user approved.
3. Run `python schemas/scripts/validate_jsons.py <domain>`, then `chopper validate --domain <domain> …`, then `chopper trim --dry-run --domain <domain> …`. Snapshot the whole `.chopper/` into a new scratch folder.
4. **Write down the predicted delta before you run**, then run `check_v2.py <scratch>/<step> --baseline <scratch>/v1` and say whether it matched. `compare_manifests.py <previous> <step>` isolates this step's change. If the gate fails or a row surprises you, stop and explain before editing further.

A dry-run lists the generated files as `generated` rows but **never writes their contents**. The checker's `PREVIEW` section shows exactly what `<flow>_feature_vars.tcl` and `<flow>_feature_procs.tcl` will contain, built the same way Chopper builds them: project order, first-seen dedup, Tcl escaping. Show it to the user. After a live trim, the `generated-content` gate proves the files on disk match it.

**Cleanup checklist (per pointer):**

- [ ] **Redundant whole-file include.** A `files.include` of the same path is now redundant. Removing it is harmless; offer to.
- [ ] **Manual variants.** A `files.include` of `tech_<name>` / `project_<name>` next to a feature pointer is now automatic. Remove it.
- [ ] **Variants that were never sourced become active.** v1 may have kept `tech_<name>` / `project_<name>` without any step sourcing them. After migration the generated file sources them, which changes values. For example, a `tech_dft_vars.tcl` that sets `dft_chains 16` overrides the 8 from `dft_vars.tcl`. List every such variant, and confirm with the user that each should now load.
- [ ] **Feature files nothing loaded before start loading.** v1 may keep a feature's vars or procs file without any step or kept Tcl file sourcing it (the checker says "Nothing references it today", or `newly-sourced` with a baseline). The pointer makes it load at startup. Ask how it is loaded today. If the infrastructure already loads it, the pointer loads it twice.
- [ ] **Double sourcing of a feature file.** A stage step or `flow_actions` item that already sources the pointer file (`source X`, `iproc_source -file X …`) now loads it twice, and **re-applies the base value after a `tech_` override**. **Ask** before removing it, because the load point moves from that stage step to infrastructure startup (Round 2, Q5). That matters when the step ran after something the vars depend on, such as `core_run`.
- [ ] **Re-sourcing the base vars.** A stage step that sources the **base** `vars.tcl` after startup resets every feature override the generated file just applied. Ask whether that step still has to run (Round 2, base row).
- [ ] **Anchor coupling.** Before removing any base step, search every feature for an `add_step_after`, `add_step_before`, `replace_step` or `remove_step` whose `reference` names that step. Re-anchor those first, for example with `add_step_before` on the next step. Otherwise that feature fails with `VE-05`.
- [ ] **A `procs` pointer keeps the whole file.** If v1 trimmed that file at proc level (`procedures.include`), a pointer silently brings back the dropped procs. Choose with the user:
  - **(a)** no `procs` pointer for that file; or
  - **(b)** pointer plus `procedures.exclude` of exactly the procs v1 dropped. Verify the file is still `proc-trim` with the same surviving procs. `excluded_procs` in the manifest is always `null`; compare the surviving procs instead. The `selection_source` label changes to `…:procedures.exclude`; that's expected. An exclude list keeps any proc added to the file later. If that's not what the user wants, option (a) is safer.
- [ ] **Reserved names.** No `files.*` entry or stage name matches `<flow>_feature_vars` / `<flow>_feature_procs`.
- [ ] **One owner per pointer file.** Two features pointing at the same file get `VW-29` / `VW-31`. Keep one owner, and use `depends_on` if the other needs it first.

**Side effects to predict, not to be surprised by:**

- Removing the only stage step that calls `iproc_source` clears its `VW-15` (the checker's `step-source-form`).
- Removing the last `flow_actions` entry that touched a stage re-credits that `<stage>.tcl` to another layer in `files_kept.txt`. The script ignores labels, so you'll see no delta.
- The generated files are credited to `feature:<name>:vars` / `:procs` in `files_kept.txt`. Pointer-implied keeps show as `feature:<name>:files.include` in `input_sources`.
- A feature that holds only a `vars` or `procs` pointer is schema-legal. It doesn't need `files` or `procedures`.

### Phase 5 — Handoff

The migration is done only when the final snapshot passes the strict gate:

```text
python .github/skills/migrate-v1-to-v2/scripts/check_v2.py <scratch>/final --baseline <scratch>/v1 --require-adoption
```

`RESULT: PASS` with adoption `full` (or `partial`, with each remaining candidate listed as a user decision) is the deterministic proof. `schema-only` fails here on purpose: the JSONs say v2, but nothing uses v2.

Give the user:
- the checker's final report (gate, adoption, preview, delta)
- a per-layer change table: before, after, and why
- the expected-versus-actual delta for each phase
- the open decisions, including any `review` suggestion the user declined

Then make the opportunities pitch (below). Offer a live trim, but don't run one. If the user runs it later, re-run the checker on that `.chopper/` to get the `generated-content` gate.

## Reviewing JSONs for better output (v1 or v2)

Use this when the user asks "is my JSON good?", "why is X dropped?", or "how do I get more from Chopper?", even without a migration:

1. Dry-run the user's real selection and snapshot the whole `.chopper/`.
2. Run `check_v2.py <snapshot>` (add `--baseline` when there's an earlier snapshot to compare).
3. Present the suggestions in the checker's order: `fix`, then `improve`, then `review`. For each one, give the evidence and the exact `edit` from the report, and say what the trim will look like afterwards.
4. Apply only what the user approves, one layer at a time. Re-run and show the new report. Each fix should remove its own suggestion and leave no `unexpected` delta.

Don't invent suggestions the report doesn't support. If you see something it misses, say it is your judgment and show the evidence (a manifest row, a diagnostic, a source line).

## Opportunities to pitch (hold their hand)

Raise each one that applies, explain the benefit in one line, and ask before acting:

1. **Split feature vars out of the base vars.** `if {$use_dft} {…}` blocks in the base `vars.tcl` belong in a `dft_vars.tcl` behind the `dft` feature's `vars` pointer. Then the trimmed base only carries what every project needs.
2. **Use `tech_` / `project_` overrides** instead of editing the shared vars or procs. Drop `tech_dft_vars.tcl` next to `dft_vars.tcl`; it's sourced after the base file and kept automatically, with no JSON change.
3. **Feature procs files.** Move procs that only one feature calls into `procs/<feature>_procs.tcl` behind a `procs` pointer. This removes `procedures.include` bookkeeping from the base.
4. **One `project-v2` recipe per product line** (`jsons/project_lp.json`, `jsons/project_full.json`). Keep project JSONs under `jsons/` or outside the domain: a live trim only preserves `jsons/` and out-of-tree inputs. A `project.json` at the domain root is dropped, and you'll see it in the `exclude_file_list` section of `p4_commands.txt`.
5. **`options.generate_stack: true`.** Both generated files become scheduler `I` inputs on every aggregate-stack record automatically.
6. **Perforce and LoC.** `trim --p4` and `.chopper/p4_commands.txt` already include `p4 add` for the two new files, and `chopper loc` counts them under GENERATED.

## Red flags — stop and correct

| Thought | Reality |
| --- | --- |
| "I'll answer the questions with reasonable assumptions and keep going." | Assumptions about the infrastructure's load order are the biggest migration risk. Ask. |
| "Flip the schemas and add the pointers in one go; it's faster." | Then you can't tell a schema regression from a pointer side effect. Do Phase 2 alone. |
| "A live trim on a throwaway copy is harmless." | It isn't requested, and it writes outside the agreed folders. Dry-run is the proof. If the user does ask for one, run it from outside the domain; on Windows a live trim run from inside the domain fails with `VE-23`. |
| "The diff shows `selection_source` changed, so behavior changed." | Labels move to whichever layer contributed last. Only treatment, surviving procs, steps, kept paths, `p4` and codes count. |
| "The pointer covers `tech_dft_vars.tcl`, so I'll also list it to be safe." | It's redundant noise. Variants are automatic. |
| "I'll put `<flow>_feature_vars.tcl` in `files.include` so it's kept." | It's reserved (`VE-40`), and it's always generated. |
| "Only flip the features in this project." | Any v1 feature selected later fails with `VE-41`. Flip the whole `jsons/` set, or record which ones you left on v1. The checker's `orphan-json` row lists them. |
| "All `$schema` values say v2 and validate passes, so the migration is done." | That's `schema-only`: same output as v1 plus two empty files. `--require-adoption` fails it. Done means pointers in use. |
| "I'll read the manifests by hand; the checker is overkill." | Hand reading took the baseline agents about five minutes per scenario, and they still disagreed. Run the checker first, then explain its rows. |
| "`VW-15` on `iproc_source` is expected because the infrastructure provides it." | It's a false positive from the `-file` form (`step-source-form`), not something to ignore. Delete the step if the file becomes a pointer, or list `iproc_source` in a `--tool-commands` file. Never add a stub proc. |
| "The gate passed, so every `review` row is fine." | `review` rows change behavior on purpose (procs brought back, variants now sourced). Explain each one and get a yes. |

## Known traps outside v2

- A stage whose name matches a whole-file include (stage `setup` plus `setup.tcl` in `files.include`) makes the generated `setup.tcl` collide with the copied file. Today that aborts with an internal error (exit 3) instead of a diagnostic. Rename the stage.
- A stage step written `iproc_source -file X` emits `VW-15` naming `iproc_source`, because the post-trim check only recognizes the single-argument `source X` / `iproc_source X` form. Don't dismiss it: see the `step-source-form` suggestion.
- A project JSON inside the domain but outside `jsons/` (for example `<domain>/project.json`) is deleted by a live trim. The checker reports it as `project-outside-jsons`.
