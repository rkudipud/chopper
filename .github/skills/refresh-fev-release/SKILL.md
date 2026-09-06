---
name: refresh-fev-release
description: 'Use when a new release of a Conformal or Formality domain arrives, including December refreshes, stale base/feature/project JSONs, F1/F2/F3 resynthesis, all-feature reconstruction, or a base SLOC limit.'
---

# Refresh FEV Release JSONs

Refresh delivery configuration against the newly supplied source, not against old generated Tcl. Preserve meaningful feature boundaries and prove the result with current evidence.

## Load First

1. Read [release instructions](../../instructions/fev-release-refresh.instructions.md).
2. Read [workflow and commands](./references/workflow.md) and [failure playbook](./references/gotchas.md) before editing.
3. Consult [September baseline](./references/september-2026.md) for retained design intent and the previous handoff. Its measurements are historical, not proof for new or edited files.

The architecture document remains authoritative for Chopper behavior. This skill adds no runtime capabilities to Chopper. Do not modify the product to accommodate a domain refresh.

## Execution Checklist

- [ ] Confirm the new source roots, permitted writes, base contract, and supported recipes. Inspect actual layout; never infer vendor nesting.
- [ ] Work in the user's `final` or other approved durable area. Keep verification outside the two domain roots. Do not create an active `/tmp` workspace.
- [ ] Verify tcsh and the installed Chopper version. Resolve executable paths explicitly.
- [ ] Inspect each domain's reserved backup sibling. If preexisting and unexplained, stop for an authority decision before running Chopper.
- [ ] Record current source/JSON hashes, file/proc/stage inventory, old/new differences, and baseline results.
- [ ] Use existing JSONs as ownership guidance. Edit JSONs directly and locally; never run previous resynthesis/publishing scripts.
- [ ] Update all F1 assets, F2 proc ownership, and F3 source-derived blocks. Keep shared setup in providers and complete optional Tcl blocks in their feature.
- [ ] Test each first meaningful patch immediately, then iterate locally. Reconcile non-callgraph dependencies as well as proc calls.
- [ ] Validate schemas and actual CLI project mode from the final paths. Require each base's actual `chopper loc` result to be strictly below its agreed limit.
- [ ] Compare full in-memory reconstruction with the new source: files, proc sets, and literal lines. Inspect differences inside multiline data separately.
- [ ] Test individual features with prerequisites and dependency-consistent omissions. Add representative interacting recipes; do not claim exhaustive permutations.
- [ ] Generate successful final dry-run audits and confirm their input snapshots match the current JSONs.
- [ ] Write durable results, caveats, rerun commands, and the next-release handoff. Verify no required process is still running.

## Stop Conditions

Stop the affected operation for ambiguous backup authority, source changes outside approval, repeated editor corruption, an unmet numeric gate, or an unapproved base-contract change. Keep useful work and report the precise blocker. A warning-bearing exit 0 is not runtime signoff.

## Skill Acceptance

Use [pressure scenarios](./references/acceptance.md) to test future edits to this skill. Keep the workflow general; put release-specific facts in the handoff rather than changing the procedure for each quarter.