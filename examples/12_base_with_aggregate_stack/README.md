# Example 12 — Aggregate scheduler stack (`options.generate_stack: true`)

Demonstrates the 3.3.0 aggregate stack-file contract.

**Inputs:** [jsons/base.json](jsons/base.json) declares three stages — `setup`,
`verify`, `promote` — and turns on `options.generate_stack`.

**Generated outputs (under `<domain_root>/`):**

```text
setup.tcl
verify.tcl
promote.tcl
my_domain.stack          # aggregate, one record per stage
```

There is **no** `setup.stack` / `verify.stack` / `promote.stack`; per-stage
stacks are emitted only when a stage opts in with `standalone_stack: true`
(see example 13).

**Aggregate file shape (`my_domain.stack`):**

```text
<Intel header>

# Chopper-generated stack: setup
N setup
J -xt vw my_shell -B BLOCK -T setup
L 0
D

# Chopper-generated stack: verify
N verify
J -xt vw my_shell -B BLOCK -T verify
L 0 3 5
D setup

# Chopper-generated stack: promote
N promote
J vw promote.tcl -B BLOCK -T verify -force
D verify
```

Notes on line derivation (per [`technical_docs/ARCHITECTURE.md`](../../technical_docs/ARCHITECTURE.md) §3.6):

- `J` is omitted when `command` is empty.
- `L` is omitted when `exit_codes` is empty.
- `I` / `O` are omitted when the corresponding `inputs` / `outputs` list is empty.
- `D` derivation: `dependencies` (one line per entry) → else `load_from` → else bare `D`.
- `R parallel` is emitted only for `run_mode: "parallel"`; serial is implicit and the line is suppressed.

**Run it:**

```sh
chopper trim --json jsons/base.json --domain <path-to-domain>
```
