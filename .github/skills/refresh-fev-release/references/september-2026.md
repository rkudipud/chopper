# September 2026 Baseline

This is the recorded close-out of the September refresh, not a certificate for files edited afterward. Re-read current inputs and rerun checks for December or any subsequent change.

## Locate The Handoff

The user-supplied September release area was `global_dev/2026.09/final/`, a sibling release area beside the Chopper checkout. Its `verification/README.md` and `verification/DOMAIN_MAP.md` describe the delivered contracts. Ask for the new release area instead of extrapolating a December pathname.

Within that final area:

| Domain | Source/JSON root | Features | Base SLOC | Full SLOC |
|---|---|---:|---:|---:|
| Conformal | `cdns/`, `cdns/jsons/` | 42 | 4858 | 20713 |
| Formality | `snps/`, `snps/jsons/` | 23 | 4398 | 9721 |

There were 70 schema-valid domain JSONs: 44 Conformal and 26 Formality. Successful final dry-runs used Chopper 4.4.3. All-on graphs recorded 277 Conformal and 236 Formality edges; these counts are observations, not acceptance targets.

## Approved Intent To Carry Forward

The user explicitly approved a minimal Conformal RTL-to-gate verification base: keep core comparison, necessary summaries, and pass/fail checks; make additional methodology checks, V2K consistency, telemetry, Synopsys guidance, and testcase packaging selectable. Reconfirm if December changes that business contract. Do not silently reduce it further to recover SLOC headroom.

The 14 added Conformal boundaries were `testcase_extraction`, `rtl_localcopy`, `rtl_dotf_readers`, `gate_dotf_reader`, `rtl_2stage_ctech_reader`, `cfm_analyzer`, `debug_fev`, `eco_presynthesis`, `remove_scan_paranoia`, `select_compare`, `methodology_checks`, `v2k_consistency`, `synopsys_guidance`, and `run_telemetry`.

Formality retained its RTL-to-gate base, with new report control and saved-reference replay behavior. Four features were added: `hip_feedthrough_constraints`, `fm_eco_mui`, `extract_testcase`, and `retime_summary`. Previously unowned helper procs were assigned to base or existing responsibility-based features. Replay was not retained as an empty feature.

The full projects preserve all source assets, including alternative stacks. Existing stacks are F1 assets; F3 generates the stage Tcl scripts. Source code was not edited, and no live trim was performed. June content was design history only, never the source of executable December/September updates.

## Evidence Available In The Release Area

- `verification/verify_domains.py`: reviewed read-only verification helper, parameterized by domain/project paths.
- `verification/run_checks.csh`: tcsh orchestration; it hardcodes September paths and must be inspected/rebound before reuse.
- `verification/cdns.base.json` and `snps.base.json`: measured base limits and rebuilt-file checks.
- `verification/cdns.reconstruction.json` and `snps.reconstruction.json`: full source comparison and single-feature-with-prerequisite cases.
- `verification/cdns.omissions.json` and `snps.omissions.json`: leave-one-out cases with dependent features removed.
- Each domain's `.chopper/`: current dependency graph, manifest/provenance, diagnostics, input snapshots, and trim reports.

Recorded tests covered 65 individual selections and 65 omissions. No missing/extra runtime files, missing procs, or nonblank non-comment literal-line differences remained in all-on reconstruction. The verifier also asserted stage report initialization before use. Vendor tools/designs were not run; exhaustive subsets/permutations and semantic equivalence of arbitrary Tcl data were not established.

## Do Not Reuse

Temporary resynthesis helpers and publishing scripts from the earlier experiment are not supported tools. They produced bad ownership, anchor, and publishing results. Do not rediscover or execute them. Use the final JSONs, durable read-only verifier, and this skill instead.

A one-time exact-file-copy recovery repaired editor-corrupted destination JSONs after explicit user approval. It was not a standing authorization for scripts, recursive copies, or future publishing bypasses.

## December Handoff Fields

Record the new release ID, confirmed source roots, base contract, installed version, source/input hashes, feature ownership changes, canonical recipes, new metrics, exact tested matrix, unresolved dynamic/external dependencies, vendor-run status, and durable rerun commands. Historical counts may increase or decrease; only the agreed base ceiling is a numeric gate.