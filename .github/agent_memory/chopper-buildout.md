# Chopper Buildout Memory

## Current Focus
- 4.11.0 composer consolidation (no behavior change) is verified and committed locally (not pushed). Next candidate work: FD-04 local web GUI over `chopper.app` (vanilla HTML/CSS/JS + stdlib `http.server`; not started), and the pre-existing ex02/ex06 parser crash below.

## 4.11.0 Composer Consolidation (T1-T10)
- One composer: `orchestrator/runner.py` orders phases, gates, and bookkeeping; `default_providers()` builds every phase and `ChopperRunner(providers=...)` swaps any one. Live trim and `chopper loc` share one P5 sequence via `orchestrator/projection.py` (`orchestrator/simulate.py` deleted).
- One source-root rule: `core/layout.source_root` ("read from `<domain>_backup/` if it exists") replaced six copies across config/parser/validator/audit/fs_walk.
- Front-end-neutral application layer `chopper.app` (`domain`, `catalog`, `session`, `trim_stats`, `errors`): returns typed results, raises `AppError(AppIssue(code|None, message, hint, detail))`, never prints/exits/parses argv. CLI (`cli/commands.py`) is a thin adapter with one `_dispatch` multi-domain loop; `cli/domain_lookup.py`, `cli/feature_lookup.py`, `cli/loc_report.py` were moved/folded into `app`.
- import-linter: 5 contracts; layers `cli -> app -> orchestrator -> services -> adapters -> core`; forbidden contract "CLI is a thin adapter over the application layer" needs `allow_indirect_imports = true` (red-green verified).
- Test patch targets moved: `chopper.app.session.{resolve_target, build_loc_report, write_internal_error_log}`, `chopper.app.domain.{Path, resolve_domain}`, `chopper.orchestrator.runner.ChopperRunner.run`, `chopper.cli.commands.{build_trim_stats, render_trim_stats, render_result}`.
- Kept separate on purpose: trim-stats reader (utf-8, `errors="replace"`) vs projection's latin-1 reader -- unifying changes SLOC counts.
- Verification: full suite 2166 passed, 10 skipped, 100.00% line+branch; ruff/format/mypy (87 files)/5 import contracts/diagnostic registry (88)/service signatures (12) green.
- Parity harness lesson: the session-local differential harness (414 CLI steps over every fixture/example) originally put a bare `src/` snapshot on PYTHONPATH with no sibling `schemas/`, so 312/414 steps crashed at P1 and early "0 diffs" results only compared crash paths. Fixed with a preflight (`_schema_dir()` must load; no untracked files in fixtures/examples) and an rc/crash histogram. Corrected run: 0 diffs across 414 steps (rc 0:151, 1:182, 2:54, 3:27); sensitivity check vs the crash-path capture reports 5135 diffs. Smoke-running the CLI against `tests/fixtures/*` leaves an untracked `.chopper/` that contaminates later copies -- delete it.
- Graphify incremental refresh (4.11.0): 44 changed files (35 code AST, 9 docs via 2 semantic agents) + 9 deletions pruned; graph now 7353 nodes, 16269 edges, 363 communities (+822/-611 nodes vs prior). Community ids kept stable with `graphify.cluster.remap_communities_to_previous` against the pre-update graph; old labels reused only where >=50% of a community's nodes overlap its matched old id (275 carried, 88 hand-labeled). Token usage recorded as unknown in `cost.json`.
- Pre-existing bug (exists at 9e152b8, not fixed to keep 1:1): `examples/02_base_procs_only` and `examples/06_base_procs_and_stages` ship only JSON; a `procedures.include` entry naming a missing file passes P1 and crashes the P2 parser (`FileNotFoundError` in `ParserService._read_with_fallback`) with exit 3 instead of a validation diagnostic. Likewise `--tool-commands <missing file>`: `core/tool_commands.load_pool` raises `FileNotFoundError` uncaught by `config/service.py` -> exit 3 instead of a user error.

