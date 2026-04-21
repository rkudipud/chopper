# Chopper — Diagnostic Codes Registry

> **Status:** Authoritative Source of Truth
> **Resolves:** E-01 (FINAL_PRODUCTION_REVIEW.md)

All diagnostic codes used by Chopper are registered here. Implementation code MUST use constants from `src/chopper/core/diagnostics.py` derived from this registry. Adding a new code requires updating this file first.

## Naming Convention

All codes follow the pattern **`<FAMILY><SEV>-<NN>`**:

| Component | Values | Meaning |
| --- | --- | --- |
| `FAMILY` | `V` Validation · `T` Trace · `P` Parser | Originating subsystem |
| `SEV` | `E` Error · `W` Warning · `I` Info | Severity baked into the name |
| `NN` | `01`–`99` | Sequential slot within that family+severity band |

**Read at a glance:** `VE-06` = Validation Error #6. `PW-04` = Parse Warning #4. `TW-02` = Trace Warning #2.

Each code also carries a **`slug`** — a kebab-case label that provides a stable human-readable identifier alongside the numeric code. Verbose and human-facing output displays the slug; machine output, JSON, and the Python constants registry use the numeric code.

Reserved rows (marked `—`) are intentionally blank — fill them sequentially when new codes are needed; never renumber existing ones.

## Code Space Summary

| Family+Severity | Range | Active | Reserved | Total | When emitted |
| --- | --- | --- | --- | --- | --- |
| `VE` Validation Errors | VE-01–VE-30 | 26 | 4 (retired: VE-16, VE-24; + 2 free: VE-30 and 1 mid-range) | 30 | Schema, path, action, ordering, filesystem failures — block output |
| `VW` Validation Warnings | VW-01–VW-20 | 17 | 3 | 20 | Soft mismatches, overlaps, stale globs, cross-source additivity vetoes, F3 cross-validate |
| `VI` Validation Info | VI-01–VI-05 | 3 | 2 (retired: VI-04, VI-05) | 5 | Advisory notices; no action required |
| `TW` Trace Warnings | TW-01–TW-10 | 4 | 6 | 10 | Proc call graph ambiguities (Phase 3) |
| `PE` Parse Errors | PE-01–PE-10 | 3 | 7 | 10 | Fatal parse failures; file skipped or partial |
| `PW` Parse Warnings | PW-01–PW-20 | 11 | 9 | 20 | Unresolvable or dynamic Tcl constructs |
| `PI` Parse Info | PI-01–PI-10 | 4 | 6 | 10 | Structural observations; fully handled |
| **Total** | | **68** | **37** | **105** | |

---

## 1. Validation Errors — `VE-01` through `VE-30`

> Phase 1 = Pre-Trim · Phase 2 = Post-Trim. All errors block output generation (exit 1) unless noted.

