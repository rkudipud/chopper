# Example 16 -- Feature vars sourcing and F2 procedure trimming (v2 schemas)

Demonstrates the v2 `vars_file` key, the generated `<flow>_feature_vars.tcl`,
and F2 procedure selection through `procedures.include`.
See [JSON_AUTHORING_GUIDE.md Sec.2.4](../../technical_docs/JSON_AUTHORING_GUIDE.md)
and [ARCHITECTURE.md Sec.3.12](../../technical_docs/ARCHITECTURE.md) for the full
contract.

## What this example shows

- Every JSON uses a v2 schema (`base-v2`, `feature-v2`, `project-v2`). Mixing v1
  and v2 in one run fails with `VE-41`.
- The base JSON is named after the flow: `jsons/apr_fc.json` for the `apr_fc`
  domain. Any other name triggers advisory `VW-28`.
- The base `vars_file: "vars.tcl"` is kept as F1 but is **not** written into the
  generated file -- the infra already sources `global/<vendor>/<flow>/vars.tcl`
  before `apr_fc_feature_vars.tcl`.
- Each feature `vars_file` entry expands into three `-optional` lines: the entry, its
  `tech_` variant, and its `project_` variant. Each of those files that exists in
  the domain is kept as F1.
- Block order follows the project `features[]` order.
- The base and feature `procedures.include` entries select named procedures in
  their hosting Tcl files. These files are handled by F2 and no procedure-source
  wrapper is generated.

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
`GENERATED`, existing vars files are `FULL_COPY`, and procedure files follow
their explicit F2 include sets. A `vars_file` entry that does not exist emits
`VW-27`; an entry already listed by an earlier feature is dropped with `VW-29`.

After a live trim of your disposable copy, `.chopper/p4_commands.txt` carries
`p4 add -t text+x` for new outputs (`p4 edit` for pre-existing generated
files). This is a filesystem-based plan, not a depot query. `loc` counts the
vars sourcing file in the GENERATED bucket. The generated stack contains:

```text
N main
J tclsh main.tcl
I apr_fc_feature_vars.tcl
D
```

The aggregate declares inputs; it does not source them. Infrastructure must
load the generated vars list after the base vars file. Standalone stack bodies
stay verbatim. Omitting all features still generates the vars wrapper, with
header and title only.

The root `project.json` is an input, not an automatic F1 keep. For live re-trim,
keep your recipe outside the trimmed tree (with paths adjusted), or restore it
from the pristine backup before using `--project` again.
