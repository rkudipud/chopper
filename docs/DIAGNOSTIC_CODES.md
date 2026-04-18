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
| `VE` Validation Errors | VE-01–VE-25 | 18 | 7 | 25 | Schema, path, action, ordering failures — block output |
| `VW` Validation Warnings | VW-01–VW-15 | 8 | 7 | 15 | Soft mismatches, overlaps, stale globs |
| `VI` Validation Info | VI-01–VI-05 | 2 | 3 | 5 | Advisory notices; no action required |
| `TW` Trace Warnings | TW-01–TW-10 | 4 | 6 | 10 | Proc call graph ambiguities (Phase 3) |
| `PE` Parse Errors | PE-01–PE-10 | 2 | 8 | 10 | Fatal parse failures; file skipped or partial |
| `PW` Parse Warnings | PW-01–PW-20 | 11 | 9 | 20 | Unresolvable or dynamic Tcl constructs |
| `PI` Parse Info | PI-01–PI-10 | 4 | 6 | 10 | Structural observations; fully handled |
| **Total** | | **49** | **46** | **95** | |

---

## 1. Validation Errors — `VE-01` through `VE-25`

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
| VE-13 | `project-path-unresolvable` | 1 | validator | 1 | `base` or `features` paths in project JSON cannot be resolved to existing files | Check paths are relative to the domain root (current working directory) |
| VE-14 | `duplicate-feature-name` | 1 | compiler | 1 | Two or more selected features have the same `name` field | Rename one feature or remove the duplicate |
| VE-15 | `missing-depends-on-feature` | 1 | validator | 1 | Feature JSON `depends_on` prerequisite is not selected in project `features` | Add the prerequisite feature to the project or remove the dependency declaration |
| VE-16 | `depends-on-out-of-order` | 1 | validator | 1 | Feature JSON `depends_on` prerequisite appears later than the dependent feature in project `features` order | Reorder project features so all prerequisites appear earlier than the dependent feature |
| VE-17 | `brace-error-post-trim` | 2 | validator | 1 | Surviving `.tcl` file has brace-matching errors after trim | Edit the file or adjust procs kept to avoid broken syntax |
| VE-18 | `template-script-path-escapes` | 2 | validator | 1 | `options.template_script` resolved path escapes domain root (symlink boundary) or does not exist at execution time | Fix the path or remove the option; skipped in `--dry-run` |
| — | — | — | — | — | **VE-19 through VE-25 reserved** | — |

---

## 2. Validation Warnings — `VW-01` through `VW-15`

> Exit 0; escalate to error with `--strict` unless noted otherwise.

| Code | Slug | Phase | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- | --- |
| VW-01 | `file-in-both-include-lists` | 1 | compiler | 0 | Same file appears in both `files.include` and `procedures.include` (ERROR in `--strict`) | Remove from one list; full-file include supersedes proc-level |
| VW-02 | `proc-in-include-and-exclude` | 1 | compiler | 0 | Same proc listed in both include and exclude across inputs | Explicit include wins; review if exclude is intentional |
| VW-03 | `glob-matches-nothing` | 1 | validator | 0 | Glob pattern in `files.include` resolved to zero files (ERROR in `--strict`) | Pattern may be stale or mistyped |
| VW-04 | `feature-domain-mismatch` | 1 | validator | 0 | Feature JSON `domain` field does not match selected base domain | Feature may be domain-agnostic; verify intended use |
| VW-05 | `dangling-proc-call` | 2 | validator | 0 | Surviving proc calls another proc not present in trimmed output or `common/` | Add missing proc to `procedures.include` or accept the dangling reference |
| VW-06 | `source-file-removed` | 2 | validator | 0 | `iproc_source`/`source` references a file that was removed | Add missing file to `files.include` or remove the sourcing call |
| VW-07 | `run-file-step-trimmed` | 2 | validator | 0 | F3-generated run file references a step file that was trimmed away | Add step file to `files.include` or remove the step from stage |
| VW-08 | `file-empty-after-trim` | 2 | trimmer | 0 | File survived trim but lost all proc definitions; exists as blank/comment-only | Expected if only top-level code mattered; review if file should be in `files.include` |
| — | — | — | — | — | **VW-09 through VW-15 reserved** | — |

---

## 3. Validation Info — `VI-01` through `VI-05`

> Exit 0; purely advisory. `VI-01` escalates to WARNING in `--strict`.

| Code | Slug | Phase | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- | --- |
| VI-01 | `empty-base-json` | 1 | validator | 0 | Base JSON has no `files`, `procedures`, or `stages` blocks (WARNING in `--strict`) | May be intentional for feature-driven flow; review if draft |
| VI-02 | `top-level-tcl-only` | 2 | trimmer | 0 | File survived trim with only top-level Tcl; no proc definitions were present | Informational; no action needed |
| — | — | — | — | — | **VI-03 through VI-05 reserved** | — |

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

