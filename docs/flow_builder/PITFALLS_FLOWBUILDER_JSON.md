# FlowBuilder JSON Design Pitfalls

> **Purpose:** Technical analysis of structural anti-patterns in FlowBuilder's JSON schema  
> **Date:** 2026-04-04  
> **Audience:** Chopper architecture team — inform JSON schema decisions

---

## 1. The Core Anti-Pattern: "Data as Keys" (Dynamic Key Proliferation)

### What FlowBuilder does

**Base JSON (`apr_fc.json`):**
```json
{
    "owner": "johndoe",
    "description": "This Default APR_FC Flow",
    "vendor": "snps",
    "tool": "fusioncompiler",
    "command": "Ifc_shell ...",
    "stages": ["import_design", "read_upf", "redefine", "init_floorplan", ...],

    "import_design": { "load_from": "", "steps": [...] },
    "read_upf":      { "load_from": "import_design", "steps": [...] },
    "redefine":      { "load_from": "read_upf", "steps": [...] },
    "init_floorplan": { "load_from": "redefine", "steps": [...] },
    ...
}
```

**Feature JSON (`csi.feature.json`):**
```json
{
    "name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"],
    "description": "Implements anchor buffer insertion...",

    "step_csi_load_spec.tcl": { "action": "add_step_after", "stage": "logic_opto", ... },
    "csi":                    { "action": "add_stage_after", "reference": "compile_initial_opto" },
    "csi_stage_bundle":       { "action": "add_step_after", "stage": "csi", "items": [...] }
}
```

### The pattern

1. An **index array** (`stages` or `name`) lists element identifiers as strings.
2. Each string in the array then appears as a **top-level key** in the same JSON object.
3. The top-level object mixes **fixed schema keys** (`owner`, `vendor`, `description`) with **dynamic data-driven keys** (`import_design`, `csi_stage_bundle`).

### What this is called

This anti-pattern goes by several names in software architecture:

| Name | Definition |
|---|---|
| **"Data as Keys"** | Using runtime data values as structural property names in a schema |
| **Dynamic Key Anti-pattern** | Object keys are not statically known — they come from data |
| **Flat Namespace Collision** | Fixed metadata keys and dynamic data keys share the same namespace |
| **Stringly-Typed Schema** | Structure is encoded in string values rather than in the schema itself |
| **Self-Referential Object** | An array within the object references keys of the same object |
| **Map-in-Object** | Using a JSON object as both a typed record AND a key-value map simultaneously |

The JSON Schema specification calls this the `additionalProperties` problem — the schema can only describe the fixed keys; all dynamic keys fall into an unvalidatable catch-all.

---

## 2. Why This is a Flaw

### 2.1 The schema is not self-describing

A well-designed JSON can be understood by reading the schema alone. FlowBuilder's JSON cannot.

```
Q: What keys does apr_fc.json have at the top level?
A: "owner", "description", "vendor", "tool", "command", "stages", and... 
   whatever strings happen to be in the "stages" array.
   Could be 5 keys. Could be 50. Depends on the data.
```

You cannot write a complete JSON Schema for this format. The best you can do is:

```json
{
    "type": "object",
    "properties": {
        "owner": { "type": "string" },
        "stages": { "type": "array" }
    },
    "additionalProperties": true   ← catch-all: anything goes
}
```

This means **no schema validator can check whether a stage definition is correct**, because the validator doesn't know which keys are stages and which are metadata.

### 2.2 Key collision risk

Fixed metadata keys and dynamic stage names share the same namespace. Nothing prevents:

```json
{
    "stages": ["import_design", "description", "stages"],
    "description": "This Default APR_FC Flow",
    ...
}
```

If someone names a stage `"description"`, `"command"`, `"vendor"`, or `"stages"`, it collides with fixed keys. This is not hypothetical — it's a **namespace collision waiting to happen**.

FlowBuilder avoids this only because the current stage names happen not to collide. There is no structural protection.

### 2.3 Tooling cannot introspect the structure

JSON tooling (editors, linters, code generators, IDEs) relies on schemas to provide:
- Autocompletion
- Validation
- Documentation on hover
- Refactoring support

With dynamic keys, none of these work for the stage/item definitions. An IDE can autocomplete `"owner"` but has no idea that `"init_floorplan"` is a valid key or what shape its value should take.

### 2.4 Parsing requires two passes

Code that consumes this JSON must:

1. **First pass:** Read the `stages` array to discover which keys are stage definitions.
2. **Second pass:** Access each discovered key from the same object.

