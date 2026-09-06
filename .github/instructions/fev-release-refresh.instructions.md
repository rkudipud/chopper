---
description: 'Use when refreshing Conformal/Formality release JSONs, modularizing FEV domains, verifying reconstruction, or preparing a December or later release handoff.'
applyTo: '**/jsons/**/*.json,**/verification/**'
---

# FEV Release Refresh Rules

- Load [refresh-fev-release](../skills/refresh-fev-release/SKILL.md) for this workflow. Scope these rules to customer-domain refreshes, not unrelated repository fixtures.
- The newly supplied release is source truth. Prior JSONs express delivery intent; old generated scripts and successful logs are not the new source or fresh proof.
- Use the user's `final` or other approved persistent work area. No active `/tmp` deliverables, hidden scratch dependencies, or hardcoded previous-release destinations.
- On this deployment use tcsh only. Probe `echo $shell`; use `set`/`setenv`, not bash activation, heredocs, or environment syntax.
- Confirm domain roots and actual layout. Stop before Chopper execution if an unexplained `<domain>_backup` exists. Never use that reserved name for a personal snapshot.
- Source Tcl and other runtime assets remain unchanged unless separately approved. Default to schema checks, `validate`, `loc`, and `trim --dry-run`. A copy's existence is not permission for live trim.
- Prefer direct reviewable patches. Read current content before every edit slice; the user or formatter may have changed it. Never use Add on an existing file or assume delete/add means replace.
- Do not run JSON-writing Python resynthesis scripts. If direct edits corrupt a destination, stop and seek a narrow recovery exception. A past exact-copy exception is not continuing permission. Never restore JSONs with globs or recursive copies.
- Keep universal initialization with its stage provider; move complete optional Tcl blocks with their matching braces and supporting procs. Preserve literal whitespace and command order.
- Trace is reporting-only. Explicitly retain necessary procs/files and check dynamic dispatch, sourced assets, report consumers, and setup variables beyond the call graph.
- Preserve declared ordering and prerequisites. `skip_if_no_stage` does not retroactively inject into a later provider. No blanket promise that arbitrary permutations work.
- Do not weaken required pass/fail behavior or hide counted files to meet SLOC. Any base-contract change needs explicit approval. The default release target is strictly less than 5000 SLOC per base unless the user changes it.
- Validate final on-disk JSONs and actual CLI project paths. Enforce full reconstruction, base limits, rebuilt Tcl checks, tested combinations, current audit inputs, and source integrity with fresh evidence.
- Delegate only when authorized, with disjoint file ownership; independently verify results. Stop parallel publishing immediately if any destination is corrupted.
- Record exactly what passed and what did not. Static checks do not execute EDA tools or prove all feature combinations. Preserve unresolved external/dynamic dependencies in the handoff.