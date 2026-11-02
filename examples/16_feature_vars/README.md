# Example 16 -- Feature vars/procs sourcing files (v2 schemas)

Demonstrates the v2 `vars` and `procs` keys and the generated `<flow>_feature_vars.tcl`
and `<flow>_feature_procs.tcl`.
See [JSON_AUTHORING_GUIDE.md Sec.2.4](../../technical_docs/JSON_AUTHORING_GUIDE.md)
and [ARCHITECTURE.md Sec.3.12](../../technical_docs/ARCHITECTURE.md) for the full
contract.

## What this example shows

- Every JSON uses a v2 schema (`base-v2`, `feature-v2`, `project-v2`). Mixing v1
  and v2 in one run fails with `VE-41`.
- The base JSON is named after the flow: `jsons/apr_fc.json` for the `apr_fc`
  domain. Any other name triggers advisory `VW-28`.
- The base `vars: "vars.tcl"` is kept as F1 but is **not** written into the
  generated file -- the infra already sources `global/<vendor>/<flow>/vars.tcl`
  before `apr_fc_feature_vars.tcl`.
- Each feature `vars` entry expands into three `-optional` lines: the entry, its
  `tech_` variant, and its `project_` variant. Each of those files that exists in
  the domain is kept as F1.
- Block order follows the project `features[]` order.
- `procs` follows the same contract: base `procs/core_procs.tcl` is only kept,
  while feature `procs/fdr_procs.tcl` contributes that path plus
  `procs/tech_fdr_procs.tcl` and `procs/project_fdr_procs.tcl`.
  DOP contributes `dop_procs.tcl`, `tech_dop_procs.tcl`, and `project_dop_procs.tcl`.
  Existing files are kept whole by F1. Infrastructure sources the procs output
  separately; Chopper does not insert loader calls.

## Expected output

With the project selected, live trim writes `apr_fc_feature_vars.tcl` at the
domain root (after the Intel header):

```tcl
# Feature vars.tcl sourcing file for apr_fc

iproc_source -file fdr_vars.tcl -optional
iproc_source -file tech_fdr_vars.tcl -optional
iproc_source -file project_fdr_vars.tcl -optional

iproc_source -file dop_vars.tcl -optional
iproc_source -file tech_dop_vars.tcl -optional
iproc_source -file project_dop_vars.tcl -optional
```

## Try it

Copy this folder to a disposable directory named **`apr_fc`** first: generated
filenames and the project domain come from that directory name. Do not live-trim
the repository example in place.

From the copied directory:

```text
chopper --strict validate --project project.json
chopper loc --project project.json
chopper trim --dry-run --project project.json
```

The supplied Tcl files are deliberately minimal example assets, not production
FDR/DOP implementations. All authored pointers exist. Some `tech_` variants
are present; missing `project_` variants demonstrate optional sourcing.
The base enables `generate_stack` and defines one `main` stage.

Inspect `.chopper/compiled_manifest.json`: `apr_fc_feature_vars.tcl` is
`GENERATED`, and each existing vars file is `FULL_COPY`. An authored `vars`
entry that does not exist emits `VW-27`; an entry already listed by an earlier
feature is dropped with `VW-29`.

The manifest also lists `apr_fc_feature_procs.tcl` as `GENERATED`.
Procs-specific diagnostics are `VW-30`, `VW-31`, and `VE-42`; see
[DIAGNOSTIC_CODES.md](../../technical_docs/DIAGNOSTIC_CODES.md).

After a live trim of your disposable copy, `.chopper/p4_commands.txt` carries
`p4 add -t text+x` for new outputs (`p4 edit` for pre-existing generated
files). This is a filesystem-based plan, not a depot query. `loc` counts both
sourcing files in the GENERATED bucket. The generated stack contains:

```text
N main
J tclsh main.tcl
I apr_fc_feature_vars.tcl
I apr_fc_feature_procs.tcl
D
```

The aggregate declares inputs; it does not source them. Infrastructure must
load the generated lists after the corresponding base libraries. Standalone
stack bodies stay verbatim. Omitting all features still generates both lists,
with header and title only.

The root `project.json` is an input, not an automatic F1 keep. For live re-trim,
keep your recipe outside the trimmed tree (with paths adjusted), or restore it
from the pristine backup before using `--project` again.