```python
data = json.load(f)
metadata_keys = {"owner", "description", "vendor", "tool", "command", "stages"}
for stage_name in data["stages"]:
    stage_def = data[stage_name]  # second lookup using data from first lookup
```

In a properly structured JSON, you'd just iterate:
```python
for stage in data["stages"]:
    stage_def = stage  # it's right there
```

### 2.5 Order is not guaranteed

JSON objects are **unordered** by specification (RFC 8259). The `stages` array preserves order, but the top-level keys do not. This means:

- Reading the file top-to-bottom does NOT tell you stage order.
- Serializers may reorder keys alphabetically, pushing `"cts"` before `"import_design"`.
- The `stages` array is the **only** source of truth for ordering — the key placement is meaningless.

This creates a **dual source of truth**: the array says the order, the keys hold the data. They can get out of sync.

### 2.6 Refactoring is fragile

Renaming a stage requires changes in **three** places:
1. The `stages` array entry
2. The top-level key name
3. Every `load_from`, `reference`, and `stage` field in other stages/features that reference it

In a properly structured JSON, renaming changes only the `name` field — references use the structural position, not the string.

### 2.7 The feature JSON is worse

In feature JSONs, the `name` array contains strings that serve as BOTH:
- **Item identifiers** (keys in the JSON object)
- **Step filenames** (the actual Tcl file to insert)

```json
{
    "name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"],
    "step_csi_load_spec.tcl": { ... }
}
```

When the item ID IS the filename, you get awkward suffixes to disambiguate:
```json
"name": ["step_csi_load_spec.tcl", "step_csi_load_spec.tcl_0"]
```

The `_0` suffix is a **hack** to work around the fact that JSON object keys must be unique, but the same step can be inserted in multiple places. The item ID has been overloaded with meaning it shouldn't carry.

---

## 3. Concrete Problems in Practice

### 3.1 Base JSON — apr_fc.json has 24 top-level keys

```
Fixed keys (6):   owner, description, vendor, tool, command, stages
Dynamic keys (17): import_design, read_upf, redefine, init_floorplan,
                    setup_timing, initial_map, floorplan, logic_opto,
                    insert_dft, compile_initial_opto, compile_final_opto,
                    cts, clock_route_opt, route_auto, route_opt, fill, finish
```

If a new stage is added, the top-level object grows. If stages are removed, it shrinks. The "shape" of the JSON is data-dependent.

### 3.2 Feature JSON — csi has item IDs that are filenames

```json
"name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"]
```

Three different "types" of items in the same array:
- `step_csi_load_spec.tcl` — a filename (also used as a key)
- `csi` — a stage name (also used as a key)
- `csi_stage_bundle` — an invented identifier (also used as a key)

There's no way to tell from the `name` array which are steps, which are stages, and which are bundles. You must read each key's `action` field to determine its type.

### 3.3 Same step, multiple placements → suffix hack

```json
{
    "name": [
        "step_clock_stamping.tcl_lo",
        "step_clock_stamping.tcl_id"
    ],
    "step_clock_stamping.tcl_lo": {
        "items": ["step_clock_stamping.tcl"],
        "action": "add_step_after",
        "stage": "logic_opto",
        "reference": "step_compile_logic.tcl"
    },
    "step_clock_stamping.tcl_id": {
        "items": ["step_clock_stamping.tcl"],
        "action": "add_step_after",
        "stage": "insert_dft",
        "reference": "step_dft_create_mv_cells.tcl"
    }
}
```

The actual file is `step_clock_stamping.tcl`. But since it's inserted in two stages, the item IDs become `step_clock_stamping.tcl_lo` and `step_clock_stamping.tcl_id` — invented suffixes that have no meaning outside this JSON. The `items` field then holds the real filename.

This is the **direct consequence** of using data as keys: when data repeats, you need synthetic disambiguators.

### 3.4 Cannot validate without custom code

Standard JSON Schema cannot express:
- "Every string in the `stages` array must also be a top-level key"
- "Every top-level key not in {owner, description, vendor, tool, command, stages} must be a stage definition matching this sub-schema"
- "The `reference` field must refer to a step that exists in the referenced stage"

All validation requires **custom code** that understands the implicit relationships.

---

## 4. The Alternative: Structured JSON with Explicit Nesting

### 4.1 Base JSON — Stages as array of objects

**Instead of:**
```json
{
    "stages": ["import_design", "read_upf"],
    "import_design": { "load_from": "", "steps": [...] },
    "read_upf": { "load_from": "import_design", "steps": [...] }
}
```

**Use:**
```json
{
    "stages": [
        {
            "name": "import_design",
            "load_from": "",
            "steps": [...]
        },
        {
            "name": "read_upf",
            "load_from": "import_design",
            "steps": [...]
        }
    ]
}
```