| Code | Slug | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- |
| PE-01 | `duplicate-proc-definition` | parser | 1 | Duplicate proc definition in the same source file; last definition wins for index | Remove one definition or rename the proc to avoid silent shadowing |
| PE-02 | `unbalanced-braces` | parser | 1 | Unbalanced braces in file; proc boundaries cannot be reliably determined | Fix brace matching in the Tcl source file; use an editor brace-matching tool |
| — | — | — | — | **PE-03 through PE-10 reserved** | — |

---

## 6. Parse Warnings — `PW-01` through `PW-20`

> Construct was seen but could not be fully indexed or traced. Exit 0.

| Code | Slug | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- |
| PW-01 | `computed-proc-name` | parser | 0 | Computed proc name (contains `$`, `[`, etc.) — skipped from index | Cannot be indexed statically; rename to literal proc name if needed for dependency tracing |
| PW-02 | `utf8-decode-failure` | parser | 0 | UTF-8 decode failed on file; fell back to Latin-1 encoding | Convert file to UTF-8 if possible; may cause character misinterpretation in comments |
| PW-03 | `non-brace-body` | parser | 0 | Proc with non-brace body (e.g., quoted body `proc foo "..."`) — skipped | Rewrite proc with brace-delimited body `proc foo {...}`; provides better scoping |
| PW-04 | `computed-namespace-name` | parser | 0 | `namespace eval` with computed name (contains `$`); body NOT parsed for procs | Use literal namespace name if procs inside need static indexing; dynamic namespaces are skipped |
| PW-05 | `backslash-continuation` | parser | 0 | Multi-line definition with backslash continuation (e.g., `define_proc_attributes ...\\`) detected | Line counts may be offset at continuation points; file still parsed correctly |
| PW-06 | `multi-value-set` | parser | 0 | Variable assignment contains multiple space-separated values (preprocessor-like `set list "VAL1 VAL2"`) | Stored as single string value; if dynamic expansion needed, verify list structure in code |
| PW-07 | `dynamic-array-index` | parser | 0 | Array element assignment with dynamic index (e.g., `set arr($var) value`) — index not resolvable at parse time | If index is computed at runtime, key may be missed; use static indices for critical lookups |
| PW-08 | `deep-nesting` | parser | 0 | Deeply nested scopes detected (depth > 8 levels); parser state machine complexity increased | Proc likely still indexed; review if body contains nested proc definitions (unsupported in Tcl) |
| PW-09 | `dynamic-variable-ref` | parser | 0 | Dynamic variable reference (e.g., `$var`, `$array($key)`) inside proc body — reference not resolvable at parse time | If variable controls critical call flow, add explicit dependencies to `procedures.include` |
| PW-10 | `proc-call-in-string` | parser | 0 | Proc call in string context (e.g., `"[proc_name ...]"` or `"$proc_name"`) — not traced as dependency | If dynamic proc invocation is intended, add explicit include or use a literal proc name |
| PW-11 | `dpa-name-mismatch` | parser | 0 | `define_proc_attributes` proc name does not match the immediately preceding proc's `qualified_name`; DPA block not associated | Verify that the `define_proc_attributes` line names the correct proc; fix the proc name or reorder the file |
| — | — | — | — | **PW-12 through PW-20 reserved** | — |

---

## 7. Parse Info — `PI-01` through `PI-10`

> Purely observational (exit 0); the construct was recognized and handled normally.

| Code | Slug | Source | Exit | Description | Recovery Hint |
| --- | --- | --- | --- | --- | --- |
| PI-01 | `structured-comment-block` | parser | 0 | Structured comment block found before proc definition (`#proc`, `#purpose`, `#usage` fields) | Treated as metadata documentation; no action needed; enables doc extraction |
| PI-02 | `command-substitution-indexed` | parser | 0 | Bracketed command substitution `[cmd ...]` found in proc body; command name indexed when statically resolvable | Does not affect proc definition; influences dependency tracing only |
| PI-03 | `comment-separator-block` | parser | 0 | Structured comment block with separator lines recognized (e.g., `####...####`) | Treated as section header; supports indexed documentation extraction |
| PI-04 | `dpa-orphan` | parser | 0 | `define_proc_attributes` (or `define_proc_arguments`) found with no associated preceding proc in the file; block skipped | Informational only; common when a DPA block follows a comment or non-proc construct; no action required |
| — | — | — | — | **PI-05 through PI-10 reserved** | — |

---

## Notes

- **Exit 0** — Does not fail the run. Reported in output unless suppressed. `--strict` escalates `VW-*` and `VI-01` to errors.
- **Exit 1** — Validation or parse failure; output generation is blocked.
- **Exit 2** — CLI usage error (`VE-11` only).
- Every code constant must be defined in `src/chopper/core/diagnostics.py` before use in implementation.
- Every code carries a kebab-case **`slug`** for human-facing display (e.g., `"duplicate-proc-definition"`). The numeric code is the canonical key in Python, JSON output, and log filtering; the slug is used only in rendered messages and verbose CLI output.
- When adding a new code: pick the lowest available reserved slot in the correct `<FAMILY><SEV>` band, assign a slug, update this table and the summary above, then implement the constant.
