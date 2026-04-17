---
applyTo: "tests/**/*.py"
description: "Test conventions for chopper project. Use when: writing or editing test files"
---

## Environment

Activate venv first: `source setup.sh` (or `source .venv/bin/activate` if already set up).

## Test Layers

- `tests/unit/` — Fast, isolated, no filesystem side effects beyond `tmp_path`
- `tests/integration/` — Full workflows using `ChopperRunner` harness and mini-domain fixtures
- `tests/golden/` — Output comparison using `pytest-regressions`
- `tests/property/` — `hypothesis`-based invariant tests (`max_examples=500`)

## Conventions

- One test module per source module: `test_parser.py` ↔ `parser/`
- Use fixtures from `tests/fixtures/` — do not recreate domain structures inline
- Use `tmp_path` for any filesystem writes
- Coverage threshold: 78% line (branch coverage tracked)
- Register new fixtures in `tests/FIXTURE_CATALOG.md`

## Doc-Driven Testing

**Before writing tests:** Read `tests/FIXTURE_CATALOG.md` for pre-built test data. Read the module spec for expected behavior and edge cases. Read `docs/DIAGNOSTIC_CODES.md` for diagnostic codes your tests should verify.

**After writing tests:** Update `docs/ENGINEERING_HANDOFF_CHECKLIST.md` to check off test coverage items. Register any new fixtures in `tests/FIXTURE_CATALOG.md`. Update `docs/ACTION_PLAN.md` if completing a sprint task.

## Fixture Catalog

See `tests/FIXTURE_CATALOG.md` for the full inventory of pre-built test fixtures.

## Validation

After editing tests, run: `make test-unit` (fast) or `make ci` (full suite)
