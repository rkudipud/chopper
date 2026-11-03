# check_v2.py reference

`scripts/check_v2.py` grades one `.chopper/` folder (from `chopper validate` or `chopper trim [--dry-run]`). It is deterministic, read-only and stdlib-only. Same input gives the same report, byte for byte.

```text
python .github/skills/migrate-v1-to-v2/scripts/check_v2.py AUDIT [--baseline V1_AUDIT] [--require-adoption] [--json]
```

- `AUDIT`: a `.chopper/` folder, or a **whole-folder copy** of one. The checker needs `chopper_run.json`, `input_*.json`, `compiled_manifest.json`, `dependency_graph.json`, `diagnostics.json`, `files_kept.txt` and `p4_commands.txt`.
- The domain source must still exist at `domain_path` (or `backup_path` after a trim). The checker reads it to count procs, find files, and spot variant files.
- Exit code: 0 when every gate passes or is skipped, 1 otherwise. The text report ends with `RESULT: PASS` or `RESULT: FAIL`.

## Gate

| Check | Fails when | Skipped when |
| --- | --- | --- |
| `run-ok` | Chopper's exit code is not 0, or any error diagnostic was emitted | never |
| `one-version` | the selected project, base and features mix v1 and v2 (`VE-41`) | never |
| `pointer-targets` | a `vars`/`procs` pointer names a missing file (`VW-27`/`VW-30`); its three lines load nothing | v1 run |
| `generated-files` | either generated file is not `generated` in the manifest, not in `files_kept.txt`, or has no `p4 add`/`p4 edit` line | v1 run, or the run stopped before compiling |
| `generated-content` | after a live trim, a generated file's `iproc_source` lines differ from the preview | dry-run, v1, or a failed run |
| `baseline-delta` | any change against `--baseline` is classed `unexpected` | no `--baseline` |
| `adoption` | `--require-adoption` is set and the run is not v2 or has no actual `vars`/`procs` pointer, regardless of candidates | flag not set (the level is still reported) |

## Adoption levels

| Level | Meaning |
| --- | --- |
| `none` | v1 run. |
| `schema-only` | v2, but no pointer is used even though candidates exist. **This is not a finished migration:** the output is the same as v1 plus two empty generated files. |
| `partial` | At least one pointer is in use; candidates remain. |
| `full` | Pointers are in use and no candidates remain. |
| `not-applicable` | v2 with no pointers and no candidates detected. Valid for an ordinary review, but fails `--require-adoption`. |

Strict adoption requires at least one actual base or feature `vars`/`procs` pointer. Only `partial` and `full` can pass it; `none`, `schema-only` and `not-applicable` cannot. All other gates still apply, including pointer-target validation. If no suitable pointer exists, report schema compatibility without claiming v2 adoption; do not invent a pointer just to pass.

A **candidate** is a vars/procs file that a pointer could take over **without changing the trim**:

- **Feature:** a literal `files.include` of `*vars.tcl` / `*procs.tcl` (not `tech_`/`project_`), or a `procedures.include` entry that already lists every proc defined in that `*procs.tcl`.
- **Base:** the same, for files named exactly `vars.tcl` / `procs.tcl`.

A procs file that is trimmed at proc level is never a candidate: a pointer would copy it whole.

## Delta classes (with `--baseline`)

The facts are the same ones `compare_manifests.py` diffs: per-file treatment and surviving procs, the surviving-proc set, stage steps and inputs, kept paths, p4 lines, and diagnostic codes.

| Class | Rows |
| --- | --- |
| `expected` | the generated files' `file`/`kept`/`p4 add` rows; diagnostics removed or reduced; proc-trim → full-copy with the identical proc set |
| `review` | pointer targets or variants newly kept; proc-trim → full-copy that **brings procs back** (the note names them); `+`/`- proc`; changed stages; `+ diag VW-28`; new info codes |
| `unexpected` | a file no longer kept or no longer in the output; a new `exclude_file_list` path; any new or increased warning or error other than `VW-28` |

Explain every `review` row to the user. An `unexpected` row fails the gate, so stop and fix it.

## Suggestions

Each suggestion has a `level` (`fix` → `improve` → `review`), a `target` (`base`, `project`, `feature:<name>` or a JSON path), the evidence in `message`, and an exact `edit`. Apply only what the user approves, then re-run the checker.

| Slug | Level | Evidence | Edit |
| --- | --- | --- | --- |
| `unflipped-json` | fix (mixed run) / improve | a layer is still `-v1` | flip `$schema` |
| `missing-pointer` | fix | the pointer file doesn't exist | the closest existing path |
| `procs-pointer-proc-trim` | fix | the procs pointer reverts a proc-level trim (`VW-09`) | drop the pointer, or pointer + `procedures.exclude` of the returned procs |
| `double-sourcing-step` | fix | a step sources a pointer file again after startup | remove the step (ask about the load point first) |
| `traced-callee-dropped` | fix | a kept proc calls a traced-only proc (`VW-05`) | add the callee to `procedures.include` |
| `project-outside-jsons` | fix | a selected JSON in the domain but outside `jsons/` is in `exclude_file_list` | move it under `jsons/` |
| `pointer-candidate` | improve | see the candidate definition above | add the pointer and remove the now-redundant include |
| `redundant-pointer-include` | improve | `files.include`/`procedures.include` repeats what the pointer keeps | remove the include |
| `manual-variant-include` | improve | `files.include` lists a `tech_`/`project_` variant of the pointer | remove it |
| `base-name` | improve | the base JSON isn't `jsons/<flow>.json` (`VW-28` on v2) | `p4 move`, then update `base` |
| `stale-exclude` | improve | a literal `files.exclude` path doesn't exist (`VW-25`) | remove it |
| `missing-description` | improve | a base or feature has no `description` | add one line |
| `file-and-proc-model` | improve | `VW-09` on a non-pointer file | per the diagnostic's hint |
| `dormant-variant` | review | a `tech_`/`project_` variant exists and becomes (or already is) sourced after the feature file, overriding its values | confirm with the user; no JSON edit |
| `newly-sourced` | review | with `--baseline`: nothing in the baseline (no stage step, no other kept Tcl file) mentions a feature pointer's file, so it now starts loading at startup. A feature `pointer-candidate` carries the same warning ("Nothing references it today") before the pointer is added | confirm it should load; otherwise drop the pointer and keep the file with `files.include` |
| `step-source-form` | review | `VW-15` names `iproc_source`/`source` because a step uses the `-file` form | delete the step if the file becomes a pointer; otherwise list the command in a `--tool-commands` file |
| `orphan-json` | review | a JSON under `jsons/` is not selected (flagged if its version differs, which would give `VE-41` later) | flip, select or delete it |
| `shared-pointer` | review | two features point at the same entry (`VW-29`/`VW-31`) | keep one owner |

The checker is a skill tool, not a Chopper command. Chopper's own diagnostics stay the source of truth. The checker only cites them, combines them with the JSON, and turns them into edits.
