# Chopper -- Engineering Plan

**Status in the doc tree.** This document is a **plan**, not a contract. The authoritative product spec is [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) ("the architecture doc"). This plan proposes *how* the spec is realized as independently developable modules. Where this plan disagrees with the architecture doc, the architecture doc wins and this plan is edited in place.

**What this plan is for.** Chopper is a **local, single-process Python CLI** -- not a web app, not a cloud service, not a daemon, not a plugin host. It runs on a VLSI engineer's workstation (or a grid node), reads <=1 GB of Tcl / JSON from disk, writes a trimmed domain back to disk, and exits. The plan below describes how to decompose this CLI into **independently developable services** (in-process, ports-and-adapters) so individual features can be added, rewritten, or replaced in isolation. Chopper is **not** extensible through plugins, AI advisors, or MCP adapters -- those are not on the roadmap, not deferred, not planned. See Sec.12 for the scope-lock rationale.

**How to read this plan.** Sec.1-Sec.3 frame the shape. Sec.4-Sec.7 define the modules and their seams. Sec.8-Sec.10 pin down the contracts that make isolated feature work safe. Sec.11 covers determinism and performance. Sec.12 records the closed decisions. The acceptance-scenario catalog lives in [`tests/TESTING_STRATEGY.md`](../tests/TESTING_STRATEGY.md) Sec.5 and the contributor playbook in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## Table of Contents

