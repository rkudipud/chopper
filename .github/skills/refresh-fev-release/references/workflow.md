# Release Refresh Workflow

## 1. Establish Source And Workspace

Get only the missing decisions: new source location, domain boundaries, permitted JSON/source changes, the minimum base behavior, SLOC limit, and expected project recipes. Reuse confirmed intent instead of restarting a full onboarding interview. Do not assume a named domain is nested below a vendor directory: September's `final/cdns` and `final/snps` were the domain roots themselves.

Use a durable user-owned layout:

```text
<release-area>/final/
  cdns/                  # or the user's actual Conformal root
    jsons/
    .chopper/            # latest successful dry-run audit
  snps/                  # or the user's actual Formality root
    jsons/
    .chopper/
  verification/          # helpers, reports, inventories, handoff
  experiments/           # only if copies are useful and approved
```

The names are examples, not prescribed directories. Put experimental domains and `.pristine` snapshots outside the measured domain roots so they cannot enter F1 selection or SLOC. Never use a name ending in `_backup` for an agent-created snapshot. For an unexplained existing reserved backup, ask whether to accept its authority or have the user rename/remove it; do not decide silently.

Read the latest handoff, actual JSONs, and local specification sections for the path being changed. Do not remap Chopper internals if the existing verification helper already provides the needed services. Check only version-sensitive APIs and concrete discrepancies.

## 2. Record Baseline Evidence

Before modifying inputs, persist an inventory and hashes of the new runtime sources and existing JSONs under `verification/`. Preserve prior audit evidence before a new run overwrites `.chopper/`; a run ID identifies a run, not a stable input version. If git is unavailable, a hash manifest plus an approved out-of-domain pristine copy provides the comparison basis.

Inventory every file, not only extensions counted by `loc`. Separate authoring JSON, runtime configuration, scripts, stacks, utilities, templates, and data. Compare the previous and new release for additions, removals, renames, and changed bodies. Compare proc definitions and stage scripts as well as filenames. A name-valid F2 selection automatically retains the new proc body, but may need newly called helpers.

Record which scripts are stage providers, which features inject into them, and which procs/files are shared. Produce a file/proc ownership map and a compact call-tree summary from Chopper. Distinguish resolved domain procs, tool commands, shared framework hooks, unresolved dynamic calls, and actual missing dependencies.

Baseline gates are evidence, not edits: schema validation, explicit-base `loc`, actual project validation, and dry-run where safe. A failed compilation's fallback `loc` totals are not a valid trimmed-base measurement.

## 3. Refresh F1, F2, And F3

### F1: Assets

Remove stale literal paths to files absent from the new release. Add new utility subtrees to responsibility-based features. Include adjacent modules/databases/configuration consumed by a utility. Keep globs intact: testing `Path('utils/**').exists()` does not expand a glob and can incorrectly delete a valid selection.

Keep existing stacks through F1 unless generating stacks is explicitly intended. Enabling all available mechanisms is not required to demonstrate F1/F2/F3. Do not change scheduler format or enable stack generation merely because the tool supports it.

### F2: Procedures

Use the installed parser and canonical file-qualified names to identify definitions and call edges. Include local callees explicitly; a traced-only proc does not survive. Shared helpers may legitimately be retained by multiple features. Do not add every reachable optional proc to base as a shortcut.

Check variable-selected readers and command strings separately. A proc-name regex across comments and strings is not a call graph. Preserve the new source's ivar dispatch rather than replacing it unconditionally with an old feature-specific command. A feature must select real assets, procs, or executable blocks; do not create an empty placeholder feature for behavior still wholly in base.

For `default_rules.*.tcl`, retain the associated configuration and milestone files. Chopper's companion synchronization follows the selected rule procs; inspect its real in-memory output. Keep required report producers when their pass/fail consumers remain selected.

### F3: Stages

Read each new stage script and reconcile it with the owning base/provider and every feature injection. Refresh every generated stage, including ECO variants and secondary flows. The generated output name follows the stage name; verify it matches the actual source filename, independently of the scheduler task name.

Use a complete new-source Tcl block as the unit of ownership. Keep matching braces, `else` arms, continuation lines, literal data, initialization, and cleanup together. A syntactically incomplete feature fragment is unsafe even if all-on happens to balance. Preserve source command order and whitespace inside quoted/braced strings. Blank lines must not become empty schema-invalid steps; encode necessary newlines in neighboring strings without changing data.

Keep universal setup in providers. In September, report initialization was incorrectly assigned to nearby `parallel_batch` and `sequential_const_check` snippets, leaving base references to an undefined variable. Similarly, a replay guard and a low-power closing brace were split across owners. Test omission, not just inclusion.

Feature anchors must be unique and byte-exact. An anchor ending with `\n` is different from the same text without it. Reconcile actions after every source-block move; do not add anchors to a complete source script while leaving the original optional block in place, which duplicates execution.

