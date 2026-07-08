---
applyTo: '**'
---

# Chopper (bundled deployment) — agent instructions

These instructions ship inside a deployed **chopper-bundle/**. They tell a
Copilot agent how to drive the bundled, venv-free Chopper executable on an
Intel EC / TFM host. They are intentionally narrower than the development-repo
instructions: the bundle contains the runtime only (no test suite, no dev
tooling, no build system).

## What is in this bundle

| Path | Purpose |
|------|---------|
| `bin/chopper` | The executable. A launcher that runs `src/` + `vendor/` on the host's Python 3.13+. No venv, no `pip install`. |
| `src/` | The Chopper package source. |
| `vendor/` | Runtime dependencies (`jsonschema`, …). |
| `schemas/` | Authoritative base / feature / project JSON schemas. |
| `MANIFEST.txt` | Build metadata (version, build time, build Python). |

## Running Chopper

Always invoke the bundled launcher, never a bare `python`:

```tcsh
./bin/chopper --help
./bin/chopper validate --project jsons/PROJECT.json
./bin/chopper trim --dry-run --base jsons/base.json
./bin/chopper trim --project jsons/PROJECT.json
./bin/chopper loc --project jsons/PROJECT.json
```

The launcher resolves a Python ≥ 3.13 in this order: `$CHOPPER_PYTHON`, then
`/usr/intel/bin/python3.13.2`, then `python3.13` / `python3` / `python` on
`$PATH`. To force an interpreter without rebuilding:

```tcsh
setenv CHOPPER_PYTHON /usr/intel/bin/python3.13.2
```

If the launcher prints "no Python >= 3.13 found", set `CHOPPER_PYTHON` and
retry — exit code 2.

## Response rules

1. The four subcommands are `validate`, `trim`, `loc`, `cleanup`.
   There is no other subcommand. Do not invent flags.
2. Recommend the safe loop: `validate` → `trim --dry-run` → review `.chopper/`
   → `trim` → `cleanup --confirm`. `validate` and `--dry-run` never modify the
   domain.
3. For any diagnostic code, cite it by its token (e.g. `VE-21`) and resolve its
   meaning from the Chopper diagnostic registry — never invent severity or exit
   behaviour from memory.
4. Exit codes: `0` success, `1` errors (or warnings under `--strict`), `2`
   CLI/environment (includes "no Python found"), `3` internal error (writes
   `.chopper/internal-error.log`).
5. Never suggest editing the trimmed domain by hand — re-trim discards it.
   Edits go in the JSON or in `<domain>_backup/`.
