# Failure Playbook

These are observed failure modes from the September refresh, not permission to bypass guardrails.

## Filesystem And Editor

| Symptom or temptation | Required response |
|---|---|
| A preexisting `<domain>_backup` is present | Stop before Chopper execution. Resolve authority with the user; `loc` can also read the backup instead of the apparent source. |
| `final/cdns` or `final/snps` is assumed to contain a nested domain | Inspect the actual layout. Do not invent child directories or trim the parent containing both domains. |
| Work in `/tmp` because it is easy | Use the approved final/user area. Scratch copies, validation helpers, logs, and delivery artifacts must be durable and outside measured source roots. |
| JSON modified by user/formatter since the last read | Reread before editing. Prior approval and prior validation do not authorize overwriting new work. |
| Add File targets an existing JSON | Stop; use an Update patch. September publishing prepended/appended a second document, producing `Extra data` errors. |
| Delete-plus-add is offered as a guaranteed replacement | It was auto-rewritten into an append in this environment. Inspect the applied result; never assume tool success means correct replacement. |
| Editor buffer is valid but disk/report is stale | Compare on-disk content and current input hashes. Resolve dirty-buffer/disk divergence before further edits or testing. |
| Direct editor repair repeatedly corrupts files | Freeze publishing. Name affected paths and verified candidates; ask for a narrow exact-copy recovery exception. Do not keep trying variants or silently switch to scripts. |
| Exact-copy recovery is approved | Copy only the explicitly approved source/destination pairs, verify bytes, parse all destinations, validate schemas, and rerun final-path checks. No glob/recursive JSON restoration. |
| A past session approved exact copies | That was one-time recovery, not a standing waiver of direct edits. |
| Broad source/JSON restoration | Never overwrite authored JSONs or runtime source as collateral. Keep source recovery and JSON authoring separate. |

Before large delegated edits, test the proposed edit mechanism on one small target and immediately validate it. Give each authorized delegate disjoint exact files, a frozen source reference, and a ban on changes outside ownership. A reported obstacle is not an invitation to invent unsafe overwrite methods. The primary agent must verify results independently.

## Source Ownership

- A proc name can remain unchanged while its new body acquires callees. Refresh explicit dependencies from the new body.
- Full source stages plus legacy injections duplicate behavior; whole-stage replacement also removes the anchors those injections expect.
- Regex word intersections count comments and data as calls. Use Chopper parser facts, then manually inspect dynamic command construction and ivar dispatch.
- A source-index entry is not a survivor. Trace visibility never substitutes for explicit selection.
- Complete control-flow blocks matter. A replay `if` in base with its close in `low_power`, or a closing brace left behind after extraction, can pass all-on and fail subsets.
- Initializers are not owned by the nearest feature. `enabled_reports_dofile` must be established before use even without `parallel_batch` or `sequential_const_check`.
- A targeted initialization assertion is necessary but not full dataflow proof: inspect branches, external setup, and dynamic execution.
- Report files are dependencies too. `VerificationFailed` consumed the result file written by the large summary routines; deleting summaries to lower SLOC would have broken pass/fail behavior.
- Optional testcase tools can leave option definitions in setup, but the delivered runtime must not request absent capabilities. Document supported task/ivar choices.
- CTECH/Lite and alternate reader branches can remain in shared source. Ensure the selected recipe supplies the branch it can actually enter; a graph checker alone does not prove that.
- Do not force new runtime behavior to manufacture a feature. An empty replay feature is misleading; source-owned replay may belong in base.
- Stage filenames and scheduler task names are not interchangeable. September's Formality ECO generated filenames needed the `fev_fm_eco_*` names even when task arguments used shorter names.
- Existing utility modules, databases, templates, and non-counted assets still need ownership. Full reconstruction covers more than the SLOC allow-list.

## Ordering And Projects