1. [Framing: It Is a Local Python CLI](#1-framing-it-is-a-local-python-cli)
2. [Architectural Style -- Recommendation](#2-architectural-style--recommendation)
3. [Repository and Module Layout](#3-repository-and-module-layout)
4. [Service Catalog](#4-service-catalog)
5. [Ports (Protocols) and Adapters](#5-ports-protocols-and-adapters)
6. [Orchestration and the Context Object](#6-orchestration-and-the-context-object)
7. [Extension Seams (Not Applicable)](#7-extension-seams-not-applicable)
8. [Diagnostic Emitter / Collector Contract](#8-diagnostic-emitter--collector-contract)
9. [Inter-Service Communication Contract](#9-inter-service-communication-contract)
10. [Feature Work Isolation Rules](#10-feature-work-isolation-rules)
11. [Determinism, Concurrency, and Performance Envelope](#11-determinism-concurrency-and-performance-envelope)
12. [Closed Decisions](#12-closed-decisions)

---

## 1. Framing: It Is a Local Python CLI

The user's ask was phrased as "service-oriented, context-aware." Taken literally that would mean networked microservices, which is the wrong shape for this workload. The right shape -- and the one this plan delivers -- keeps the engineering essence of SOA **in a single Python process**:

| You asked for | What it means for a local CLI |
|---|---|
| Service-oriented | Each of the 7 pipeline phases is a **service class** with a single `run(...)` method. Services do not import each other. |
| Modular / isolated feature work | One feature = one service module = one stage gate. Change it end-to-end without touching siblings. |
| Context-aware | All cross-cutting state (paths, flags, clock, filesystem, sinks) lives on a single `ChopperContext` -- a service bundle plus run config with stable port bindings (Sec.6.1) -- passed explicitly. No globals, no singletons. |
| Cloud / network services | **Not in scope.** Chopper is a desktop/grid CLI. No HTTP, no IPC, no message bus. |
| Plugin host / MCP / AI advisors | **Not in scope, not deferred, not planned.** Chopper is a self-contained CLI. Any proposal to add a plugin loader, AI integration, or network surface is rejected on sight (Sec.12 Q1). |

**Named pattern:** Hexagonal (ports-and-adapters) + Pipeline. This is the shape Ruff, mypy, Pylint, dbt-core, and Snakemake converge on -- all are local single-process tools with strong modularity and swappable backends.

**Your ask was not vague.** It maps cleanly to Hexagonal + Pipeline. The only word this plan tightens is "service-oriented": locally, that means *service classes behind ports*, not *services across a network*.

---

## 2. Architectural Style -- Recommendation

| Option | Fit for Chopper | Verdict |
|---|---|---|
| Flat monolith (everything in one package, phases call each other) | Ships fast, but couples phases and kills isolated feature work | **Reject** |
| **Modular monolith + Hexagonal (ports/adapters) + Pipeline** | Matches the 8-phase architecture doc contract, preserves determinism, enables isolated stage work | **Recommended** |
| Networked microservices | Requires IPC, serialization, process lifecycle -- zero business benefit for a <1 GB, 5-min run | Reject |
| Event-driven bus | Eventual consistency inside a deterministic pipeline is a contradiction | Reject |
| Serverless / lambda | Anti-fit for filesystem-heavy workloads on VLSI checkouts | Reject |

**Why the recommendation wins:**

- Preserves the architecture doc's 8-phase contract (P0-P7) and determinism guarantees.
- Aligns 1:1 with the Stage 0-5 build model in [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md).
- Cross-module data flow is typed frozen dataclasses -- services cannot corrupt each other's state.

---

## 3. Repository and Module Layout

Authoritative layout of `src/chopper/` as of v4.11.0. Every file below exists on disk; `__init__.py` and `__pycache__/` elided for brevity.

```
src/chopper/
+-- __main__.py                  # `python -m chopper` -> cli.main
+-- core/                        # Stage 0 -- no deps on sibling modules
|   +-- models_common.py         # Shared primitives: FileTreatment, DomainState, FileStat
|   +-- models_parser.py         # P2 parser records: ProcEntry, ParsedFile, ParseResult
|   +-- models_config.py         # P1 JSON/config records: BaseJson, FeatureJson, LoadedConfig
|   +-- models_compiler.py       # P3/P4 records: CompiledManifest, DependencyGraph, StageSpec, ...
|   +-- models_trimmer.py        # P5 trimmer/generator records: TrimReport, GeneratedArtifact
|   +-- models_audit.py          # P7/run records: RunRecord, RunResult, AuditManifest, LocReport
|   +-- diagnostics.py           # Severity, Phase, Diagnostic, code registry guard
|   +-- _diagnostic_registry.py  # Machine-generated band -> code mapping (mirrors DIAGNOSTIC_CODES.md)
|   +-- errors.py                # Exception types (programmer errors only)
|   +-- protocols.py             # Ports: FileSystemPort, DiagnosticSink, ProgressSink
|   +-- context.py               # ChopperContext + RunConfig (service bundle, Sec.6.1)
|   +-- layout.py                # source_root(ctx): the one backup-else-domain rule (architecture Sec.2.8)
|   +-- serialization.py         # JSON encode/decode for all models
|   +-- globs.py                 # glob_match: the one Sec.6.3.1 glob matcher (P1, P1 validation, P3)
|   +-- tool_commands.py         # Vendor-tool command pool parser (TI-01)
|   +-- file_perms.py            # Cross-phase permission helpers (ensure_executable, mirror_perms_plus_exec)
|   +-- fs_walk.py               # Domain walk + copy helpers (iter_domain_files, walk_files, copy_tree)
|   +-- header.py                # Intel-standard copyright header for generated files
|   +-- provenance_markers.py    # Sec.3.11 marker text (F2 procs, F3 steps/stages)
|
+-- adapters/                    # Concrete implementations of ports (ctx.fs / ctx.diag / ctx.progress only)
|   +-- fs_local.py              # LocalFS
|   +-- fs_memory.py             # InMemoryFS (tests, chopper loc projection)
|   +-- sink_collecting.py       # CollectingSink (default)
|   +-- progress_rich.py         # RichProgress
|   +-- progress_silent.py       # SilentProgress
|
+-- data/                        # Bundled static data consumed at runtime
|   +-- tool_commands/           # Vendor tool-command pools (auto-loaded; see Sec.3.10 in architecture doc)
|       +-- pt.commands          # PrimeTime (~1 050 commands)
|       +-- pwr.commands         # PrimePower (~1 110)
|       +-- pe.commands          # PrimeECO (~1 000)
|       +-- ps.commands          # PrimeSim (~1 000)
|       +-- fm.commands          # Formality (~650)
|       +-- pc.commands          # PrimeClosure (~350)
|
+-- parser/                      # Stage 1 -- Tcl static analysis (P2)
|   +-- service.py               # ParserService.run(ctx, files) -> ParseResult
|   +-- tokenizer.py             # Tcl state machine tokenizer
|   +-- proc_extractor.py        # ProcEntry extraction from token stream
|   +-- namespace_tracker.py     # LIFO namespace stack
|   +-- call_extractor_body.py   # Call-site extraction from proc bodies
|   +-- call_extractor_classify.py  # Call classification (local / qualified / dynamic)
|   +-- call_extractor_constants.py # Constant patterns for call recognition
|   +-- call_extractor_sources.py   # Source-reference extraction
|   +-- call_extractor_structural.py # Structural call patterns (namespace eval, etc.)
|
+-- config/                      # Stage 2a -- JSON loading (part of P1)
|   +-- service.py               # ConfigService.run(ctx, state) -> LoadedConfig
|   +-- loaders.py               # File I/O + depends_on topo-sort
|   +-- schema.py                # jsonschema validation adapters
|
+-- compiler/                    # Stage 2b -- Merge + trace + F3 (P3, P4)
|   +-- merge_service.py         # CompilerService.run(...) -- R1 ordered-overlay fold
|   +-- trace_service.py         # TracerService.run(...) -- BFS call-tree trace
|   +-- flow_resolver.py         # F3 flow-action resolver (add_stage_after, replace_steps, ...)
|   +-- stack_graph.py           # Stage dependency graph + Kahn topo-sort for aggregate stacks
|
+-- trimmer/                     # Stage 3a -- Trim state machine (P5a, P5c, P5d)
|   +-- service.py               # TrimmerService.run(...) -- P5a dispatch loop
|   +-- file_writer.py           # FULL_COPY / PROC_TRIM / REMOVE file dispatch
|   +-- proc_dropper.py          # Atomic proc-body deletion from Tcl files
|   +-- indentation.py           # TclIndentationService -- P5c opt-in normaliser
|   +-- companion_sync.py        # CompanionSyncService -- P5d companion-file sync
|   +-- input_preserver.py       # P5a tail: mirror jsons/ + out-of-tree inputs into rebuilt domain
|   +-- p4_checkout.py           # --p4 open-for-edit of the live domain before the rebuild
|
+-- generators/                  # Stage 3b -- Run-file emission (P5b)
|   +-- service.py               # GeneratorService.run(...)
|   +-- stage_emitter.py         # F3 <stage>.tcl writer
|   +-- stack_emitter.py         # F3 <stage>.stack writer (N/J/L/D/I/O/R format)
|   +-- vars_emitter.py          # v2 <flow>_feature_vars.tcl writer
|
+-- audit/                       # Stage 3c -- .chopper/ writes (P7)
|   +-- service.py               # AuditService.run(...)
|   +-- writers.py               # Per-artifact writers (JSON, txt, logs)
|   +-- hashing.py               # Deterministic content hashing for manifests
|   +-- sloc.py                  # SLOC counting orchestrator (cloc -> fallback strategy)
|   +-- cloc_backend.py          # cloc.pl invocation + JSON result parsing
|   +-- internal_error.py        # internal-error.log writer (exit-3 path)
|   +-- vendor/                  # Vendored third-party tools
|       +-- cloc.pl              # cloc v2.x (Perl; used by cloc_backend.py)
|
+-- validator/                   # Stage 4 -- Pre+post validation (P1, P6)
|   +-- functions.py             # validate_pre(ctx, loaded), validate_post(ctx, manifest, graph, rewritten)
|
+-- orchestrator/                # The single composer (architecture Sec.5.2)
|   +-- runner.py                # ChopperRunner, Providers, default_providers(), RunLedger, execute_output()
|   +-- projection.py            # chopper loc: in-memory P5 replay + LoC accounting
|   +-- domain_state.py          # DomainStateService (P0)
|   +-- gates.py                 # Phase-boundary gating logic
|
+-- app/                         # Front-end-neutral use cases (architecture Sec.5.11.2); no print, no SystemExit, no argv
|   +-- errors.py                # AppIssue / AppError -- typed use-case failures (code, message, hint, detail)
|   +-- domain.py                # Domain resolution: path / $ward logical name (VE-32/33/34), _backup redirect, cwd fallback
|   +-- catalog.py               # Base / project-config discovery, feature-name lookup (VE-36), feature-dir expansion
|   +-- session.py               # RunConfig building (VE-35/36), VE-13 preflight, context factory, run, LoC, cleanup, crash log
|   +-- trim_stats.py            # Per-file before/after rows for the post-trim statistics table
|
+-- cli/                         # Stage 5 -- thin CLI (argparse, rendering, exit mapping only)
    +-- main.py                  # argparse entrypoint
    +-- commands.py              # validate / trim / loc / cleanup handlers + one multi-domain loop
    +-- render.py                # Rich-based output formatting (diagnostics, tables, LoC report)
```

**The dependency rule is strict and enforced at CI** (`import-linter`):

```
cli -> app -> orchestrator -> services -> core (ports + models)
                                             ^
adapters ------------------------------------+
```

- `core` imports nothing from siblings -- only stdlib.
- Service packages (`parser`, `compiler`, `trimmer`, ...) import only from `core`.
- `adapters` import from `core` and third-party libs.
- `orchestrator` imports from `core` + every service + selects adapters. `runner.default_providers()` is the only place phase implementations are constructed.
- `app` imports from `core`, `adapters`, `orchestrator`, and the leaf helpers it reads (`audit.sloc` for SLOC counts, `audit.internal_error` for the crash log).
- `cli` imports from `core`, `app`, and `adapters` only -- never a phase service, the orchestrator, or audit (import-linter contract "CLI is a thin adapter over the application layer").
- **No `plugins/`, no `advisor/`, no `mcp/` directory exists or is planned.** These are not v1-deferred features -- they are permanently excluded (see Sec.12 Q1). Any PR that creates such a directory is rejected without review. The read-only stdio MCP server that briefly existed under `src/chopper/mcp/` (0.4.0-3.5.x) was **removed in 4.0.0**; MCP is a closed decision and `adapters/mcp_*.py` or any MCP surface remains forbidden.

Circular imports, inter-service imports, and reverse imports (service importing orchestrator or cli) are all rejected at CI.

---

## 4. Service Catalog

Each service is a class with a single public `run(...) -> TypedResult`. Services are **stateless between invocations**; all state flows via `ChopperContext` and the typed result objects.

| Service | Phase(s) | Input -> Output | Where it lives |
|---|---|---|---|
| `DomainStateService` | P0 | `ctx` -> `DomainState` | `orchestrator/domain_state.py` |
| `ConfigService` | P1 | `ctx, state` -> `LoadedConfig` | `config/service.py` |
| `validate_pre` (function) | P1 | `ctx, loaded` -> emits diagnostics | `validator/functions.py` |
| `ParserService` | P2 | `(ctx: ChopperContext, files: Sequence[Path], *, loaded: LoadedConfig | None = None) -> ParseResult` | `parser/service.py` |
| `CompilerService` | P3 | `ctx, loaded, parsed` -> `CompiledManifest` | `compiler/merge_service.py` -- **Ordered overlay implementation required.** Apply layers in declared order: `base` first, then each entry of `loaded.features` left-to-right. For each layer, fold its `files.include` / `files.exclude` / `procedures.include` / `procedures.exclude` into the running file/proc set produced by previous layers; the **last layer that mentions a file or proc wins**. Any transition that changes a prior decision (a later layer cancels an include, removes a proc that was kept, or downgrades a whole-file include to PROC_TRIM) emits `VW-21 layer-shadowed` with `(layer, prior_layer, action)` provenance. Feature ordering is authoritative for F1, F2, **and** F3 (was F3-only). The previous two-pass per-source classification + cross-source aggregation is gone; do not reintroduce a pass that collects per-source contribution sets and then resolves cross-source conflicts -- that is the additive-only model and was retired in 2.0.0-alpha (see [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) Sec.4 R1, Sec.5.3). |
| `TracerService` | P4 | `ctx, manifest, parsed, loaded?` -> `DependencyGraph` | `compiler/trace_service.py` |
| `TrimmerService` | P5a | `ctx, manifest, parsed, state` -> `TrimReport` | `trimmer/service.py` |
| `GeneratorService` | P5b | `ctx, manifest` -> `tuple[GeneratedArtifact, ...]` | `generators/service.py` |
| `TclIndentationService` | P5c | `ctx, manifest, trim_report, artifacts, *, enabled` -> `(TrimReport, tuple[GeneratedArtifact, ...], tuple[Path, ...])` -- opt-in via `base.options.indent` (default off) | `trimmer/indentation.py` |
| `CompanionSyncService` | P5d | `ctx: ChopperContext, manifest: CompiledManifest, trim_report: TrimReport` -> `TrimReport` | `trimmer/companion_sync.py` -- filters `default_config.<sfx>.csv` and `default_milestone.<sfx>.tcl` companion files for every `PROC_TRIM` `default_rules.<sfx>.tcl` file; uses the final PI set from `manifest.proc_decisions`; emits `VW-24 companion-file-missing` / `VI-04 companion-sync-applied`; updates companion `bytes_out` in the returned `TrimReport`. |
| `validate_post` (function) | P6 | `ctx, manifest, graph, rewritten` -> emits diagnostics | `validator/functions.py` |
| `AuditService` | P7 | `ctx, record` -> `AuditManifest` | `audit/service.py` |

**Every service has exactly one public method named `run(...)`.** Pre- and post-validation are plain module-level functions (`validate_pre`, `validate_post` in `validator/functions.py`) -- they read inputs and emit diagnostics; no service class is warranted. Every other pipeline step is a service class with one `run()` method.

**Key discipline:** Services **do not** call each other directly. They return typed results; the orchestrator decides what flows where. This is what makes isolated feature development possible -- you can rewrite `TracerService` without touching `CompilerService` because neither imports the other.

**Minimal service base (informal, by convention -- not inherited):**

```python
# Every service module exposes a class with this shape.
class SomeService:
    def run(self, ctx: ChopperContext, *typed_inputs) -> TypedResult:
        # 1. Read inputs via ctx.fs (never Path.read_text directly).
        # 2. Compute.
        # 3. Emit diagnostics via ctx.diag.emit(...).
        # 4. Return a frozen dataclass result.
        ...
```

No ABC, no decorator magic, no framework. A service is a class with `run`. That is the entire interface.

---

## 5. Ports (Protocols) and Adapters

Ports live in `src/chopper/core/protocols.py` as `typing.Protocol` definitions. Adapters live in `src/chopper/adapters/`.

| Port | Responsibility | Default Adapter (v1) | Alternate Adapters |
|---|---|---|---|
| `FileSystemPort` | `read_text` / `write_text` / `exists` / `list` / `stat` / `rename` / `remove` / `mkdir` / `copy_tree` | `LocalFS` | `InMemoryFS` (tests), `ReadOnlyFS` (dry-run) |
| `DiagnosticSink` | `emit(Diagnostic)` / `snapshot()` / `finalize()` | `CollectingSink` | `JSONLSink` (audit) |
| `ProgressSink` | `phase_started` / `phase_done` / `step` | `RichProgress` | `SilentProgress` |

**Only two progress adapters exist.** Under `--plain`, no new `PlainProgress` class is introduced -- `RichProgress` is instantiated with a `rich.Console(no_color=True, force_terminal=False, legacy_windows=False)` and the live progress bar is disabled, so it emits single-line ASCII status messages. Same class, reconfigured. The CLI selects the adapter as follows: `-q / --quiet` -> `SilentProgress`; `--plain` -> `RichProgress` in ASCII/no-color mode; otherwise -> `RichProgress` in styled mode.

**No `ClockPort`, no `SerializerPort`, no `AuditStore`, no `TableRenderer` port.** Each was considered at design time and cut:

- **Clock** -- `datetime.now(timezone.utc)` is called directly by `AuditService`. Tests use `freezegun` or `monkeypatch` to freeze time. Two call sites do not warrant a port.
- **Serialization** -- `core/serialization.py` exposes a single helper `dump_model(obj) -> str` (`json.dumps(asdict(obj), sort_keys=True, default=_encode)`). Services and `AuditService` call it directly. No port, no `ctx.serde`.
- **Audit storage** -- `AuditService.run()` writes its fixed audit artifacts directly via `ctx.fs.write_text(ctx.config.audit_root / name, ...)`. Tests point `audit_root` at an `InMemoryFS` path; no separate store abstraction.
- **Table renderer** -- rendering is a CLI concern. `cli/render.py` calls `rich.print` / `rich.Table` directly. Services never render. One output path, not a three-adapter matrix.

**`FileSystemPort` -- the full honest surface.** Trimmer, domain-state detection, and audit all need more than `read_text` / `write_text`. The complete port is:

```python
class FileSystemPort(Protocol):
    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str: ...
    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...
    def exists(self, path: Path) -> bool: ...
    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]: ...  # sorted
    def stat(self, path: Path) -> FileStat: ...           # size, mtime, is_dir
    def rename(self, src: Path, dst: Path) -> None: ...   # e.g. domain/ -> domain_backup/
    def remove(self, path: Path, *, recursive: bool = False) -> None: ...
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...
    def copy_tree(self, src: Path, dst: Path) -> None: ...
    # CONTRACT: copy_tree must NEVER copy a .chopper/ subdirectory from src into dst.
    # LocalFS skips any child named ".chopper" at the top level of src during the
    # recursive copy. InMemoryFS must enforce the same exclusion. This guarantees
    # that each trim run starts with a fresh .chopper/ and that backup metadata
    # never contaminates the rebuilt domain (architecture doc Sec.2.4).
```

Services never call `pathlib.Path.read_text()`, `Path.rename()`, `shutil.rmtree()`, or `os.makedirs()` directly. Everything goes through `ctx.fs.*`. `InMemoryFS` implements the full surface so every service is unit-testable without hitting disk.

**Written surface is constrained.** `ctx.fs.write_text` / `remove` / `rename` / `mkdir` may only target `ctx.config.domain_root`, `ctx.config.backup_root`, or `ctx.config.audit_root`. Any other target is a programmer error and raises -- enforced by `LocalFS` at adapter level, not by services. This prevents silent scope creep into sibling domains or shared infrastructure.

**Path resolution is a service responsibility.** Adapters receive whatever path the caller hands them; they do not auto-resolve against a domain root. Services own the rule: pipeline data structures (models, diagnostics, audit artifacts) store **domain-relative** paths for byte-stable cross-machine artifacts, and each service absolutises at the moment of I/O by prepending `ctx.config.domain_root`. This separation keeps `LocalFS` and `InMemoryFS` interchangeable without either knowing what "domain" means, while preserving the determinism guarantees of the serialised surface.

**No `LockPort`.** Chopper is a single-user, single-process, single-invocation tool against a single on-disk domain. There is no lock, no concurrency guard, no stale-lock recovery. Two users racing the same domain is an operator-level mistake, not an architectural concern -- if it happens, the second invocation will see a half-written state from `DomainStateService` and abort with a normal validation error. The CLI reference makes this policy explicit.

**Why Protocols, not ABCs.** Structural typing lets test fakes satisfy a port without importing Chopper internals. A test fake is just any object with the right method names; no inheritance.

**Port count is deliberately small.** Three ports (`FileSystemPort`, `DiagnosticSink`, `ProgressSink`) cover every effectful surface Chopper needs. Everything else (clock, serialization, audit, rendering) is a direct call or a plain helper. Port abstractions for single-implementation concerns add ceremony without testability benefit.

---

## 6. Orchestration and the Context Object

### 6.1 Honest naming

`ChopperContext` is a **port bundle plus run config**, not an immutable data record. Its three port fields (`fs`, `diag`, `progress`) are all effectful; the rest is `config: RunConfig` (frozen flags and paths). `@dataclass(frozen=True)` on the wrapper only guarantees that **port bindings cannot be rebound mid-run** -- it does not make the ports themselves pure. Contributors should read `ctx.<port>.<method>(...)` as "call into a possibly-effectful adapter."

**Rendering is not on `ctx`.** Rendering is a CLI concern; services never render. `cli/render.py` calls `rich.print` directly on the `RunResult` returned by `ChopperRunner.run()`. There is no `TableRenderer` port.

To make the split visible in code, the context is composed of two inner records:

```python
# core/context.py
@dataclass(frozen=True)
class RunConfig:
    """Pure engine-behavior config. No methods, no effects. Consumed by services."""
    domain_root: Path
    backup_root: Path
    audit_root: Path                     # .chopper/ -- reserved; see architecture doc Sec.5.5
    strict: bool                         # exit-code policy, applied at CLI (Sec.8.2)
    dry_run: bool
    # Optional / name-mode fields (None in path-mode)
    ward_root: Path | None               # $ward root from name-mode --domain resolution (4.1.0+)
    domain_logical_name: str | None      # "vendor/name" resolved via $ward/global/ (4.1.0+)
    project_config_path: Path | None     # auto-discovered .project.features.config path (4.2.0+)
    # No `mode` field. The CLI dispatches on subcommand name (`validate` / `trim` /
    # `cleanup`); `cleanup` never enters ChopperRunner at all (it is a standalone
    # `shutil.rmtree(<domain>_backup)` function).


@dataclass(frozen=True)
class PresentationConfig:
    """CLI-side UX config. Drives adapter selection; never read by services."""
    verbose: bool = False                # -v   : raise progress verbosity (DEBUG-ish detail)
    quiet: bool = False                  # -q   : SilentProgress; suppresses progress output
    plain: bool = False                  # --plain : no Rich rendering; plain text + no ANSI colors
    # `--debug`, `--no-color`, `--json` were considered and cut. Rich honors NO_COLOR
    # automatically; exit-code-3 writes .chopper/internal-error.log; diagnostics.json
    # in the audit bundle is the machine-readable surface (tracked as FD-10).


@dataclass(frozen=True)
class ChopperContext:
    """Port bundle + run config. Frozen bindings; ports are effectful."""
    config: RunConfig

    # Effectful ports (stateful adapters; fresh instance per run).
    fs: FileSystemPort
    diag: DiagnosticSink
    progress: ProgressSink
    # No clock / serde / audit ports. Services call datetime.now(timezone.utc),
    # core.serialization.dump_model(), and ctx.fs directly.
```

**Flag-to-adapter mapping (CLI responsibility; see [`user_docs/02_CLI_GUIDE.md`](../user_docs/02_CLI_GUIDE.md) for flag definitions).**

| `PresentationConfig` field | Source flag | Effect |
|---|---|---|
| `verbose` | `-v / --verbose` | CLI progress renderer prints DEBUG-level detail; library code has no internal logger (architecture doc Sec.5.12.4). |
| `quiet` | `-q / --quiet` | `ProgressSink` = `SilentProgress`; no progress output (CI / grid). |
| `plain` | `--plain` | `ProgressSink` = `RichProgress` reconfigured with `Console(no_color=True, force_terminal=False)` and the live progress bar disabled. Output is ASCII single-line status -- no ANSI, no Unicode box-drawing, no spinners. No dedicated `PlainProgress` class. |

`SilentProgress` is used by `-q / --quiet` and by test harnesses. Rich honors the `NO_COLOR` environment variable automatically -- no dedicated flag is required.

**Construction rules.**

- Built exactly once per run -- by `app/session.py` in production (on behalf of whichever front end is running), by `make_test_context()` in tests.
- Never mutated. Port *bindings* are fixed; port *state* may change via method calls.
- Services receive `ctx` plus the typed inputs they declare -- nothing else. No module-level globals, no singletons, no thread-locals.
- Services read only `ctx.config` (the `RunConfig`). `PresentationConfig` is CLI-local and never enters the service layer.

### 6.2 The runner

`ChopperRunner.run()` is the only place phases are sequenced (architecture doc Sec.5.2, single composer). It reads phase implementations from a `Providers` bundle and records results in a private `RunLedger`:

```python
# orchestrator/runner.py
@dataclass(frozen=True)
class Providers:                       # typed callables; one per phase implementation
    domain_state, load_config, validate_pre, parse, compile, trace,
    trim, generate, indent, sync_companions, preserve_inputs, validate_post, audit


def default_providers() -> Providers:  # the single composition root
    return Providers(domain_state=DomainStateService().run, load_config=ConfigService().run, ...)


def execute_output(ctx, providers, ledger, *, manifest, parsed, state, gated) -> TrimReport | None:
    """P5a trim -> P5b generate -> P5c indentation -> P5d companion sync.
    Writes each result into the ledger as it lands. Returns None on a gated P5 error."""
    ledger.trim_report = providers.trim(ctx, manifest, parsed, state)
    if gated and has_errors(ctx, Phase.P5_TRIM): return None
    ledger.artifacts = providers.generate(ctx, manifest)
    ledger.trim_report, ledger.artifacts, ledger.rewritten = providers.indent(ctx, ...)
    if gated and has_errors(ctx, Phase.P5_TRIM): return None
    ledger.trim_report = providers.sync_companions(ctx, manifest, ledger.trim_report)
    return ledger.trim_report


class ChopperRunner:
    def __init__(self, providers: Providers | None = None): ...

    def run(self, ctx, *, command) -> RunResult:
        p = self._providers or default_providers()
        ledger = RunLedger()
        try:
            ledger.state  = p.domain_state(ctx)                          # P0 -- case 4 -> exit 2
            ledger.loaded = p.load_config(ctx, ledger.state)             # P1a
            p.validate_pre(ctx, ledger.loaded)                           # P1b -- gate P1
            ledger.parsed   = p.parse(ctx, ledger.loaded.surface_files, loaded=ledger.loaded)  # P2 -- gate
            ledger.manifest = p.compile(ctx, ledger.loaded, ledger.parsed)                     # P3 -- gate
            ledger.graph    = p.trace(ctx, ledger.manifest, ledger.parsed, ledger.loaded)      # P4 -- no gate
            if not ctx.config.dry_run:
                if execute_output(ctx, p, ledger, ..., gated=True) is None: return ledger.result(ctx, 1)
                p.preserve_inputs(ctx, ledger.loaded)                    # P5a tail (jsons/ mirror)
                p.validate_post(ctx, ..., ledger.rewritten, trim_report=ledger.trim_report)  # P6 -- gate
            else:
                ledger.artifacts = p.generate(ctx, ledger.manifest)      # in-memory only on dry-run
                p.validate_post(ctx, ..., rewritten=(), generated_artifacts=ledger.artifacts, trim_report=None)
            return ledger.result(ctx, 0 or 1 under --strict with warnings)
        except Exception:
            ledger.exit_code = 3                                         # + internal-error.log
        finally:
            # P7 audit always runs (except `loc`) -- even on exceptions, even on early return --
            # from whatever the ledger holds at that moment. Audit failure is reported on stderr
            # and never masks the primary failure.
            if command != "loc": p.audit(ctx, ledger.record(...))
```

`chopper loc` calls the same `execute_output()` against an in-memory copy of the source tree with `gated=False` (`orchestrator/projection.py`), so the P5 order exists exactly once. Swapping a phase implementation means passing `ChopperRunner(providers=replace(default_providers(), trim=my_trim))`; nothing else changes.

**Gate semantics (explicit).** `_has_errors(ctx, phase)` inspects `ctx.diag.snapshot()` and returns `True` iff any diagnostic with `severity == ERROR` and `phase == <phase>` is present. **Severity is never rewritten by the gate.** `--strict` does not affect gating -- see Sec.8.2 rule 4. On abort, the runner returns a `RunResult` with `exit_code=1`; the `finally` block guarantees `AuditService` runs so `.chopper/` gets whatever artifacts are reachable.

**Phase-gate policy (summary).**

| Phase | Emits | Gated? | Rationale |
|---|---|---|---|
| P0 `DomainStateService` | -- | No | Never emits `ERROR` diagnostics; filesystem failures raise at the port boundary (CLI emits `VE-21` / `VE-23`). |
| P1 `ConfigService` + `validate_pre` | `VE-*` | **Yes** | Invalid input must not reach parser. |
| P2 `ParserService` | `PE-*` | **Yes** | A corrupted proc index corrupts everything downstream; abort before P3. |
| P3 `CompilerService` | `VE-*` compiler | **Yes** | Manifest contradictions (e.g. `VE-05`) must not reach the trimmer. |
| P4 `TracerService` | `TW-*` | No | Reporting-only; tracer emits only warnings. Internal invariant violations raise -> exit 3. |
| P5 `TrimmerService` + `GeneratorService` | `VE-*` trimmer | **Yes** | A failed trim must not emit run-files into a broken tree. No staging; failure leaves `<domain>/` half-rebuilt and `<domain>_backup/` intact (architecture doc Sec.2.8). |
| P6 `validate_post` | `VE-*` + `VW-*` | **Yes** (error only) | Final correctness gate before a successful exit. |
| P7 `AuditService` | `VI-*` | No | Always runs in `finally`; never gates. |

**Rollback model.** There is no staging tree and no atomic promotion. If P5 fails, `<domain>/` is left in whatever half-rebuilt state the failure produced, and `<domain>_backup/` is untouched. On the next invocation, `DomainStateService` observes both directories and classifies the state as Case 2 (re-trim); `TrimmerService` treats `<domain>_backup/` as the source of truth and rebuilds `<domain>/` from scratch. Operators who want a pristine restart may run `rm -rf <domain> && mv <domain>_backup <domain>` manually. The registered codes covering the P5 gate are `VE-23`, `VE-24`, `VE-25`, `VE-26` in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).

---

## 7. Extension Seams (Not Applicable)

**Chopper has no general extension seams.** There is no plugin host, no plugin loader, no observer fan-out, no MCP server, no MCP client, no AI advisor, no `X*` diagnostic family, no `adapters/mcp_*.py`, no `mcp/` package, no `plugins/` package. These are not stubs, not reserved, not "architecturally enabled" for a later release -- they are **permanently out of scope** (see Sec.12 Q1). The read-only stdio MCP server introduced in 0.4.0 was removed in 4.0.0 and MCP is again a closed decision.

**Why this is stated explicitly.** Previous drafts reserved MCP/plugin seams "for future use." Experience showed that reservations drift into implementations: an agent reading "reserved" treats it as "TODO", a contributor fills in the TODO, and a feature the project never approved ships anyway. Scope-lock requires the absence of reservations, not a list of them.

**What this means operationally.**

- No code path references `PluginHost`, `TeeSink`, `MCPProgressBridge`, `EntryPointPluginHost`, `advisor`, or similar identifiers.
- No diagnostic code in the `XE-*` / `XW-*` / `XI-*` space is defined or reserved.
- No `adapters/mcp_*.py`, `plugins/`, `mcp_server/`, or `advisor/` module exists in the tree (Sec.3).
- No "post-v1" or "stage 6" roadmap row carries plugin or MCP content.
- Any PR that adds any of the above is rejected at review without further discussion.

If a future release genuinely needs a plugin mechanism, it starts a fresh design doc and updates [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) first. It does not resurrect stubs from this plan.

**The provider bundle is not a seam.** `ChopperRunner(providers=...)` (Sec.6.2) takes a typed, frozen bundle of callables as an ordinary constructor argument. There is no discovery, no registry, no entry-point loading, and no runtime insertion of phases; `default_providers()` is a plain function that names every implementation. It exists so one phase implementation can be replaced (by a test or by a later in-tree rewrite) without touching the others.

---

## 8. Diagnostic Emitter / Collector Contract

This is the **single communication spine** for user-visible outcomes. Every service uses it; nothing else is allowed to surface user-facing messages.

### 8.1 Data shape

```python
# core/diagnostics.py
class Severity(Enum):
    ERROR = "error"; WARNING = "warning"; INFO = "info"

class Phase(IntEnum):
    P0_STATE = 0; P1_CONFIG = 1; P2_PARSE = 2; P3_COMPILE = 3
    P4_TRACE = 4; P5_TRIM = 5; P6_POSTVALIDATE = 6; P7_AUDIT = 7

@dataclass(frozen=True)
class Diagnostic:
    code:     str                 # e.g. "VE-06" -- must exist in DIAGNOSTIC_CODES.md
    slug:     str                 # e.g. "file-not-in-domain"
    severity: Severity
    phase:    Phase
    source:   str                 # service name: "parser", "compiler", ...
    message:  str                 # one-line, no newlines
    path:     Path | None = None
    line_no:  int  | None = None
    hint:     str  | None = None
    context:  Mapping[str, object] = field(default_factory=dict)  # JSON-safe
    dedupe_bucket: str = ""       # optional namespace for multi-context emission; default collapses across sites
```

**Invariants:**

- `code` MUST match a registered code in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md). Construction validates this against a compile-time registry; unknown codes raise immediately. Tests fail fast on typos.
- `Diagnostic` is immutable and hashable (default frozen-dataclass `__eq__` compares all fields).
- **Dedupe key is a subset of equality.** The sink deduplicates on `(code, path, line_no, message, dedupe_bucket)` -- *not* on full-field equality. Within a bucket, **last write wins**: a later `emit()` with the same key replaces the prior entry. Different buckets for the same `(code, path, line_no, message)` produce distinct entries; callers that need multi-context emission set distinct bucket values. Default bucket `""` preserves the original collapse-on-duplicate semantics. `hint` and `context` do not affect the dedupe key.
- `context` values must be JSON-serializable. No live objects.

### 8.2 Sink contract

```python
class DiagnosticSink(Protocol):
    def emit(self, d: Diagnostic) -> None: ...
    def snapshot(self) -> Sequence[Diagnostic]: ...    # read-only, ordered
    def finalize(self) -> DiagnosticSummary: ...       # counts by severity+family
```

**Rules binding every service:**

1. **No `print`, no user-facing `raise`.** Services call `ctx.diag.emit(...)`. Programmer errors stay as exceptions.
2. **No diagnostic is emitted twice within the same bucket.** Sinks dedupe on `(code, path, line_no, message, dedupe_bucket)`. Within a bucket, a later emit **replaces** the prior entry (last-write-wins), so callers can refine the `hint`/`context` of a previously-emitted diagnostic without duplication. Callers that want multiple concurrent entries for the same logical issue set distinct `dedupe_bucket` values.
3. **Ordering is emission order, preserved verbatim.** `snapshot()` returns diagnostics in the exact order `emit()` was called. The sink does **not** sort. Determinism of the user-visible diagnostic sequence follows from (a) single-threaded execution (Sec.11) and (b) a fixed phase sequence in `ChopperRunner.run()`. Services that iterate user data (files, procs) must iterate in a documented sorted order so their own emissions are reproducible across runs.
4. **`--strict` is an exit-code policy, not a severity rewrite.** Services always emit the nominal severity -- a `WARNING` stays a `WARNING` in the sink, in `diagnostics.json`, and in all rendered output, with or without `--strict`. Phase gates fire on nominal `ERROR` only (see Sec.6.2). At the very end of the run, the CLI computes the process exit code from `sink.finalize()`:
   - exit `0` -- no `ERROR`, and either `--strict` is off or no `WARNING` is present.
   - exit `1` -- any `ERROR`, **or** `--strict` is on and any `WARNING` is present. (No individual `VI-*` code is singled out; advisories do not affect the exit code.)
   - exit `2` -- CLI / pre-pipeline fatal conditions the runner never even enters: `VE-11` conflicting CLI options, `VE-13` unresolvable `--project` paths (authoring error; no partial recovery), `VE-21` missing domain + backup.
   - exit `3` -- unhandled exception escaped a service (programmer error). The outer `try / finally` in Sec.6.2 catches it, logs a stack trace to `.chopper/internal-error.log` via `AuditService`, and exits `3`. This is deliberately distinct from exit `1` so CI systems can tell "pipeline found a problem" from "Chopper itself broke."

   `--strict` never changes what the pipeline *does*, only how the caller *interprets* the outcome. The stored diagnostic severity is the truth; `--strict` is a policy layer on top. **There is no warn-to-error promotion anywhere in the pipeline or in the sink -- only in the final exit-code computation.**
5. **No fatal-on-first-error mode.** Default and only behavior: collect within a phase; stop at phase boundary if any `ERROR` is present (Sec.6.2). This simplifies recovery and matches the architecture doc.

### 8.3 `CollectingSink` guarantees (single-threaded)

- **Not thread-safe. Not required to be. No future-concurrency story.** v1 and every planned future version run single-threaded (Sec.11). The sink never needs a lock and never will. If some later version wants parallelism it is a brand-new design discussion, not an implicit promise this doc makes.
- **O(1) dedupe** via a set of equality keys. Duplicate emits never appear in `snapshot()`.
- **Append-only storage.** `snapshot()` returns an immutable view of the current list. No sort, no copy beyond what `Sequence[Diagnostic]` requires.
- **`finalize()`** returns a `DiagnosticSummary` (counts by severity and by family) used by the CLI for exit-code computation (Sec.8.2 rule 4) and by `AuditService` to write `diagnostics.json`.

### 8.4 Render path

```
Service -emit()-> CollectingSink -snapshot()-> CLI cli/render.py (Rich)
                        +-- AuditService -> .chopper/diagnostics.json (via core.serialization.dump_model)
```

The CLI is the **only** layer that formats for humans. Libraries stay silent.

### 8.5 Retired code slots

**Retired codes keep their slot.** A removed code is marked `RETIRED` in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) and its slot is never reused (today: `VW-18`, `VW-19`, `PE-04`). There is no `X*` plugin family -- see Sec.7 and Sec.12 Q1.

---

## 9. Inter-Service Communication Contract

Diagnostics are the user-facing spine. This section pins down how services hand **data** to each other. The rule is unambiguous: **services never call services; they return typed results and the orchestrator wires them.**

### 9.1 Shapes (frozen dataclasses, phase-owned imports)

Concrete dataclass definitions live in phase-owned `core/models_*.py` modules. Callers import each model from the module that owns its phase; for example, parser records from `chopper.core.models_parser`, compiler records from `chopper.core.models_compiler`, and audit/run records from `chopper.core.models_audit`.

```python
@dataclass(frozen=True)
class DomainState:
    case: Literal[1,2,3,4]               # architecture doc Sec.2.8 matrix (cases 1-4 only)
    domain_exists: bool
    backup_exists: bool

@dataclass(frozen=True)
class LoadedConfig:
    base: BaseJson
    features: tuple[FeatureJson, ...]    # topo-sorted by depends_on
    project: ProjectJson | None
    surface_files: tuple[Path, ...]      # all files named by any source

@dataclass(frozen=True)
class ProcEntry:
    canonical_name: str                  # "<domain-relative-posix-path>::<proc_name>"
    name:           str                  # bare proc name (without namespace prefix)
    qualified_name: str                  # fully-qualified name (namespace + bare name)
    start_line:     int                  # line of the `proc` keyword (1-based)
    end_line:       int                  # line of the closing `}` of the proc body (1-based)
    body_start_line: int                 # line of the opening `{` of the proc body
    body_end_line:   int                 # line of the closing `}` of the proc body
    source_file:    Path                 # domain-relative path to the source file
    # --- DPA and comment-banner span fields (required by TrimmerService for atomic drop) ---
    # All four fields are None when the corresponding block is absent or could not
    # be associated. P5 TrimmerService uses these to build each drop-range atomically.
    dpa_start_line:     int | None = None  # first line of define_proc_attributes/arguments block
    dpa_end_line:       int | None = None  # last line (inclusive) of DPA block, after continuations
    comment_start_line: int | None = None  # first line of the contiguous backward comment banner
    comment_end_line:   int | None = None  # last line of the banner (= start_line - 1)

@dataclass(frozen=True)
class ParsedFile:
    path: Path
    procs: tuple[ProcEntry, ...]
    unresolved_calls: tuple[CallSite, ...]
    encoding: Literal["utf-8", "latin-1"]
    # No `parse_errors` field. Parse errors are emitted into `ctx.diag` as they
    # are discovered -- the single user-facing channel (Sec.8.2 rule 1). A per-file
    # diagnostic accumulator is a parser-internal detail of `parse_file()` and
    # is flushed into `ctx.diag` at the service boundary; it never appears on
    # the public dataclass.

@dataclass(frozen=True)
class ParseResult:
    files: Mapping[Path, ParsedFile]     # sorted at construction
    index: Mapping[str, ProcEntry]       # canonical_name -> entry
    # Canonical name format is fixed by contract: "<domain-relative-posix-path>::<proc_name>"
    # (for example, "common/helpers.tcl::foo"). Enforced at ParseResult construction;
    # tests assert the format. See IMPLEMENTATION.md (pitfalls) TC-02.

@dataclass(frozen=True)
class CompiledManifest:
    file_decisions: Mapping[Path, FileTreatment]
    proc_decisions: Mapping[str, ProcDecision]    # surviving procs
    proc_removals:  Mapping[str, ProcRemoval]     # excluded procs (F2 provenance)
    provenance:     Mapping[Path, FileProvenance]
    stages:         tuple[StageSpec, ...]
    stack_order:    tuple[str, ...]               # topological aggregate-stack order
    options:        BaseOptions                   # base JSON `options`, frozen at P3;
                                                  # the only channel P5/P6 read switches from

@dataclass(frozen=True)
class DependencyGraph:
    nodes: tuple[str, ...]                         # canonical proc names, lex-sorted
    edges: tuple[Edge, ...]                        # (caller, callee), lex-sorted
    reachable_from_includes: frozenset[str]        # PI+ set, reporting-only

@dataclass(frozen=True)
class RunResult:
    # manifest and graph are None on early-abort paths (P1/P2/P3 gate fires before
    # the phase that produces them completes). CLI renderer must handle None gracefully
    # and display "pipeline aborted before <artifact> was available" in place of the
    # normal summary. AuditService tolerates None for both fields.
    manifest:    CompiledManifest | None
    graph:       DependencyGraph  | None
    diagnostics: Sequence[Diagnostic]
    exit_code:   int
    duration:    timedelta

# ---------------------------------------------------------------------------
# Stage 3 outputs -- returned by TrimmerService / GeneratorService / AuditService.
# All fields are JSON-serializable via core.serialization.dump_model; golden snapshots pin them.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileOutcome:
    path: Path                                  # domain-relative, POSIX
    treatment: FileTreatment                    # FULL_COPY | PROC_TRIM | GENERATED | REMOVE
    bytes_in:  int                              # size before trim (0 if new)
    bytes_out: int                              # size after trim (0 if removed)
    procs_kept:    tuple[str, ...]              # canonical names, lex-sorted
    procs_removed: tuple[str, ...]              # canonical names, lex-sorted

@dataclass(frozen=True)
class TrimReport:
    """Returned by TrimmerService.run -- drives .chopper/trim_report.{json,txt}.
    Architecture Doc Sec.P5a."""
    outcomes:           tuple[FileOutcome, ...]   # one per file in the domain, lex-sorted by path
    files_copied:       int
    files_trimmed:      int
    files_removed:      int
    procs_kept_total:   int
    procs_removed_total: int
    rebuild_interrupted: bool                     # True if P5a aborted after partial writes; next run rebuilds from backup

@dataclass(frozen=True)
class GeneratedArtifact:
    """A single file emitted by GeneratorService (P5b). Architecture Doc Sec.P5b / F3.
    Generated run files live alongside normal domain files; they are still
    subject to post-trim validation (P6)."""
    path:    Path                               # domain-relative, POSIX
    kind:    Literal["stack", "tcl", "csv"]     # architecture doc Sec.F3 output kinds
    content: str                                # full generated text
    source_stage: str                           # which StageSpec produced it

@dataclass(frozen=True)
class AuditArtifact:
    name:    str                                # e.g. "trim_report.json"
    path:    Path                               # absolute, under ctx.config.audit_root
    size:    int
    sha256:  str                                # deterministic content hash

@dataclass(frozen=True)
class AuditManifest:
    """Returned by AuditService.run -- inventory of everything written under
    .chopper/. Architecture Doc Sec.P7. The manifest itself is the last thing written
    (as .chopper/chopper_run.json) so it describes the full bundle."""
    run_id:       str                           # ISO-8601 UTC start time
    started_at:   datetime
    ended_at:     datetime
    exit_code:    int
    artifacts:    tuple[AuditArtifact, ...]     # lex-sorted by name
    diagnostic_counts: Mapping[str, int]        # {"error": N, "warning": N, "info": N}
```

### 9.2 Service signatures (the whole public API)

| Service | Signature |
|---|---|
| `DomainStateService.run` | `(ctx: ChopperContext) -> DomainState` |
| `ConfigService.run` | `(ctx: ChopperContext, state: DomainState) -> LoadedConfig` |
| `ParserService.run` | `(ctx: ChopperContext, files: Sequence[Path], *, loaded: LoadedConfig | None = None) -> ParseResult` -- wraps the pure `parse_file()` utility described in [`technical_docs/IMPLEMENTATION.md` (parser section)](IMPLEMENTATION.md) Sec.1.2.1. The utility stays a small, callback-driven internal function (`on_diagnostic` forwards straight into `ctx.diag.emit(...)`); the service is what the orchestrator and other services actually depend on. Reading through `ctx.fs` (never `Path.read_text` directly) is the service's job -- the utility takes already-decoded text. **O1 optimization:** when `loaded` is provided and `loaded.domain_file_cache` is non-empty (P1 walked the domain for glob expansion), the full-domain harvest phase filters the cache for `.tcl` files instead of re-walking the filesystem. **Path normalization contract:** `ParserService.run()` normalises every path in `files` to a domain-relative POSIX string before passing it to `parse_file()`. The canonical-name prefix in every `ProcEntry.canonical_name` and in every key of `ParseResult.index` is therefore always a domain-relative POSIX path (e.g. `"procs/core.tcl::setup"`). Neither absolute paths nor OS-native separators ever appear in the index. **I/O-boundary contract:** paths flow through the pipeline in domain-relative form (models, diagnostics, audit artifacts), but `ctx.fs.read_text(...)` calls are made against `ctx.config.domain_root / path` -- i.e. the parser absolutises only at the filesystem boundary. This keeps `LocalFS` (real disk) and `InMemoryFS` interchangeable without either adapter having to know what `domain_root` is. |
| `CompilerService.run` | `(ctx: ChopperContext, loaded: LoadedConfig, parsed: ParseResult) -> CompiledManifest` |
| `TracerService.run` | `(ctx: ChopperContext, manifest: CompiledManifest, parsed: ParseResult, loaded: LoadedConfig | None = None) -> DependencyGraph` |
| `TrimmerService.run` | `(ctx: ChopperContext, manifest: CompiledManifest, parsed: ParseResult, state: DomainState) -> TrimReport` |
| `GeneratorService.run` | `(ctx: ChopperContext, manifest: CompiledManifest) -> tuple[GeneratedArtifact, ...]` -- writes each generated file directly via `ctx.fs.write_text()` as it is produced; the returned tuple is handed to `TclIndentationService.run` for optional P5c indentation normalization (gated by `base.options.indent`, default off). |
| `TclIndentationService.run` | `(ctx: ChopperContext, manifest: CompiledManifest, trim_report: TrimReport, artifacts: tuple[GeneratedArtifact, ...]) -> tuple[TrimReport, tuple[GeneratedArtifact, ...], tuple[Path, ...]]` -- P5c live-only normalization pass. **Gated by `manifest.options.indent` (the base JSON's `options.indent`, default `false`).** When the option is off, the service is a no-op pass-through that returns `trim_report` and `artifacts` unchanged but still computes the rewritten-path tuple via `tcl_output_paths(manifest)` so P6's brace-balance check (`VE-16`) covers every PROC_TRIM and GENERATED `.tcl` output. When on, reads every emitted `.tcl` whose manifest treatment is `PROC_TRIM` or `GENERATED`, rewrites leading indentation with the legacy brace-driven rules, updates `TrimReport.bytes_out` for `PROC_TRIM` outcomes, updates generated Tcl artifact content, and returns the absolute Tcl path tuple consumed by `validate_post`. `FULL_COPY` outputs are always excluded (issue #22). The current formatter has known structural gaps (no quote/comment awareness, no line-continuation handling) documented inline in the architecture doc Sec.3.1 (`options.indent` row) and Sec.5.5 (P5c paragraph); leave the flag off unless the formatter has been explicitly verified for the domain in question. |
| `CompanionSyncService.run` | `(ctx: ChopperContext, manifest: CompiledManifest, trim_report: TrimReport) -> TrimReport` -- P5d companion-file sync. For every `PROC_TRIM` file whose basename matches `default_rules.<sfx>.tcl`, filters `default_config.<sfx>.csv` (removes data rows for non-surviving procs) and `default_milestone.<sfx>.tcl` (removes `change_config <ProcName>` lines for non-surviving procs). The surviving proc set is the final PI set from `manifest.proc_decisions`. Emits `VW-24 companion-file-missing` if a companion is absent; `VI-04 companion-sync-applied` on success. Returns an updated `TrimReport` with corrected `bytes_out` for modified `FULL_COPY` outcomes. |
| `validate_pre` | `(ctx: ChopperContext, loaded: LoadedConfig) -> None` -- plain module function in `validator/functions.py`; emits diagnostics. |
| `validate_post` | `(ctx: ChopperContext, manifest: CompiledManifest, graph: DependencyGraph, rewritten: Sequence[Path], *, generated_artifacts: Sequence[GeneratedArtifact] = (), trim_report: TrimReport | None = None, tool_command_pool: frozenset[str] = frozenset()) -> None` -- plain module function; emits diagnostics. `rewritten` contains final Tcl outputs rewritten or indentation-normalized during P5. `graph` is the P4 :class:`DependencyGraph`; VW-05 / VW-06 read resolved edges from it to detect calls/source-refs into trimmed-away procs/files without re-parsing. `manifest.options.cross_validate` gates the F3 step cross-checks. |
| `AuditService.run` | `(ctx: ChopperContext, record: RunRecord) -> AuditManifest` -- the runner assembles a :class:`RunRecord` in its `finally` block with whatever phase outputs were produced (manifest / graph / trim_report may be ``None``) and hands it to the audit service, which writes every artifact under `ctx.config.audit_root` via `ctx.fs.write_text()`. |

### 9.3 Communication rules

1. **No inter-service imports.** `compiler/` never imports from `parser/`; services import shared contracts through the phase-owned `core/models_*.py` modules. Enforced at CI by `import-linter`.
2. **All I/O through ports.** A service that reads a file calls `ctx.fs.read_text(path)`, never `path.read_text()`. Makes every service unit-testable with `InMemoryFS`.
3. **Failure propagation.** A service either completes and returns its result (possibly with emitted diagnostics) or raises. Exceptions are the programmer-error channel. User-facing failures are diagnostics plus a phase gate.
4. **Phase boundaries.** After each service returns, the orchestrator calls `_has_errors(ctx, phase)` (Sec.6.2) against `ctx.diag.snapshot()`. If any `ERROR`-severity diagnostic with the matching `phase` is present and the phase is gating (P1, P3, P6), the orchestrator stops, jumps to P7 audit, and returns a non-zero `RunResult`. Severity is never rewritten; `--strict` is a separate CLI-only policy (Sec.8.2 rule 4). See architecture doc Sec.5.2.
5. **No hidden channels.** No event bus, no callback registry, no queue between services. Data flows only through typed return values.
6. **Determinism discipline for user data.** Every `Mapping` / `set` / `frozenset` that crosses a service boundary and represents user data (proc indexes, file decisions, graph nodes/edges) is either (a) replaced at construction by a `tuple` sorted on a documented key, or (b) iterated through a sorted view at every read site. Golden tests enforce this. *Diagnostics are the explicit exception* -- their order is emission order (Sec.8.2 rule 3), which is deterministic by virtue of single-threaded sequential phase execution.

### 9.4 What this buys

- **Services are testable in isolation with minimal setup.** A shared `make_test_context()` helper (see Sec.10.2) constructs a fresh `ChopperContext` with stub adapters (`InMemoryFS`, `CollectingSink`, `SilentProgress`) in one call. Simple services test in a handful of lines; services with richer input (Parser, Compiler) need fixture data but still no boilerplate for the port layer. The goal is **stateless test setup**, not a literal line count.
- **Swap any service without touching the others.** Its contract is its signature plus its result dataclass; the runner receives it through one `Providers` field (Sec.6.2).
- **Audit artifacts are free.** Every result already has a JSON shape via `core.serialization.dump_model()`; `AuditService` dumps them without custom formatters.

---

## 10. Feature Work Isolation Rules

To make every feature "individually and isolatedly developable/enhanceable" (your words), these rules are hard:

### 10.1 Rules

1. **One service = one module = one stage gate.** You rewrite `TracerService` end-to-end; tests live at `tests/unit/compiler/test_trace.py` with stub adapters.
2. **Public surface of a service is its `run(...)` signature and its result dataclass.** Change that -> documented breaking change + registry bump.
3. **Cross-service data flows only through frozen dataclasses.** Two services never share a mutable object.
4. **Diagnostic codes are the API contract for user-visible behavior.** Adding a code requires a registry edit in [`technical_docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) before use.
5. **Stage discipline is hard.** Stage N may not import from Stage N+1. Enforced by `import-linter` contracts in CI.

   **Permitted exception:** P6 validator imports P2 parser for post-trim validation accuracy. The validator's `validate_post` function calls `parse_file()` from the parser to re-parse trimmed `.tcl` outputs and verify that the proc set matches the `TrimReport` promise (VW-10 check). This is the **only** permitted cross-stage import; all other stage boundaries remain sealed. See [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) Sec.5.12.9 and [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) Sec.1.1 for the full rationale: re-parsing is the cleanest way to catch real bugs (incorrect proc drops), and the parser is a lower-level service that does not import validator, so there is no bidirectional coupling.

6. **Adapters are swappable in tests.** Unit tests inject `InMemoryFS`, `CollectingSink`, `SilentProgress` -- they never touch the real filesystem. Time is controlled via `freezegun` / `monkeypatch` on `datetime.now`; there is no ClockPort.
7. **New features that span services** go through the orchestrator, never via new inter-service imports. The orchestrator is a single hand-wired pipeline (Sec.6.2) -- no plugin registry, no dynamic phase insertion. Adding a new phase means editing `Providers`, `default_providers()`, and `run()` in `runner.py`; adding a P5 step means editing `execute_output()` once, which live trim and `chopper loc` both call. That is deliberate.
8. **`ctx` bindings are stable; port state is not.** A service must not try to swap or reassign ports on `ctx`. Local scratch data stays local and is returned as part of the typed result.
9. **Front ends go through `app/`.** A user action that a front end exposes is one `chopper.app` use case returning a typed result. The CLI (and a future GUI, `FD-04`) only translates input and renders output; discovery, ordering, config building, and dispatch live in `app/` once.

### 10.2 The shared test helper

All unit and integration tests use a single factory for context construction:

```python
# tests/support/context.py
def make_test_context(
    *,
    files: Mapping[Path, str] | None = None,
    strict: bool = False,
    dry_run: bool = False,
    domain_root: Path = Path("/domain"),
) -> ChopperContext:
    """Build a fresh ChopperContext backed entirely by stub adapters.

    Time is controlled via `freezegun` / `monkeypatch` on `datetime.now`
    in tests that need it; there is no ClockPort to inject.
    """
    return ChopperContext(
        config=RunConfig(
            domain_root=domain_root,
            backup_root=domain_root.with_name(domain_root.name + "_backup"),
            audit_root=domain_root / ".chopper",
            strict=strict,
            dry_run=dry_run,
        ),
        fs=InMemoryFS(files or {}),
        diag=CollectingSink(),
        progress=SilentProgress(),
    )
```

**Every test calls `make_test_context()` fresh** -- no module-level contexts, no shared sinks, no reuse across tests. This is what makes test setup stateless: adapters have lifetime bounded by the test, so state cannot leak. Service-specific fixtures (parsed files, JSON configs, manifests) are built on top of this one call.

---

## 11. Determinism, Concurrency, and Performance Envelope

- **Determinism is a first-class invariant.** All map/set iteration over user data is replaced with sorted sequences before emission (architecture doc Sec.5.4 BFS lex-sort rule). Non-negotiable.
- **Diagnostic order is emission order.** Because v1 is single-threaded and phase order is fixed (Sec.6.2), emission order is reproducible without any sort. `CollectingSink` preserves it verbatim (Sec.8.3).
- **Concurrency.** **Chopper is single-threaded. Period.** No thread pools, no `asyncio`, no `multiprocessing`, no background workers, no locks of any kind -- not in the sink, not around `.chopper/`, not around the domain tree. Chopper is a single-user push-button tool: one operator runs it against one on-disk domain, it finishes, and it exits. If two operators race the same checkout, the second invocation will observe a half-written `DomainStateService` state and abort through normal diagnostics -- that is the intended failure mode, not a bug to guard against with locking. This is a closed design decision, not a deferral.
- **Memory envelope.** <=1 GB domain -> whole-file reads acceptable (architecture doc Sec.11 NFR-06). No streaming.
- **Performance posture.** Correctness first, optimization later. 5-10 minute runtime for a typical domain is acceptable. No per-phase time budget is enforced. Audit artifacts are written even on failure. A `make bench` harness and phase-time budgets are explicitly deferred (see [`technical_docs/IMPLEMENTATION.md`](IMPLEMENTATION.md) Future Considerations Sec.FD-09).

---

## 12. Closed Decisions

Questions raised during planning. All are resolved for v1.

### Q1 -- Plugin host / AI advisor / MCP (CLOSED)

**Closed permanently.** Chopper has no plugin system, no AI advisor, and no reserved extension seams. There is no `PluginHost`, no `X*` diagnostic family, no `plugins/` or `advisor/` module, and no "stage 6" on the roadmap for any of these. Previous drafts reserved these concepts "for future use"; that reservation is withdrawn. PRs that add plugin or advisor scaffolding are rejected at review.

**Closed permanently -- MCP surface (all kinds).** No MCP surface of any kind exists. A read-only, stdio-only MCP server (`chopper mcp-serve`, the `src/chopper/mcp/` package, the `mcp` runtime dependency, and `PE-04`/exit-code 4) was briefly permitted in 0.4.0 and **removed in 4.0.0**. There is no `MCPDiagnosticSink`, no `MCPProgressBridge`, no `adapters/mcp_*.py`, no MCP client code, no read-only or destructive MCP tools, no HTTP/TCP/WebSocket/stdio MCP transport, and no `mcp` dependency.

**Rationale.** Reserving open-ended extension points (plugins, advisors, MCP) invites drift: an agent reading "reserved" treats it as "TODO", a contributor fills in the TODO, and a surface the project never approved ships. The narrowed read-only MCP shipped in 0.4.0 carried ongoing dependency and maintenance cost for a surface that was not used, so it was removed and the decision re-closed. Reintroduction requires explicit user approval and an architecture-doc-first cascade.

### Q2 -- Hand-edit preservation (CLOSED -- not supported)

**Chopper does not preserve hand edits.** There is no `--preserve-hand-edits` flag, no stash path, no `.chopper/hand_edits/` directory, and no `VI-03` diagnostic to detect divergence. When re-trim runs, `DomainStateService` rebuilds `<domain>/` from `<domain>_backup/` unconditionally. The CLI prints a fixed pre-flight warning every run (*"Re-trim rebuilds `<domain>/` from `<domain>_backup/`. Any manual edits in `<domain>/` will be discarded."*); operators who ran Chopper once have been warned once and are responsible for committing or stashing hand edits before the next run.

**Rationale.** The single source of truth for the trimmed domain is `<domain>_backup/` plus the JSON selection. Shipping an automatic stash would encourage operators to rely on it as a versioning system, which it is not. A diagnostic-level detector (the retired `VI-03 domain-hand-edited`) would require storing a content hash between runs -- complexity with no payoff, since the fixed pre-flight warning already informs every user every time.

### Q3 -- Concurrency / locking (CLOSED -- not supported)

**Chopper has no lock and no concurrency guard.** There is no `.chopper/.lock`, no `LockPort`, no dedicated concurrency diagnostic, and no stale-lock recovery. Chopper is a single-user push-button tool: one operator, one invocation, one on-disk domain, one result. If two operators race the same checkout on the same filesystem, the second invocation sees a half-written `DomainStateService` state and aborts through the normal `VE-21` / filesystem-error path. That is the intended failure mode, not a bug to guard against.

**Rationale.** Adding locks buys nothing: the real hazard (two concurrent writers on the same disk) is an operator-level contract violation that no cooperative file lock can fully prevent. Removing locks eliminates an entire category of stale-lock, crash-recovery, and cross-platform `fcntl` / `msvcrt` complexity.

### Q6 -- Non-UTF8 encoding policy (CLOSED)

Already covered by `PW-02 utf8-decode-failure`. No new code.

Policy: read each file as UTF-8. On `UnicodeDecodeError`, retry as Latin-1 and emit `PW-02`. Parse continues on the Latin-1 content. Determinism requires a fixed fallback; Latin-1 is chosen because every byte decodes.

### Deferred (explicitly not v1)

- Runtime optimization and per-phase budgets -- deferred to [`technical_docs/IMPLEMENTATION.md`](IMPLEMENTATION.md) Future Considerations Sec.FD-09.

---

*This plan is subordinate to [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md). When this plan and the architecture doc disagree, the architecture doc wins and this plan is updated in place (no addendums -- per [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) Documentation Conventions).*
