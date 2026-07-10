# 03 — How Chopper Works

> **Audience:** anyone who wants to understand the pipeline, decide where Chopper fits, or troubleshoot results at a deeper level than the CLI guide.
> **Goal:** by the end you can explain the 8-phase pipeline, the determinism contract, where Chopper belongs in your flow, and where it does **not**.

---

## 1. Where to use Chopper

| Use Chopper when... | Don't use Chopper when... |
|---|---|
| You have a single domain that needs to be tailored per project / block / methodology | You need to *combine* unrelated domains (cross-domain trimming is out of scope) |
| You want a reproducible, machine-checkable record of "what survives" | You need a one-off hand-tweak you will never repeat |
| You want declarative JSON to replace conditional `if {$project eq ...}` Tcl | Your slice is so small a hand-edit costs less than authoring JSON |
| Your domain mixes Tcl with Perl/Python/csh/configs that should travel together | You need subroutine-level trimming for non-Tcl languages (only Tcl gets proc-level F2) |
| You want auto-generated `<stage>.tcl` run scripts from declarative stage JSON | You need a runtime scheduler — Chopper emits artefacts; it does not run them |

Chopper sits **upstream of the runtime flow**. You trim once per project (or per project + methodology combination), commit the JSONs, and run the trimmed domain through your normal scheduler / job manager / EDA tool.

---

## 2. The 8-phase pipeline (P0–P7)

Every live `trim` executes this sequence. `validate` and `trim --dry-run` run the same front half (P0–P4) plus a manifest-only P6, skipping P5 filesystem rebuild.

```text
P0  Domain state    →  P1  Config + pre-validate  →  P2  Parse Tcl  →  P3  Compile
                                                                          │
                                                                          ▼
P7  Audit  ←  P6  Post-validate  ←  P5  Build output  ←  P4  Trace (BFS, reporting-only)
```

| Phase | Owner module | Responsibility | Output |
|---|---|---|---|
| **P0** | `orchestrator/domain_state.py` | Detect `<domain>/` and `<domain>_backup/`; classify first-trim vs re-trim vs recovery vs fatal | `DomainState` |
| **P1** | `config/`, `validator/functions.py` | Load base + features, resolve `depends_on`, schema-validate, check file/proc existence | `LoadedConfig` + pre-validation diagnostics |
| **P2** | `parser/` | Tokenize each `.tcl` file, extract `ProcEntry` records (definitions, calls, namespaces). Phase 2a parses surface files with diagnostics; Phase 2b silently parses every other `.tcl` under `domain_root` so the proc index is **full-domain**. | `ParseResult` |
| **P3** | `compiler/merge_service.py` | Apply R1 merge rules across base + features; produce per-file treatments | `CompiledManifest` |
| **P4** | `compiler/trace_service.py` | BFS from explicit proc includes; emit `dependency_graph.json` and `TW-*` warnings. **Reporting only — no auto-copy.** | `DependencyGraph` |
| **P5** | `trimmer/`, `generators/` | Execute file copies, proc-level rewrites, generated stage files, optional P5c indentation pass, P5d companion-file sync, JSON input preservation | `TrimReport` |
| **P6** | `validator/functions.py` | Re-parse trimmed output; brace balance, dangling refs, namespace consistency, stage-step references | post-validation diagnostics |
| **P7** | `audit/service.py` | Write `.chopper/` bundle. Always runs in `finally`, even after upstream failure. | `AuditManifest` |

> **Single orchestrator.** `ChopperRunner.run(ctx, command=...)` in `src/chopper/orchestrator/runner.py` owns the entire sequence. There is no event bus, no plugin host, no dynamic dispatch.

---

## 3. Why three rules govern everything

