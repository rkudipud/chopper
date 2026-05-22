# Example 13 — Aggregate stack + per-stage standalone stack

Mixes `options.generate_stack: true` (aggregate) with one stage that sets
`standalone_stack: true` (verbatim per-stage stack file).

**Inputs:** [jsons/base.json](jsons/base.json) declares two stages —
`setup` and `eco_apply_patch`. The aggregate flag is on, and
`eco_apply_patch` additionally opts in to its own standalone stack
file.

**Generated outputs (under `<domain_root>/`):**

```text
setup.tcl
eco_apply_patch.tcl
eco_apply_patch.stack    # standalone: verbatim steps, no record derivation
my_domain.stack          # aggregate: one record per stage
```

`setup` does **not** get a per-stage `.stack` (it did not opt in). The
aggregate `my_domain.stack` still contains a record for every stage,
including `setup` and `eco_apply_patch`.

**Standalone shape (`eco_apply_patch.stack`):**

```text
<Intel header>

rm -rf $ward/old_artifacts
cp -r $ward/patch_src $ward/patch_dst
bash $ward/apply.sh
```

The standalone file is the Intel header + one blank line + the `steps`
array joined by `\n`, verbatim. `command`, `exit_codes`,
`dependencies`, `inputs`, `outputs`, `load_from`, and `run_mode` are
**ignored** for the standalone file — they affect only the aggregate
record.

**Orthogonality summary (per [`technical_docs/ARCHITECTURE.md`](../../technical_docs/ARCHITECTURE.md) §3.6):**

| `options.generate_stack` | stage `standalone_stack` | `<stage>.tcl` | `<stage>.stack` | `<basename>.stack` |
|---|---|---|---|---|
| false | false | ✓ | — | — |
| false | true | ✓ | ✓ | — |
| true | false | ✓ | — | ✓ (record for stage) |
| true | true | ✓ | ✓ | ✓ (record for stage) |

**Run it:**

```sh
chopper trim --json jsons/base.json --domain <path-to-domain>
```