| Code | Slug | Phase | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- | --- |
| VE-01 | `missing-schema` | 1 | schema | 1 | JSON `$schema` field missing or not a known Chopper schema version | Add `"$schema": "chopper/base/v1"` (or feature/project variant) |
| VE-02 | `missing-required-fields` | 1 | schema | 1 | Required fields missing (base: `domain`; feature: `name`; project: `project`, `domain`, `base`) | Add the missing required field to your JSON |
| VE-03 | `empty-procs-array` | 1 | compiler | 1 | `procedures.include` entry has empty `procs` array (`"procs": []`) | Move the file to `files.include` for whole-file inclusion |
| VE-04 | `unsupported-flow-action` | 1 | compiler | 1 | `flow_actions` entry uses an unsupported `action` value | Use one of: `add_step_before`, `add_step_after`, `add_stage_before`, `add_stage_after`, `remove_step`, `remove_stage`, `load_from`, `replace_step`, `replace_stage` |
| VE-05 | `missing-action-target` | 1 | compiler | 1 | `add_*`, `replace_*`, or `remove_*` references a target that does not exist | Check that the `reference` stage/step exists prior to this action in compilation order |
| VE-06 | `file-not-in-domain` | 1 | validator | 1 | File in `files.include` does not exist in domain (or `_backup`) | Verify file paths are domain-relative and the file exists |
| VE-07 | `proc-not-in-file` | 1 | validator | 1 | Proc in `procedures.include` not found in the referenced file | Verify proc name matches a `proc` definition in the file |
| VE-08 | `duplicate-stage-names` | 1 | compiler | 1 | Duplicate stage names after all stage actions are applied | Rename one of the conflicting stages |
| VE-09 | `malformed-glob` | 1 | validator | 1 | Malformed glob pattern in file rules | Fix the glob syntax; supported: `*`, `?`, `**` |
| VE-10 | `occurrence-suffix-overflow` | 1 | compiler | 1 | `@n` suffix where `n` exceeds actual occurrence count for that step string | Reduce `@n` or verify the step appears enough times |
| VE-11 | `conflicting-cli-options` | 1 | cli | **2** | `--project` provided alongside `--base` or `--features` | Use `--project` alone or `--base`/`--features` alone |
| VE-12 | `project-schema-invalid` | 1 | schema | 1 | Project JSON fails `chopper/project/v1` schema validation | Fix project JSON: requires `$schema`, `project`, `domain`, `base` |
| VE-13 | `project-path-unresolvable` | 1 | cli | **2** | `base` or `features` paths in project JSON cannot be resolved to existing files. Owned by the **CLI pre-runner check** (before `ChopperRunner.run()` starts): Chopper renders the offending path(s) via the CLI's `TableRenderer`, emits the diagnostic on stderr (text or JSONL depending on `--json`), and exits 2 without entering the pipeline. | Fix the paths in the project JSON (relative to the domain root; no `..`, no absolute paths) and re-run |
| VE-14 | `duplicate-feature-name` | 1 | compiler | 1 | Two or more selected features have the same `name` field | Rename one feature or remove the duplicate |
| VE-15 | `missing-depends-on-feature` | 1 | validator | 1 | Feature JSON `depends_on` prerequisite is not selected in project `features` | Add the prerequisite feature to the project or remove the dependency declaration |
| VE-16 | `depends-on-out-of-order` | — | — | — | **RETIRED.** Feature order in `project.features` is no longer required to match `depends_on` order. Dependencies are checked after *all* feature JSONs are loaded: if a `depends_on` prerequisite is missing from the project selection, `VE-15` fires. Out-of-order placement is allowed. | — |
| VE-17 | `brace-error-post-trim` | 2 | validator | **3** | Post-trim re-tokenization of a rewritten `.tcl` file reports brace imbalance. This is an **internal-consistency assertion**: `PE-02` already rejects pre-existing imbalanced files in P2, so the only way P6 sees one is if the trimmer itself introduced it (programmer error). Exit 3 signals "Chopper broke," not "user input is bad." | File a bug with the offending path and the `trim_report.json`; restore `<domain>_backup/` and re-run |
| VE-18 | `template-script-path-escapes` | 1 | validator | 1 | `options.template_script` resolves (via `Path.resolve()`) to a path outside the domain root (symlink escape) or fails the schema path-shape check. The field itself is reserved and not executed in v1; only path safety is validated. | Fix the path or remove the option |
| VE-19 | `project-domain-mismatch` | 1 | validator | 1 | Project JSON `domain` field does not match the basename of the current working directory. Comparison is **case-insensitive** (`Path.cwd().name.casefold() == project.domain.casefold()`): operators authoring on Windows and running on Linux grid nodes are tolerated. | Run Chopper from the correct domain root, or fix `domain` in the project JSON |
| VE-20 | `duplicate-feature-entry` | 1 | validator | 1 | Same feature path appears more than once in project `features[]` | Remove duplicate entries; feature order must be unique |
| VE-21 | `occurrence-suffix-zero` | 1 | compiler | 1 | `@0` used on an action `reference` — `@n` is 1-based | Use `@1` for the first occurrence, or omit `@n` entirely |
| VE-22 | `ambiguous-step-target` | 1 | compiler | 1 | `replace_step` / `remove_step` targets a duplicate step string without `@n` disambiguation | Add `@n` to the `reference` to pick a specific occurrence |
| VE-23 | `no-domain-or-backup` | 1 | cli | 2 | Neither `<domain>/` nor `<domain>_backup/` exists at invocation — nothing to trim | Verify you are in the correct working directory; restore the domain from version control |
| VE-24 | `concurrent-invocation` | — | — | — | **RETIRED.** Chopper has no lock and no concurrency guard. It is a single-user, single-invocation push-button tool against a single on-disk domain. Two operators racing the same checkout is an operator-level contract violation; Chopper does not attempt to detect or prevent it. See [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §16 Q3. | — |
| VE-25 | `feature-depends-on-cycle` | 1 | compiler | 1 | Selected features form a `depends_on` cycle; topological sort is not possible | Break the cycle by removing or reordering `depends_on` declarations in the offending feature JSONs |
| VE-26 | `filesystem-error-during-trim` | 5 | trimmer | 1 | Filesystem operation failed during P5 trim (permission denied, disk full, read-only FS, missing parent directory, cross-device rename). No staging is used; on failure, `<domain>/` is left in whatever half-rebuilt state the failure produced and `<domain>_backup/` is untouched. Re-invocation detects this state as Case 2 (re-trim) and rebuilds `<domain>/` from `<domain>_backup/`. Audit bundle is still written to `.chopper/` on a best-effort basis. | Verify filesystem permissions and available space; re-run Chopper to resume from backup, or run `rm -rf <domain> && mv <domain>_backup <domain>` to reset manually |
| VE-27 | `backup-contents-missing` | 5 | trimmer | 1 | A file named in `CompiledManifest` as `FULL_COPY` or `PROC_TRIM` was not found under `<domain>_backup/` at P5. Manifest is out of sync with the backup tree (typically because the backup was hand-edited between runs). | Re-create the domain from version control and re-run; do not hand-edit `<domain>_backup/` |
| VE-28 | `domain-write-failed` | 5 | trimmer | 1 | Write to the rebuilt `<domain>/` failed mid-operation (partial write, post-write size mismatch, directory-vs-file collision). Distinct from `VE-26` which covers OS-reported errors; `VE-28` covers semantic-integrity failures (the write returned OK but the result is wrong). | Inspect `trim_report.json` for the offending path; re-run to resume from `<domain>_backup/` |
| VE-29 | `proc-atomic-drop-failed` | 5 | trimmer | 1 | The trimmer could not align a proc's byte span with its parser-reported line range during atomic deletion. Typically caused by DPA-block or comment-banner lookahead drift between P2 and P5 (files were edited between parse and trim, or parser output is stale). | Re-run Chopper end-to-end (parser output will be regenerated); if it persists, file a parser bug with the offending file |
| — | — | — | — | — | **VE-30 reserved** | — |

---

## 2. Validation Warnings — `VW-01` through `VW-20`

> Exit 0; `--strict` forces the final process exit code to 1 if any warning is present, but does **not** rewrite severity. Warnings stay warnings in `diagnostics.json` and in rendered output.

| Code | Slug | Phase | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- | --- |
| VW-01 | `file-in-both-include-lists` | 1 | compiler | 0 | Same file appears in both `files.include` and `procedures.include` | Remove from one list; full-file include supersedes proc-level |
| VW-02 | `proc-in-include-and-exclude` | 1 | compiler | 0 | Same proc listed in both include and exclude across inputs | Explicit include wins; review if exclude is intentional |
| VW-03 | `glob-matches-nothing` | 1 | validator | 0 | Glob pattern in `files.include` resolved to zero files | Pattern may be stale or mistyped |
| VW-04 | `feature-domain-mismatch` | 1 | validator | 0 | Feature JSON `domain` field does not match selected base domain | Feature may be domain-agnostic; verify intended use |
| VW-05 | `dangling-proc-call` | 2 | validator | 0 | Surviving proc calls another proc not present in trimmed output or `common/` | Add missing proc to `procedures.include` or accept the dangling reference |
| VW-06 | `source-file-removed` | 2 | validator | 0 | `iproc_source`/`source` references a file that was removed | Add missing file to `files.include` or remove the sourcing call |
| VW-07 | `run-file-step-trimmed` | 2 | validator | 0 | F3-generated run file references a step file that was trimmed away | Add step file to `files.include` or remove the step from stage |
| VW-08 | `file-empty-after-trim` | 2 | trimmer | 0 | File survived trim but lost all proc definitions; exists as blank/comment-only | Expected if only top-level code mattered; review if file should be in `files.include` |
| VW-09 | `fi-pi-overlap` | 1 | compiler | 0 | File is in `files.include` and also has procs in `procedures.include`; PI entries are redundant on FULL_COPY files | Remove from `files.include` to enable selective proc inclusion, or remove from `procedures.include` |
| VW-10 | `cross-source-fe-vetoed` | 1 | compiler | 0 | File is in one source's `files.exclude` but survives because another source (base or another feature) contributes the file via FI, PI, or PE. The excluding source's FE entry is discarded. Features are purely additive and cannot remove content contributed by other sources. | Remove the redundant `files.exclude` entry, or verify the other source's inclusion is intentional |
| VW-11 | `fe-pe-same-source-conflict` | 1 | compiler | 0 | Within a single JSON source, the same file appears in both `files.exclude` and `procedures.exclude` with no matching `procedures.include`. Both are removal-within-this-source signals; this source contributes nothing for the file (other sources may still contribute). | Within one JSON, use `files.exclude` alone to drop a file, or `procedures.exclude` alone to keep it with some procs removed |
| VW-12 | `pi-pe-same-file` | 1 | compiler | 0 | Same file has procs in both `procedures.include` and `procedures.exclude`; PI takes precedence, PE ignored for this file | Choose one model per file: additive (PI) or subtractive (PE), not both |
| VW-13 | `pe-removes-all-procs` | 1 | compiler | 0 | All procs excluded from file via `procedures.exclude`; file survives as comment/blank-only | Consider using `files.exclude` to remove the entire file instead |
| VW-14 | `step-file-missing` | 2 | validator | 0 | F3 step string is a bare `.tcl` filename but the target file did not survive trim (cross-validate) | Add the file to `files.include` or remove the step |
| VW-15 | `step-proc-missing` | 2 | validator | 0 | F3 step string is a bare proc name but the proc did not survive trim (cross-validate) | Add the proc to `procedures.include` or remove the step |
| VW-16 | `step-source-missing` | 2 | validator | 0 | F3 step contains `source` / `iproc_source` with a literal file path that did not survive trim | Add the sourced file to `files.include` or remove the step |
| VW-17 | `external-reference` | 2 | validator | 0 | Surviving code references a path outside the domain boundary (not an error; informational for cross-domain awareness) | Verify the external dependency is intentional; no action required if expected |
| VW-18 | `cross-source-pe-vetoed` | 1 | compiler | 0 | A source lists proc `p` of file `F` in `procedures.exclude`, but `p` survives because another source contributes `F` whole-file or includes `p` explicitly via `procedures.include`. The PE entry from the excluding source is discarded. Features cannot strip procs from content contributed by other sources. | Remove the redundant PE entry, or align with the other source's include intent |
| — | — | — | — | — | **VW-19 through VW-20 reserved** | — |

---

## 3. Validation Info — `VI-01` through `VI-05`

> Exit 0; purely advisory. `--strict` does **not** affect VI-* codes — advisories never flip the exit code.

| Code | Slug | Phase | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- | --- |
| VI-01 | `empty-base-json` | 1 | validator | 0 | Base JSON has no `files`, `procedures`, or `stages` blocks | May be intentional for feature-driven flow; review if draft |
| VI-02 | `top-level-tcl-only` | 2 | trimmer | 0 | File survived trim with only top-level Tcl; no proc definitions were present | Informational; no action needed |
| VI-03 | `domain-hand-edited` | 1 | cli | 0 | Re-trim detected that `<domain>/` contents diverged from the last generated output; rebuild from `_backup` will discard local edits. Chopper does **not** preserve hand edits — the single source of truth for the trimmed domain is `<domain>_backup/` plus the JSON selection. | Commit or stash local edits **before** re-running Chopper; once the rebuild starts, the divergent content is gone. |
| VI-04 | `hand-edits-stashed` | — | — | — | **RETIRED.** `--preserve-hand-edits` is not supported — no stash path exists. See [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §16 Q2. | — |
| VI-05 | `stale-lock-recovered` | — | — | — | **RETIRED.** Chopper has no lock file, so there is nothing to go stale. See [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §16 Q3. | — |

---

## 4. Trace Warnings — `TW-01` through `TW-10`

> All trace codes are warnings (exit 0). Emitted during Phase 3 (Merge & Trace) by the compiler.

| Code | Slug | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- |
| TW-01 | `ambiguous-proc-match` | compiler | 0 | Proc call token resolves to multiple canonical procs in the domain (ambiguous namespace match) | Disambiguate with namespace-qualified name in source or add explicit `procedures.include` |
| TW-02 | `unresolved-proc-call` | compiler | 0 | No in-domain proc matches after namespace resolution; assumed external or cross-domain | If the proc is needed, add it explicitly or verify it lives in external libraries or stdlib |
| TW-03 | `dynamic-call-form` | compiler | 0 | Dynamic or syntactically unresolvable call form (`$cmd`, `eval`, `uplevel`) — cannot statically trace | Add missing dependency explicitly to `procedures.include` if needed; review call site |
| TW-04 | `cycle-in-call-graph` | compiler | 0 | Cycle detected in proc call graph (e.g., A → B → A or self-recursion A → A) | Both procs are included (conservative approach); review for correctness and intentionality |
| — | — | — | — | **TW-05 through TW-10 reserved** | — |

---

## 5. Parse Errors — `PE-01` through `PE-10`

> Parse errors (exit 1) block the file from being fully indexed. The file is skipped or yields partial results.

| Code | Slug | Source | Exit | Description | Recovery Hint | Parser spec § |
| --- | --- | --- | --- | --- | --- | --- |
| PE-01 | `duplicate-proc-definition` | parser | 1 | Duplicate proc definition in the same source file; last definition wins for index | Remove one definition or rename the proc to avoid silent shadowing | §6.3 |
| PE-02 | `unbalanced-braces` | parser | 1 | Unbalanced braces in file; proc boundaries cannot be reliably determined | Fix brace matching in the Tcl source file; use an editor brace-matching tool | §3 |
| PE-03 | `ambiguous-short-name` | parser | 1 | A file defines two procs that collapse to the same `short_name` once namespace stripping is applied; F2 cannot disambiguate by short name alone | Rename one proc or reference it by namespace-qualified name in `procedures.include` | §4.3 |
| — | — | — | — | **PE-04 through PE-10 reserved** | — | — |

---

## 6. Parse Warnings — `PW-01` through `PW-20`

> Construct was seen but could not be fully indexed or traced. Exit 0.

| Code | Slug | Source | Exit | Description | Recovery Hint | Parser spec § |
| --- | --- | --- | --- | --- | --- | --- |
| PW-01 | `computed-proc-name` | parser | 0 | Computed proc name (contains `$`, `[`, etc.) — skipped from index | Cannot be indexed statically; rename to literal proc name if needed for dependency tracing | §4.3 |
| PW-02 | `utf8-decode-failure` | parser | 0 | UTF-8 decode failed on file; fell back to Latin-1 encoding | Convert file to UTF-8 if possible; may cause character misinterpretation in comments | §2 |
| PW-03 | `non-brace-body` | parser | 0 | Proc with non-brace body (e.g., quoted body `proc foo "..."`) — skipped | Rewrite proc with brace-delimited body `proc foo {...}`; provides better scoping | §4.3 |
| PW-04 | `computed-namespace-name` | parser | 0 | `namespace eval` with computed name (contains `$`); body NOT parsed for procs | Use literal namespace name if procs inside need static indexing; dynamic namespaces are skipped | §4.2 step 3 |
| PW-05 | `backslash-continuation` | parser | 0 | Multi-line definition with backslash continuation (e.g., `define_proc_attributes ...\\`) detected | Line counts may be offset at continuation points; file still parsed correctly | §3.2 |
| PW-06 | `multi-value-set` | parser | 0 | Variable assignment contains multiple space-separated values (preprocessor-like `set list "VAL1 VAL2"`) | Stored as single string value; if dynamic expansion needed, verify list structure in code | — |
| PW-07 | `dynamic-array-index` | parser | 0 | Array element assignment with dynamic index (e.g., `set arr($var) value`) — index not resolvable at parse time | If index is computed at runtime, key may be missed; use static indices for critical lookups | — |
| PW-08 | `deep-nesting` | parser | 0 | Deeply nested scopes detected (depth > 8 levels); parser state machine complexity increased | Proc likely still indexed; review if body contains nested proc definitions (unsupported in Tcl) | — |
| PW-09 | `dynamic-variable-ref` | parser | 0 | Dynamic variable reference (e.g., `$var`, `$array($key)`) inside proc body — reference not resolvable at parse time | If variable controls critical call flow, add explicit dependencies to `procedures.include` | — |
| PW-10 | `proc-call-in-string` | parser | 0 | Proc call in string context (e.g., `"[proc_name ...]"` or `"$proc_name"`) — not traced as dependency | If dynamic proc invocation is intended, add explicit include or use a literal proc name | — |
| PW-11 | `dpa-name-mismatch` | parser | 0 | `define_proc_attributes` proc name does not match the immediately preceding proc's `qualified_name`; DPA block not associated | Verify that the `define_proc_attributes` line names the correct proc; fix the proc name or reorder the file | §4.6 |
| — | — | — | — | **PW-12 through PW-20 reserved** | — | — |

---

## 7. Parse Info — `PI-01` through `PI-10`

> Purely observational (exit 0); the construct was recognized and handled normally.

| Code | Slug | Source | Exit | Description | Recovery Hint | Parser spec § |
| --- | --- | --- | --- | --- | --- | --- |
| PI-01 | `structured-comment-block` | parser | 0 | Structured comment block found before proc definition (`#proc`, `#purpose`, `#usage` fields) | Treated as metadata documentation; no action needed; enables doc extraction | §4.7 |
| PI-02 | `command-substitution-indexed` | parser | 0 | Bracketed command substitution `[cmd ...]` found in proc body; command name indexed when statically resolvable | Does not affect proc definition; influences dependency tracing only | §5.3 |
| PI-03 | `comment-separator-block` | parser | 0 | Structured comment block with separator lines recognized (e.g., `####...####`) | Treated as section header; supports indexed documentation extraction | §4.7 |
| PI-04 | `dpa-orphan` | parser | 0 | `define_proc_attributes` (or `define_proc_arguments`) found with no associated preceding proc in the file; block skipped | Informational only; common when a DPA block follows a comment or non-proc construct; no action required | §4.6 |
| — | — | — | — | **PI-05 through PI-10 reserved** | — | — |

---

## Notes

- **Exit 0** — Does not fail the run. Reported in output unless suppressed. `--strict` does **not** rewrite severity; it only forces the CLI to exit 1 if any nominal `WARNING` is present. `VI-*` advisories never flip the exit code.
- **Exit 1** — Validation or parse failure; output generation is blocked.
- **Exit 2** — CLI / pre-pipeline fatal: `VE-11` conflicting options, `VE-13` unresolvable `--project` paths, `VE-23` missing domain + backup.
- **Exit 3** — Unhandled exception inside a service (programmer error). Covered by the outer `try/finally` in [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §6.2; `AuditService` still writes `.chopper/internal-error.log`.
- **Retired codes** (`VE-16`, `VE-24`, `VI-04`, `VI-05`) retain their slot numbers for historical continuity and are never re-assigned. New codes take the lowest unused slot.
- **No plugin / MCP / advisor code family exists or is reserved.** There is no `X*` band. Plugin host, MCP driver, and AI advisor are permanently out of scope for Chopper (see [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §16 Q1 and [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) Scope Lock).
- Every code constant must be defined in `src/chopper/core/diagnostics.py` before use in implementation.
- Every code carries a kebab-case **`slug`** for human-facing display (e.g., `"duplicate-proc-definition"`). The numeric code is the canonical key in Python, JSON output, and log filtering; the slug is used only in rendered messages and verbose CLI output.
- When adding a new code: pick the lowest available reserved slot in the correct `<FAMILY><SEV>` band, assign a slug, update this table and the summary above, then implement the constant.
- **VW-10 re-assignment (2026-04-19):** `VW-10` was briefly retired (old slug `fi-pe-overlap`) when FI+PE was still modeled as a conflict. Under the purely additive feature model, FI+PE within a single source is a valid L2.2 authoring pattern, so the old semantics are dead. `VW-10` has been re-assigned to `cross-source-fe-vetoed` to report feature `files.exclude` entries that are discarded because another source contributes the file. The companion code `VW-18 cross-source-pe-vetoed` covers the same cross-source veto for `procedures.exclude`.
