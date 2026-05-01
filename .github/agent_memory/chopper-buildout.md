# Chopper Buildout Agent Memory

## Current Focus

- 2026-05-01 audit + remediation. **Wave A IMPLEMENTED + Wave B reviewed.** Version bumped 0.6.0 → 0.7.0.

## Wave B Verdict (2026-05-01, post-Wave-A review)

- **O2 — DONE.** `_build_short_to_canonical()` helper added to `compiler/merge_service.py`; per-file dict cached once at top of `CompilerService.run()` and threaded into classify + aggregate passes. Collapses `2*S*F` rebuilds to `F`. 136 compiler+integration+golden tests green.
- **O3 — NO-OP (already optimal).** Re-read showed `_resort_by_posix` is called twice at the **end** of `_register_generated_stage_files`, not in a loop. Original audit description was wrong. No change.
- **O4 — NO-OP (already streaming per artifact).** `audit/service.py` writes each artifact independently via `ctx.fs.write_text`. In-memory render cost bounded by ≤1 GB NFR-1. Skipped until profiling pressure justifies.
- **O1, O5, O6 — DEFERRED.** Each is a real refactor warranting its own PR with benchmark + golden-file diff. Documented in IMPROVEMENTS.md §6 with rationale. Not blocking.

## Wave A Completed (2026-05-01)

All decisions from `IMPROVEMENTS.md` absorbed and implemented in a single coordinated change. Validation: **857 unit + 38 integration/golden/property tests pass; ruff clean; mypy clean; 4/4 import contracts kept; docs-gate green.**

- **D1 — `internal-error.log` writer** — new module `src/chopper/audit/internal_error.py`. Writes plain-text crash log with run_id, traceback, diagnostic snapshot, RunConfig, version, platform.
- **D2 — Generic exceptions caught at runner + CLI** — runner's `except ChopperError` extended with a parallel `except Exception` branch (also exit 3 + internal-error.log). New top-level `try/except Exception` in `cli/main.py` for pre-runner failures (exit 1, ctx-less internal-error.log fallback).
- **D3 — Exit-code 4 widened** — `RunResult`, `RunRecord`, `AuditManifest` validators now allow `{0,1,2,3,4}` to align with PE-04's registry exit-code. Schema enum widened to match.
- **D4 — Python 3.11+** — spec §5.12 narrative aligned to "≥ 3.11 (3.13 preferred)". pyproject/ruff/mypy untouched (already 3.11).
- **D5 — PE-04 as Diagnostic** — `mcp/server.py` now constructs `Diagnostic.build("PE-04", ...)` for both per-call and fatal protocol errors via new `_build_pe04()` helper.
- **D6 — `print()` removed** — replaced with `sys.stderr.write(...)`.
- **D7 — Tcl-aware brace counter** — `_brace_delta` rewritten to skip backslash-escapes, `"..."` quoted strings, and full-line `#` comments. Eliminates false-positive class `puts "{"` → VE-16 exit 3.
- **D8 — VW-20 `audit-write-failed`** — registered in DIAGNOSTIC_CODES.md + `_diagnostic_registry.py`; emitted from `audit/service.py` on swallowed OSError. Active code count 70 → 71.
- **D9 — Bare `except: pass` removed** — runner's `finally` audit block now writes `[chopper] internal: audit bundle failed to write: ...` to stderr instead of swallowing silently.
- **SLOC** — `audit/sloc.py` extended with `.py`, `.tcsh`, `.zsh`, `.ksh` (was missing Python entirely). Module docstring documents triple-quote behaviour.

## Files Changed (Wave A)

- `src/chopper/core/models.py` — `InternalError`, internal_error field, exit-code widening.
- `src/chopper/core/_diagnostic_registry.py` — VW-20 entry + header comment.
- `src/chopper/audit/internal_error.py` — **NEW**.
- `src/chopper/audit/service.py` — VW-20 emission.
- `src/chopper/audit/sloc.py` — Python/tcsh/zsh/ksh.
- `src/chopper/orchestrator/runner.py` — generic except, internal_error wiring, finally fix.
- `src/chopper/cli/main.py` — top-level guard.
- `src/chopper/mcp/server.py` — PE-04 Diagnostic + stderr write.
- `src/chopper/validator/functions.py` — Tcl-aware `_brace_delta`.
- `schemas/run-result-v1.schema.json` — exit_code enum widened.
- `technical_docs/DIAGNOSTIC_CODES.md` — VW-20 row + summary counts.
- `technical_docs/chopper_description.md` §5.12 — Python 3.11+ policy.
- `tests/unit/core/test_diagnostics.py` — count 70 → 71.

## Wave B (Deferred)

O1 cache domain walk; O2 cache short_to_canonical; O3 sort-once; O4 stream audit artifacts; O5 split `core/models.py` god-module; O6 split `parser/call_extractor.py`. All approved by user but kept out of the safety-critical fix wave.

---

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
