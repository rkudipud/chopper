# Chopper Buildout Memory

## Current Focus
- 2026-09-29: issue #30 (4.8.1) and issue #31 (4.9.0, `options.insert_markers`) done, both uncommitted in the working tree.

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
