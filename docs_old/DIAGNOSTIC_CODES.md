# Chopper — Diagnostic Codes Registry

> **Status:** Authoritative Source of Truth
> **Resolves:** E-01 (FINAL_PRODUCTION_REVIEW.md)

All diagnostic codes used by Chopper are registered here. Implementation code MUST use constants from `src/chopper/core/diagnostics.py` derived from this registry. Adding a new code requires updating this file first.

---

## Validation — Phase 1: Pre-Trim (V-01 through V-18)

| Code | Severity | Source | Exit | Description | Recovery Hint |
|---|---|---|---|---|---|
| V-01 | ERROR | schema | 1 | JSON `$schema` field missing or not a known Chopper schema version | Add `"$schema": "chopper/base/v1"` (or feature/project variant) |
| V-02 | ERROR | schema | 1 | Required fields missing (base: `domain`; feature: `name`; project: `project`, `domain`, `base`) | Add the missing required field to your JSON |
| V-03 | ERROR | compiler | 1 | `procedures.include` entry has empty `procs` array (`"procs": []`) | Move the file to `files.include` for whole-file inclusion |
| V-04 | WARNING | compiler | 0 | Same file in both `files.include` and `procedures.include` (ERROR in `--strict`) | Remove from one list; full-file include supersedes proc-level |
| V-05 | WARNING | compiler | 0 | Same proc listed in both include and exclude across inputs | Explicit include wins; review if exclude is intentional |
| V-06 | ERROR | compiler | 1 | `flow_actions` entry uses an unsupported `action` value | Use one of: `add_step_before`, `add_step_after`, `add_stage_before`, `add_stage_after`, `remove_step`, `remove_stage`, `load_from`, `replace_step`, `replace_stage` |
| V-07 | ERROR | compiler | 1 | `add_*`, `replace_*`, or `remove_*` references a target that does not exist | Check that the `reference` stage/step exists prior to this action in compilation order |
| V-08 | ERROR | validator | 1 | File in `files.include` does not exist in domain (or `_backup`) | Verify file paths are domain-relative and the file exists |
| V-09 | ERROR | validator | 1 | Proc in `procedures.include` not found in the referenced file | Verify proc name matches a `proc` definition in the file |
| V-10 | ERROR | compiler | 1 | Duplicate stage names after all stage actions are applied | Rename one of the conflicting stages |
| V-11 | ERROR | validator | 1 | Malformed glob pattern in file rules | Fix the glob syntax; supported: `*`, `?`, `**` |
| V-12 | ERROR | compiler | 1 | `@n` suffix where `n` exceeds actual occurrence count for that step string | Reduce `@n` or verify the step appears enough times |
| V-13 | ERROR | cli | 2 | `--project` provided alongside `--base` or `--features` | Use `--project` alone or `--base`/`--features` alone |
| V-14 | ERROR | schema | 1 | Project JSON fails `chopper/project/v1` schema validation | Fix project JSON: requires `$schema`, `project`, `domain`, `base` |
| V-15 | ERROR | validator | 1 | `base` or `features` paths in project JSON cannot be resolved to existing files | Check paths are relative to the domain root (current working directory) |
| V-16 | WARNING | validator | 0 | Glob pattern in `files.include` resolved to zero files (ERROR in `--strict`) | Pattern may be stale or mistyped |
| V-17 | INFO | validator | 0 | Base JSON has no `files`, `procedures`, or `stages` blocks (WARNING in `--strict`) | May be intentional for feature-driven flow; review if draft |
| V-18 | ERROR | compiler | 1 | Two or more selected features have the same `name` field | Rename one feature or remove the duplicate |
| V-19 | WARNING | validator | 0 | Feature JSON `domain` field does not match selected base domain | Feature may be domain-agnostic; verify intended use |

---

## Validation — Phase 2: Post-Trim (V-20 through V-26)

| Code | Severity | Source | Exit | Description | Recovery Hint |
|---|---|---|---|---|---|
| V-20 | ERROR | validator | 1 | Surviving `.tcl` file has brace-matching errors | Edit the file or adjust procs kept to avoid broken syntax |
| V-21 | WARNING | validator | 0 | Surviving proc calls another proc not present in trimmed output or `common/` | Add missing proc to `procedures.include` or accept the dangling reference |
| V-22 | WARNING | validator | 0 | `iproc_source`/`source` references a file that was removed | Add missing file to `files.include` or remove the sourcing call |
| V-23 | WARNING | validator | 0 | F3-generated run file references a step file that was trimmed away | Add step file to `files.include` or remove the step from stage |
| V-24 | WARNING | trimmer | 0 | File went through F2 and lost all proc definitions; survives as blank/comment-only | Expected if only top-level code mattered; review if file should be in `files.include` |
| V-25 | INFO | trimmer | 0 | File survives F2 with only top-level Tcl, no proc definitions | Informational; no action needed |
| V-26 | ERROR | validator | 1 | `options.template_script` resolved path escapes domain root (symlink boundary) or does not exist at execution time | Fix the path or remove the option; skipped in `--dry-run` |

---

## Trace Expansion (TRACE-xx)

| Code | Severity | Source | Exit | Description | Recovery Hint |
|---|---|---|---|---|---|
| TRACE-AMBIG-01 | WARNING | compiler | 0 | Proc call token resolves to multiple canonical procs in the domain | Disambiguate with namespace-qualified name in source or add explicit `procedures.include` |
| TRACE-CROSS-DOMAIN-01 | WARNING | compiler | 0 | No in-domain proc matches after namespace resolution; assumed external | If the proc is needed, add it explicitly or verify it lives in `common/` |
| TRACE-UNRESOLV-01 | WARNING | compiler | 0 | Dynamic or syntactically unresolvable call form (`$cmd`, `eval`, `uplevel`) | Add missing dependency explicitly to `procedures.include` if needed |
| TRACE-CYCLE-01 | WARNING | compiler | 0 | Cycle detected in proc call graph (e.g., A → B → A) | Both procs are included (conservative); review for correctness |

---

## Parser (PARSER-xx / PARSE-xx)

| Code | Severity | Source | Exit | Description | Recovery Hint |
|---|---|---|---|---|---|
| PARSER-DUP-01 | ERROR | parser | 1 | Duplicate proc definition (`short_name`) in the same source file; last wins for index | Remove one definition or rename the proc |
| PARSE-DYNA-01 | WARNING | parser | 0 | Computed proc name (contains `$`, `[`, etc.) — skipped | Cannot be indexed statically; rename to literal if needed |
| PARSE-UNBRACE-01 | ERROR | parser | 1 | Unbalanced braces in file; proc boundaries cannot be determined | Fix brace matching in the Tcl source file |
| PARSE-ENCODING-01 | WARNING | parser | 0 | UTF-8 decode failed; fell back to Latin-1 | Convert file to UTF-8 if possible |
| PARSE-NOBODY-01 | WARNING | parser | 0 | Proc with non-brace body (e.g., quoted body); skipped | Rewrite proc with brace-delimited body |
| PARSE-COMPNS-01 | WARNING | parser | 0 | `namespace eval` with computed name (contains `$`); body NOT parsed for procs | Use literal namespace name if procs inside need indexing |

---

## Notes

- **Exit code 0** means the code does not by itself cause a nonzero exit; warnings are reported but do not fail the run unless `--strict` is active.
- **Exit code 1** means user-visible validation or trim failure.
- **Exit code 2** means CLI usage error.
- Codes with `(ERROR in --strict)` or `(WARNING in --strict)` note the severity escalation behavior.
- Every code constant must be defined in `src/chopper/core/diagnostics.py` before use in implementation.
