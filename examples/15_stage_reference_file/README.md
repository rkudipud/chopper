# Example 15 -- Stage steps sourced from a reference file

Demonstrates `reference_file`: instead of duplicating an existing stage script's
lines into JSON `steps`, point the stage at the file directly. See
[JSON_AUTHORING_GUIDE.md Sec.2.3](../../technical_docs/JSON_AUTHORING_GUIDE.md)
and [ARCHITECTURE.md Sec.3.6](../../technical_docs/ARCHITECTURE.md) for the full
contract.

## What this example shows

- `stages[0]` (`setup`) sets `reference_file: "scripts/setup_stage.steps"` instead
  of `steps`. Chopper reads that file at P1 and uses one step per physical line --
  including the blank line and the comment line, preserved verbatim.
- `stages[1]` (`run_verify`) authors `steps` inline as usual, for contrast. Both
  forms produce an identical kind of generated `<stage>.tcl` -- the resolved
  `steps` are indistinguishable downstream regardless of origin.
- `files.include` deliberately also lists `scripts/setup_stage.steps`, so the
  source file itself survives trimming alongside the generated `setup.tcl`. Omit
  it and Chopper still works, but emits advisory `VW-26` to flag that the source
  of truth will not be present in the trimmed output.
- `jsons/features/dft.feature.json` shows the 4.8.0 extension: `add_step_after`
  injects a block at the `run_verification` anchor in `run_verify`, sourced from
  `scripts/scan_block.steps` via `reference_file` instead of an inline `items`
  array -- the same mechanism, applied to a step-level anchor injection rather
  than a whole stage.

## Try it

```
chopper validate --domain . --base jsons/base.json
chopper trim --dry-run --domain . --base jsons/base.json
```

Inspect `.chopper/compiled_manifest.json` -- `setup`'s resolved `steps` will show
`["source setup.tcl", "", "# load default config", "load_design"]`, exactly as if
authored inline.

Add the feature to see the step-level injection:

```
chopper validate --domain . --base jsons/base.json --features dft
chopper trim --dry-run --domain . --base jsons/base.json --features dft
```

`run_verify`'s resolved `steps` will show `run_scan` and `verify_scan` spliced in
right after `run_verification`, wrapped in `## CHOPPER: BEGIN/END added step`
provenance markers (Sec.3.11) -- indistinguishable from an inline-authored
injected block.
