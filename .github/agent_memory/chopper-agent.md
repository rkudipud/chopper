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
- Future release refreshes: load .github/skills/refresh-fev-release/SKILL.md and .github/instructions/fev-release-refresh.instructions.md. Detailed workflow, gotchas, historical baseline, and pressure scenarios are linked there; final/verification/NEXT_RELEASE.md is the release-area entry point.
- Final verification complete: 44 Conformal JSONs and 26 Formality JSONs valid; base SLOC 4858/4398; 42+23 individual and 42+23 omission cases passed; both final audits record trim/dry-run/exit 0 and input_base.json is byte-identical to the current published base.
- No verification process remained running at close-out. Active deliverables, metadata, reports, and rerun helper are under final; temporary experiments are not used by the delivery.
- Use final/verification/README.md for base contracts, recipe order, static verification limits, and rerun command.

## Open Questions
- Vendor-tool execution tests require suitable project environment; dry-run alone cannot establish runtime equivalence.
- All-on keeps both legacy and MUI ECO stacks; runtime must select the intended scheduler. Reader/task/ivar choices must match delivered features; arbitrary feature permutations are not interchangeable.

## Validation Notes
- ARCHITECTURE.md Sec.5.7 excludes authoring JSON from SLOC; CLI_REFERENCE.md counted-file-types section is stale and incorrectly includes it.
- Never run live trim on originals. Never use reserved *_backup names for user snapshots. Preserve user JSONs via reviewable patches, not recursive restoration copies.
- User requested direct manual JSON patches instead of Python resynthesis. Publishing agents misused Add on existing files, creating duplicate JSON documents; delete/add in one patch also misbehaved. User explicitly approved a one-time exact-file copy recovery. All 70 final JSONs were repaired, byte-verified, and parsed afterward. Do not reuse resynthesis scripts or infer permission for future bulk rewrites.
- Verification lessons: call build_loc_report with ctx keyword; validate_post rewritten paths must be absolute or file reads silently skip. Project metadata must be exercised via project_path, not only extracting feature paths. Cached subset parse contains Tcl only, unlike surface_files which also contains CSV/stacks.
- Source-partition regression: new report initialization must stay in its stage provider, not be grouped into nearby optional parallel_batch/sequential_const_check blocks. Both domains were corrected; durable verifier asserts initialization precedes each fev_run_report use.