# Chopper Buildout Memory

## Current Focus
- 2026-09-06: GitHub issue #29 fixed and validated; no open implementation work.

## Issue #29
- Escaped carriage returns and line feeds in provenance marker names and sources so every F2/F3 marker remains one physical Tcl comment line.
- Dry-run P6 now generates F3 artifacts in memory and checks generated Tcl brace balance before returning success.
- Added regression tests for multiline marker metadata and malformed generated Tcl during dry-run; affected modules passed (61 tests) and `make check` passed (1623 unit tests).
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

## Next Actions
- Run `make check` or `make ci` before push.
- Push with the repository's GitHub API push workflow if the user asks to sync remote.

## Open Questions
- None.

## Validation Notes
- `make release-cth` smoke test passed with `chopper 4.0.0`.
- Real CTH prompt direct invocation passed after launcher fix.
- Fresh CTH reset via `cth_psetup ... -force` completed; patched bundle installed with `make install-cth WARD=/nfs/site/disks/ddi_r2g_13/rkudipud/global_dev/turn_in/r2g.1278_dev`.
- `make check` passed: 1405 passed, 99.53% coverage.
- `make ci` passed: 1501 passed, 100% coverage.
- `make bundle`, `make release-cth`, and `make install-cth` passed after keeping `schemas/scripts`.
