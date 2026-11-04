# v1 → v2 interview question bank

Ask with the ask-user tool. Use one form per round, with the fields in the order listed. Pre-fill defaults from the Phase 0 inventory and the baseline `check_v2.py` report, so the user confirms instead of typing:

| Field | Pre-fill from |
| --- | --- |
| Round 1 Q3, feature row 1 | `pointer-candidate` rows (their `edit` names the pointer value; "Nothing references it today" means ask how that file loads now) |
| Round 1 Q5 | `base-name` |
| Feature row 2 | Procedure-hosting files named in existing `procedures.include` / `procedures.exclude` rules |
| Feature row 3 | `redundant-pointer-include`, `manual-variant-include` |
| Feature row 5 | `double-sourcing-step` |
| Feature row 6 | `dormant-variant`, `newly-sourced` |
| Round 3 | the remaining `improve` and `review` rows (for example `traced-callee-dropped`, `project-outside-jsons`, `orphan-json`, `stale-exclude`) |

## Round 1 — scope and infrastructure (before any edit)

| # | Field | Type | Default / options | Why it matters |
| --- | --- | --- | --- | --- |
| 1 | Recipes to migrate | multi-select | every project JSON found, plus "base + features passed on the command line" | Each selected recipe is one set that must flip together (`VE-41`). |
| 2 | Infrastructure loads the vars files | enum | "Yes — base vars then feature-vars wrapper" / "Not yet — I'll add it" / "Unsure" | Chopper never sources the wrapper. If the answer isn't "Yes", feature vars silently stop loading after the steps that sourced them are removed. There is no generated procedure wrapper. |
| 2a | Loaded in every stage's tool run, and before or after `load_from` session restore? | enum | "Every stage, after restore" / "Every stage, before restore" / "Only the first stage" / "Unsure" | A restored session can overwrite values the generated file just set, and a stage that never loads it loses the feature settings. This decides whether the stage steps that source the files today can go. |
| 3 | Base vars file | string | the most likely candidate (`vars.tcl`, `<flow>_vars.tcl`) or empty | It becomes the base `vars_file`: kept by F1 and merged with normal R1/F2 decisions, but never listed in the wrapper. |
| 4 | Base procedure-hosting files | string | files already selected by F2, or empty | These remain `procedures.include` / `procedures.exclude` selections; there is no proc pointer. |
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
| 2 | `<feature>` procedure files and procs | string | file paths and explicitly selected proc names, or empty | These remain F2 `procedures.include` / `procedures.exclude` selections; Chopper does not create a proc wrapper. |
| 3 | Remove the redundant `files.include` of the vars pointer and variants | boolean | true | Pure cleanup; no behavior change. |
| 4 | Remove the steps that already source the vars pointer file | enum | "Remove — infra loads it at startup" / "Keep — the load point matters" | Removing moves the load from a stage step to startup, which matters when the step ran after something the vars depend on (e.g. `core_run`). Keeping double-loads, and resets `tech_` overrides. |
| 5 | Activate the `tech_`/`project_` vars variants kept but not sourced today | boolean | false when any exist, and list them | After migration they're sourced automatically and override the feature file's values. |

## Round 3 — opportunities (after the migration is green)

A multi-select over the applicable items in the SKILL "Opportunities to pitch" list plus the checker's remaining `improve`/`review` suggestions, where each label states the benefit. Only act on what's selected, and run the Phase 4 loop for each one.