**Benefits:**
- Order is intrinsic (array position = execution order)
- No dual source of truth
- Schema is fully describable — `stages` is `array<StageDefinition>`
- Top-level keys are fixed and predictable
- No namespace collision risk
- Adding/removing stages doesn't change the object's shape
- IDE autocompletion works for stage fields

### 4.2 Feature JSON — Actions as array of objects

**Instead of:**
```json
{
    "name": ["step_csi_load_spec.tcl", "csi", "csi_stage_bundle"],
    "step_csi_load_spec.tcl": { "action": "add_step_after", ... },
    "csi": { "action": "add_stage_after", ... },
    "csi_stage_bundle": { "action": "add_step_after", "items": [...] }
}
```

**Use:**
```json
{
    "actions": [
        {
            "action": "add_step_after",
            "stage": "logic_opto",
            "reference": "step_starrc_indesign_setup.tcl",
            "items": ["step_csi_load_spec.tcl"]
        },
        {
            "action": "add_stage_after",
            "name": "csi",
            "reference": "compile_initial_opto"
        },
        {
            "action": "add_step_after",
            "stage": "csi",
            "reference": "",
            "items": [
                "source $ward/global/snps/$env(flow)/setup.tcl",
                "step_load.tcl",
                "step_csi_load_spec.tcl",
                "step_close.tcl"
            ]
        }
    ]
}
```

**Benefits:**
- No suffix hacks (`_lo`, `_id`, `_0`)
- Same step can appear in multiple actions without disambiguation
- Each action is self-contained — no cross-referencing between `name` array and keys
- Schema is `array<ActionDefinition>` — fully validatable
- Order of application is explicit (array position)

### 4.3 Comparison

| Aspect | FlowBuilder (data-as-keys) | Structured (array-of-objects) |
|---|---|---|
| Top-level keys | Unpredictable (6 + N stages) | Fixed (always the same) |
| JSON Schema | Partial — additionalProperties catch-all | Complete — fully describable |
| IDE support | Broken for dynamic keys | Full autocompletion & validation |
| Ordering | Array + scattered keys (dual truth) | Array position (single truth) |
| Namespace collisions | Possible | Impossible |
| Duplicate handling | Suffix hacks (`_0`, `_lo`) | Multiple array entries (natural) |
| Refactoring | 3 places to update | 1 place (`name` field) |
| Parsing | Two-pass (read index, then keys) | One-pass (iterate array) |
| Human readability | Key names visible at top level | Slightly more nested |

---

## 5. The One Legitimate Argument FOR Data-as-Keys

**Human readability at first glance.** When you collapse the JSON in an editor, FlowBuilder's format shows:

```
▶ owner
▶ stages
▶ import_design
▶ read_upf
▶ redefine
▶ init_floorplan
...
```

Stage names are immediately visible as top-level keys. In the structured format, you'd see:

```
▶ owner
▶ stages
    ▶ [0]
    ▶ [1]
    ▶ [2]
    ...
```

This is a real (minor) UX advantage for manual JSON editing. However, it comes at the cost of every other engineering benefit listed above. The tradeoff is not worth it — especially when tooling (IDE, GUI, `fb_gui`) should be the primary editing interface, not raw JSON.

---

## 6. Severity Assessment

| Issue | Severity | Impact on Chopper |
|---|---|---|
| Non-self-describing schema | **HIGH** | Chopper's JSON must be fully schema-describable |
| Key collision risk | **MEDIUM** | Chopper must use fixed top-level keys |
| No IDE/tooling support | **HIGH** | Chopper JSONs should support JSON Schema for validation |
| Two-pass parsing | **LOW** | Minor code complexity; not a blocker |
| Suffix disambiguation hacks | **MEDIUM** | Chopper must not require synthetic IDs |
| Dual source of truth for ordering | **MEDIUM** | Chopper must use array position as single truth |
| Fragile refactoring | **MEDIUM** | Chopper should minimize cross-references |

---

## 8. Additional Pitfalls Discovered (Deep Review — 2026-04-04)

### 8.1 Implicit Step Ordering via Chained References (Hidden DAG)

In the `csi.feature.json` wiki example, when **not** using `items` bundling, each step's `reference` points to the **previously inserted step** — creating an implicit insertion chain:

```json
"source $ward/.../setup.tcl":     { "reference": "" },
"step_load.tcl":                   { "reference": "source $ward/.../setup.tcl" },
"fc.app_options.tcl":              { "reference": "step_load.tcl" },
"step_csi_load_spec.tcl":         { "reference": "fc.app_options.tcl" }
```

