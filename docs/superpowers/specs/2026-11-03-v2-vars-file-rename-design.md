# v2 mutation: `vars` -> `vars_file`, drop the procs pointer and wrapper

## Intent

The v2 pointer key `procs` reads like the `procs` list inside every
`procedures.include` / `procedures.exclude` entry. v2 is unreleased (shipped
version is 4.5.0), so v2 is changed in place to remove the collision and the
feature that caused it.

## Decisions (user)

1. Rename `vars` -> `vars_file` on `base-v2` and `feature-v2`. No alias, no
   deprecation warning, no v3. `project-v2` is unchanged.
2. Remove the `procs` pointer from base and feature, the generated
   `<flow>_feature_procs.tcl`, and everything that serves only it. The setup
   team removes the executor's load of that file.
3. Base `vars_file`: the flow loads it itself. Chopper treats it as a
   layer-local whole-file include merged through normal R1 / F2 (later
   `files.exclude` or `procedures.exclude` apply; reversals report `VW-21`).
   Never listed in the wrapper.
4. Feature `vars_file`: feeds `<flow>_feature_vars.tcl` (`<flow>` = domain root
   name). Three entries per pointer in project feature order -- authored,
   `tech_` basename, `project_` basename -- each `iproc_source -file <e>
   -optional`, deduplicated first-wins (`VW-29`). Also a layer-local whole-file
   include of the declaring feature.
5. Proc libraries are trimmed only through `procedures.include` /
   `procedures.exclude`, like any F2 file. No new behavior.

## Approaches

- **A. Mutate v2 in place (chosen).** Same schema IDs, rename the key, delete
  the procs path end to end. Mostly removals; no new behavior.
- B. Rename the key, keep procs code unreachable -- rejected: dead code,
  violates YAGNI and the 100% branch-coverage gate.
- C. New v3 -- rejected: v2 never shipped, a third version is pure cost.

## Scope of change

Architecture first, then cascade, then code (project.instructions.md Sec.2).

- **Spec:** `technical_docs/ARCHITECTURE.md` Sec.3.12, FR-57, Sec.3.6 stack `I`
  inputs (vars wrapper only), revision-history row; `DIAGNOSTIC_CODES.md`
  (`VW-30`, `VW-31` return to reserved slots, counts updated; `VE-40`/`VE-42`
  wording if it names procs); `ENGINEERING.md`, `JSON_AUTHORING_GUIDE.md`,
  `user_docs/01_OVERVIEW.md`, `user_docs/02_CLI_GUIDE.md`, `README.md`
  changelog, `tests/TESTING_STRATEGY.md`.
- **Schemas:** `schemas/base-v2.schema.json`, `schemas/feature-v2.schema.json`.
- **Code:** `config/loaders.py`, `config/service.py` (resolver loses the
  `kind` switch), `core/models_config.py` (`vars_file`, drop `procs`,
  `procs_keep`), `core/models_compiler.py`, `compiler/merge_service.py`
  (single wrapper registration), `generators/service.py`,
  `generators/vars_emitter.py`, `core/_diagnostic_registry.py`.
- **Tests:** delete `tests/integration/test_feature_procs.py` and
  `tests/unit/config/test_service_feature_procs.py`; update the vars, sourcing,
  schema, property, stack-emitter and `check_v2` tests.
- **Examples/agent surface:** `examples/16_feature_vars/`,
  `.github/skills/migrate-v1-to-v2/` (SKILL, references, `check_v2.py`),
  `.github/agents/chopper-agent.agent.md`, `AGENTS.md`,
  `.github/instructions/project.instructions.md`.
- **Out of scope:** `dist/`, `graphify-out/`, `presentation/*.html` (generated
  or presentation artifacts; regenerate separately).

## Non-goals / anti-goals

- No proc-level trimming driven by a pointer; no new diagnostic codes; no
  change to v1 output; no change to the wrapper name.

## Builder's calls (mine, for review)

- Version bump to 4.12.0 with matching ARCHITECTURE revision row and README
  changelog entry.
- `VW-30` / `VW-31` become reserved (never shipped) rather than retired.
- Done = `make ci` green (100% line + branch), forbidden-identifier grep clean,
  no remaining `feature_procs` / `"procs":` pointer references outside history
  rows.