- Providers before injectors: an action skipped for a missing stage will not be replayed automatically after that stage is introduced.
- Canonical project ordering and dependency closure define supported compositions. Selecting all features, sorting alphabetically, or testing all singletons does not prove arbitrary orders.
- Include/exclude decisions are ordered overlays. Do not hide an all-on reconstruction failure behind a final blanket whole-file include or a catch-all feature.
- Project mode checks the project domain against the physical root basename in the observed Chopper version. September's flat folders needed `cdns`/`snps` project domains; base/features retained their logical names. Recheck this contract in later versions rather than renaming every domain field indiscriminately.
- A helper that only extracts `project.features` and invokes direct base/features mode bypasses project metadata validation. Run actual CLI project mode and pass `project_path` in the initial API run.
- Keep legacy and MUI ECO assets in the full reconstruction. A real run still chooses one scheduler recipe; file coexistence is not simultaneous execution.

## Chopper Verification APIs

The September helper used the following existing services; check their signatures in the installed version rather than copying assumptions into product code:

- `ChopperRunner.run(ctx, command="loc")` with `dry_run=True` returns typed loaded, parsed, manifest, and graph data without a real output rebuild.
- `simulate_trim_in_memory(ctx, loaded=..., parsed=..., manifest=...)` replays real P5 services; it does not run EDA tools.
- `build_loc_report` requires `ctx=` as a keyword argument.
- `validate_post` needs absolute rewritten paths in the simulated filesystem. Relative paths caused silent read skips and false confidence.
- Cached full-domain parsing can make the feature matrix practical, but `parsed.files` has Tcl entries while `loaded.surface_files` also has CSV/stacks. Filter by actual parsed membership, retain the full index, and rerun configuration, compile, trace, build, and validation per case.
- Never reuse that cache after editing source Tcl or changing parser version/options. Rebuild the initial full parse.
- A comparison helper must return failure on missing files/procs, executable/literal differences, local dangling calls, matrix failures, and a breached SLOC threshold. Merely printing failures with exit 0 is not a gate.
- Test the checker itself with a known defect. Verify the root-level CLI path separately from a helper that calls internal APIs.
- Zero SLOC delta is not reconstruction proof. Comment-stripping and whitespace normalization can erase meaningful Tcl string content. Preserve literal line whitespace and inspect multiline data when blank/comment-looking lines are excluded.

## Terminal And Evidence

- Detect tcsh once per session. Use `where`, `set`, `setenv`, `source setup.csh`, and tcsh redirection. The repository `.venv/bin/chopper` worked even when `chopper` and `python` were absent from `PATH`.
- Do not launch an interactive interpreter via a heredoc in the persistent terminal. It can consume later shell commands. Do not feed multiple prompts at once or mix shell dialects.
- Run one-shot checks synchronously. A tool result containing no output, an echoed command, or a fragment of another command is not successful completion.
- In this session some terminal snapshots returned while a command was still running. Avoid queueing more commands into an ambiguous terminal. Prefer a reliable execution ID/notification; if the integration gives none, make one justified process/output-state check, not a polling loop or sleep.
- If a command explicitly moves to background, use its returned execution ID. Never fabricate IDs or call output tools for already completed synchronous commands.
- Capture progress and durable results. For noninteractive runs `tee` helped show and save output, but inspect the JSON `checks_passed` field, raw CLI summary, and run metadata as well as the command status.
- A populated result may belong to an earlier run. Check timestamps/run IDs, current input snapshots, source/input hashes, and the delivery path. After any final edit, refresh affected reports and audit inputs.
- Validate/dry-run audits overwrite `.chopper/`. Old failed path-mismatch logs are historical, not the current completion record. Clearly identify authoritative latest reports.
- Do not finish while a required check is still running. Explicitly state unrun gates and unresolved warnings instead of reporting an old success.

## Scope And Claims

Do not patch Chopper internals, change schemas, change the SLOC backend, suppress warnings by inventing tool-command lists, or modify diagnostic behavior to make a refresh pass. Distinguish configuration mistakes from genuine product bugs; route product issues through the repository's approved reporting process without exposing proprietary code or paths.

For diagnostic meanings, use only the current registry at `technical_docs/DIAGNOSTIC_CODES.md`. This playbook intentionally does not duplicate diagnostic metadata. A warning-bearing successful static run can still have external commands, unresolved dynamic hooks, or untested vendor execution. Report these limits explicitly.