(Restated from [01_OVERVIEW.md §5](01_OVERVIEW.md#5-the-rules-that-govern-everything) — these are the rules a confused result almost always traces back to.)

1. **Default is exclude.**
2. **Explicit include always wins.**
3. **Tracing is reporting-only.**

The most-missed rule is #3. If a JSON lists `foo` and `foo` calls `bar`:

- `foo` survives in the trimmed output.
- `bar` appears in `dependency_graph.json` as a *traced-only* (PT) proc.
- `bar` is **not** copied. Calling `foo` at runtime crashes.

To keep `bar`, list it explicitly in `procedures.include` *or* include the whole defining file with `files.include`. Trace gives you visibility; it does not give you safety.

### Worked example

`base.json`:

```json
{
  "procedures": { "include": [{"file": "procs/core.tcl", "procs": ["foo"]}] }
}
```

`procs/core.tcl`:

```tcl
proc foo {} { bar }
proc bar {} { puts "hi" }
```

After trim: `foo` in output, `bar` not in output, `bar` listed as PT in `dependency_graph.json`. Fix:

```json
{ "procedures": { "include": [{"file": "procs/core.tcl", "procs": ["foo", "bar"]}] } }
```

Or:

```json
{ "files": { "include": ["procs/core.tcl"] } }
```

### Include/exclude behavior table

| Author intent | JSON shape | Result |
|---|---|---|
| Keep only listed files | `files.include: ["a.tcl"]` | `a.tcl` survives; unnamed files are removed. |
| Keep all files except a list | `files.include: ["**"]`, `files.exclude: [...]` | Chopper starts from every file under the domain, then removes paths matched by `files.exclude`. |
| Exclude-only file list | `files.exclude: [...]` | No file-level keep signal exists; under default-exclude, live trim can rebuild an almost empty domain. Add `files.include: ["**"]` for a negative-list trim. |
| Literal include plus matching exclude | `files.include: ["debug_old.tcl"]`, `files.exclude: ["debug*.tcl"]` | `debug_old.tcl` survives; literal include wins. |
| Glob include plus matching exclude | `files.include: ["*.tcl"]`, `files.exclude: ["debug*.tcl"]` | The glob-expanded include list is pruned; `debug*.tcl` matches are removed from that list. |
| Keep only certain procs | `procedures.include` | File becomes `PROC_TRIM`; only listed procs survive. |
| Keep file minus some procs | `procedures.exclude` | File becomes `PROC_TRIM`; all parsed procs except excluded procs survive. |
| File exclude plus proc exclude on the same file | `files.exclude` + `procedures.exclude` | Same-source contradiction; the source contributes nothing and emits `VW-11`. |
| Feature tries to remove a base file | Base includes file, a later feature excludes file | Feature is the later layer under R1 ordered overlay; the file is removed and `VW-21 layer-shadowed` records the transition. |

---

## 4. Determinism contract

Same inputs → byte-identical output. Enforced by:

| Mechanism | Where |
|---|---|
| Sorted BFS frontier | `compiler/trace_service.py` — frontier sorted lexicographically each iteration |
| `json.dumps(..., sort_keys=True)` everywhere | `audit/writers.py` |
| Stable insertion order in the diagnostic sink | `adapters/sink_collecting.py` |
| POSIX-normalised paths in serialised output | All writers |
| No `set()` iteration in output paths | Property tests in `tests/property/` enforce this |

Property tests (Hypothesis, 500 examples) run the same inputs twice and compare outputs.

---

## 5. The trace is your X-ray, not your safety net

Phase P4 emits `dependency_graph.json` and four warning families:

| Code | Meaning | What to do |
|---|---|---|
| `TW-01` resolved-ambiguous | Call could match multiple procs (same short name in different files) | Pick one or qualify with namespace |
| `TW-02` external-or-cross-domain | No in-domain proc with this name. Either an external (vendor / system) call or a cross-domain reference. | If needed, include explicitly. Otherwise accept — and consider adding it to a `--tool-commands` pool to surface as `TI-01` info instead. |
| `TW-03` dynamic-call-form | `$cmd`, `eval "..."`, `uplevel` — not statically resolvable | Add the resolved targets explicitly if needed |
| `TW-04` cycle-in-call-graph | Two procs call each other | Review for intent — usually safe; trace terminates via visited-set |

> **Open `dependency_graph.json` before shipping.** Every `TW-*` is a place Chopper could not prove a dependency. Every one needs a conscious decision.

---

## 6. The `.chopper/` audit bundle

Already enumerated in [02_CLI_GUIDE.md](02_CLI_GUIDE.md#the-chopper-audit-bundle). The design rules behind it:

- **Always written.** Even after an upstream phase failure, P7 runs in `finally`. Inputs may be `None`; each writer tolerates missing data and emits a valid JSON shell so downstream tooling never sees a missing file.
- **Replaced on every run.** Copy it elsewhere if you need history. Treat it as run output, not as proof that the domain was rebuilt.
- **Machine-readable first, human-readable second.** `trim_report.json` is the source of truth; `trim_report.txt` is a projection. Schemas live in [../schemas/](../schemas/).
- **Provenance is per file.** `files_kept.txt` and `files_removed.txt` record *which JSON pulled this in* (or vetoed it) on each line, tab-separated. Use `cut -f1` if you only want paths.

---

## 7. Performance envelope

| Dimension | Target |
|---|---|
| Domain size | ≤ 1 GB |
| Runtime | 3–5 minutes acceptable |
| Memory | Whole-file reads (no streaming) |
| Parallelism | **Single-threaded by design.** Correctness over speed at this scale. |

Chopper deliberately optimises for determinism and auditability over raw throughput. Future opt-in parallelism is tracked as a roadmap item (`FD-09`) but is not on the current path.

---

## 8. Error model

Three layers:

1. **User-visible outcomes** — always a `Diagnostic` emitted via `ctx.diag`. Exit codes 0, 1, 2.
2. **Programmer errors** — `ChopperError` subclasses raised from within services. Caught by the runner's final `except`, surfaced as exit `3`. `.chopper/internal-error.log` is written with run ID, traceback, diagnostic snapshot, and `RunConfig`. `RunResult.internal_error` is also populated so GUIs / CI can inspect the failure without reading the log file.
3. **Unexpected exceptions** — same path as (2). The CLI's top-level `try/except` is a second safety net for pre-runner failures.

No bare `print()` in library code. No bare `except:`. Every error path is typed.

---

## 9. Module map

```text
src/chopper/
├── core/         Shared frozen dataclasses, diagnostics, protocols, errors, serialization,
│              filesystem helpers (fs_walk, file_perms, globs, header, tool_commands)
├── config/       JSON loading, schema validation, depends_on topo-sort       (P1)
├── parser/       Tcl tokenizer, proc + call extractors, namespace tracker    (P2)
├── compiler/     R1 merge algorithm, BFS trace, F3 flow-actions, stack graph  (P3, P4)
├── trimmer/      File copier, proc dropper, indentation normaliser,
│              companion-file sync, JSON input preservation                  (P5a, P5c, P5d)
├── generators/   F3 stage + stack file emitter                               (P5b)
├── validator/    Pre- and post-trim validation                               (P1, P6)
├── audit/        .chopper/ writers, SLOC counter (cloc + fallback), hashing,
│              internal-error log                                            (P7)
├── data/         Bundled tool-command pools (PrimeTime, Formality, etc.)      (P4)
├── orchestrator/ ChopperRunner, phase-gate logic, domain-state detection     (all)
├── adapters/     LocalFS, InMemoryFS, CollectingSink, RichProgress, SilentProgress
└── cli/          argparse, render helpers, four subcommand handlers           (user)
```

Each service depends only on `core/` and its own submodules. The lone permitted exception is the validator importing the parser's `parse_file` for post-trim proc-set reconciliation (`VW-10`) — documented in `technical_docs/ARCHITECTURE.md` §5.12.9.

---

## 10. Ports — what is and isn't abstracted

Three protocol surfaces in `src/chopper/core/protocols.py`:

| Port | Purpose | Adapters |
|---|---|---|
| `FileSystemPort` | Read/write files | `LocalFS` (production), `InMemoryFS` (tests) |
| `DiagnosticSink` | Collect `Diagnostic` records | `CollectingSink` |
| `ProgressSink` | User-facing progress | `RichProgress` (production), `SilentProgress` (tests / `--quiet`) |

What is **not** a port (deliberately direct calls):

- Clock / time
- Serialization
- Audit storage (writers use `ctx.fs` directly)
- CLI rendering (`rich` is CLI-local)
- JSON schema (`jsonschema` is called directly)

Narrow port surface keeps the architecture useful without speculative abstractions.

---

## 11. Frequently asked questions

### Why did my feature's `files.exclude` do nothing?

Your feature is **earlier** than the layer that includes the file (or the file isn't named anywhere). Under R1 ordered overlay, only the *last* layer that mentions the file wins — a base or later-feature `files.include` after your `files.exclude` will re-include it. Reorder `project.features[]` so your feature appears after the layer you intend to override; check `VW-21 layer-shadowed` events in the audit bundle to verify the transition fired.

### Why did my proc survive even though I excluded it?

A later layer re-included it: another feature's `procedures.include`, or a whole-file `files.include` in the base or a later feature. Look for `VW-21 layer-shadowed` events involving the proc to see which layer last touched it.

### Why is my traced callee not in the output?

Tracing is reporting-only. Add it to `procedures.include`, or include the whole file. See §3 (rule 3) and §5.

### Can I trim across domains?

No. Cross-domain trimming is out of scope. Each domain owner trims their own domain independently.

### Can I auto-generate JSON from my existing flow?

No. "Scan mode" was evaluated and rejected. Use the `--dry-run` feedback loop instead. The Chopper Agent's bootstrap-domain prompt can produce a starter JSON from a cold scan, but it is a starting point, not authoritative.

### What exactly does `--dry-run` skip?

Domain rebuild only. Chopper still loads JSONs, parses Tcl, compiles, traces, runs manifest-only post-validation, and writes `.chopper/`. It does not rename `<domain>/`, rewrite files, remove files, or emit `<stage>.tcl` files into the domain.

### Can I preserve manual edits to `<domain>/` across re-trims?

No. Re-trim is deliberately destructive. Either move the edit into source files under `<domain>_backup/` (then re-trim picks it up), or apply it post-trim outside Chopper's workflow.

### Does Chopper run in parallel?

No. Single-threaded and deterministic. Runtime of 3–5 minutes per domain is acceptable. Parallelism was deferred (`FD-09`).

### What Python version?

3.13 or later. The default `.venv` from `setup.*` uses whatever interpreter `python` resolves to.

### What happens if Chopper crashes mid-trim?

`<domain>_backup/` is untouched. The next invocation sees both directories, classifies as "re-trim", and rebuilds cleanly from backup.

### Can I use Chopper on non-EDA Tcl?

Yes. The parser handles standard Tcl (`proc`, `namespace eval`, `source`, control flow). EDA-specific suppression filters (`iproc_msg`, `define_proc_attributes`, `foreach_in_collection`) are conservative and won't break on generic Tcl.

### How do I quiet a flood of `TW-02` warnings?

Six vendor pools are bundled (PrimeTime, PrimePower, PrimeECO, PrimeSim, Formality, PrimeClosure) and loaded automatically. For site-local or additional tool pools, pass `--tool-commands <path>` for each extra file. Matches surface as `TI-01` (info, exit 0) instead of `TW-02` (warning).

### What does `options.cross_validate` do?

When `true` (default), P6 checks every step string in every surviving stage against the files and procs that survived trimming. Missing targets emit `VW-14` (step file missing), `VW-15` (step proc missing), or `VW-16` (step source missing) — all warnings, never errors. Set to `false` if your stages intentionally reference content outside the trimmed domain (e.g. cross-domain sources). `VW-17 external-reference` is always emitted regardless of this flag.

### My feature injects steps into stages created by another feature. How do I avoid VE-05 when that feature is not loaded?

Add `"skip_if_no_stage": true` to each flow_action that targets the feature-created stage. When the stage is absent from the compiled sequence, Chopper emits `VI-05` (info, exit 0) and skips the action silently. When the stage is present, the action runs normally. This is the canonical pattern for cross-cutting features in modular domains. See [JSON_AUTHORING_GUIDE.md §7 "Optional stage targets"](../technical_docs/JSON_AUTHORING_GUIDE.md) and [ARCHITECTURE.md §6.7](../technical_docs/ARCHITECTURE.md).

### What is `p4_commands.txt` in `.chopper/`?

A Perforce audit file for this trim. Two `p4` command sections (`p4 edit`, `p4 add`) plus an `exclude_file_list` section of `$ward`-relative paths (4.1.0+) for files removed from the domain. Use the exclude list as P4 client-spec exclusion mapping lines. Chopper never invokes `p4` itself to produce or act on this file (see the separate `--p4` flag below for the one exception, which checks files out live during the trim itself).

### What is `files_exclude_p4.txt` in `.chopper/`?

The same `exclude_file_list` path set from `p4_commands.txt`, written as its own standalone file (4.3.0+) with no `p4 edit`/`p4 add` sections. Use it when a script only needs the exclusion list and shouldn't have to parse it out of `p4_commands.txt`.

### What does `chopper trim --p4` do?

Opt-in, live-trim-only (4.4.0+): before rewriting a file, Chopper runs `p4 edit -t text+x` on it, so a later `p4 submit` doesn't fight Perforce's checkout-before-edit protocol (Perforce keeps synced files read-only until checked out; editing them out-of-band and running `p4 edit` afterward is an unsupported recovery path). Only runs on a genuine first trim; skipped with an on-screen notice (not an error) if `p4` isn't available or this is a re-trim. Never active under `--dry-run`. On failure the whole trim aborts and reverts everything already checked out — if the failure happens after checkout succeeded, the domain is also restored from backup immediately. Chopper never runs `p4 add`, `p4 delete`, or `p4 submit` — only `p4 edit` and, on rollback, `p4 revert`. See [ARCHITECTURE.md §5.5.18](../technical_docs/ARCHITECTURE.md).

---

## 12. Where to go next

| Resource | Purpose |
|---|---|
| [01_OVERVIEW.md](01_OVERVIEW.md) | The thesis — re-read when intent is unclear |
| [02_CLI_GUIDE.md](02_CLI_GUIDE.md) | Day-to-day commands and deep examples |
| [../technical_docs/ARCHITECTURE.md](../technical_docs/ARCHITECTURE.md) | Authoritative specification |
| [../technical_docs/DIAGNOSTIC_CODES.md](../technical_docs/DIAGNOSTIC_CODES.md) | Every diagnostic code |
| [../technical_docs/JSON_AUTHORING_GUIDE.md](../technical_docs/JSON_AUTHORING_GUIDE.md) | Complete JSON field reference |
| [../technical_docs/IMPLEMENTATION.md](../technical_docs/IMPLEMENTATION.md) | Parser internals, pitfalls, roadmap (`FD-xx`) |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contributor workflow |
