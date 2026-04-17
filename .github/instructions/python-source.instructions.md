---
applyTo: "src/**/*.py"
description: "Python source code conventions for chopper library modules. Use when: editing any Python file under src/"
---

## Environment

Activate venv first: `source setup.sh` (or `source .venv/bin/activate` if already set up).

## Conventions

- All public functions require type hints (`mypy --strict`)
- Use `pathlib.Path` for file paths — never raw `str`
- Use `structlog` for logging — never bare `print()`
- Import shared models from `chopper.core.models` — do not duplicate dataclasses
- Import errors from `chopper.core.errors` — do not define new exception classes outside `core/`
- Diagnostic codes must be registered in `docs/DIAGNOSTIC_CODES.md` **before** adding constants to `core/diagnostics.py`
- Internal modules (parser, tracer) emit diagnostics via `DiagnosticCollector` callback, not by returning them
- Service-level modules use `ProgressSink` for diagnostic emission and progress reporting

## Doc-Driven Development

**Before writing code:** Read the module's spec doc (see `copilot-instructions.md` Module Reference table) and `docs/IMPLEMENTATION_PITFALLS_GUIDE.md` for relevant pitfalls.

**During implementation:** If you discover a spec gap, update the spec doc. If you add a diagnostic code, register it in `docs/DIAGNOSTIC_CODES.md` first. If you change a public API, update all references in `copilot-instructions.md`, `docs/ACTION_PLAN.md`, and `docs/DEVELOPER_KICKOFF.md`.

**After implementation:** Update `docs/ENGINEERING_HANDOFF_CHECKLIST.md` (check off items) and `docs/ACTION_PLAN.md` (mark tasks done). Register any new test fixtures in `tests/FIXTURE_CATALOG.md`.

## Key References

- Architecture: `docs/ARCHITECTURE.md`
- Requirements: `docs/TECHNICAL_REQUIREMENTS.md`
- Parser spec: `docs/TCL_PARSER_SPEC.md`
- Diagnostic registry: `docs/DIAGNOSTIC_CODES.md`
- Pitfalls: `docs/IMPLEMENTATION_PITFALLS_GUIDE.md`
- JSON schemas: `schemas/`

## Validation

After editing, run: `make check` (lint + format + type-check + unit tests)
