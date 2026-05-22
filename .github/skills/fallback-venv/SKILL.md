---
name: fallback-venv
description: 'Create a working Python venv in /tmp when the repo checkout is owned by another user or your home directory is over quota, so make check/ci can still run.'
---

# Fallback Venv (Shared Disk / Foreign-Owned Checkout)

Use this when `source setup.csh` (or `setup.sh`) fails because:

- The repo directory is owned by another user (`drwxr-s---`), so `.venv/` cannot be created in-tree, **or**
- Your `$HOME` is over quota and `pip install` aborts with `OSError: [Errno 122] Disk quota exceeded`, **or**
- `git pull` in `setup.csh` fails with `Permission denied` on `.git/FETCH_HEAD`.

`make check` / `make ci` still need `pytest`, `ruff`, `mypy`, etc. The fix is a venv on a writable, roomy filesystem (`/tmp` on the build host) — **not** in `$HOME` and **not** in the repo.

## Detection (tcsh — PRIMARY)

```tcsh
# 1. Repo writable by me?
ls -ld $cwd                          # look for group/other write perms
# 2. Home quota OK?
df -h ~                              # check Avail
# 3. /tmp roomy?
df -h /tmp                           # need ~1 GB free
```

If repo is foreign-owned OR home is tight, skip `setup.csh` and use the steps below.

## Procedure (tcsh)

```tcsh
# Pick the project's required interpreter. For Chopper:
set PY = /usr/intel/bin/python3.13.2
set VENV = /tmp/chopper_venv_${USER}

# Wipe any half-built venv from a previous failed run
rm -rf $VENV

# Create + activate
$PY -m venv $VENV
source $VENV/bin/activate.csh
rehash                               # tcsh: refresh command hash so pytest/ruff resolve

# Install dev extras from the repo (editable)
cd /path/to/chopper
pip install -e ".[dev]"

# Verify
which pytest ruff mypy               # all three must resolve under $VENV/bin
```

## Procedure (bash/zsh fallback)

```bash
PY=/usr/intel/bin/python3.13.2
VENV=/tmp/chopper_venv_$USER
rm -rf "$VENV"
"$PY" -m venv "$VENV"
source "$VENV/bin/activate"
cd /path/to/chopper
pip install -e ".[dev]"
which pytest ruff mypy
```

## Run the Gate

```tcsh
cd /path/to/chopper
make ci |& tail -200                 # tcsh uses |& not 2>&1 |
echo "exit=$status"
```

A clean run ends with `============================ N passed in Xs ============================` and `exit=0`.

## Re-Activation in Later Sessions

The venv persists at `/tmp/chopper_venv_${USER}` until the host reboots or `/tmp` is reaped. On a new shell:

```tcsh
source /tmp/chopper_venv_${USER}/bin/activate.csh
rehash
```

If `activate.csh` is missing, the venv was reaped — recreate it with the procedure above.

## Gotchas

- **tcsh redirection**: use `cmd |& tail` (not `cmd 2>&1 | tail`). Plain `>&` works, `2>&1` does not.
- **`rehash`** is required in tcsh after creating or activating a venv, or `which pytest` will report `Command not found.` even though it exists in `$PATH`.
- Do **not** edit `setup.csh` to point at `/tmp` — the script is shared infrastructure for the repo owner. The fallback venv is a per-user workaround that lives outside the repo.
- Do **not** commit anything from this procedure. It produces no repo changes; it only enables the gate to run.
- If `pip install` still fails on `/tmp` (rare), check `df -h /tmp` and try `/tmp/$USER/chopper_venv` on a different shared scratch disk.

## When to Tell the User

Mention it once, briefly, when reporting test results — so they know why the standard `source setup.csh` path was skipped. Example:

> Used a fallback venv at `/tmp/chopper_venv_${USER}` because the checkout is owned by another user and `setup.csh` couldn't create `.venv` in-tree.