## V2 Feature Sourcing Verification
- All-v2 runs generate both `<flow>_feature_vars.tcl` and `<flow>_feature_procs.tcl`; base pointers are F1-only, while feature pointers expand into authored/tech_/project_ optional entries. Both paths participate in audit, filesystem-based p4 planning, LoC, P6, and every aggregate-stack record's I inputs. Infrastructure owns sourcing; standalone bodies remain verbatim.
- Added 128 option/version/dry-live/stage-mode combinations, feature order/subsets, all schema-version mixes, strict warning policy, two 500-example properties, and a real-CLI lifecycle for the runnable example 16.
- Fixed default schema-validator discovery, Windows quoting assertions, literal Tcl source-argument escaping, and v2 pointer rejection of directory/dot/drive paths, including invalid components after newlines. Tcl argument cases execute through a real interpreter.
- Final strict suite: 2168 passed, 10 skipped, 100.00% line and branch coverage. Skips: unavailable cloc backend (3), shell fixtures on Windows (2), POSIX mode semantics (5). No Linux/tcsh or vendor-tool runtime certification is implied.
- Ruff lint/format, mypy (83 source files), four import contracts, diagnostic registry, service signatures, and all 35 example JSON validations passed. Onboarding and runtime presentations passed offline Edge checks at 1440x900 and 2048x1320; replaced the onboarding deck's unnecessary Tailwind dependency with its existing native CSS.
- Graphify incremental refresh: 394 files, 7110 nodes, 16362 edges, 360 communities; graph JSON, HTML, and report regenerated. Validated endpoints, hyperedges, zero pending corpus changes, preservation of 5734 unchanged repository nodes and 13884 unchanged edge directions/relations. Schema reference IDs were source-qualified in refresh orchestration to avoid extractor collisions; no global package edits.
- Graphify 0.9.100 reports skill 0.8.41 mismatch; do not silently update global skills. Semantic-agent token usage is unavailable and recorded as unknown, not zero. The retrieval benchmark is heuristic, not measured LLM savings.
- The configured review agent could not start because its model was unavailable. GitNexus remains stale and cannot resolve new symbols; do not interpret UNKNOWN/no-callers results as safety proof.

