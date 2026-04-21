# snort/ — Inspiration Source

**Status:** Frozen. Reference-only.

`snort/` contains the predecessor Tcl proc-chasing tool that inspired Chopper's parser and trace algorithms. It is kept in-tree so engineers can consult the prior implementation when working on the parser (P2) or tracer (P4) without hunting through git history.

The authoritative Chopper parser specification is [`docs/TCL_PARSER_SPEC.md`](../docs/TCL_PARSER_SPEC.md); authoritative product behavior lives in [`docs/chopper_description.md`](../docs/chopper_description.md).

Do not edit files in this directory. Do not import from it. Nothing in `snort/` is part of Chopper's build or runtime.

## Files

- `snort` — main script (the prior tool)
- `procdiff` — proc-diff helper
- `tcl_builtins.txt` — builtin-name list consulted during call extraction (may be useful reference data for Chopper's parser)