This creates a **hidden DAG** where:
- Order depends on following the reference chain manually.
- Adding a step in the middle requires updating the step that previously pointed to the insertion point.
- Removing a step breaks the chain — the next step's reference becomes dangling.

The `items` bundling was introduced to work around this, but both mechanisms coexist, creating **two different paradigms** for the same operation in the same JSON format.

### 8.2 Raw Source Commands as JSON String Keys

FlowBuilder allows raw Tcl commands (like `source $ward/global/snps/$env(flow)/setup.tcl`) to be used as both **item identifiers in the `name` array** and as **top-level JSON keys**. This is deeply problematic:

- A Tcl command containing `$`, `/`, spaces, and parentheses is used as a JSON property name.
- The string is fragile — any whitespace change, path change, or env variable name change breaks the key match.
- It conflates **data** (a command to execute) with **identity** (a lookup key).
- It makes the JSON unreadable to anyone unfamiliar with the Tcl command's exact syntax.

### 8.3 No Feature Composition Validation

FlowBuilder applies features sequentially with no structural validation that the combined result is consistent:

- Feature A adds a step after `reference_X` in stage `S`. Feature B removes stage `S`. The step from Feature A now references a non-existent stage.
- Feature A adds stage `Z` after `Y`. Feature B also adds stage `Z` after `Y`. Duplicate stage names — undefined behavior.
- Feature A uses `load_from` to redirect stage `S` to load from `T`. Feature B also redirects `S` to load from `U`. Last-wins by accident, not by design.

There is no validation pass that checks the **composed result** for dangling references, duplicates, or contradictions.

### 8.4 Feature Priority is External to the JSON

The priority ordering that determines feature application order lives in a **separate config file** (`feature_priority.config`), not in the feature JSONs themselves. This means:

- The JSONs are not self-contained — their behavior depends on external ordering.
- A feature JSON cannot express "I must be applied before feature X" — there is no `depends` or `before`/`after` key.
- If the priority file is missing, features are applied in config-file order — which may differ between design_class, project, and user configs.
- The priority format changed between 2025.09 and 2025.12 — creating a migration burden with no schema version to distinguish.

### 8.5 Config Format Evolution Without Versioning

FlowBuilder's config format changed across releases:
- **2025.09:** One feature per line in `.features.config`
- **2025.12:** `features_<flow> = feat1 feat2 ...` syntax with backslash continuation

The parser uses heuristic detection (`"If features_ is detected, the new format is assumed"`). This is fragile — a feature named `features_helper` would trigger false detection. No `version` key, no format header, no explicit migration path.

### 8.6 Mixed Semantics in the `name` Array

Within a single feature JSON, the `name` array conflates at least four different types:

| Entry Type        | Example                                  | Purpose                          |
|-------------------|------------------------------------------|----------------------------------|
| Step filename     | `"step_csi_load_spec.tcl"`              | File to insert into flow         |
| Stage name        | `"csi"`                                  | New stage to create              |
| Bundle identifier | `"csi_stage_bundle"`                    | Invented name for grouped steps  |
| Property override | `"redefine"` (with `load_from` action)  | Modify existing stage property   |

All four types are mixed in one flat array with no type discriminator. The consumer must read each entry's `action` field to determine what type it is — making the `name` array semantically meaningless as a grouping mechanism.

---

## 9. Recommendation for Chopper

**Do not replicate FlowBuilder's data-as-keys pattern.** Use structured arrays of objects:

- `"stages": [{ "name": "X", "load_from": "Y", "steps": [...] }, ...]`
- `"actions": [{ "action": "add_step_after", "stage": "X", ... }, ...]`
- `"files": { "include": [...], "exclude": [...] }` (Proposal 1 got this right)
- `"procedures": { "include": [...], "exclude": [...] }` (use array-of-objects, not object-as-map)

Every top-level key in Chopper's JSON should be **statically known**. No data-driven keys at the root level.

The `procedures` section from Proposal 1 (`"file.tcl": ["proc1"]`) also uses data-as-keys (filenames as keys). Chopper should restructure this:

**Instead of:**
```json
"procedures": {
    "include": {
        "flow_procs.tcl": ["proc_a", "proc_b"],
        "feature_procs.tcl": []
    }
}
```

**Use:**
```json
"procedures": {
    "include": [
        { "file": "flow_procs.tcl", "procs": ["proc_a", "proc_b"] },
        { "file": "feature_procs.tcl", "procs": [] }
    ]
}
```

This keeps the schema fully describable and avoids all six pitfalls documented above.
