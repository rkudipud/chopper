# Chopper Agent Memory

## Current Focus
- Resynthesize Conformal/Formality F1/F2/F3 JSONs from September production sources under /nfs/site/disks/ddi_r2g_13/rkudipud/global_dev/2026.09/final: cdns is the Conformal domain itself; snps is Formality itself.
- User explicitly confirmed September is authoritative; June /p/hdk/cad/eou_flow_global/2026.06.plus.p8 is reference for modularization intent only. May update September JSONs; no original Tcl changes or live trim planned.
- Goals: working base RTL-to-gate under 5000 Chopper SLOC per domain; all executable assets accounted for; full feature composition reconstructs September; verify valid dependency-ordered subsets.

## Last Completed Work
- Added and wired the refresh-fev-release skill, companion scoped instructions, workflow/gotcha/baseline/acceptance references, and final/verification/NEXT_RELEASE.md. Frontmatter/links passed and 10/10 read-only pressure scenarios passed. This documentation task did not edit or revalidate the user JSONs changed after the previous close-out.
- tcsh verified via echo $shell: /usr/intel/bin/tcsh. Use tcsh only. Chopper available at repo .venv/bin/chopper, version 4.4.3; not on PATH.
- Published September JSONs under final/cdns/jsons (42 features) and final/snps/jsons (23 features); 70 JSON files passed schema validation.
- User explicitly approved Conformal minimal verification base: methodology checks, V2K consistency, telemetry, Synopsys guidance, and testcase extraction are optional features. Required comparison/pass-fail summaries remain in base.
- Actual final base checks: Conformal 4858 SLOC; Formality 4398 SLOC after restoring unconditional report initialization. Both exit 0 with external/source warnings. Full reconstructions measure 20713 and 9721 respectively.
- Both final all-on reconstructions have no missing/extra files, no missing procs, and no nonblank/non-comment line differences, including a whitespace-preserving comparison. Source bytes outside authoring JSON/audits were verified unchanged against analysis copies.
- 65 individual-feature-plus-prerequisite cases and 65 leave-one-out-with-dependents cases passed in-memory static checks. This does not prove every subset/permutation or vendor-tool execution.
- Durable verifier moved to final/verification/verify_domains.py. It never writes source/JSON. final/verification/run_checks.csh records results and regenerates final dry-run audits. No new work should depend on /tmp.
- Project-mode validates physical basename: project domain fields in final are cdns/snps, while base/feature domain labels remain fev_conformal/fev_formality. This correction was tested through actual CLI validation.

## Next Actions
- v1->v2 work (migrate, "is my migration done?", "review my JSONs"): load .github/skills/migrate-v1-to-v2/SKILL.md and grade a whole-folder copy of `.chopper/` with its scripts/check_v2.py. A migration is done only when `--require-adoption` passes with at least one actual `vars_file` pointer; `none`, `schema-only` and `not-applicable` do not prove adoption. No-pointer/no-candidate bundles still pass ordinary review, but strict adoption fails; do not invent pointers to pass. Procedure-hosting files remain F2 selections; there is no proc pointer or generated proc wrapper. `VW-15` on `iproc_source -file ...` steps is a validator false positive (`_SOURCE_CMD_RE` only accepts one argument), not "expected".
- Future release refreshes: the refresh-fev-release skill and fev-release-refresh instructions were removed from this repo; use final/verification/NEXT_RELEASE.md and final/verification/README.md.
- Final verification complete: 44 Conformal JSONs and 26 Formality JSONs valid; base SLOC 4858/4398; 42+23 individual and 42+23 omission cases passed; both final audits record trim/dry-run/exit 0 and input_base.json is byte-identical to the current published base.
- No verification process remained running at close-out. Active deliverables, metadata, reports, and rerun helper are under final; temporary experiments are not used by the delivery.
- Use final/verification/README.md for base contracts, recipe order, static verification limits, and rerun command.