## Issue #31 (4.9.0, FD-17 adopted)
- Owner approved a base-JSON key `insert_markers` (under `options`, default false) as the master switch for all Sec.3.11 markers (F2 + F3); scope delegated to me -> one switch, standalone stacks never marked.
- Resolver always inserts markers tagged as `_Marker(str)` (keeps block-aware anchoring identical on/off), then a final pass strips them (off / standalone) or `_place_markers` moves pairs to top-level Tcl command boundaries (depth 0, no open quote, no `\` continuation, not above line-1 shebang); content never moves; pairs with no boundary are dropped. This subsumed #30's `_keep_shebang_first`.
- F2: `annotate_procs(..., insert_markers=True)` default at function level; `proc_trim_file` requires the flag; `CompiledManifest.insert_markers` carries it to P5a (generate_stack precedent). Payload escaping `\ " { }` + CR/LF in `marker_pair`.
- Verified in real Tcl 9.0.4 (tkinter) and through the real CLI; full suite 100% coverage. GitNexus detect_changes rates CRITICAL (touches config/compile/trim flows) -- expected for a pipeline-wide option.
- Unreleased 4.8.2 (escaping only) was folded into 4.9.0 in README + ARCH revision history.

## Issue #30 (4.8.1)
- Bug: F3 emitters prepended Intel header + `# Chopper-generated stage:` banner unconditionally, so a `reference_file` stage regenerated in place from a `#!/bin/sh` -> `exec tclsh` bootstrap lost its line-1 shebang and duplicated its own copyright header.
- Fix: `core/header.py::needs_header(path, lines)` -- inject only into `#`-comment types, never above a line-1 `#!`, never on top of a leading-comment copyright notice (`copyright` word + `(c)`/4-digit year). Emitters (`stage_emitter`, standalone `stack_emitter`) write the body verbatim otherwise; aggregate stack stays unconditional. `flow_resolver._keep_shebang_first` moves a shebang preceded only by Sec.3.11 marker lines back to index 0 (single line only -- moving comment blocks breaks `\`-continued Tcl bootstrap comments).
- Docs: ARCH Sec.6.6.1/3.6/3.11 + rev history; JSON guide 2.2/2.3; user_docs 01/03; IMPLEMENTATION P-49; README changelog; pyproject 4.8.1; chopper-agent.agent.md.
- Test vectors: `tests/fixtures/header_domain/` + parametrized `test_needs_header_vectors`; 9 new behavioral tests proven to fail on pre-fix code.
- Gates: ruff/format/mypy/import-linter/docs-gate green; full suite 100% coverage; only failures are 2 pre-existing Windows-only `tests/unit/test_p4_sync_planner.py` cases (`shlex.quote` quotes Windows paths) from HEAD commit bd7e6bf -- unrelated.
- Pre-existing, not fixed: a feature-added `standalone_stack` stage gets Sec.3.11 markers in its `.stack` despite Sec.3.11 saying standalone stacks are never marked.
- GitNexus: re-ran `node .gitnexus/run.cjs analyze` (6276 symbols / 12552 edges / 241 flows); MCP server still served the stale index for impact(), so blast radius came from VS Code usages (LOW: 1 caller each).

## Issue #29
- Escaped carriage returns and line feeds in provenance marker names and sources so every F2/F3 marker remains one physical Tcl comment line.
- Dry-run P6 now generates F3 artifacts in memory and checks generated Tcl brace balance before returning success.
- Added regression tests for multiline marker metadata and malformed generated Tcl during dry-run; affected modules passed (61 tests) and `make check` passed (1623 unit tests).
- Committed and pushed via the Git Data API as `82bb2ab7d483c73f9eede734e83a6412212840a9` (`fix: validate generated Tcl during dry runs`); local `main` is synchronized with `origin/main`.
- GitNexus index is one commit stale. Neither `gitnexus` CLI nor `.gitnexus/run.cjs` is available in this checkout, so graph impact/diff results were lower-bound only; local usage searches confirmed direct callers.

## Last Completed Work
- Patched `scripts/dist/chopper.cth.csh` so CTH installs derive `${workarea}/.venv_cth.ai/bin/python3` from the ward layout before falling back to generic Python.
- Installed `dist/chopper-cth` into `/nfs/site/disks/ddi_r2g_13/rkudipud/global_dev/turn_in/r2g.1278_dev` after CTH setup returned.
- Verified in the real CTH shell: `which chopper` resolves to `.../global/eouFW/bin/chopper`; `chopper --version` prints `chopper 4.0.0`.
- Fresh CTH ward validation passed using normal `chopper` CLI commands: `validate` all copied feature JSONs exit 0, `loc` exit 0, `trim --dry-run` with `fev_fm_rtl2rtl` exit 0, live `trim` with `fev_fm_rtl2rtl` exit 0, post-trim `validate` exit 0.
- Confirmed the prior P5c read-only Tcl failure is fixed: live trim rewrote `default_fm_procs.tcl` without `VE-25`, preserving read-only executable mode (`-r-xr-x--x`).
- Rebuilt fresh CTH ward after `/turn_in` cleanup; installed rebuilt payload; copied Formality JSONs; validated all-feature `validate`, `loc`, `trim --dry-run`, live `trim`, post-trim `validate` all exit 0.
- Packaging fix: keep `schemas/scripts` in `make bundle` and `make release-cth` payloads so tested helper scripts ship with runtime/CTH artifacts.
- Ward-copied pytest gate passed after copying tests for validation only: 1501 passed, 100% coverage against ward `global/common/chopper/src`; removed validation-only `tests/`, `dom`, and `__pycache__` afterward.
- Removed GitNexus repo customization files and obsolete workspace helper config; remaining protocol references are explicit closure/removal records only.
- 4.9.1 cleanup (uncommitted): base `options` now travels as `CompiledManifest.options: BaseOptions` (P5/P6 read switches there; no per-call kwargs); one glob matcher `core.globs.glob_match` (stdlib `PurePath.full_match`, fixes `*`/`?` crossing `/` vs ARCH Sec.6.3.1); one domain walker `core.fs_walk.iter_domain_files` (+ `copy_tree`); feature schema regained `standalone_stack`; dead code removed (`DomainState.hand_edited`, `ProgrammerError`); signature gate now checks `validate_pre`/`validate_post` bidirectionally, scoped to ENGINEERING Sec.9.2; new guards `test_schema::test_every_shipped_chopper_json_is_schema_valid` and `tests/unit/test_doc_links.py`; box-drawing mojibake in 9 docs repaired to ASCII.

## Next Actions
- None.

## Open Questions
- None.

## Validation Notes
- 4.9.1 full gate (Windows): 1848 passed, 100.00% line+branch; only the 2 known Windows-only `test_p4_sync_planner` failures. Signature gate 12/12, registry gate OK, import contracts 4/4.
- `make release-cth` smoke test passed with `chopper 4.0.0`.
- Real CTH prompt direct invocation passed after launcher fix.
- Fresh CTH reset via `cth_psetup ... -force` completed; patched bundle installed with `make install-cth WARD=/nfs/site/disks/ddi_r2g_13/rkudipud/global_dev/turn_in/r2g.1278_dev`.
- `make check` passed: 1405 passed, 99.53% coverage.
- `make ci` passed: 1501 passed, 100% coverage.
- `make bundle`, `make release-cth`, and `make install-cth` passed after keeping `schemas/scripts`.
