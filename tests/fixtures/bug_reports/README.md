# Real-world bug-report fixtures

Each `.tcl` file in this directory is a **verbatim** snippet lifted from a
production Tcl file in the `sta_pt` domain (Intel `pesg_2026.06`). Each
snippet was the minimal reproducer for a bug filed against Chopper's
parser/tracer/validator pipeline.

Tests under `tests/unit/`, `tests/integration/`, and `tests/golden/`
reference these fixtures directly so the regression coverage is anchored
to actual production code patterns rather than synthetic toy inputs.

| Fixture | Bug report | Failure mode |
|---------|------------|--------------|
| `dpa_multiline.tcl` | `PW-11_PI-04_dpa_line_continuation_misparse.md` | DPA name absorbs `\`-continued args |
| `quoted_semicolon.tcl` | `TW-02_quoted_string_semicolon_misparse.md` | `;` inside `"..."` treated as cmd separator |
| `regex_literals.tcl` | `TW-02_regex_literal_misparse.md` | Regex `{...}` walked for proc calls |
| `switch_patterns.tcl` | `TW-02_switch_pattern_label_misparse.md` | `switch` pattern labels treated as proc calls |
| `python_braces.py` | `PE-02_python_brace_false_positive.md` | Tcl brace counter ran against `.py` |

The `diagnostics_file_null_for_p4_p6.md` bug is asserted via path-population
checks on diagnostics emitted from these fixtures (no separate `.tcl` file
needed; reuses the others).
