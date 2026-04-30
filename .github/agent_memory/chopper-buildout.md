# Chopper Buildout Agent Memory

## Current Focus

- None active. Last task closed: Option A (P2 full-domain proc index) — landed and documented.

## Last Completed Work (2026-04-26)

**P2 full-domain proc index (Option A):**

- **Model.** `src/chopper/core/models.py::ParseResult.__post_init__` relaxed from `set(files.procs) == set(index)` to `set(files.procs) ⊆ set(index)`. The `files` view stays the surfaced subset (what the compiler operates on); `index` is now the full-domain canonical-name map (what P4 trace consults). Same-instance check uses `from_files.items()` so identity equality still holds for entries present in both.
- **Parser.** `src/chopper/parser/service.py::ParserService.run` split into:
  - **Phase 2a — surface parse.** Iterates `loaded.surface_files`, emits `PE-*` / `PW-*` / `PI-*` via `ctx.diag`, populates both `parsed_files` and `index`.
  - **Phase 2b — full-domain harvest.** New `_enumerate_domain_tcl(ctx)` BFS via `ctx.fs.list/stat/exists` (excludes `.chopper/`, returns sorted `.tcl` rel paths). Non-surfaced files parsed silently through `_noop_diagnostic` and merged via `index.setdefault(...)` so surface entries always win on canonical-name collisions.
  - `_parse_one(ctx, path, *, emit_diagnostics=True)` and `_read_with_fallback(ctx, path, sink)` updated to take an explicit sink argument.
- **Tests.**
  - `tests/unit/core/test_models.py`: invariant tests updated for the relaxed model (extra `index` keys now positively allowed).
  - `tests/integration/test_cli_e2e.py::TestFullDomainProcIndex`: two new integration tests pin the contract — `test_trace_resolves_callee_in_non_surfaced_file` (dry-run; asserts resolved edge into `helper.tcl::bar` and absence of `TW-02`) and `test_non_surfaced_file_is_not_copied` (live trim; asserts `helper.tcl` is not in trimmed output).
- **Docs.** `technical_docs/chopper_description.md` §5.2 pipeline diagram, §5.2.1 P2 narrative, and §5.4.1 Step 2 code block updated. Revision-history row added (2026-04-26).
- **Validation.** Full regression: **880 passed, 2 skipped, 0 failed** (17.60s). The two skips are the `gh issue create` `tests/unit/scripts/` cases that require a `#!/bin/sh` stub and skip on Windows; they pass on Linux/macOS CI.

## Key Architectural Invariants (verified this pass)

- **Critical Principle #7** holds: trace is reporting-only. Full-domain index makes `dependency_graph.json` truthful (resolved edge → actual `defined_in`) but never copies a traced-only proc.
- **Domain boundary respected.** Phase 2b walk via `ctx.fs` rooted at `domain_root`, excludes `.chopper/`; files outside `domain_root` never read.
- **Determinism preserved.** `_enumerate_domain_tcl` returns sorted list; `setdefault` makes surface-vs-harvest collision behaviour deterministic (surface always wins).
- **Compiler unaffected.** Compiler reads only `parsed.files`; the wider `index` does not perturb F1/F2/F3 decisions.

## Next Actions

- None pending. Await next task.

## Open Questions

- None.

## Validation Notes

- Pre-existing 7 `tests/unit/scripts/` failures fixed: 5 via path correction (`scripts/*.py` → `schemas/scripts/*.py`, the canonical post-`json_kit/`-dissolution location), 2 marked `@pytest.mark.skipif(sys.platform == "win32")` because their fixture is a `#!/bin/sh` `gh` stub.
- Version bumped 0.5.0 → 0.5.2 in `pyproject.toml`. README changelog has a 0.5.2 entry covering Option A + the test cleanup. (0.5.1 had been documented in README without a corresponding pyproject bump; 0.5.2 reconciles.)
