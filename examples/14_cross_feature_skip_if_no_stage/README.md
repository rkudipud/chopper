# Example 14 -- Cross-Feature `skip_if_no_stage`

Demonstrates how a **cross-cutting feature** safely injects steps into stages created by other optional features.

## Domain Structure

```text
base.json          -> defines "main" stage only
dft.feature.json   -> creates "dft_check" stage (after main)
power.feature.json -> creates "power_check" stage (after main)
coverage_reporting.feature.json -> injects into main, dft_check, AND power_check
```

## The Pattern

`coverage_reporting` adds coverage-reporting steps into **all three stages**. But `dft_check` and `power_check` only exist when their respective features are loaded.

Without `skip_if_no_stage`, selecting coverage_reporting without power would fail:
```
VE-05 missing-action-target: stage "power_check" not found (exit 1)
```

With `"skip_if_no_stage": true` on the dft_check and power_check actions:
```
VI-05 flow-action-skipped-no-stage: skipped add_step_after targeting "power_check" (exit 0)
```

## Two Project Compositions

| Project file | Features loaded | Behaviour |
|---|---|---|
| `project_dft_only.json` | dft + coverage_reporting | power_check injection skipped (VI-05) |
| `project_full.json` | dft + power + coverage_reporting | All injections succeed |

## Key Rules

1. **Base stages don't need the flag** -- `main` is always present.
2. **Feature-created stages do** -- `dft_check` and `power_check` may be absent.
3. **Step-miss inside a present stage is still VE-05** -- `skip_if_no_stage` only softens the *stage-not-found* case.
4. **Intra-feature chaining doesn't need the flag** -- if your own feature creates a stage earlier in its `flow_actions`, it will be present by top-to-bottom application.

## Running

```bash
# Partial composition -- VI-05 for skipped power_check action
chopper validate --project project_dft_only.json

# Full composition -- all actions succeed
chopper validate --project project_full.json
```