Diff/sequence matching is useful for investigation, not an authority for ownership. Do not automatically transfer labels across changed Tcl; newly inserted universal statements can inherit the wrong optional owner. Direct manual patches remain the default.

## 4. Control Base Size Honestly

Measure the real rebuilt base using `chopper loc`, with explicit `--base` to avoid automatic project selection. Use the same installed counter/backend for comparisons. Do not rename suffixes, alter counting rules, minify source, disable required checks, or move assets outside the domain to satisfy the number.

Rank per-file and per-proc contributions using Chopper's SLOC counter and in-memory output. Extract logically optional capabilities together with callers, rules, and required assets. Keep minimal shared helpers when a retained proc calls them. Seek approval before changing what base guarantees. If the agreed behavior cannot fit, report the measured deficit and decision required rather than inventing a passing number.

## 5. Verify Final Inputs And Output

Required gates:

1. Every current base/feature/project JSON parses as one document and validates against the installed schemas.
2. Actual final-path CLI project validation passes. Project metadata must be exercised, not bypassed by extracting only its feature list.
3. Each explicit base's CLI `loc` exits successfully and reports SLOC strictly below the agreed limit.
4. The full in-memory rebuild has no unexplained missing/extra runtime files or procs, and no executable-content differences from the new source.
5. Rebuilt Tcl is checked with absolute rewritten paths. Include targeted assertions for shared initialization and known cross-feature defects.
6. Each feature plus prerequisites and each omission plus removal of dependents passes. Add representative multi-feature recipes where interactions warrant it. Report the exact tested set, not an exhaustive-combinations claim.
7. A final successful `trim --dry-run` produces graphs, manifest, diagnostics, reports, and input snapshots matching the final JSONs.
8. Original runtime-source hashes are unchanged unless specific source edits were approved. Current audit inputs and verification files refer to the actual delivery tree.

Compare literal lines as well as normalized ones. Line filters can hide blank or comment-looking text inside multiline strings; inspect such regions with Tcl-aware parsing or focused evaluation. Never declare semantic equivalence from SLOC equality, brace balance, or a comment-stripped diff alone. Vendor runs with representative designs are a separate signoff gate.

## 6. tcsh Command Templates

Set real paths from the user; these are not shell-ready defaults:

```tcsh
echo $shell
set repo_root = /path/to/chopper
set release_root = /user/approved/new-release/final
set python = "$repo_root/.venv/bin/python"
set chopper = "$repo_root/.venv/bin/chopper"
set domain = "$release_root/cdns"
set checks = "$release_root/verification"
"$chopper" --version
```

Inspect the parent directory for backup siblings first. The sibling-list glob is read-only; it is never a restore/copy pattern. Do not paste bash `2>/dev/null` or heredocs into tcsh.

```tcsh
ls -d "${domain}"*
"$python" "$repo_root/schemas/scripts/validate_jsons.py" --schema-dir "$repo_root/schemas" "$domain/jsons"
"$chopper" validate --domain "$domain" --project "$domain/jsons/project_all_on.json"
"$chopper" loc --domain "$domain" --base "$domain/jsons/base.json"
"$chopper" trim --dry-run --domain "$domain" --project "$domain/jsons/project_all_on.json"
```

The explicit `--schema-dir` is important: the helper's default was unsuitable in this checkout. Verify the installed CLI flags before adapting templates to a later Chopper version.

Reuse the read-only September verifier only after inspecting its source and confirming its imported APIs still exist. Put the reviewed helper in the new durable `verification/` area, not in an old release or `/tmp`. It accepts the new domain/project paths; the old `run_checks.csh` instead hardcodes September paths and must not be run unchanged on December.

```tcsh
"$python" "$checks/verify_domains.py" "$domain" --base-limit 5000 --brief
"$python" "$checks/verify_domains.py" "$domain" --project "$domain/jsons/project_all_on.json" --compare --matrix --brief
"$python" "$checks/verify_domains.py" "$domain" --project "$domain/jsons/project_all_on.json" --matrix --omit --brief
```

Use `--start` and `--stop` for bounded matrix ranges if needed. Keep stderr progress separate from JSON stdout. `>& log` captures both streams; `> report.json` captures stdout. For a noninteractive check, `| tee report.json` can display and save stdout, but pipeline status may be `tee`'s status: inspect the saved check result and underlying completion rather than trusting the pipeline exit alone.

## 7. Finish In The Delivery Area

Prefer editing/testing final JSONs in place with a recorded recovery path, which avoids a second publishing step. If approved experiments are useful, make copies in the user area with disjoint names and freeze verified candidates before publishing. Revalidate actual final paths after any transfer or later edit.

Store the source/hash inventory, ownership map, base counts, reconstruction differences, tested recipes/matrices, warnings, runtime limitations, and exact rerun commands. Record current executable/version and source/input fingerprints. Update the handoff and repository memory. Do not rely on temporary paths, old logs, remembered metric values, or an agent's claim of completion.