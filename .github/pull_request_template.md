<!--
Title format: <type>: <what changed> (#<issue>)
  <type> is feat, fix, docs, test, refactor, or chore.
  Example: fix: report a missing procedures.include file as a validation error (#47)
PRs are squash-merged; this title becomes the commit message on main.
-->

Fixes #

## What changed and why

## Checklist

- [ ] Tests or validation checks were run for the touched area.
- [ ] `make ci` passes locally, or the steps in `.github/workflows/ci.yml` were run if `make` is unavailable.
- [ ] New diagnostics, if any, are registered in `technical_docs/DIAGNOSTIC_CODES.md`.
- [ ] User-facing docs were updated when command behavior or outputs changed.
- [ ] Engineering docs were updated when architectural behavior or contracts changed.
- [ ] No out-of-scope features were introduced implicitly through helper code, comments, or stubs.
- [ ] The PR title names the change and its issue (it becomes the commit message on `main`).
