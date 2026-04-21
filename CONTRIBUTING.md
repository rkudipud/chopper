# Contributing to Chopper v2

This guide describes how to add, modify, or replace functionality in Chopper. It complements (does not replace) [`.github/instructions/project.instructions.md`](.github/instructions/project.instructions.md) and the authoritative specs in [`docs/`](docs/).

**Scope lock applies to every contribution.** Before writing any code, re-read [`.github/instructions/project.instructions.md`](.github/instructions/project.instructions.md) §1 ("Closed Decisions — Do Not Reintroduce"). The bible ([`docs/chopper_description.md`](docs/chopper_description.md)) is the only document that can add a capability. All subordinate docs and source code cascade from it.

---

## 1. Development Setup

See [`README.md`](README.md) for platform-specific setup instructions (`setup.csh` for tcsh primary, `setup.ps1` for Windows PowerShell, `setup.sh` for bash/zsh fallback). Run `make install-dev` after activating the venv.

**Pre-commit gate:**

```bash
make check    # lint + format-check + type-check + unit tests (fast)
make ci       # full gate: all code quality + all test suites (pre-push)
```

---

## 2. Adding or Replacing a Feature

This is what "isolated feature development" looks like in practice. The rules follow from the architecture contracts in [`docs/ARCHITECTURE_PLAN.md`](docs/ARCHITECTURE_PLAN.md) §9–§10.

### 2.1 Add a brand-new service (rare)

1. Decide which phase the feature belongs to. If it does not fit the 7 phases defined in [`docs/chopper_description.md`](docs/chopper_description.md), revisit the design with the bible before coding.
2. Create `src/chopper/<package>/service.py` with a class exposing `run(ctx, ...) -> Result`.
3. Declare new result dataclasses in `src/chopper/core/models.py` as frozen dataclasses.
4. Register any new diagnostic codes in [`docs/DIAGNOSTIC_CODES.md`](docs/DIAGNOSTIC_CODES.md) before emitting them (take the lowest available reserved slot in the correct `<FAMILY><SEV>` band; never renumber existing codes).
5. Wire the service into `src/chopper/orchestrator/runner.py` at the correct phase boundary.
6. Write unit tests under `tests/unit/<package>/` using `make_test_context()` for the port layer.
7. Add an integration fixture under `tests/fixtures/` and an acceptance test under `tests/integration/`.
8. Add a golden snapshot for any new public JSON shape (see [`tests/GOLDEN_FILE_GUIDE.md`](tests/GOLDEN_FILE_GUIDE.md)).
9. Run `make check` then `make ci` before pushing.

### 2.2 Rewrite an existing service end-to-end

1. Keep the `run(...)` signature and result dataclass identical.
2. Delete the module's internals; re-implement behind the same class.
3. Run the service's unit tests — they exercise the port-adapter boundary, so a correct rewrite passes unchanged.
4. Run golden snapshots — these validate that user-visible JSON shapes did not drift.
5. If a signature change is truly required, treat it as a breaking change: update the orchestrator wiring in `runner.py`, every affected service test, and any golden snapshots that bind the old shape — all in the same commit. There is no separate version number to bump; the commit is the contract change.

### 2.3 Add a new diagnostic code

1. Open [`docs/DIAGNOSTIC_CODES.md`](docs/DIAGNOSTIC_CODES.md) and take the lowest available reserved slot in the correct `<FAMILY><SEV>` band.
2. Fill in the registry row (code, slug, phase, source, exit, description, hint).
3. Add a matching constant in `src/chopper/core/diagnostics.py`.
4. Emit it from the owning service only via `ctx.diag.emit(...)` — never `print()`, never a direct `raise` for user-facing failures.
5. Reference it by **code only** in other docs and tests — never paraphrase.

### 2.4 Add a new adapter

Adapters implement a port Protocol from `src/chopper/core/protocols.py`. There are three ports: `FileSystemPort`, `DiagnosticSink`, `ProgressSink`.

1. Create `src/chopper/adapters/<port>_<variant>.py` (for example, `progress_silent.py`).
2. Implement the port Protocol — no inheritance required (structural typing).
3. Wire selection into `cli/main.py` (based on flags) or into test harnesses.
4. No changes to services, orchestrator, or `core/` — that is the whole point of adapters.

Clock / serialization / audit-storage / rendering are **not** ports (see [`docs/DAY0_REVIEW.md`](docs/DAY0_REVIEW.md) A2–A5). They are direct calls to stdlib (`datetime.now`), plain helpers (`core/serialization.dump_model`), direct `ctx.fs` writes, or CLI-local `rich` calls respectively.

---

## 3. Hard Rules (Enforced by CI)

These rules are enforced by `import-linter`, `ruff`, `mypy`, and the diagnostic registry:

