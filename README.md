# Chopper

![Status](https://img.shields.io/badge/status-ready-0a7a3d)
![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![License](https://img.shields.io/badge/license-Intel%20Proprietary-555555)
![Pipeline](https://img.shields.io/badge/pipeline-P0--P7-8a3ffc)

[![Chopper Domain Companion](https://img.shields.io/badge/🤖_Agent-Chopper_Domain_Companion-0f62fe)](.github/agents/chopper-domain-companion.agent.md)

**Chopper is a Python CLI that surgically trims VLSI EDA tool-flow domains down to exactly what a project actually needs** — specified by JSON, reproducible on every run, and audited automatically after every trim.

Instead of editing Tcl by hand and hoping you caught every dependency, you write JSON to say which files, which procedures, and which run-script stages survive. Chopper parses your domain, compiles your selections, traces the call graph for visibility, trims the domain on disk, generates run scripts if needed, and writes a full audit bundle for review.


---

## 🤖 Meet the Companion

You do not have to figure out domain boundaries or JSON structure by hand. A purpose-built agent ships in-repo for VS Code Copilot Chat.

### Chopper Domain Companion

![Chopper Domain Companion](https://img.shields.io/badge/VS%20Code%20Agent-Chopper%20Domain%20Companion-0f62fe)

The **Chopper Domain Companion** ([.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md)) is the **single user-facing agent** for anything Chopper-related — from a convoluted Tcl codebase all the way to a validated, trimmed output. It absorbs the former Domain Analyzer.

**What it does:**

- Runs the **Q1–Q5 discovery protocol** on an unfamiliar codebase (domain root, stack files, scripts, configs, utility dirs)
- Authors `base.json`, `*.feature.json`, and `project.json` from your domain
- Runs `chopper validate` and `chopper trim --dry-run` and explains the results
- Reads `.chopper/` audit artifacts (manifests, trace graphs, diagnostics) and tells you what to fix
- Explains any diagnostic code against [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md)
- Runs named CLI playbooks: **bisect** a feature that broke trim, **compare** two runs, **prove-safe** a JSON change
- Works in two modes: **analyze-only** (JSON authoring, no CLI calls) or **full-loop** (analyze + run + audit)

**Prompt library** — ready-to-use starting points under [.github/prompts/](.github/prompts/): `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`.

> [!TIP]
> Open VS Code Copilot Chat, pick the Chopper Domain Companion, and say: *"bootstrap a starter JSON for my domain at `path/to/domain/`"* — or just *"hi"* and it will show you a two-tier menu of everything it can do.

---

## What Chopper Does

Chopper has three capabilities, all driven by JSON and all running through the same eight-phase pipeline:

| Capability | What It Does |
| --- | --- |
| **F1 — File trimming** | Copies or drops entire files based on `files.include` / `files.exclude` |
| **F2 — Proc trimming** | Surgically removes unwanted Tcl procedures inside a file, leaving the rest |
| **F3 — Run-file generation** | Emits `<stage>.tcl` run scripts from JSON stage definitions, replacing manual stack files |

The three commands that operate on those capabilities:

```text
chopper validate    # Full read-only analysis — checks schema, targets, Tcl, and call graph
chopper trim        # Runs validation then rebuilds the trimmed domain on disk
chopper cleanup     # Removes the backup directory after you have confirmed the trim
```

Every run — validate or trim — writes a `.chopper/` audit bundle with manifests, diagnostics, trace graphs, and reports so you can review and reproduce any result.

---

## How to Use Chopper

### Step 1 — Set up the environment

| Platform | Command |
| --- | --- |
| Windows PowerShell | `. .\setup.ps1` |
| Windows cmd.exe | `setup.bat` |
| Unix tcsh/csh | `source setup.csh` |
| Unix bash/zsh/sh | `source setup.sh` |

The bootstrap scripts create `.venv`, activate it, and install dependencies.

### Step 2 — Author your JSON selections

Chopper uses two or three JSON files. **Base and feature JSONs live inside your domain. The project JSON is optional and can live anywhere.**

| JSON | Where it lives | Required? | Purpose |
| --- | --- | --- | --- |
| **`base.json`** | `<domain>/jsons/base.json` | Yes | Universal files, procs, and stages every project in this domain needs |
| **Feature JSON** (zero or more) | `<domain>/jsons/features/<name>.feature.json` | No | Adds files, procs, or stage modifications for one optional capability |
| **`project.json`** | Anywhere — inside the domain, in a shared configs dir, wherever | No | A named recipe: records one base path + an ordered list of feature paths so you can commit a specific combination and invoke it with a single `--project` flag |

You **do not need a project JSON** to use features. Pass `--base` and `--features` directly on the command line. The project JSON is simply a way to commit a named combination.

#### Invocation modes

```text
# Mode 1 — Base only (most common starting point)
chopper validate --base jsons/base.json

# Mode 2 — Base + features directly (no project file required)
chopper validate --base jsons/base.json \
    --features jsons/features/feature_a.feature.json,jsons/features/feature_b.feature.json

# Mode 2b — Validate every feature JSON in a directory at once
# (validate only; trim/--project still require explicit per-file paths)
chopper validate --base jsons/base.json --features jsons/features/

# Mode 3 — Project recipe (single flag for a committed base + feature combination)
chopper validate --project project.json
```

#### Directory layout

Base-only (simplest):

```text
<domain_root>/
└── jsons/
    └── base.json                          ← universal files/procs/stages
```

Base + feature JSONs (Mode 2 — no project file needed):

```text
<domain_root>/
└── jsons/
    ├── base.json
    └── features/
        ├── feature_a.feature.json         ← optional capability layer A
        └── feature_b.feature.json         ← optional capability layer B
```

Base + feature JSONs + project recipe (Mode 3):

```text
<domain_root>/
├── jsons/
│   ├── base.json
│   └── features/
│       ├── feature_a.feature.json
│       └── feature_b.feature.json
└── project.json                           ← optional recipe: names base + [feature_a, feature_b]
```

The project JSON can also sit outside the domain — in a separate `configs/` directory or a team repository. It just holds paths to the base and feature JSONs.

#### Worked examples in `examples/`

| Example folder | What it shows |
| --- | --- |
| `01_base_files_only/` | Base with file trimming only |
| `02_base_procs_only/` | Base with proc trimming only |
| `03_base_stages_only/` | Base with stage JSON for run-file generation |
| `07_base_full/` | Full base — files, procs, and stages |
| `08_base_plus_one_feature/` | Base + one feature JSON (includes a `project.json`) |
| `09_base_plus_multiple_features/` | Base + two independent features |
| `10_chained_features_depends_on/` | Features with `depends_on` ordering |
| `11_project_base_only/` | Project file referencing base only (no features) |

Copy the nearest example into your domain root, replace every placeholder, then validate with `python scripts/validate_jsons.py <domain_root>/`. Full field reference is in [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md).

Use the **Chopper Domain Companion** ([.github/agents/chopper-domain-companion.agent.md](.github/agents/chopper-domain-companion.agent.md)) to generate JSONs from your codebase, or adapt from the examples above. The schemas in `schemas/` enforce correctness.

### Step 3 — Validate first, always

```text
# Base only
chopper validate --base jsons/base.json

# Base + features (no project file required)
chopper validate --base jsons/base.json \
    --features jsons/features/feature_a.feature.json

# Project recipe
chopper validate --project project.json
```

Validation is fully read-only. It parses Tcl, compiles selections, runs trace, checks the call graph, and reports every issue — without touching the domain on disk.

### Step 4 — Dry-run before you trim

```text
# Base only
chopper trim --dry-run --base jsons/base.json

# Base + features
chopper trim --dry-run --base jsons/base.json \
    --features jsons/features/feature_a.feature.json

# Project recipe
chopper trim --dry-run --project project.json
```

Dry-run produces the same analysis as validate but under the `trim` command surface, with trim-specific reporting in `.chopper/`. Review `.chopper/trim_report.txt` and `.chopper/dependency_graph.json` before committing to a live run.

### Step 5 — Trim live when dry-run matches intent

```text
chopper trim --project project.json
```

> [!IMPORTANT]
> Live trim renames your domain to `<domain>_backup/`, rebuilds a clean trimmed copy, and runs post-validation. Run live only after dry-run output matches intent.

### Step 6 — Review the audit bundle

Open `.chopper/` after any run. All artifacts are JSON and plain text, readable in any editor:

| Artifact | What to Look For |
| --- | --- |
| `trim_report.txt` | Which files were kept, dropped, or proc-trimmed |
| `dependency_graph.json` | Full trace of the call graph — what calls what |
| `compiled_manifest.json` | Final file, proc, and stage decisions before trim |
| `diagnostics.json` | Every diagnostic code emitted (errors, warnings, info) |
| `chopper_run.json` | Run metadata — exit code, phase reached, timing |

---

## The .chopper/ Audit Bundle

Chopper writes `.chopper/` on every run, including failed runs and dry-runs. Nothing is discarded on a re-run — the previous bundle is replaced. If you need to keep history, copy the folder before re-running.

The bundle is designed to be machine-readable. The `run-result-v1.schema.json` and `diagnostic-v1.schema.json` schemas in `schemas/` document the format.

---

## MCP Server (`chopper mcp-serve`)

Since 0.4.0, Chopper ships a **Model Context Protocol** server so MCP-capable clients — Claude Desktop, Claude Code, or any conforming MCP host — can inspect a domain without a shell. The surface is intentionally small, **read-only**, and stdio-only.

### What it is (and isn't)

| Property | Value |
| --- | --- |
| Transport | **stdio JSON-RPC only** — reads frames on stdin, writes responses on stdout, logs to stderr |
| Network exposure | **None** — no TCP, no HTTP, no WebSocket, no daemon, no discovery beacon |
| Side effects | **None** — the server cannot trim, cleanup, or otherwise mutate the filesystem under any parameter combination |
| Runtime dependency | Hard dependency on the `mcp` Python SDK (declared in [pyproject.toml](pyproject.toml)) |
| Lifecycle | Starts on `chopper mcp-serve`, blocks until the client disconnects (stdin EOF) or SIGINT |
| Exit codes | `0` clean shutdown · `3` programmer error · `4` MCP protocol error (`PE-04 mcp-protocol-error`) |

### Tools exposed

The server advertises **exactly three** tools via `tools/list`. A runtime guard plus an integration test (`tests/integration/test_mcp_stdio_e2e.py`) assert that nothing else is ever registered.

| Tool | Parameters | Returns |
| --- | --- | --- |
| `chopper.validate` | `{ domain_root, base?, features?, project?, strict? }` | Typed `RunResult` JSON — exit code, diagnostics array, artifact paths. Same code path as `chopper validate` on the CLI. |
| `chopper.explain_diagnostic` | `{ code }` (e.g. `"VE-06"`) | Registry entry: `{ code, slug, severity, phase, source, exit_code, description, recovery_hint }` sourced from [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md). |
| `chopper.read_audit` | `{ bundle_path }` | Full JSON contents of every file under the `.chopper/` bundle, keyed by relative path. |

**Explicitly NOT exposed:** `chopper.trim` and `chopper.cleanup`. These destructive operations are never registered on the MCP server — by design, by code, and by test.

### Running it

```text
chopper mcp-serve
```

That's the whole invocation. The process stays in the foreground, speaking JSON-RPC on stdin/stdout. Point any MCP client at it as a subprocess command.

#### Example: Claude Desktop `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "chopper": {
      "command": "chopper",
      "args": ["mcp-serve"]
    }
  }
}
```

Once connected, ask the client to validate a domain or explain a diagnostic — the calls route through the three tools above.

### Diagnostics

Protocol-level failures (malformed frames, unknown tool name, bad parameter shape) surface as `PE-04 mcp-protocol-error` with exit code `4`. Diagnostics returned inside a tool response use the same codes the underlying CLI path would have produced — the MCP surface does not invent or rewrite codes.

The authoritative specification for the MCP surface is [technical_docs/chopper_description.md](technical_docs/chopper_description.md) §3.9.

---

## Documentation

| Who You Are | Where to Start |
| --- | --- |
| First-time operator | [doc/USER_MANUAL.md](doc/USER_MANUAL.md) — commands, flags, tasks, troubleshooting |
| JSON author / domain owner | [doc/BEHAVIOR_GUIDE.md](doc/BEHAVIOR_GUIDE.md) — merge rules, tracing, patterns, FAQ |
| Integrator or contributor | [doc/TECHNICAL_GUIDE.md](doc/TECHNICAL_GUIDE.md) — pipeline, modules, ports, error model |
| Engineer reading the code | [doc/IMPLEMENTATION_GUIDE.md](doc/IMPLEMENTATION_GUIDE.md) — code-level walkthrough |
| JSON schemas and examples | [schemas/](schemas/) and [examples/](examples/) — authoritative schemas and 11 worked examples; see [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md) |
| Authoritative specification | [technical_docs/chopper_description.md](technical_docs/chopper_description.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, quality gates, scope rules |

---

## Reporting Issues

Found a bug? [Open a bug report](../../issues/new?template=bug_report.yml) on GitHub. The form guides you through providing everything needed to reproduce the problem quickly.

**What to include:**

| What | How |
| --- | --- |
| Full terminal output | Run `chopper <command> 2>&1 \| tee chopper.log` and attach the log file |
| `.chopper/` audit bundle | Zip the `.chopper/` folder and drag it into the issue form — it contains `diagnostics.json`, `chopper_run.json`, and `trim_report.txt` |
| JSON configuration | Paste a minimal reproduction of your `base.json`, feature JSON, or `project.json` (remove sensitive paths) |
| Screenshots | Drag and drop PNG/JPG/GIF directly into any GitHub text field |

> [!TIP]
> Run `chopper validate` before `chopper trim` — it often surfaces the root cause without modifying your domain. Attach the validate output alongside the trim output when both are relevant.

---

## Contributing

Contributor workflow, local quality gates, working rules, and the pull-request checklist live in [CONTRIBUTING.md](CONTRIBUTING.md). The short version: run `make check` before opening a pull request, and read the spec before adding anything new.

---

## Changelog

Major milestones only. The canonical release version number lives in [pyproject.toml](pyproject.toml) (`[project].version`) and is exposed at runtime via `chopper.__version__`.

### 0.5.0 — 2026-04-25

- **Tool-command pool (`TI-01`).** Real EDA domains emit thousands of `TW-02 unresolved-proc-call` warnings per trim run, one per vendor-tool-command call (`get_app_var`, `set_dont_touch`, `report_timing`, …), burying genuine hits on actually-missing procs. Chopper now ships a domain-agnostic registry of known external tool-command names, seeded with PrimeTime (~850 commands at `src/chopper/data/tool_commands/pt.commands`) and extensible via the repeatable CLI flag `--tool-commands <path>`. Matches against the pool are reported as the new info-severity diagnostic `TI-01 known-tool-command` (exit 0, not counted against `--strict`). Architecture Doc §3.10 and **FR-44** specify the contract.
- **`chopper validate --features` accepts directories.** For `validate` only, any entry in the `--features` comma-separated list may be a directory path; it expands in place to the sorted, non-recursive set of its immediate `*.json` children. Files and directories may be mixed freely. `chopper trim` and `--project` still require explicit per-file paths so the ordered feature sequence recorded in audit artifacts stays unambiguous. Added as **FR-43** in the architecture doc. Intended use: CI/regression pipelines that need to validate an entire `jsons/features/` tree in one command.

### 0.4.0 — 2026-04-24

- **`chopper mcp-serve` — read-only stdio MCP surface.** Chopper now ships a stdio-only Model Context Protocol server, letting MCP-aware clients (Claude Desktop, Claude Code, etc.) inspect a domain without a shell. Exactly three read-only tools are advertised: `chopper.validate` (run `chopper validate` and return the typed RunResult JSON), `chopper.explain_diagnostic` (look up any code in the diagnostic registry), and `chopper.read_audit` (return the full contents of a `.chopper/` audit bundle). The destructive subcommands (`trim`, `cleanup`) are intentionally **not** exposed over MCP — an in-process guard and an integration test block any attempt to advertise them. Malformed frames or unknown tool names surface as the new diagnostic `PE-04 mcp-protocol-error` (exit code 4).
- **New hard runtime dependency: `mcp>=1.0,<2`.** The MCP SDK is required even for users who never run `mcp-serve` — this keeps the CLI surface predictable and avoids conditional-import complexity.
- **Docs cascade.** Architecture Doc §3.9 specifies the MCP contract authoritatively. The scope-lock in [.github/instructions/project.instructions.md](.github/instructions/project.instructions.md) was amended with a new §1.1 "Narrowed from a prior closure (read-only MCP)" subsection — the original "no MCP" closure is narrowed, not removed. [technical_docs/ARCHITECTURE_PLAN.md](technical_docs/ARCHITECTURE_PLAN.md), [technical_docs/CLI_HELP_TEXT_REFERENCE.md](technical_docs/CLI_HELP_TEXT_REFERENCE.md), and [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md) were all updated in the same pass.

### 0.3.3 — 2026-04-24

- **`options.generate_stack` end-to-end tested (D1 + D2).** The F3 stack-file generation path now has full integration-test coverage: a new `tests/fixtures/stages_domain/` fixture exercises a three-stage domain with `generate_stack: true`, and four new integration tests in `tests/integration/test_runner_localfs_e2e.py` verify the full P0→P7 pipeline on real disk — dry-run manifest shape, live-trim file emission, stack-file content (N/J/L/D/R correctness), and audit-bundle recording of `.stack` entries. Eight unit tests in `tests/unit/orchestrator/test_runner.py` cover the same paths via `InMemoryFS`. The `(new, untested)` label and pilot-user callouts have been removed from `JSON_AUTHORING_GUIDE.md`, `README.md`, and the companion agent memory; `options.generate_stack` is now a fully supported and tested feature.

### 0.3.2 — 2026-04-24

- **Companion consolidation + discoverability.** The former `domain-analyzer` agent was absorbed into the [Chopper Domain Companion](.github/agents/chopper-domain-companion.agent.md), now the **single user-facing agent** for anything Chopper-related. The companion card gained explicit **Operating Modes** (`analyze-only` vs `full-loop`), a **Q1–Q5 Discovery Protocol** for unfamiliar codebases, **JSON Templates & Checklists**, a **Schema Error → Fix Mapping** table, a **Bootstrapping-a-new-domain** playbook, and named **Common CLI Workflows** (Bisect / Compare-two-runs / Prove-JSON-safe / Explain-a-diagnostic). The greeting is now a tier-2 menu (Tier 1 "where are you starting from?" table → Tier 2 full capability list).
- **Prompt library.** New [`.github/prompts/`](.github/prompts/) directory with six ready-to-use starting points: `bootstrap-domain`, `explain-last-run`, `why-was-dropped`, `validate-my-jsons`, `bisect-feature-breakage`, `report-chopper-bug`.
- **USER_MANUAL cross-ref.** [doc/USER_MANUAL.md](doc/USER_MANUAL.md) now points at the companion at the top of the Operating Tasks section.
- No runtime, schema, diagnostic-registry, or scope-lock changes — agents, docs, and version files only.

### 0.3.1 — 2026-04-24

- **First-time-user setup hardened across all four shells.** [setup.ps1](setup.ps1), [setup.sh](setup.sh), [setup.csh](setup.csh), and [setup.bat](setup.bat) now (1) detect stale / relocated `.venv` directories by comparing the venv's reported `sys.prefix` against the script directory and recreate automatically on mismatch, (2) invoke pip exclusively through `python -m pip` so a stale `pip.exe` shim (the common failure mode when a `.venv` is copied from another repo) can no longer block the install, (3) unconditionally regenerate the `chopper` console-script launcher on every run via `pip install -e . --force-reinstall --no-deps`, and (4) smoke-test `chopper --help` and report `Chopper : <version> (launcher OK)` in the "Setup complete" banner. The result: `git clone … && . setup.ps1 && chopper --help` now works end-to-end without manual recovery steps.
- The `chopper` command is already wired as a standard `[project.scripts]` console entry point in [pyproject.toml](pyproject.toml), so activating the venv puts `chopper` directly on `PATH` — the setup hardening above ensures the shim that gets there is always valid.

### 0.3.0 — 2026-04-24

- **F3 stack-file auto-generation (`options.generate_stack`).** Base JSON gains an optional `options.generate_stack` boolean (default `false`). When enabled alongside `stages`, the generator (P5b) emits one `<stage>.stack` per resolved stage alongside `<stage>.tcl`, using the N/J/L/D/I/O/R format documented in the architecture doc §3.6. Dependency-line derivation follows `dependencies` > `load_from` > bare `D`. Generated `.stack` files participate in `compiled_manifest.json`, the trimmer skip-set, and the audit bundle exactly like `.tcl` run scripts.
...it/` dissolved.** Now that the Chopper runtime has shipped, the standalone authoring kit was absorbed into the main repository: schemas moved to `schemas/`, examples to `examples/`, the authoring guide to [technical_docs/JSON_AUTHORING_GUIDE.md](technical_docs/JSON_AUTHORING_GUIDE.md), the domain-analyzer agent to `.github/agents/domain-analyzer.agent.md` (later absorbed into the Chopper Domain Companion in 0.3.2), and the validator to [scripts/validate_jsons.py](scripts/validate_jsons.py). The kit's private version file was folded into the main package metadata.
- Authoring guide §2.1 added; example 03 and example 07 opted in to `generate_stack` for demonstration.

### 0.2.0 — 2026-04-23

- Release channel and packaging metadata stabilized; canonical version surface consolidated into [pyproject.toml](pyproject.toml) as the single source of truth.
- Documentation suite modernized: user manual expanded with detailed JSON usage and invocation examples; audience-targeted formatting pass across all technical guides.
- Repository rebranded to **Chopper** (from earlier internal name), with all schemas, help text, and audit artifacts updated in lockstep.

### 0.1.x — Early Buildout

- **CLI surface complete.** Three subcommands — `validate`, `trim`, `cleanup` — with `--project`, `--base`, feature selection, `--dry-run`, and `--strict` all wired through.
- **Pre- and post-trim validators.** `validate_pre()` and `validate_post()` enforce schema, structural, and cross-validation invariants; `VE-*` / `VW-*` / `VI-*` families registered and emitted.
- **Trimmer + generator path.** File-level, proc-level, and stage-based trimming land; `GeneratorService` emits `<stage>.tcl` run files from resolved stages.
- **Parser hardening.** Tokenizer state machine and proc extractor cover the Tcl edge cases catalogued in [technical_docs/TCL_PARSER_SPEC.md](technical_docs/TCL_PARSER_SPEC.md) and the `tests/fixtures/edge_cases/` corpus.
- **Audit bundle.** Every run (success or failure) writes `.chopper/` with `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt`, and JSON-Lines event log.
- **JSON Kit extraction (superseded in 0.3.0).** Base/feature/project schemas, validator, authoring guide, and eleven worked examples were packaged as a standalone kit under `json_kit/` so domain owners could author JSON before the runtime shipped. The kit was absorbed into the main repository in 0.3.0.
- **Agentic workflow.** Chopper Buildout Agent and Chopper Domain Companion shipped with the repository, each backed by a local memory file under `.github/agent_memory/`.
- **Spec-first foundation.** Eight-phase pipeline (P0–P7), R1 merge rules, diagnostic-code registry, and risks/pitfalls catalogue established as the authoritative basis for every subsequent change.

---

## Acknowledgments

Chopper was inspired by and builds on the foundational thinking behind:

- **SNORT** by Mike McCurdy ([michael.mccurdy@intel.com](mailto:michael.mccurdy@intel.com)) — domain state detection and trim-lifecycle design
- **FlowBuilder** by Stelian Alupoaei ([stelian.alupoaei@intel.com](mailto:stelian.alupoaei@intel.com)) — stage-driven flow modeling and the run-file generation concept
