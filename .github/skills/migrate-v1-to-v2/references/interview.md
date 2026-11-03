# v1 → v2 interview question bank

Ask with the ask-user tool. Use one form per round, with the fields in the order listed. Pre-fill defaults from the Phase 0 inventory and the baseline `check_v2.py` report, so the user confirms instead of typing:

| Field | Pre-fill from |
| --- | --- |
| Round 1 Q3/Q4, feature rows 1/2 | `pointer-candidate` rows (their `edit` names the pointer value; "Nothing references it today" means ask how that file loads now) |
| Round 1 Q5 | `base-name` |
| Feature row 3 | `procs-pointer-proc-trim`, or a procs file that is `proc-trim` in the manifest |
| Feature row 4 | `redundant-pointer-include`, `manual-variant-include` |
| Feature row 5 | `double-sourcing-step` |
| Feature row 6 | `dormant-variant`, `newly-sourced` |
| Round 3 | the remaining `improve` and `review` rows (for example `traced-callee-dropped`, `project-outside-jsons`, `orphan-json`, `stale-exclude`) |

## Round 1 — scope and infrastructure (before any edit)

| # | Field | Type | Default / options | Why it matters |
| --- | --- | --- | --- | --- |
| 1 | Recipes to migrate | multi-select | every project JSON found, plus "base + features passed on the command line" | Each selected recipe is one set that must flip together (`VE-41`). |
| 2 | Infrastructure loads the generated files | enum | "Yes — after base vars/procs" / "Not yet — I'll add it" / "Unsure" | Chopper never sources them. If the answer isn't "Yes", the feature vars and procs silently stop loading after the steps that sourced them are removed. |
| 2a | Loaded in every stage's tool run, and before or after `load_from` session restore? | enum | "Every stage, after restore" / "Every stage, before restore" / "Only the first stage" / "Unsure" | A restored session can overwrite values the generated file just set, and a stage that never loads it loses the feature settings. This decides whether the stage steps that source the files today can go. |
| 3 | Base vars file | string | the most likely candidate (`vars.tcl`, `<flow>_vars.tcl`) or empty | It becomes the base `vars` pointer: kept as F1 and never listed. |
| 4 | Base procs file | string | the most likely candidate (`procs/core_procs.tcl`, …) or empty | It becomes the base `procs` pointer. Leave it empty if the base procs are trimmed at proc level. |
| 5 | Rename the base JSON to `jsons/<flow>.json` | boolean | true when `VW-28` would fire | Clears `VW-28`. Every `--base` caller must be updated. |
| 6 | Scratch folder for baselines | string | a sibling of the domain, e.g. `<domain>.v2_migration/` | Keeps the evidence out of the trimmed tree. |

## Round 2 — per layer (the base row first, then one row per feature in project order)

**Base row**

| # | Field | Type | Default / options | Why it matters |
| --- | --- | --- | --- | --- |
| B1 | Stage steps that source the base vars file | enum | "Remove — infra loads it at startup" / "Keep — it must run at that point" | A step that re-sources the base `vars.tcl` after startup **resets every feature override** that the generated file applied. If you keep it, record the reason. |
| B2 | Base steps that a feature uses as an anchor | info | list them from the inventory | Removing them makes the feature fail with `VE-05`. Re-anchor first. |

**Feature rows**

| # | Field | Type | Default / options | Why it matters |
| --- | --- | --- | --- | --- |
| 1 | `<feature>` vars pointer | string | the feature's `*_vars.tcl` from `files.include`, or empty | Three `-optional` lines in `<flow>_feature_vars.tcl`. |
| 2 | `<feature>` procs pointer | string | the feature's `*_procs.tcl`, or empty | Three lines in `<flow>_feature_procs.tcl`, **and the whole file is kept**. |
| 3 | Proc-level trim on that procs file | enum | "No procs pointer" / "Pointer + procedures.exclude of v1-dropped procs" | Only when v1 used `procedures.include` on that file. An exclude list also keeps procs added later. |
| 4 | Remove the redundant `files.include` of pointer and variant paths | boolean | true | Pure cleanup; no behavior change. |
| 5 | Remove the steps that already source the pointer file | enum | "Remove — infra loads it at startup" / "Keep — the load point matters" | Removing moves the load from a stage step to startup, which matters when the step ran after something the vars depend on (e.g. `core_run`). Keeping double-loads, and resets `tech_` overrides. |
| 6 | Activate the `tech_`/`project_` variants that are kept but not sourced today | boolean | false when any exist, and list them | After migration they're sourced automatically and override the feature file's values. |

## Round 3 — opportunities (after the migration is green)

A multi-select over the applicable items in the SKILL "Opportunities to pitch" list plus the checker's remaining `improve`/`review` suggestions, where each label states the benefit. Only act on what's selected, and run the Phase 4 loop for each one.