1. **Stage discipline.** Stage N may not import from Stage N+1. `core/` imports nothing from siblings. Services import only from `core/`. `orchestrator/` imports from `core/` + every service. `cli/` imports from `core/` + `orchestrator/`.
2. **No inter-service imports.** `compiler/` never imports from `parser/`; both import only from `core/models.py`.
3. **All I/O through ports.** Services call `ctx.fs.read_text(path)`, never `path.read_text()` or `shutil.*` or `os.*` directly.
4. **Frozen dataclasses across boundaries.** Every public return type is `@dataclass(frozen=True)`.
5. **Diagnostics are the only user-facing channel.** No `print()` in library code; no user-facing `raise`.
6. **Diagnostic codes are the API contract.** Adding a code requires a registry edit in [`docs/DIAGNOSTIC_CODES.md`](docs/DIAGNOSTIC_CODES.md) before use.
7. **Determinism for user data.** Every `Mapping` / `set` / `frozenset` that crosses a service boundary and represents user data is sorted on a documented key before emission. Golden tests enforce this.
8. **`ctx` bindings are stable.** A service must not try to swap or reassign ports on `ctx`.

---

## 4. Scope Lock — Forbidden Additions

The following concepts are permanently out of scope. Any PR that introduces them is rejected at review without discussion. See [`.github/instructions/project.instructions.md`](.github/instructions/project.instructions.md) §1 and [`docs/ARCHITECTURE_PLAN.md`](docs/ARCHITECTURE_PLAN.md) §7 + §16 for rationale.

| Forbidden | Why not |
|---|---|
| `PluginHost`, `plugins/`, observer fan-out, entry-point discovery | Q1 closed — no extensibility in v1 |
| `MCPProgressBridge`, `mcp_server/`, `adapters/mcp_*.py`, any MCP client code | Q1 closed — no network surface |
| `advisor/`, LLM-powered JSON proposals | Q1 closed — no AI integration |
| `LockPort`, `.chopper/.lock`, stale-lock recovery, `fcntl` / `msvcrt` logic | Q3 closed — single-user, single-process tool |
| `--preserve-hand-edits`, `.chopper/hand_edits/`, hand-edit stash | Q2 closed — user commits or stashes manually |
| `chopper scan` subcommand, scan-mode | Only `validate`, `trim`, `cleanup` exist |
| Severity-rewriting `--strict` | `--strict` is exit-code-only; never changes `Diagnostic.severity` |
| `X*` diagnostic family (`XE-*`, `XW-*`, `XI-*`) | Reserved for plugin codes that do not and will not exist |
| Thread pools, `asyncio`, `multiprocessing`, background workers | Single-threaded, period (see [`docs/ARCHITECTURE_PLAN.md`](docs/ARCHITECTURE_PLAN.md) §11) |
| HTTP server, IPC, message bus, daemon mode | Local CLI only |

If you catch yourself writing code for any of the above, stop. File an `FD-xx` stub in [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](docs/FUTURE_PLANNED_DEVELOPMENTS.md) stating what the idea is, why it was considered, and why it is not in v1. Do **not** implement it. Do **not** stub it. Do **not** reserve a namespace for it.

---

## 5. Documentation Conventions

See [`.github/instructions/project.instructions.md`](.github/instructions/project.instructions.md) "Editing Conventions" for the authoritative rules. Summary:

- **No addendums.** Edit in place. If a document is out of date, update it directly — do not append "Clarifications" sections at the bottom.
- **Cascading updates.** When content changes in one document, update every related reference in the same pass. A change is complete only when every cross-reference is consistent.
- **Single source of truth.** [`docs/chopper_description.md`](docs/chopper_description.md) (the bible) is the only document that can add a capability. Every other document is subordinate and must yield when it disagrees with the bible.
- **Reference diagnostic codes by identifier.** Outside [`docs/DIAGNOSTIC_CODES.md`](docs/DIAGNOSTIC_CODES.md), use the code token (`VE-06`, `PW-11`) — never paraphrase the description.

---

## 6. Pull Request Checklist

Before opening a PR:

- [ ] `make check` passes (lint + type-check + unit tests).
- [ ] `make ci` passes locally (full test suites).
- [ ] New diagnostic codes registered in [`docs/DIAGNOSTIC_CODES.md`](docs/DIAGNOSTIC_CODES.md) and constant declared in `src/chopper/core/diagnostics.py`.
- [ ] Golden snapshots updated for any new public JSON shape; snapshot changes reviewed deliberately (not blindly regenerated).
- [ ] Coverage gates satisfied: parser ≥ 85%, compiler ≥ 80%, trimmer ≥ 80%, overall ≥ 78%.
- [ ] No new cross-package imports that violate the stage-discipline rule; `import-linter` clean.
- [ ] No `print()` or user-facing `raise` added to library code.
- [ ] If the PR touches anything on the "Forbidden Additions" list (§4 above), it is instead an `FD-xx` entry in [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](docs/FUTURE_PLANNED_DEVELOPMENTS.md).
- [ ] Every doc that references the changed behavior is updated in the same PR (no addendums; cascade in place).
