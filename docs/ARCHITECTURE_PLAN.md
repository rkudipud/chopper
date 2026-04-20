# Chopper v2 — Modular Service Architecture Plan

**Status in the doc tree.** This document is a **plan**, not a contract. The authoritative product spec is [`docs/chopper_description.md`](chopper_description.md) ("the bible"). This plan proposes *how* the spec is realized as independently developable modules. Where this plan disagrees with the bible, the bible wins and this plan is edited in place.

**What this plan is for.** Chopper is a **local, single-process Python CLI** — not a web app, not a cloud service, not a daemon, not a plugin host. It runs on a VLSI engineer's workstation (or a grid node), reads ≤1 GB of Tcl / JSON from disk, writes a trimmed domain back to disk, and exits. The plan below describes how to decompose this CLI into **independently developable services** (in-process, ports-and-adapters) so individual features can be added, rewritten, or replaced in isolation. Chopper is **not** extensible through plugins, AI advisors, or MCP adapters — those are not on the roadmap, not deferred, not planned. See §16 for the scope-lock rationale.

**How to read this plan.** §1–§3 frame the shape. §4–§7 define the modules and their seams. §8–§10 pin down the contracts that make isolated feature work safe. §11–§12 cover performance and corner cases. §13 is a multi-expert review. §14–§16 are the contributor playbook, roadmap, and closed decisions.

---

## Table of Contents

