<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **chopper** (6083 symbols, 11974 relationships, 239 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/chopper/context` | Codebase overview, check index freshness |
| `gitnexus://repo/chopper/clusters` | All functional areas |
| `gitnexus://repo/chopper/processes` | All execution flows |
| `gitnexus://repo/chopper/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

# Chopper — Agent Operating Guide

**Standard:** root **`AGENTS.md`** (plural) is the harness-neutral instruction file for this repo (Cursor, Claude Code, Copilot, CI bots). Vendor-specific packs live elsewhere (see table below).

**Related files:**

| File | Role |
|------|------|
| **`AGENTS.md` (this file)** | GitNexus block above + Chopper operating guide below |
| **`CLAUDE.md`** | GitNexus mirror; links here for the Chopper guide |
| **`.github/agents/chopper-agent.agent.md`** | VS Code Copilot agent definition (tools, memory)—not a duplicate of this file |
| **`.github/instructions/project.instructions.md`** | Contributor scope lock, `make check` |

When behavior is ambiguous, **`technical_docs/ARCHITECTURE.md` wins**.

**Agent mission (two halves):**

1. **Chopper system** — how the tool works, safe CLI use, audit artifacts, R1 semantics.
2. **User domain** — the customer’s Tcl/EDA flow tree under a single domain root; discover boundaries, identify features, author `jsons/`, and iterate until trim intent matches requirements.

You are not done until you can explain **what the user’s codebase does**, **what their project slice should keep**, and **how the JSON layers express that**.

Extended playbooks and GHCP tool names: **`.github/agents/chopper-agent.agent.md`**.

---

## Essentials (Chopper system)

- **Capabilities:** F1 file trim, F2 proc trim, F3 run-file generation. **Pipeline:** P0–P7 (never label phases F1–F7).
- **R1:** default exclude; within a JSON include wins exclude; across layers base then `project.features[]` left-to-right, **last mention wins**; trace is **reporting-only** (explicit `procedures.include` or whole-file `files.include` keeps procs).
- **Safe loop:** `validate` → `trim --dry-run` → inspect `.chopper/` → live `trim` only with explicit intent. Never use `<domain>_backup/` as a user snapshot (`domain.pristine/` instead).
- **Domains:** `$ward/global/<vendor>/fev_formality` (medium), `.../power` (high). CLI: `--domain fev_formality`, `--features dft,power`. Composition: `examples/09`, `examples/14` (`skip_if_no_stage`).
- **Chopper repo source edits:** GitNexus block at top of this file + `.github/instructions/project.instructions.md`; `make check` / `make ci`. GitNexus is for **`src/chopper/`**, not the user’s domain Tcl tree.

---

## User domain — what you must learn

A **domain** is one directory Chopper trims (e.g. `$ward/global/snps/power/`). Everything outside that path is out of scope—never classify or recommend paths outside the user-confirmed root.

Your job is to build a **mental model** of:

- Which **files** are universal vs scenario-specific (F1).
- Which **procs** matter inside shared libraries (F2).
- Which **stages / run scripts** define the scheduler flow (F3)—existing `.stack` / hand-written `<stage>.tcl` vs JSON-driven generation.
- How **optional flows** group into named **features** and how **projects** combine them.

Reference complexity (architecture §8.1): **`fev_formality`** (~16 Tcl, ~60 procs) for medium splits; **`power`** (~60+ Tcl, ~150+ procs) for heavy F2, globs, and feature layering.

---

## Q0 — Ask the user what they want to trim (before deep analysis)

Do not assume F1+F2+F3. Confirm explicitly:

| User goal | Chopper surface | Your JSON focus |
|-----------|-----------------|-----------------|
| Drop whole files only | **F1** | `files.include` / `files.exclude`, globs |
| Keep files but drop procs | **F2** | `procedures.include` / `exclude`; avoid redundant `files.include` on same file (`VW-09`) |
| Generate / maintain run scripts from JSON | **F3** | `stages[]`, `flow_actions`, optional `generate_stack` |
| Full signoff slice | **F1+F2+F3** | Base minimal flow + feature overlays + project recipe |

Also confirm:

- **Business goal** — e.g. “LP-only project”, “FM without DFT”, “eco replay”.
- **Domain root path** (or logical name via `$ward`).
- **Mandatory vs optional** flows and whether **live trim** is in scope or JSON-only for now.
- **Code changes** — may you suggest Tcl refactors to make boundaries clearer, or JSON-only?

---

## Discovery protocol (Q1–Q5)

Ask in order; pause for confirmation after inventory, after call-tree review, and after base/feature split proposal. **Do not recommend files outside the confirmed boundary.**

| Step | Question | You produce |
|------|----------|-------------|
| **Q1** | Domain root? Primary entry scripts / stacks? | Scoped path; seed list for trace |
| **Q2** | Stack files (optional)? | Stage candidates for F3 mapping (`N/J/L/D/I/O/R`) |
| **Q3** | Script inventory? | Table: core libs, stage scripts, `-optional` sources, setup/promote |
| **Q4** | Config/data files? | F1 keeps (csv, rules, vars) |
| **Q5** | Utility dirs? | base vs feature vs `files.exclude` |

Classify each asset:

| Classification | JSON placement |
|----------------|----------------|
| Every project needs it | **base** `files.include` / `procedures.include` / `stages` |
| Scenario-specific | **feature** JSON |
| Legacy / debug | **base** or **feature** `files.exclude` / `procedures.exclude` |
| `iproc_source -optional` only | Usually **feature**, not base |
| Optional at Tcl load time (not Chopper-managed) | Omit from JSON; note in inventory |

Naming hints: `default_*`, `core_*` → base; `*_dft`, `*_power`, `eco_*`, `*_lite` → feature candidates.

---

## Chopper-powered domain analysis (preferred)

Static reading of Tcl is not enough for reliable F2 boundaries. **Run Chopper** to produce the **`.chopper/` audit bundle**—same compile, parse, and trace as a real trim.

### Workflow

```text
1. Draft minimal base.json (conservative includes) + schema validate
2. chopper validate --domain <path|name> [--base jsons/base.json] [--features ...]
3. chopper trim --dry-run ...   # no destructive rebuild; still writes .chopper/
4. Read audit artifacts (below)
5. Propose split / JSON edits; repeat from step 2 until manifest matches intent
6. Live chopper trim only on explicit user request
```

If Chopper is not installed: **`python schemas/scripts/validate_jsons.py <domain>/`** plus manual proc trace from source—but tell the user validate/dry-run gives authoritative **`dependency_graph.json`**.

### Artifacts to use for “understanding the codebase”

| Artifact | Use for domain understanding |
|----------|------------------------------|
| **`dependency_graph.json`** | Proc call graph, seeds, reachable vs traced-only nodes, cycles (`TW-04`) |
| **`compiled_manifest.json`** | What would survive/drop per file; `FULL_COPY` vs `PROC_TRIM`; layer provenance |
| **`diagnostics.json`** | Parse/trace gaps (`PW-*`, `TW-*`), layer shadows (`VW-21`), blockers (`VE-*`) |
| **`trim_report.json`** | Physical delta preview (dry-run still populates report semantics) |
| **`input_base.json`**, **`input_features/`** | What Chopper actually compiled |

Build a **PROC TRACE LOG** for the user (roots, edges, unresolved, per-file defined/reachable/unreachable, external EDA commands vs proc calls). **Never treat traced-only procs as kept**—recommend explicit `procedures.include` when they must survive.

### Iteration loop

1. Start **conservative** (keep more); dry-run.
2. Tighten **`files.exclude`** / **`procedures.exclude`** or move assets into **features** when manifest shows unwanted survivors.
3. Add **features** one at a time; bisect failures by growing `--features` list.
4. Compare two dry-runs by diffing **`compiled_manifest.json`** before suggesting live trim.

---

## Split design — files, procs, stages (ask the user)

When proposing a split, present **options** and get explicit choice:

### F1 — File-level split

- **Whole-file keep:** `files.include` (literal or glob `procs/**/*.tcl`, `server_reports/**`).
- **Negative list:** `files.include: ["**"]` + targeted `files.exclude` (dangerous without user buy-in—default-exclude applies if include is wrong).
- Ask: “Should **entire directories** (e.g. `utils/debug/`) disappear for this project class?”

### F2 — Proc-level split

- **Surgical:** one `procedures.include` per shared `.tcl` when only a subset of procs is needed (typical in **power**-scale domains).
- **File keep + proc drop:** `files.include` + `procedures.exclude` for debug procs in an otherwise core file.
- Ask: “For **`shared.tcl`**, keep **all** procs (F1) or **named** procs only (F2)?”

### F3 — Stage / generated run files

- Map existing **`.stack`** → `stages[]` in base or features.
- Optional flows: **`flow_actions`** (`add_stage_after`, `add_step_after`, `replace_stage`, …).
- **`options.generate_stack`:** Chopper emits aggregate stack; confirm with user before relying on it in production domains.
- Ask: “Do you want Chopper to **generate** `<stage>.tcl` (and stacks), or only **trim** hand-written scripts (F1+F2, no `stages`)?”

**Do not mix models blindly:** same file with both whole-file include and proc include in one JSON triggers **`VW-09`**—pick one model per file per layer.

---

## Feature identification and nesting

### When to create a feature (one responsibility each)

Create **`jsons/features/<name>.feature.json`** when:

- A scenario adds files, procs, or stages not every project uses.
- A variant **replaces** or **removes** base behavior for a product line.
- Cross-cutting behavior targets stages another feature may create (use **`skip_if_no_stage`** — see `examples/14`).

Keep in **base** when the minimal viable flow needs it unconditionally.

### Feature nesting and ordering

| Mechanism | Meaning |
|-----------|---------|
| **`depends_on`** | Feature B requires feature A’s **`name`**; A must appear **earlier** in `project.features[]` |
| **Project order** | Authoritative overlay order for F1, F2, and F3; reordering changes survival and stage injection order |
| **Layer shadow** | Later feature can undo earlier includes (`VW-21`)—use intentionally, not by accident |

**Feature nesting patterns:**

- **Stacked capabilities:** `dft` → `scan_eco` (`depends_on: ["dft"]`) — project lists `[dft, scan_eco]`.
- **Independent overlays:** `dft` + `power` both after `main` — order affects stage sequence (`examples/09`).
- **Cross-cutting:** `coverage_reporting` injects into `main`, `dft_check`, `power_check` — optional stages need **`skip_if_no_stage: true`**.

Ask: “Which features are **mandatory** for this project recipe vs **optional toggles**?” Propose **one project JSON per recipe** (e.g. `project_lp.json`, `project_full_signoff.json`).

### Project JSON

```json
{
  "$schema": "project-v1",
  "project": "PROJECT_ID",
  "domain": "<domain_name>",
  "base": "jsons/base.json",
  "features": [
    "jsons/features/feature_a.feature.json",
    "jsons/features/feature_b.feature.json"
  ],
  "notes": ["feature_b depends_on feature_a — order enforced above"]
}
```

Validate: schema script → **`chopper validate --project ...`** → **`trim --dry-run`**.

---

## JSON authoring checklist

- `"$schema": "base-v1" | "feature-v1" | "project-v1"` on every file.
- Forward slashes; no `..`; no empty arrays (omit optional keys).
- Feature **`name`** unique; **`domain`** matches base when set.
- Stage **`reference`** / step anchors **byte-exact** (including `\n` in anchor comments).
- After edits: **`validate_jsons.py`** then **`chopper validate`** then **`trim --dry-run`**.

Templates and field reference: **`technical_docs/JSON_AUTHORING_GUIDE.md`**, **`examples/01`–`14`**.

---

## Assisting arbitrary user requirements

Map requests to actions:

| User says | You do |
|-----------|--------|
| “Bootstrap JSON for my domain” | Q0–Q5 → minimal base → first features → validate/dry-run loop |
| “Why was X dropped?” | `compiled_manifest.json` + provenance; check explicit includes vs trace-only |
| “Split DFT from core” | New feature JSON; move conditional files/procs/stages; project recipe |
| “Nest power under LP mode” | `depends_on`, ordered features, optional `flow_actions` / stage replacements |
| “Compare two project configs” | Two dry-runs; diff manifests and `trim_report.json` |
| “Prove JSON change is safe” | Dry-run before/after manifest diff |
| “Trim for CI” | Project JSON in repo; document `chopper validate` + `--strict` if warnings must fail |
| Refactor Tcl for clearer boundaries | Propose isolation of optional flows, explicit proc entry points—frame as trimming-enabling |

Always end a turn with **one focused question** when intent is unclear (split granularity, feature list, or F3 yes/no).

---

## Portable use — copy `AGENTS.md` to another machine

**Yes.** You can use this guide on any system where **`chopper` is on `PATH`** and an agent can read the file. You do **not** need the Chopper source repo on that machine to **organize or create JSONs** and run analysis for a customer domain.

### What you need on the target system

| Requirement | Notes |
|-------------|--------|
| **`chopper` CLI** | Installed and on `PATH` (bundled `schemas/` ship with the install; `$schema` IDs `base-v1`, `feature-v1`, `project-v1` resolve automatically). |
| **Domain directory** | The Tcl/EDA tree to trim—single root; create **`jsons/base.json`** and optional **`jsons/features/*.feature.json`** inside it. |
| **Agent + this file** | Copy **`AGENTS.md`** into the domain (e.g. `<domain>/AGENTS.md`), the team config repo, or point the harness at it via rules. |
| **`$ward` (optional)** | Only if you use logical names like `--domain fev_formality` or `snps/power`; absolute paths work without `$ward`: `chopper validate --domain /path/to/my_domain`. |

### What to copy vs ignore

| Block | On a domain-only machine |
|-------|---------------------------|
| **GitNexus section** (`<!-- gitnexus:start -->` … `end`) | **Ignore** — applies only when editing Chopper’s Python source in the chopper git repo. |
| **Chopper — Agent Operating Guide** (below the GitNexus block) | **Use this** — discovery, JSON splits, validate/dry-run, audit reading. |
| **Links to `examples/`**, **`technical_docs/`**, **`.github/agents/`** | Optional extras from the chopper repo; not required if the agent follows this guide and you use **`chopper validate` / `trim --dry-run`** for truth. |

**Minimal portable kit:** copy from **`# Chopper — Agent Operating Guide`** through **Success criteria** into e.g. `my_domain/AGENTS.md`, or copy the whole file and tell the agent to skip the GitNexus header.

### Minimal bootstrap on the domain machine

```text
my_domain/
  AGENTS.md              # optional but recommended for the agent
  jsons/
    base.json            # start minimal; expand after dry-run
    features/            # add as you identify optional flows
  *.tcl                  # existing domain sources
```

```text
cd /path/to/my_domain
chopper validate --domain . --base jsons/base.json
chopper trim --dry-run --domain . --base jsons/base.json
# read .chopper/dependency_graph.json, compiled_manifest.json, diagnostics.json
# refine jsons/; repeat validate + dry-run until intent matches
```

Add features incrementally:

```text
chopper validate --domain . --base jsons/base.json --features dft,power
chopper trim --dry-run --domain . --base jsons/base.json --features dft,power
```

Or use a project recipe once stable:

```text
chopper validate --project project.json
chopper trim --dry-run --project project.json
```

### What the agent can do without the chopper repo

- Run **Q0–Q5** discovery on the domain tree (read/search Tcl, stacks, configs).
- Author and iterate **`jsons/`** (base, features, project).
- Drive **validate → dry-run → audit** loops using only the installed CLI.
- Explain drops/keeps from **`.chopper/`** artifacts and propose feature splits, nesting, and project order.

### What still lives in the chopper repo (optional)

- **`examples/01`–`14`** — copy-paste JSON templates.
- **`technical_docs/JSON_AUTHORING_GUIDE.md`** — exhaustive field reference.
- **`.github/agents/chopper-agent.agent.md`** — VS Code Copilot–specific companion.

If something fails, use **`chopper validate`** diagnostics and **`technical_docs/DIAGNOSTIC_CODES.md`** from the install or chopper docs site—not invented codes.

---

## Success criteria (domain + Chopper)

You succeed when the user can:

1. State their **domain boundary** and **project slice** in plain language.
2. See **base vs features** reflected in JSON with sensible **`depends_on`** and project order.
3. Run **validate → dry-run** and read **`.chopper/`** without guesswork.
4. Adjust F1/F2/F3 split (**files / procs / generated stages**) deliberately.
5. Ship a **project recipe** that reproduces the same trimmed output on demand.

For GHCP-only flows (auto bug filing, agent memory paths), see **`.github/agents/chopper-agent.agent.md`**.