## Open Questions
- Vendor-tool execution tests require suitable project environment; dry-run alone cannot establish runtime equivalence.
- All-on keeps both legacy and MUI ECO stacks; runtime must select the intended scheduler. Reader/task/ivar choices must match delivered features; arbitrary feature permutations are not interchangeable.

## Validation Notes
- ARCHITECTURE.md Sec.5.7 excludes authoring JSON from SLOC; `user_docs/02_CLI_GUIDE.md` (the canonical CLI reference since `technical_docs/CLI_REFERENCE.md` was merged into it) lists the correct counted file types from `core/fs_walk.py`.
- Never run live trim on originals. Never use reserved *_backup names for user snapshots. Preserve user JSONs via reviewable patches, not recursive restoration copies.
- User requested direct manual JSON patches instead of Python resynthesis. Publishing agents misused Add on existing files, creating duplicate JSON documents; delete/add in one patch also misbehaved. User explicitly approved a one-time exact-file copy recovery. All 70 final JSONs were repaired, byte-verified, and parsed afterward. Do not reuse resynthesis scripts or infer permission for future bulk rewrites.
- Verification lessons: call chopper.orchestrator.projection.build_loc_report with ctx keyword (moved from cli/loc_report in 4.11.0); validate_post rewritten paths must be absolute or file reads silently skip. Project metadata must be exercised via project_path, not only extracting feature paths. Cached subset parse contains Tcl only, unlike surface_files which also contains CSV/stacks.
- Source-partition regression: new report initialization must stay in its stage provider, not be grouped into nearby optional parallel_batch/sequential_const_check blocks. Both domains were corrected; durable verifier asserts initialization precedes each fev_run_report use.
## CTH ward domain test (cth2026.09_1278, pesg/2026.09)
- Ward: /nfs/site/disks/ddi_r2g_13/rkudipud/global_dev/cth_ward; drive CTH via `SHELL=/usr/intel/bin/tcsh expect cth_run.exp <script.csh>` (needs pty + tcsh -c; stdin piping skips -x).
- CTH ships chopper 4.5.0 at $ward/global/eouFW/bin/chopper. 12 v1 domains with jsons/; sta_pt base is jsons/sta_pt.json.
- 232-case matrix (validate/dry-run/loc, per-feature, all, reverse-all, projects) in cth_ward/chopper_tests. HEAD 4.11.3 == 4.5.0 on SLOC for every common case.
- 4.5.0 bug (rc=3): literal files.exclude of absent file -> P2 FileNotFoundError (intel/intel_caliber). Fixed by HEAD (now VW-25 + rc=1); CTH needs newer deploy.
- Domain JSON defects: power onepower_reports -> glitch_reports.tcl moved to onepower/glitch_reports.tcl (VE-06); intel/cdns intel_caliber extractfc/duet include absent files (VE-06); lv_pegasus/lv_calibre base excludes of files never included (VE-27); fev_formality read_rtl_dotf_impl replace_step stale anchor (VE-05), read_rtl_dotf_ref @n overflow (VE-10); onenoise feature name has a space.

## fev_formality v1->v2 migration (copy, cth_ward/chopper_tests/fev_formality_v2)
- Phases p2 (flip 29 $schema), p3 (base.json -> jsons/fev_formality.json), p4 (base "vars": "vars.tcl", dropped from files.include) all matched predictions; final --require-adoption PASS, adoption full, 0 unexpected, both recipes (base-only, 27 features).
- Historical pre-mutation v2 evidence: the prior migration used the old vars pointer and had empty generated feature_vars/procs files. Under the current unreleased contract, rename any old vars pointer to `vars_file`; no proc wrapper is generated. Infra-load of the vars wrapper remains unconfirmed.
- Copied ward JSONs are read-only: chmod u+w before Python writes (sed -i works regardless).
- CTH setup -force re-syncs $ward/global: wipes installed chopper and ward JSON edits.