1. [Framing: It Is a Local Python CLI](#1-framing-it-is-a-local-python-cli)
2. [Architectural Style — Recommendation](#2-architectural-style--recommendation)
3. [Repository and Module Layout](#3-repository-and-module-layout)
4. [Service Catalog](#4-service-catalog)
5. [Ports (Protocols) and Adapters](#5-ports-protocols-and-adapters)
6. [Orchestration and the Context Object](#6-orchestration-and-the-context-object)
7. [Extension Seams (Not Applicable)](#7-extension-seams-not-applicable)
8. [Diagnostic Emitter / Collector Contract](#8-diagnostic-emitter--collector-contract)
9. [Inter-Service Communication Contract](#9-inter-service-communication-contract)
10. [Feature Work Isolation Rules](#10-feature-work-isolation-rules)
11. [Determinism, Concurrency, and Performance Envelope](#11-determinism-concurrency-and-performance-envelope)
12. [Corner-Case Simulation Catalog](#12-corner-case-simulation-catalog)
13. [Multi-Expert Review Panel](#13-multi-expert-review-panel)
14. [Contributor Playbook — Adding or Replacing a Feature](#14-contributor-playbook--adding-or-replacing-a-feature)
15. [Adoption Roadmap (Stage-Aligned)](#15-adoption-roadmap-stage-aligned)
16. [Closed Decisions](#16-closed-decisions)

---

## 1. Framing: It Is a Local Python CLI

The user's ask was phrased as "service-oriented, context-aware." Taken literally that would mean networked microservices, which is the wrong shape for this workload. The right shape — and the one this plan delivers — keeps the engineering essence of SOA **in a single Python process**:

| You asked for | What it means for a local CLI |
|---|---|
| Service-oriented | Each of the 7 pipeline phases is a **service class** with a single `run(...)` method. Services do not import each other. |
| Modular / isolated feature work | One feature = one service module = one stage gate. Change it end-to-end without touching siblings. |
| Context-aware | All cross-cutting state (paths, flags, clock, filesystem, sinks) lives on a single `ChopperContext` — a service bundle plus run config with stable port bindings (§6.1) — passed explicitly. No globals, no singletons. |
| Cloud / network services | **Not in scope.** Chopper is a desktop/grid CLI. No HTTP, no IPC, no message bus. |
| Plugin host / MCP / AI advisors | **Not in scope, not deferred, not planned.** Chopper is a self-contained CLI. Any proposal to add a plugin loader, AI integration, or network surface is rejected on sight (§16 Q1). |

**Named pattern:** Hexagonal (ports-and-adapters) + Pipeline. This is the shape Ruff, mypy, Pylint, dbt-core, and Snakemake converge on — all are local single-process tools with strong modularity and swappable backends.

**Your ask was not vague.** It maps cleanly to Hexagonal + Pipeline. The only word this plan tightens is "service-oriented": locally, that means *service classes behind ports*, not *services across a network*.

---

## 2. Architectural Style — Recommendation

| Option | Fit for Chopper | Verdict |
|---|---|---|
| Flat monolith (everything in one package, phases call each other) | Ships fast, but couples phases and kills isolated feature work | **Reject** |
| **Modular monolith + Hexagonal (ports/adapters) + Pipeline** | Matches the 7-phase bible contract, preserves determinism, enables isolated stage work | **Recommended** |
| Networked microservices | Requires IPC, serialization, process lifecycle — zero business benefit for a <1 GB, 5-min run | Reject |
| Event-driven bus | Eventual consistency inside a deterministic pipeline is a contradiction | Reject |
| Serverless / lambda | Anti-fit for filesystem-heavy workloads on VLSI checkouts | Reject |

**Why the recommendation wins:**

- Preserves the bible's 7-phase contract (P0–P7) and determinism guarantees.
- Aligns 1:1 with the Stage 0–5 build model in [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md).
- Cross-module data flow is typed frozen dataclasses — services cannot corrupt each other's state.

---

## 3. Repository and Module Layout

This is the target layout under `src/chopper/`. Stage 0 creates the skeleton; later stages fill in the services.

```
src/chopper/
├── __init__.py
├── core/                        # Stage 0 — no deps on sibling modules
│   ├── models.py                # Frozen dataclasses: ProcEntry, CompiledManifest, ...
│   ├── diagnostics.py           # Severity, Phase, Diagnostic, code registry guard
│   ├── errors.py                # Exception types (programmer errors only)
│   ├── protocols.py             # Ports: FileSystemPort, DiagnosticSink, ...
│   ├── context.py               # ChopperContext + RunConfig (service bundle, §6.1)
│   ├── result.py                # RunResult, phase-level result dataclasses
│   └── serialization.py         # JSON encode/decode for all models
│
├── adapters/                    # Concrete implementations of ports
│   ├── fs_local.py              # LocalFS
│   ├── fs_memory.py             # InMemoryFS (tests)
│   ├── sink_collecting.py       # CollectingSink (default)
│   ├── sink_jsonl.py            # JSONLSink (audit)
│   ├── progress_rich.py         # RichProgress
│   ├── progress_silent.py       # SilentProgress
│   ├── clock_system.py          # SystemClock
│   ├── clock_frozen.py          # FrozenClock (tests, golden)
│   ├── audit_dotchopper.py      # DotChopperAuditStore
│   └── table_rich.py            # RichTable renderer
│
├── parser/                      # Stage 1 — Tcl static analysis (P2)
│   ├── service.py               # ParserService.run(ctx, files) -> ParseResult
│   ├── tokenizer.py
│   ├── proc_extractor.py
│   └── namespace_tracker.py
│
├── config/                      # Stage 2a — JSON loading (part of P1)
│   ├── service.py               # ConfigService.run(ctx, state) -> LoadedConfig
│   ├── loaders.py
│   └── schema.py                # jsonschema adapters
│
├── compiler/                    # Stage 2b — Merge + trace (P3, P4)
│   ├── merge_service.py         # CompilerService.run(...)
│   ├── trace_service.py         # TracerService.run(...)
│   └── provenance.py
│
├── trimmer/                     # Stage 3a — Trim state machine (P5a)
│   └── service.py               # TrimmerService.run(...)
│
├── generators/                  # Stage 3b — Run-file emission (P5b)
│   └── service.py               # GeneratorService.run(...)
│
├── audit/                       # Stage 3c — .chopper/ writes (P7)
│   └── service.py               # AuditService.run(...)
│
├── validator/                   # Stage 4 — Pre+post validation (P1, P6)
│   ├── pre_service.py            # PreValidatorService.run (P1)
│   └── post_service.py           # PostValidatorService.run (P6)
│
├── orchestrator/                # Composes the services; owns phase loop
│   ├── runner.py                # ChopperRunner
│   ├── domain_state.py          # DomainStateService (P0)
│   └── gates.py                 # Phase-boundary gating logic
│
└── cli/                         # Stage 5 — thin CLI (no business logic)
    ├── main.py                  # argparse / typer entrypoint
    ├── commands.py              # validate / trim / cleanup
    └── render.py                # TableRenderer-backed output
```

**The dependency rule is strict and enforced at CI** (`import-linter`):

```
cli ─► orchestrator ─► services ─► core (ports + models)
                                      ▲
adapters ──────────────────────────────┘
```

- `core` imports nothing from siblings — only stdlib.
- Service packages (`parser`, `compiler`, `trimmer`, …) import only from `core`.
- `adapters` import from `core` and third-party libs.
- `orchestrator` imports from `core` + every service + selects adapters.
- `cli` imports from `core` + `orchestrator` only.
- **No `plugins/`, no `mcp_server/`, no `advisor/` directory exists or is planned.** These are not v1-deferred features — they are permanently excluded (see §16 Q1). Any PR that creates such a directory is rejected without review.

Circular imports, inter-service imports, and reverse imports (service importing orchestrator or cli) are all rejected at CI.

---

## 4. Service Catalog

Each service is a class with a single public `run(...) -> TypedResult`. Services are **stateless between invocations**; all state flows via `ChopperContext` and the typed result objects.

| Service | Phase(s) | Input → Output | Where it lives |
|---|---|---|---|
| `DomainStateService` | P0 | `ctx` → `DomainState` | `orchestrator/domain_state.py` |
| `ConfigService` | P1 | `ctx, state` → `LoadedConfig` | `config/service.py` |
| `PreValidatorService` | P1 | `ctx, loaded` → emits diagnostics | `validator/pre_service.py` |
| `ParserService` | P2 | `ctx, files` → `ParseResult` | `parser/service.py` |
| `CompilerService` | P3 | `ctx, loaded, parsed` → `CompiledManifest` | `compiler/merge_service.py` |
| `TracerService` | P4 | `ctx, manifest, parsed` → `DependencyGraph` | `compiler/trace_service.py` |
| `TrimmerService` | P5a | `ctx, manifest, state` → `TrimReport` | `trimmer/service.py` |
| `GeneratorService` | P5b | `ctx, manifest` → `tuple[GeneratedArtifact, ...]` | `generators/service.py` |
| `PostValidatorService` | P6 | `ctx, manifest` → emits diagnostics | `validator/post_service.py` |
| `AuditService` | P7 | `ctx, manifest, graph` → `AuditManifest` | `audit/service.py` |

**Every service has exactly one public method named `run(...)`.** Pre- and post-validation are **two separate services** (`PreValidatorService` at P1, `PostValidatorService` at P6), each with its own `run()`. No service exposes multiple public entry points.

**Key discipline:** Services **do not** call each other directly. They return typed results; the orchestrator decides what flows where. This is what makes isolated feature development possible — you can rewrite `TracerService` without touching `CompilerService` because neither imports the other.

**Minimal service base (informal, by convention — not inherited):**

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
| `ClockPort` | `now()` / `monotonic()` | `SystemClock` | `FrozenClock` (golden tests) |
| `TableRenderer` | tabular output for CLI | `RichTable` | `JSONTable`, `MarkdownTable` |
| `AuditStore` | persist artifacts under `.chopper/` | `DotChopperAuditStore` | `EphemeralAuditStore` (tests) |
| `SerializerPort` | model ↔ JSON | `JsonSerde` | — |

**`FileSystemPort` — the full honest surface.** Trimmer, domain-state detection, and audit all need more than `read_text` / `write_text`. The complete port is:

```python
class FileSystemPort(Protocol):
    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str: ...
    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...
    def exists(self, path: Path) -> bool: ...
    def list(self, path: Path, *, pattern: str | None = None) -> Sequence[Path]: ...  # sorted
    def stat(self, path: Path) -> FileStat: ...           # size, mtime, is_dir
    def rename(self, src: Path, dst: Path) -> None: ...   # e.g. domain/ → domain_backup/
    def remove(self, path: Path, *, recursive: bool = False) -> None: ...
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...
    def copy_tree(self, src: Path, dst: Path) -> None: ...
```

Services never call `pathlib.Path.read_text()`, `Path.rename()`, `shutil.rmtree()`, or `os.makedirs()` directly. Everything goes through `ctx.fs.*`. `InMemoryFS` implements the full surface so every service is unit-testable without hitting disk.

**Written surface is constrained.** `ctx.fs.write_text` / `remove` / `rename` / `mkdir` may only target `ctx.config.domain_root`, `ctx.config.backup_root`, or `ctx.config.audit_root`. Any other target is a programmer error and raises — enforced by `LocalFS` at adapter level, not by services. This prevents silent scope creep into sibling domains or shared infrastructure.

**No `LockPort`.** Chopper is a single-user, single-process, single-invocation tool against a single on-disk domain. There is no lock, no concurrency guard, no stale-lock recovery. Two users racing the same domain is an operator-level mistake, not an architectural concern — if it happens, the second invocation will see a half-written state from `DomainStateService` and abort with a normal validation error. The CLI reference makes this policy explicit.

**Why Protocols, not ABCs.** Structural typing lets test fakes satisfy a port without importing Chopper internals. A test fake is just any object with the right method names; no inheritance.

---

## 6. Orchestration and the Context Object

### 6.1 Honest naming

`ChopperContext` is a **service bundle plus run config**, not an immutable data record. Four of its port fields are effectful (`fs`, `diag`, `progress`, `audit`); two are pure (`clock`, `serde`); the rest is `config: RunConfig` (frozen flags and paths). `@dataclass(frozen=True)` on the wrapper only guarantees that **port bindings cannot be rebound mid-run** — it does not make the ports themselves pure. Contributors should read `ctx.<port>.<method>(...)` as "call into a possibly-effectful adapter."

`TableRenderer` is **not** on `ctx`. Rendering is a CLI concern; services never render. The CLI constructs a `TableRenderer` locally and feeds it the `RunResult` it got back from `ChopperRunner.run()`.

To make the split visible in code, the context is composed of two inner records:

```python
# core/context.py
@dataclass(frozen=True)
class RunConfig:
    """Pure invocation config. No methods, no effects."""
    domain_root: Path
    backup_root: Path
    audit_root: Path                     # .chopper/
    strict: bool                         # exit-code policy, applied at CLI (§8.2)
    dry_run: bool


@dataclass(frozen=True)
class ChopperContext:
    """Service bundle + run config. Frozen bindings; ports are effectful."""
    config: RunConfig

    # Pure ports (no observable state).
    clock: ClockPort
    serde: SerializerPort

    # Effectful ports (stateful adapters; fresh instance per run).
    fs: FileSystemPort
    diag: DiagnosticSink
    progress: ProgressSink
    audit: AuditStore
```

**Construction rules.**

- Built exactly once per run — by `cli/main.py` in production, by `make_test_context()` in tests.
- Never mutated. Port *bindings* are fixed; port *state* may change via method calls.
- Services receive `ctx` plus the typed inputs they declare — nothing else. No module-level globals, no singletons, no thread-locals.

### 6.2 The runner

`ChopperRunner.run()` is the only place phases are sequenced:

```python
# orchestrator/runner.py
def run(ctx: ChopperContext) -> RunResult:
    state = manif = graph = None
    try:
        state   = DomainStateService().run(ctx)                         # P0
        loaded  = ConfigService().run(ctx, state)                       # P1a
        PreValidatorService().run(ctx, loaded)                          # P1b
        if _has_errors(ctx, Phase.P1_CONFIG): return _abort(ctx, state, manif, graph)
        parsed  = ParserService().run(ctx, loaded.surface_files)        # P2
        manif   = CompilerService().run(ctx, loaded, parsed)            # P3
        if _has_errors(ctx, Phase.P3_COMPILE): return _abort(ctx, state, manif, graph)
        graph   = TracerService().run(ctx, manif, parsed)               # P4 (reporting-only)
        if not ctx.config.dry_run:
            TrimmerService().run(ctx, manif, state)                     # P5a
            if _has_errors(ctx, Phase.P5_TRIM): return _abort(ctx, state, manif, graph)
            GeneratorService().run(ctx, manif)                          # P5b
            PostValidatorService().run(ctx, manif)                      # P6
            if _has_errors(ctx, Phase.P6_POSTVALIDATE): return _abort(ctx, state, manif, graph)
        return _build_result(ctx, manif, graph, exit_code=0)
    finally:
        # P7 audit always runs — even on exceptions, even on early return.
        # AuditService tolerates `None` inputs and writes whatever is available
        # (state snapshot, partial manifest, partial graph, full diagnostic trail).
        try:
            AuditService().run(ctx, manif, graph)
        except Exception:
            # Audit itself failed (disk full, perms). Log to stderr only;
            # never mask the primary failure. Exit code is unaffected.
            pass


def _abort(ctx, state, manif, graph) -> RunResult:
    """Early-return on a gated ERROR. P7 still fires via the outer `finally`."""
    return _build_result(ctx, manif, graph, exit_code=1)
```

**Gate semantics (explicit).** `_has_errors(ctx, phase)` inspects `ctx.diag.snapshot()` and returns `True` iff any diagnostic with `severity == ERROR` and `phase == <phase>` is present. **Severity is never rewritten by the gate.** `--strict` does not affect gating — see §8.2 rule 4. On abort, the runner returns a `RunResult` with `exit_code=1`; the `finally` block guarantees `AuditService` runs so `.chopper/` gets whatever artifacts are reachable.

**Gate between P5a (Trimmer) and P5b (Generator).** Historically the plan ran them back-to-back. That let a failed trim produce run-files pointing into a half-trimmed tree. The gate shown above stops the pipeline after P5a if any `ERROR`-severity `phase == P5_TRIM` diagnostic is present, so the Generator never writes into a broken state. The registered codes covering this gate live in the `VE-*` trimmer range in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).

---

## 7. Extension Seams (Not Applicable)

**Chopper has no extension seams.** There is no plugin host, no plugin loader, no observer fan-out, no MCP server, no MCP client, no AI advisor, no `X*` diagnostic family, no `adapters/mcp_*.py`, no `plugins/` package. These are not stubs, not reserved, not "architecturally enabled" for a later release — they are **permanently out of scope** (see §16 Q1).

**Why this is stated explicitly.** Previous drafts reserved MCP/plugin seams "for future use." Experience showed that reservations drift into implementations: an agent reading "reserved" treats it as "TODO", a contributor fills in the TODO, and a feature the project never approved ships anyway. Scope-lock requires the absence of reservations, not a list of them.

**What this means operationally.**

- No code path references `PluginHost`, `TeeSink`, `MCPProgressBridge`, `EntryPointPluginHost`, `advisor`, or similar identifiers.
- No diagnostic code in the `XE-*` / `XW-*` / `XI-*` space is defined or reserved.
- No `adapters/mcp_*.py`, `plugins/`, `mcp_server/`, or `advisor/` module exists in the tree (§3).
- No "post-v1" or "stage 6" roadmap row carries plugin or MCP content (§15).
- Any PR that adds any of the above is rejected at review without further discussion.

If a future release genuinely needs a plugin mechanism, it starts a fresh design doc and updates [`docs/chopper_description.md`](chopper_description.md) first. It does not resurrect stubs from this plan.

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
    code:     str                 # e.g. "VE-06" — must exist in DIAGNOSTIC_CODES.md
    slug:     str                 # e.g. "file-not-in-domain"
    severity: Severity
    phase:    Phase
    source:   str                 # service name: "parser", "compiler", ...
    message:  str                 # one-line, no newlines
    path:     Path | None = None
    line_no:  int  | None = None
    hint:     str  | None = None
    context:  Mapping[str, object] = field(default_factory=dict)  # JSON-safe
```

**Invariants:**

- `code` MUST match a registered code in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md). Construction validates this against a compile-time registry; unknown codes raise immediately. Tests fail fast on typos.
- `Diagnostic` is immutable and hashable (default frozen-dataclass `__eq__` compares all fields).
- **Dedupe key is a subset of equality.** The sink deduplicates on `(code, path, line_no, message)` — *not* on full-field equality. Two diagnostics with identical code/path/line/message but different `hint` or `context` still collapse to one at the sink. This is intentional: `hint` and `context` are presentational or diagnostic-local metadata and must not create spurious duplicates.
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
2. **No diagnostic is emitted twice.** Sinks dedupe on the equality key `(code, path, line_no, message)`. Duplicate emits are silently dropped — no error, no second entry.
3. **Ordering is emission order, preserved verbatim.** `snapshot()` returns diagnostics in the exact order `emit()` was called. The sink does **not** sort. Determinism of the user-visible diagnostic sequence follows from (a) single-threaded execution (§11) and (b) a fixed phase sequence in `ChopperRunner.run()`. Services that iterate user data (files, procs) must iterate in a documented sorted order so their own emissions are reproducible across runs.
4. **`--strict` is an exit-code policy, not a severity rewrite.** Services always emit the nominal severity — a `WARNING` stays a `WARNING` in the sink, in `diagnostics.json`, and in all rendered output, with or without `--strict`. Phase gates fire on nominal `ERROR` only (see §6.2). At the very end of the run, the CLI computes the process exit code from `sink.finalize()`:
   - exit `0` — no `ERROR`, and either `--strict` is off or no `WARNING` is present.
   - exit `1` — any `ERROR`, **or** `--strict` is on and any `WARNING` is present. (No individual `VI-*` code is singled out; advisories do not affect the exit code.)
   - exit `2` — CLI / pre-pipeline fatal conditions the runner never even enters: `VE-11` conflicting CLI options, `VE-13` unresolvable `--project` paths (authoring error — see §12 scenario 20), `VE-23` missing domain + backup.
   - exit `3` — unhandled exception escaped a service (programmer error). The outer `try / finally` in §6.2 catches it, logs a stack trace to `.chopper/internal-error.log` via `AuditService`, and exits `3`. This is deliberately distinct from exit `1` so CI systems can tell "pipeline found a problem" from "Chopper itself broke."

   `--strict` never changes what the pipeline *does*, only how the caller *interprets* the outcome. The stored diagnostic severity is the truth; `--strict` is a policy layer on top. **There is no warn-to-error promotion anywhere in the pipeline or in the sink — only in the final exit-code computation.**
5. **No fatal-on-first-error mode.** Default and only behavior: collect within a phase; stop at phase boundary if any `ERROR` is present (§6.2). This simplifies recovery and matches the bible.

### 8.3 `CollectingSink` guarantees (single-threaded)

- **Not thread-safe. Not required to be. No future-concurrency story.** v1 and every planned future version run single-threaded (§11). The sink never needs a lock and never will. If some later version wants parallelism it is a brand-new design discussion, not an implicit promise this doc makes.
- **O(1) dedupe** via a set of equality keys. Duplicate emits never appear in `snapshot()`.
- **Append-only storage.** `snapshot()` returns an immutable view of the current list. No sort, no copy beyond what `Sequence[Diagnostic]` requires.
- **`finalize()`** returns a `DiagnosticSummary` (counts by severity and by family) used by the CLI for exit-code computation (§8.2 rule 4) and by `AuditService` to write `diagnostics.json`.

### 8.4 Render path

```
Service ─emit()─► CollectingSink ─snapshot()─► CLI TableRenderer
                        └─► AuditService ─► .chopper/diagnostics.json (via SerializerPort)
```

The CLI is the **only** layer that formats for humans. Libraries stay silent.

### 8.5 Retired code slots

| Family | Use | Active |
|---|---|---|
| `VE-25` | `feature-depends-on-cycle` | Yes |
| `VE-26` | `filesystem-error-during-trim` | Yes |
| `VE-16` | **RETIRED** — `depends_on` out-of-order no longer an error (see §12 scenario 11) | No |
| `VE-24` | **RETIRED** — no locks, no concurrency guard | No |
| `VI-04` | **RETIRED** — `--preserve-hand-edits` removed | No |
| `VI-05` | **RETIRED** — no locks | No |

The registry in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) is authoritative; this table is a pointer only. Retired slots are never renumbered; they stay reserved and inactive so history stays readable. **There is no `X*` plugin family** — see §7 and §16 Q1.

---

## 9. Inter-Service Communication Contract

Diagnostics are the user-facing spine. This section pins down how services hand **data** to each other. The rule is unambiguous: **services never call services; they return typed results and the orchestrator wires them.**

### 9.1 Shapes (frozen dataclasses, all in `core/models.py`)

```python
@dataclass(frozen=True)
class DomainState:
    case: Literal[1,2,3,4,5,6]           # bible §2.8 matrix
    domain_exists: bool
    backup_exists: bool
    hand_edited: bool                    # triggers VI-03 / stash

@dataclass(frozen=True)
class LoadedConfig:
    base: BaseJson
    features: tuple[FeatureJson, ...]    # topo-sorted by depends_on
    project: ProjectJson | None
    surface_files: tuple[Path, ...]      # all files named by any source

@dataclass(frozen=True)
class ParsedFile:
    path: Path
    procs: tuple[ProcEntry, ...]
    unresolved_calls: tuple[CallSite, ...]
    encoding: Literal["utf-8", "latin-1"]
    # No `parse_errors` field. Parse errors are emitted into `ctx.diag` as they
    # are discovered — the single user-facing channel (§8.2 rule 1). A per-file
    # diagnostic accumulator is a parser-internal detail of `parse_file()` and
    # is flushed into `ctx.diag` at the service boundary; it never appears on
    # the public dataclass.

@dataclass(frozen=True)
class ParseResult:
    files: Mapping[Path, ParsedFile]     # sorted at construction
    index: Mapping[str, ProcEntry]       # canonical_name → entry
    # Canonical name format is fixed by contract: "<domain-relative-posix-path>::<proc_name>"
    # (for example, "common/helpers.tcl::foo"). Enforced at ParseResult construction;
    # tests assert the format. See RISKS_AND_PITFALLS.md TC-02.

@dataclass(frozen=True)
class CompiledManifest:
    file_decisions: Mapping[Path, FileTreatment]
    proc_decisions: Mapping[str, ProcDecision]
    provenance:     Mapping[str, Provenance]
    stages:         tuple[StageSpec, ...]

@dataclass(frozen=True)
class DependencyGraph:
    nodes: tuple[str, ...]                         # canonical proc names, lex-sorted
    edges: tuple[Edge, ...]                        # (caller, callee), lex-sorted
    reachable_from_includes: frozenset[str]        # PI+ set, reporting-only

@dataclass(frozen=True)
class RunResult:
    manifest:    CompiledManifest
    graph:       DependencyGraph
    diagnostics: Sequence[Diagnostic]
    exit_code:   int
    duration:    timedelta

# ---------------------------------------------------------------------------
# Stage 3 outputs — returned by TrimmerService / GeneratorService / AuditService.
# All fields are JSON-serializable via SerializerPort; golden snapshots pin them.
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
    """Returned by TrimmerService.run — drives .chopper/trim_report.{json,txt}.
    Bible §P5a."""
    outcomes:           tuple[FileOutcome, ...]   # one per file in the domain, lex-sorted by path
    files_copied:       int
    files_trimmed:      int
    files_removed:      int
    procs_kept_total:   int
    procs_removed_total: int
    rollback_performed: bool                      # True if P5a aborted and restored from backup

@dataclass(frozen=True)
class GeneratedArtifact:
    """A single file emitted by GeneratorService (P5b). Bible §P5b / F3.
    Generated run files live alongside normal domain files; they are still
    subject to post-trim validation (P6)."""
    path:    Path                               # domain-relative, POSIX
    kind:    Literal["stack", "tcl", "csv"]     # bible §F3 output kinds
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
    """Returned by AuditService.run — inventory of everything written under
    .chopper/. Bible §P7. The manifest itself is the last thing written
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
| `DomainStateService.run` | `(ctx) -> DomainState` |
| `ConfigService.run` | `(ctx, state) -> LoadedConfig` |
| `ParserService.run` | `(ctx, files: Sequence[Path]) -> ParseResult` — wraps the pure `parse_file()` utility described in [`docs/TCL_PARSER_SPEC.md`](TCL_PARSER_SPEC.md) §2.1. The utility stays a small, callback-driven internal function (`on_diagnostic` forwards straight into `ctx.diag.emit(...)`); the service is what the orchestrator and other services actually depend on. Reading through `ctx.fs` (never `Path.read_text` directly) is the service's job — the utility takes already-decoded text. |
| `CompilerService.run` | `(ctx, loaded, parsed) -> CompiledManifest` |
| `TracerService.run` | `(ctx, manifest, parsed) -> DependencyGraph` |
| `TrimmerService.run` | `(ctx, manifest, state) -> TrimReport` |
| `GeneratorService.run` | `(ctx, manifest) -> tuple[GeneratedArtifact, ...]` |
| `ValidatorService.run_pre` | — **REMOVED.** Split into `PreValidatorService.run(ctx, loaded) -> None`. |
| `ValidatorService.run_post` | — **REMOVED.** Split into `PostValidatorService.run(ctx, manifest) -> None`. |
| `PreValidatorService.run` | `(ctx, loaded) -> None` (emits diagnostics) |
| `PostValidatorService.run` | `(ctx, manifest) -> None` (emits diagnostics) |
| `AuditService.run` | `(ctx, manifest, graph) -> AuditManifest` |

### 9.3 Communication rules

1. **No inter-service imports.** `compiler/` never imports from `parser/`; both import only from `core/models.py`. Enforced at CI by `import-linter`.
2. **All I/O through ports.** A service that reads a file calls `ctx.fs.read_text(path)`, never `path.read_text()`. Makes every service unit-testable with `InMemoryFS`.
3. **Failure propagation.** A service either completes and returns its result (possibly with emitted diagnostics) or raises. Exceptions are the programmer-error channel. User-facing failures are diagnostics plus a phase gate.
4. **Phase boundaries.** After each service returns, the orchestrator calls `_has_errors(ctx, phase)` (§6.2) against `ctx.diag.snapshot()`. If any `ERROR`-severity diagnostic with the matching `phase` is present and the phase is gating (P1, P3, P6), the orchestrator stops, jumps to P7 audit, and returns a non-zero `RunResult`. Severity is never rewritten; `--strict` is a separate CLI-only policy (§8.2 rule 4). See bible §5.2.
5. **No hidden channels.** No event bus, no callback registry, no queue between services in v1. Data flows only through typed return values.
6. **Determinism discipline for user data.** Every `Mapping` / `set` / `frozenset` that crosses a service boundary and represents user data (proc indexes, file decisions, graph nodes/edges) is either (a) replaced at construction by a `tuple` sorted on a documented key, or (b) iterated through a sorted view at every read site. Golden tests enforce this. *Diagnostics are the explicit exception* — their order is emission order (§8.2 rule 3), which is deterministic by virtue of single-threaded sequential phase execution.

### 9.4 What this buys

- **Services are testable in isolation with minimal setup.** A shared `make_test_context()` helper (see §10.2) constructs a fresh `ChopperContext` with stub adapters (`InMemoryFS`, `FrozenClock`, `CollectingSink`, `EphemeralAuditStore`) in one call. Simple services test in a handful of lines; services with richer input (Parser, Compiler) need fixture data but still no boilerplate for the port layer. The goal is **stateless test setup**, not a literal line count.
- **Swap any service without touching the others.** Its contract is its signature plus its result dataclass.
- **Audit artifacts are free.** Every result already has a JSON shape via `SerializerPort`; `AuditService` dumps them without custom formatters.

---

## 10. Feature Work Isolation Rules

To make every feature "individually and isolatedly developable/enhanceable" (your words), these rules are hard:

### 10.1 Rules

1. **One service = one module = one stage gate.** You rewrite `TracerService` end-to-end; tests live at `tests/unit/compiler/test_trace.py` with stub adapters.
2. **Public surface of a service is its `run(...)` signature and its result dataclass.** Change that → documented breaking change + registry bump.
3. **Cross-service data flows only through frozen dataclasses.** Two services never share a mutable object.
4. **Diagnostic codes are the API contract for user-visible behavior.** Adding a code requires a registry edit in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) before use.
5. **Stage discipline is hard.** Stage N may not import from Stage N+1. Enforced by `import-linter` contracts in CI.
6. **Adapters are swappable in tests.** Unit tests inject `InMemoryFS`, `FrozenClock`, `CollectingSink`, `EphemeralAuditStore` — they never touch the real filesystem or clock.
7. **New features that span services** go through the orchestrator, never via new inter-service imports. The orchestrator is a single hand-wired pipeline (§6.2) — no plugin registry, no dynamic phase insertion. Adding a new phase means editing `runner.py`. That is deliberate: v1 has seven phases, period.
8. **`ctx` bindings are stable; port state is not.** A service must not try to swap or reassign ports on `ctx`. Local scratch data stays local and is returned as part of the typed result.

### 10.2 The shared test helper

All unit and integration tests use a single factory for context construction:

```python
# tests/support/context.py
def make_test_context(
    *,
    files: Mapping[Path, str] | None = None,
    strict: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
    domain_root: Path = Path("/domain"),
) -> ChopperContext:
    """Build a fresh ChopperContext backed entirely by stub adapters."""
    return ChopperContext(
        config=RunConfig(
            domain_root=domain_root,
            backup_root=domain_root.with_name(domain_root.name + "_backup"),
            audit_root=domain_root / ".chopper",
            strict=strict,
            dry_run=dry_run,
        ),
        clock=FrozenClock(now or datetime(2026, 1, 1)),
        serde=JsonSerde(),
        fs=InMemoryFS(files or {}),
        diag=CollectingSink(),
        progress=SilentProgress(),
        audit=EphemeralAuditStore(),
    )
```

**Every test calls `make_test_context()` fresh** — no module-level contexts, no shared sinks, no reuse across tests. This is what makes test setup stateless: adapters have lifetime bounded by the test, so state cannot leak. Service-specific fixtures (parsed files, JSON configs, manifests) are built on top of this one call.

---

## 11. Determinism, Concurrency, and Performance Envelope

- **Determinism is a first-class invariant.** All map/set iteration over user data is replaced with sorted sequences before emission (bible §5.4 BFS lex-sort rule). Non-negotiable in v1.
- **Diagnostic order is emission order.** Because v1 is single-threaded and phase order is fixed (§6.2), emission order is reproducible without any sort. `CollectingSink` preserves it verbatim (§8.3).
- **Concurrency.** **Chopper is single-threaded. Period.** No thread pools, no `asyncio`, no `multiprocessing`, no background workers, no locks of any kind — not in the sink, not around `.chopper/`, not around the domain tree. Chopper is a single-user push-button tool: one operator runs it against one on-disk domain, it finishes, and it exits. If two operators race the same checkout, the second invocation will observe a half-written `DomainStateService` state and abort through normal diagnostics — that is the intended failure mode, not a bug to guard against with locking. This is a closed design decision, not a deferral.
- **Memory envelope.** ≤1 GB domain → whole-file reads acceptable (bible §11 NFR-06). No streaming.
- **Performance posture.** Correctness first, optimization later. 5–10 minute runtime for a typical domain is acceptable in v1. No per-phase time budget is enforced. Audit artifacts are written even on failure. A `make bench` harness and phase-time budgets are explicitly deferred (see [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](FUTURE_PLANNED_DEVELOPMENTS.md) §FD-09).

---

## 12. Corner-Case Simulation Catalog

Every row is a scenario the architecture must handle by design, not by patching. Each row maps to a test fixture under `tests/fixtures/` and an acceptance test under `tests/integration/` or `tests/property/`. All referenced codes are active in v1 unless noted.

| # | Scenario | Expected Behavior | Owning Service | Diagnostic |
|---|---|---|---|---|
| 1 | Cyclic proc calls (A→B→A) | BFS visited-set terminates; cycle reported | `TracerService` | `TW-04` |
| 2 | Dirty `.chopper/` from prior crash | Detected; stale artifacts overwritten; run proceeds | `AuditService` | — (silent) |
| 3 | Parser fails mid-domain (unbalanced braces) | Phase records error; orchestrator aborts before P5; backup untouched | `ParserService` → `Runner` | `PE-02` |
| 4 | Feature-level `FE` vetoed by another source's `FI` | Cross-source L1 wins: include survives; warning emitted | `CompilerService` | `VW-10` |
| 5 | Feature-level `PE` vetoed by another source's `PI` | Cross-source L1 wins: include survives; warning emitted | `CompilerService` | `VW-18` |
| 6 | Duplicate `proc foo {...}` in same file | Last definition wins; `PE-01` emitted; index reflects the last one | `ParserService` | `PE-01` |
| 7 | Backslash line continuation across proc header | Lines are **not** physically merged; tokenizer carries state across newlines; line numbers in diagnostics point at the continuation start | `ParserService` | `PW-05` |
| 8 | Comment line with open brace (`# { ...`) | Treated as a comment (to end of line); brace does **not** enter the brace-depth counter | `ParserService` | — |
| 9 | Pre-body quoted arg word (`proc foo "a b" { ... }`) | Discovered as a valid proc per strict Tcl word-parsing; indexed normally | `ParserService` | — |
| 10 | Very large domain (10k files, 500k LoC) | Single-threaded parse; 5–10 min runtime acceptable | `ParserService` | — |
| 11 | Latin-1 source file | UTF-8 decode fails; fall back to Latin-1; warn | `ParserService` | `PW-02` |
| 12 | `feature.depends_on` cycle | Topological sort fails at load; reject before P2 | `ConfigService` | `VE-25` |
| 13 | `feature.depends_on` prerequisite missing from project selection | After all feature JSONs are loaded, emit `VE-15` and abort P1. Order in `project.features` is **not** checked — out-of-order is allowed. | `ConfigService` → `ValidatorService.run_pre` | `VE-15` |
| 14 | Computed proc name (`proc $n {...}`) | Skip + warn; never indexed | `ParserService` | `PW-01` |
| 15 | User passes `--dry-run` | P5/P6 skipped; P0–P4 + P7 still produce audit; zero FS mutations | `Runner` | — |
| 16 | Backup present, domain missing (recovery) | Case 3 from bible §2.8: restore then re-trim | `DomainStateService` | `VI-03` |
| 17 | Hand-edited `domain/` detected | Discard hand edits; rebuild from backup; emit `VI-03`. (No `--preserve-hand-edits` flag — hand edits are the user's responsibility to commit or stash **before** running Chopper.) | `DomainStateService` | `VI-03` |
| 18 | Domain missing AND backup missing | Fatal; exit 2 | `DomainStateService` | `VE-23` |
| 19 | `--project` points at stale / unresolvable feature paths | **Hard crash before the pipeline starts.** Emit `VE-13`, print the bad path(s), exit 2. Authoring error — no partial recovery. | CLI / `ConfigService` pre-pass | `VE-13` |
| 20 | CLI conflicts (`--project` with `--base`) | Pre-pipeline; emit `VE-11`; exit 2 | CLI | `VE-11` |
| 21 | Trimmer writes a partially-invalid file (e.g. dangling proc) | P5a gate trips on `VE-2x` trimmer error; P5b (Generator) is **not** run; existing backup restored by `TrimmerService` rollback; exit 1 | `TrimmerService` → `Runner` | `VE-2x` (registry) |
| 22 | Service raises unexpectedly | Outer `try/finally` in §6.2 writes `.chopper/internal-error.log` + partial audit; exits `3` (programmer-error channel) | `Runner` | (internal error log) |
| 23 | Identical diagnostic emitted twice | Deduplicated at sink by `(code, path, line_no, message)` | `CollectingSink` | — |
| 24 | JSON with trailing commas / BOM | Reject at load with a schema error; do not enter P2 | `ConfigService` | `VE-01` / schema |
| 25 | `project.json` overrides a feature's `PE` with `PI` | Project L1 wins over feature L2; proc survives | `CompilerService` | — |
| 26 | Feature selects a proc that doesn't exist in any parsed file | Emit warning; dependency graph records miss; trim proceeds | `CompilerService` | `VW-11` |
| 27 | File is included but referenced proc is in a different file | Whole-file include wins; other file unchanged | `CompilerService` | — |
| 28 | Trim interrupted by Ctrl-C mid-write | Next run detects inconsistent state via `DomainStateService` (bible §2.8 matrix); restore from backup proceeds normally. No lock file is inspected (there is no lock file). | `DomainStateService` | — |
| 29 | Read-only filesystem under `domain/` | Trimmer's `ctx.fs.rename`/`write_text` fails; emit `VE-26 filesystem-error-during-trim` with the offending path; P5a rollback restores `<domain>_backup/` → `<domain>/`; audit writes to a best-effort path; exit 1 | `TrimmerService` | `VE-26` |
| 30 | Windows case-insensitive path collision | `pathlib.Path.resolve()` + POSIX normalization dedupe; golden snapshot stable across OSes | all services | — |
| 31 | Symlinks inside the domain | Follow once; detect cycles via visited-set on resolved paths | `ParserService` | `PW-0x` (registry) |
| 32 | Non-ASCII path characters | Handled by `pathlib`; no encoding-specific logic required | all services | — |
| 33 | `--strict` with warnings present | Pipeline runs to completion unchanged; CLI exits 1 at the end because `finalize()` reports `WARNING > 0` and `--strict` is set. **No severity rewriting** — the warnings remain warnings in `diagnostics.json` and in rendered output. | CLI exit-code layer | — |

**Every scenario has a test.** The catalog is the acceptance checklist for v1.

---

## 13. Multi-Expert Review Panel

Each reviewer sees the same plan and raises objections grounded in their role. Each objection is either defended here or moved to the action items below the panel.

### 13.1 Principal Software Engineer (Fowler-style)

**Endorses.** Hexagonal over literal SOA — correct shape. Strict stage imports enforced by tooling — matches the stage-gated build model. Frozen dataclasses plus Protocols — high testability, low coupling. Diagnostic sink as the single user-visible spine — no hidden log channels.

**Objections.**

- *O1 — "Distributed monolith" risk.* Addressed by §9.3 rule 1: services do not call services; only the orchestrator composes them. `import-linter` contracts block regressions.
- *O2 — `ChopperContext` looks like a god object.* Reframed and accepted. The context is a **service bundle plus run config** (§6.1), not an immutable data record. Port bindings are stable; port state is not. This is a DI container, not a service locator — services accept `ctx` and use only the ports they need. The `RunConfig` / ports split in §6.1 makes the distinction visible at every call site.
- *O3 — How do you keep the sink from becoming a global?* It is a field on `ctx`, passed explicitly, and every test builds a fresh one via `make_test_context()` (§10.2). No module-level sink exists.

**Action items.** (Consolidated in §13.6.)

### 13.2 Product Manager

**Endorses.** Stage-aligned delivery: every stage produces a demoable artifact. Closed decisions (§16) replace open questions — no ambiguity to negotiate later. Plugin / MCP / AI concepts are permanently excluded, not deferred (§7), removing an entire class of "is-it-really-out-of-scope" debates.

**Objections.** None open.

### 13.3 Customer Developer (VLSI Domain Owner)

Flow owner who authors JSONs and runs Chopper daily. Concerns are operator ergonomics.

**Endorses.** Deterministic output means diff review is meaningful. `--dry-run` previews without touching `<domain>_backup/`. Typed diagnostics — runbooks can be keyed on `code`.

**Objections.**

- *O1 — "Latin-1 files on old scripts must not break my flow."* Handled by `PW-02` fallback (scenario 11).
- *O2 — "I author on Windows, trim runs on Linux grid."* `pathlib.Path` + POSIX normalization. JSONs are LF-normalized.
- *O3 — "I want to know what would change before I run trim."* `--dry-run` produces `dependency_graph.json` and diagnostics without touching the domain.
- *O4 — **UNRESOLVED** — "What if I hand-edit `domain/` between trims and forget to commit?"* By design, Chopper discards hand edits on re-trim (`VI-03`, scenario 17). There is no `--preserve-hand-edits` safety net (see §16). This is a deliberate trade-off: the single-source-of-truth for the trimmed domain is `<domain>_backup/` + the JSON selection, not `<domain>/`. Operators must commit or stash hand edits **before** re-running. The `VI-03` diagnostic is the only mitigation. Accepted as a sharp edge; documented in the CLI help and runbook.

**Action items.**

1. CLI help text and runbook must call out `VI-03` prominently alongside `VE-23` — it is the only warning an operator can get about destroyed hand edits.

### 13.4 Market Evangelist (Latest-in-Market / Ecosystem)

**Endorses.** Single-process-first — matches how Ruff, dbt-core, and Pylance shipped. Stable JSON shapes for every result (via `SerializerPort`) mean downstream consumers (CI systems, diff reviewers, future report generators the user might build) get a frozen contract. Deterministic output is the prerequisite for any downstream automation.

**Objections.** None open. Golden-snapshot coverage is tracked in the consolidated action list (§13.6).

### 13.5 Optimization Engineer

**Endorses.** Frozen dataclasses for result objects — reproducible and profileable. Sink dedupe is O(1) via a hash set. Single-threaded v1 is the right call — measure before parallelizing, no speculative thread-safety.

**Objections.**

- *O1 — "Will frozen dataclasses thrash the allocator on 10k-proc domains?"* Not measured as a problem in comparable tools (mypy, Ruff). If a hotspot emerges post-v1, `slots=True` is a one-line fix.
- *O2 — "BFS frontier sort at every level is O(N log N)."* Real domain sizes are ~5–10k procs; sort cost is negligible vs I/O.
- *O3 — "5–10 min runtime guarantee is soft."* Intentional. v1 prioritizes correctness; benchmark harness and phase budgets are deferred to [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](FUTURE_PLANNED_DEVELOPMENTS.md) §FD-09.

**Action items.**

1. Record baseline wall-clock per phase on the large-domain fixture once stage 3 completes (observational, not gating).

### 13.6 Consolidated Verdict

| Dimension | Verdict |
|---|---|
| Architectural soundness | Ship stages 0–5 as spec'd. No stage 6. |
| Determinism | Enforced by design; golden tests on JSON shapes. |
| Diagnostic contract | Single emitter/collector spine; emission-order preservation + O(1) dedupe; `--strict` is an exit-code-only policy, never a severity rewrite. |
| Inter-service contract | Typed dataclasses + no inter-service imports; import-linter enforces. |
| User ergonomics | `VI-03` is the single warning-channel for destroyed hand edits — 13.3 O4 is an accepted sharp edge, not a solved problem. |
| Extensibility | **None.** Chopper has no plugin host, no MCP adapter, no AI advisor, no extension seams — permanently out of scope (§7, §16 Q1). |
| Concurrency | Single-threaded, single-user, no locks — closed decision, not a deferral. |
| Performance | Correctness first; 5–10 min runtime acceptable in v1; benchmarks deferred. |
| Risk to v1 delivery | Low — the plan organizes existing stage work; no new scope. |

**Consolidated action items (de-duplicated across all reviewers).**

1. **Import-linter contracts** for the stage layering described in §3.
2. **Golden snapshots** for the JSON shape of every public dataclass crossing a service boundary: `Diagnostic`, `RunResult`, `CompiledManifest`, `DependencyGraph`, `TrimReport`, `AuditManifest`. Treated as public contracts; any shape change is a breaking change per §14.2.
3. **Operator-facing docs** must call out `VI-03` prominently alongside `VE-23` — the only warning channel for destroyed hand edits.
4. **Observational benchmarks** per phase on the large-domain fixture once Stage 3 completes (not gating).

---

## 14. Contributor Playbook — Adding or Replacing a Feature

This is what "isolated feature development" looks like in practice.

### 14.1 Add a brand-new service (rare)

1. Decide which phase the feature belongs to. If it does not fit the 7 phases, revisit the design with the bible before coding.
2. Create `src/chopper/<package>/service.py` with a class exposing `run(ctx, ...) -> Result`.
3. Declare new result dataclasses in `core/models.py` (frozen).
4. Register any new diagnostic codes in [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) before emitting them.
5. Wire the service into `orchestrator/runner.py` at the correct phase boundary.
6. Write unit tests under `tests/unit/<package>/` using `make_test_context()` (§10.2) for the port layer.
7. Add an integration fixture under `tests/fixtures/` and an acceptance test under `tests/integration/`.
8. Add a golden snapshot for any new public JSON shape.
9. Run `make check` then `make ci` before pushing.

### 14.2 Rewrite an existing service end-to-end

1. Keep the `run(...)` signature and result dataclass identical.
2. Delete the module's internals; re-implement behind the same class.
3. Run the service's unit tests — they exercise the port-adapter boundary, so a correct rewrite passes unchanged.
4. Run golden snapshots — these validate that user-visible JSON shapes did not drift.
5. If a signature change is truly required, treat it as a breaking change: update the orchestrator wiring in `runner.py`, every affected service test, and any golden snapshots that bind the old shape — all in the same commit. There is no separate version number to bump; the commit is the contract change.

### 14.3 Add a new diagnostic code

1. Open [`docs/DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md) and take the lowest available reserved slot in the correct `<FAMILY><SEV>` band.
2. Fill in the registry row (code, phase, source, exit, description, hint).
3. Add a matching constant in `core/diagnostics.py`.
4. Emit it from the owning service only via `ctx.diag.emit(...)`.
5. Reference it by **code only** in other docs — never paraphrase.

### 14.4 Add a new adapter (for example, `JSONLProgress`)

1. Create `src/chopper/adapters/progress_jsonl.py`.
2. Implement the `ProgressSink` Protocol — no inheritance required.
3. Wire selection into the CLI or test harness.
4. No changes to services, orchestrator, or `core/`.

---

## 15. Adoption Roadmap (Stage-Aligned)

How this plan maps onto the existing Stage 0–5 build model in [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md).

| Stage | Current Scope | Architecture Plan Adds |
|---|---|---|
| **Stage 0** — `core/` | Shared frozen models, diagnostics, protocols, serialization | Add `ChopperContext` + `RunConfig`; finalize ports (`FileSystemPort`, `DiagnosticSink`, `ProgressSink`, `ClockPort`, `AuditStore`, `SerializerPort`, `TableRenderer`). **No `LockPort`, no `PluginHost`.** Codes `VE-25` and `VE-26` activated. `VE-16`, `VE-24`, `VI-04`, `VI-05` retired in registry. Import-linter contracts in place. |
| **Stage 1** — `parser/` | `parse_file()` returns `list[ProcEntry]`; `ParserService` wraps it (§9.2) | Service consumes `FileSystemPort` + `ClockPort`. Latin-1 fallback path tied to `PW-02`. Duplicate proc `PE-01` last-wins contract enforced. Backslash continuation `PW-05` tokenizer state. |
| **Stage 2** — `config/`+`compiler/` | Config loading, P3 merge, P4 BFS | Services expose `run(ctx, ...) -> Result`. `depends_on` cycle → `VE-25`; `depends_on` prerequisite missing → `VE-15`; feature order is **not** required (out-of-order allowed). Unresolvable `--project` paths → hard crash with `VE-13`, exit 2. |
| **Stage 3** — `trimmer/`+`generators/`+`audit/` | Trim state machine, run-file emission, `.chopper/` | `AuditStore` is the only writer under `.chopper/`. `--dry-run` gates P5. P5a→P5b gate prevents Generator from writing into half-trimmed tree. Filesystem errors during trim surface as `VE-26` with rollback. |
| **Stage 4** — `validator/` | Pre- and post-trim validation | Two services — `PreValidatorService.run` at P1, `PostValidatorService.run` at P6 — each emitting only to `DiagnosticSink`. |
| **Stage 5** — `cli/` | `validate`, `trim`, `cleanup` | CLI builds `ChopperContext`, calls `ChopperRunner`, owns the `TableRenderer`, and computes the exit code from `sink.finalize()` per §8.2 rule 4. Zero business logic in CLI. `--strict` is applied only at exit-code computation — never by rewriting severities. |

**There is no Stage 6 and none is planned.** Plugin host, MCP, AI advisor: permanently out of scope (§7, §16 Q1).

**No stage 0–5 change is required beyond what the bible and project conventions already demand.**

---

## 16. Closed Decisions

Questions raised during planning. All are resolved for v1.

### Q1 — Plugin host / MCP / AI advisor (CLOSED — permanently out of scope)

**Chopper has no plugin system, no MCP driver, no AI advisor, and no reserved extension seams.** There is no `PluginHost`, no `X*` diagnostic family, no `plugins/`, `mcp_server/`, or `advisor/` module, and no "stage 6" on the roadmap for any of these. Previous drafts reserved these concepts "for future use"; that reservation is now withdrawn.

**Rationale.** Reserving extension points that nobody is committed to building invites drift: an agent reading "reserved" treats it as "TODO", a contributor fills in the TODO, and a surface the project never approved ships. The cost of *not* reserving is near zero — if a future release ever genuinely needs a plugin mechanism, it will start with a fresh design doc (updating [`docs/chopper_description.md`](chopper_description.md) first) rather than resurrecting stubs from this plan. PRs that add plugin / MCP / advisor scaffolding are rejected at review.

### Q2 — Hand-edit preservation (CLOSED — not supported)

**Chopper does not preserve hand edits.** There is no `--preserve-hand-edits` flag, no stash path, no `.chopper/hand_edits/` directory. When re-trim detects that `<domain>/` diverges from the last generated output, `DomainStateService` emits `VI-03 domain-hand-edited`, discards the divergence, and rebuilds from `<domain>_backup/`.

**Rationale.** The single source of truth for the trimmed domain is `<domain>_backup/` plus the JSON selection. Shipping an automatic stash would encourage operators to rely on it as a versioning system, which it is not. Operators who want to keep hand edits commit or stash them **in their own VCS** before running `chopper trim`. `VI-03` is the explicit warning that any in-place edits to `<domain>/` are about to be destroyed.

### Q3 — Concurrency / locking (CLOSED — not supported)

**Chopper has no lock and no concurrency guard.** There is no `.chopper/.lock`, no `LockPort`, no `VE-24`, no stale-lock recovery, no `VI-05`. Chopper is a single-user push-button tool: one operator, one invocation, one on-disk domain, one result. If two operators race the same checkout on the same filesystem, the second invocation sees a half-written `DomainStateService` state and aborts through the normal `VE-23` / filesystem-error path. That is the intended failure mode, not a bug to guard against.

**Rationale.** Adding locks buys nothing: the real hazard (two concurrent writers on the same disk) is an operator-level contract violation that no cooperative file lock can fully prevent. Removing locks eliminates an entire category of stale-lock, crash-recovery, and cross-platform `fcntl` / `msvcrt` complexity.

### Q6 — Non-UTF8 encoding policy (CLOSED)

Already covered by `PW-02 utf8-decode-failure`. No new code.

Policy: read each file as UTF-8. On `UnicodeDecodeError`, retry as Latin-1 and emit `PW-02`. Parse continues on the Latin-1 content. Determinism requires a fixed fallback; Latin-1 is chosen because every byte decodes.

### Deferred (explicitly not v1)

- Runtime optimization and per-phase budgets — deferred to [`docs/FUTURE_PLANNED_DEVELOPMENTS.md`](FUTURE_PLANNED_DEVELOPMENTS.md) §FD-09.

---

*This plan is additive to, and subordinate to, [`docs/chopper_description.md`](chopper_description.md). When this plan and the bible disagree, the bible wins and this plan is updated in place (no addendums — per [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md) Documentation Conventions).*
