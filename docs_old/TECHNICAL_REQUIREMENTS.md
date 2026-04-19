# Chopper — Technical Requirements

> **Status:** Draft — Implementation Technical Baseline (Rev 11)
> **Last Updated:** 2026-04-05 (Rev 11)
> **Author:** rkudipud

---

## 1. Purpose and Boundary

This document complements `docs/ARCHITECTURE.md`.

`docs/ARCHITECTURE.md` defines:
- product behavior
- capability boundaries
- architecture decisions
- functional rules

This document defines:
- implementation engineering standards
- Python coding requirements
- repository and package structure
- runtime and file-system contracts
- CLI usability requirements
- diagnostics, logging, and exception behavior
- testing and release-quality gates

If the two documents appear to conflict:
- architecture decisions govern product behavior
- this document governs implementation detail

---

## 2. Engineering Principles

### 2.1 General Principles

- Prefer high cohesion and low coupling.
- Follow the Single Responsibility Principle for modules, classes, and functions.
- Use standard library components by default unless a focused dependency materially improves correctness or operator usability.
- Keep the core engine presentation-agnostic so CLI, TUI, and GUI layers can evolve independently.
- Favor deterministic behavior over convenience shortcuts.
- Prefer explicit configuration and explicit diagnostics over hidden magic.

### 2.2 SOLID Guidance

The implementation should apply SOLID pragmatically, not ceremonially.

| Principle | Chopper interpretation |
|---|---|
| **S** | A module or service should own one clear concern. |
| **O** | Add new domain behaviors through narrow extension points, not by rewriting core compilation logic. |
| **L** | Alternate implementations of parsers, renderers, or generators must preserve published contracts. |
| **I** | Keep interfaces small; do not force all consumers to depend on CLI-only or GUI-only behavior. |
| **D** | Core logic depends on abstractions and typed contracts, not on terminal rendering or filesystem details. |

### 2.3 Non-Negotiable Technical Outcomes

- No hardcoded environment-specific paths in implementation code.
- No `print()` in library code.
- No implicit half-written output state after trim failure.
- No UI formatting embedded inside compiler, parser, trimmer, or validator logic.
- No undocumented ad hoc JSON shapes.

---

## 3. Python Implementation Standards

### 3.1 Style and Naming

- Use 4 spaces per indentation level.
- Use `snake_case` for functions, methods, variables, and modules.
- Use `CamelCase` for classes.
- Use `UPPER_CASE` for module constants.
- Add type hints for all public functions and for important internal boundaries.
- Prefer short, single-purpose functions over long multi-branch routines.
- Keep reusable logic in separate modules rather than growing `cli.py` into a god module.

### 3.2 Line Length Policy

The repo currently enforces Ruff line length 120 in `pyproject.toml`.

- enforce that policy through Ruff rather than relying on manual review
- keep the existing 120-character toolchain setting until a dedicated formatting change is made
- prefer substantially shorter lines for prose, comments, docstrings, and new APIs when practical

### 3.3 Typing and Data Modeling

- Use `dataclass` models for internal records such as run selections, manifests, and diagnostics.
- Use `Enum` for constrained vocabularies such as file treatments, severities, and command modes.
- Use `Protocol` or similarly narrow interfaces where future alternate implementations are expected.
- Avoid passing raw untyped dicts through the core pipeline after input parsing.
- Convert external JSON input into typed internal models before compilation begins.

### 3.4 Exceptions and Error Handling

- Never assume filesystem, parsing, or configuration operations will always succeed.
- Catch exceptions at clear boundaries and re-emit user-facing diagnostics.
- Avoid bare `except:`.
- Avoid swallowing exceptions without logging context.
- Reserve raw stack traces for `--debug` or internal failure modes.
- Map expected user errors to stable exit codes and diagnostic records.

#### 3.4.1 Error Hierarchy

All Chopper-specific errors inherit from a single base class. Each error carries its exit code.

```python
# src/chopper/core/errors.py

class ChopperError(Exception):
    """Base for all Chopper-specific errors."""
    exit_code: ExitCode = ExitCode.INTERNAL_ERROR

class SchemaValidationError(ChopperError):
    """JSON input fails schema validation."""
    exit_code = ExitCode.VALIDATION_FAILURE

class CompilationError(ChopperError):
    """Conflict or invalid state during compilation."""
    exit_code = ExitCode.VALIDATION_FAILURE

class ParseError(ChopperError):
    """Tcl file cannot be parsed."""
    exit_code = ExitCode.VALIDATION_FAILURE

class TrimWriteError(ChopperError):
    """Live write failed; state should be restored."""
    exit_code = ExitCode.WRITE_FAILED_RESTORED

class DomainStateError(ChopperError):
    """Domain is in an unexpected lifecycle state."""
    exit_code = ExitCode.VALIDATION_FAILURE
```

The CLI entrypoint catches `ChopperError` and maps to exit codes; everything else maps to exit code 4 (INTERNAL_ERROR).

### 3.5 Logging

- Use the Python `logging` module as the foundational API.
- Library modules obtain named module loggers and do not configure global handlers.
- CLI entrypoints own log level, handler setup, and console/file output policy.
- Structured logging is required for machine-readable operational context.
- Use `structlog` (>= 24.1.0) as the structured logging wrapper for context binding and dual rendering.

#### 3.5.1 Logging Architecture

```python
# Library modules:
import logging
logger = logging.getLogger(__name__)

# CLI entrypoint configures structlog pipeline:
#   - Console handler: human-readable via structlog ConsoleRenderer (Rich-formatted if TTY)
#   - File handler (optional): JSON lines via structlog JSONRenderer
#   - Level: WARNING default, INFO with -v, DEBUG with --debug
```

#### 3.5.2 Structured Context Fields

Bound via `structlog.contextvars.bind_contextvars()` at the start of each command:

| Field | Source | Description |
|---|---|---|
| `run_id` | Generated per run | Unique run identifier |
| `command` | CLI subcommand | `scan`, `validate`, `trim`, `cleanup` |
| `domain` | CLI argument | Domain being operated on |
| `mode` | Execution mode | `scan`, `validate`, `trim`, `cleanup` |
| `feature_count` | Compiled selection | Number of selected features |

#### 3.5.3 JSON Log Format (JSON Lines)

```json
{
    "timestamp": "2026-04-04T10:30:00Z",
    "level": "WARNING",
    "logger": "chopper.compiler",
    "run_id": "abc123",
    "domain": "fev_formality",
    "message": "Duplicate file in include and exclude",
    "diagnostic_code": "V-04",
    "location": "feature_dft.json:files.include[2]"
}
```

#### 3.5.4 Diagnostic Correlation

- Diagnostics and log events are separate but correlated.
- Diagnostics are collected into reports (`trim_report.json`).
- Log events are streaming and include diagnostics as they occur.
- `--debug` enables full stack traces; default mode shows only diagnostic summaries.

#### 3.5.5 Library Logging Contract

- Attach a `logging.NullHandler()` to the top-level `chopper` logger so library usage does not trigger `lastResort` output when the caller has not configured logging.
- All module loggers must be descendants of `chopper` and should use `logging.getLogger(__name__)`.
- The CLI entrypoint should call `logging.captureWarnings(True)` after handler configuration so Python warnings appear in the same operator-visible stream.
- JSON logs use UTC timestamps in ISO 8601 form with a trailing `Z`.
- Shared logging helper functions must use `stacklevel` where needed so file/line attribution points at the caller, not the helper.
- Do not introduce custom log levels; use the standard Python levels only.

### 3.6 Dependency and Security Hygiene

- Keep third-party dependencies minimal and justified.
- Review runtime and dev dependencies regularly for security updates.
- Add dependency upgrades through explicit change review, not silent drift.
- Avoid bringing in a dependency when the standard library already provides a robust solution.
- Security scanning and dependency review must be part of the release gate.

---

## 4. Recommended Repository Structure

The repo should evolve toward a package layout aligned to Chopper's responsibilities, not a monolithic flat package.

```text
chopper/
├── bin/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TECHNICAL_REQUIREMENTS.md
│   └── ...
├── data/
│   ├── sample_inputs/
│   └── sample_outputs/
├── schemas/
│   ├── base-v1.schema.json
│   ├── feature-v1.schema.json
│   └── project-v1.schema.json
├── src/
│   └── chopper/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── commands.py
│       │   └── render.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loaders.py
│       │   └── settings.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── diagnostics.py
│       │   └── protocols.py
│       ├── compiler/
│       ├── parser/
│       ├── trimmer/
│       ├── validator/
│       ├── audit/
│       ├── generators/
│       └── ui/
│           ├── __init__.py
│           ├── progress.py
│           └── tables.py
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── property/
├── pyproject.toml
├── README.md
└── LICENSE
```

Notes:
- `bin/` is for wrappers or convenience launchers, not core logic.
- `json_kit/schemas/` should be first-class rather than embedded ad hoc in Python strings.
- `tests/fixtures/` should contain curated Tcl mini-domains and expected outputs.
- `ui/` or `cli/render.py` should be the only place that knows about colors, glyphs, terminal width, or tables.

### 4.1 Public API Surface

```python
# src/chopper/__init__.py
"""Chopper — EDA TFM trimming tool."""
__version__ = "0.1.0"

# src/chopper/core/__init__.py
"""Core models, protocols, and diagnostics."""
from chopper.core.models import *
from chopper.core.errors import *
from chopper.core.protocols import *

# Other packages export nothing by default — consumers import from submodules
```

Rule: only `core/` re-exports. All other packages require explicit submodule imports (e.g., `from chopper.parser.tcl_parser import ...`). This prevents circular imports and keeps the dependency graph clean.

---

## 5. Module Boundaries and GUI Readiness

### 5.1 Layering

Use this dependency direction:

```text
presentation layer  ->  application services  ->  domain/core logic
terminal/gui layer  ->  commands/results       ->  compiler/parser/trimmer
```

Hard rule:
- core logic must not depend on terminal rendering libraries

### 5.2 Future GUI Requirement

The program must be able to add a GUI later without rewriting the engine.

That requires:
- command handlers that return typed result objects, not pre-rendered strings
- progress emitted as structured events
- diagnostics emitted as structured records
- feature lists, manifests, and validation results available as serializable data models
- renderer adapters for CLI tables/views rather than inline formatting in service code

**Serialization contract:** Every frozen dataclass in the core models must be JSON-serializable via a standard `ChopperEncoder`:

```python
# src/chopper/core/serialization.py
import dataclasses
import json
from pathlib import PurePosixPath
from enum import Enum

class ChopperEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, PurePosixPath):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        return super().default(o)

def serialize(obj) -> str:
    return json.dumps(obj, cls=ChopperEncoder, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
```

- CLI `--json` flag uses this serializer for machine-readable output
- GUI reads the same JSON format
- Audit artifacts use the same serializer (per §7.3 deterministic key ordering)

**Future GUI wire protocol:** GUI communication will use JSON-over-stdio when implemented. The Chopper engine will accept a `TrimRequest` as JSON on stdin and emit a `TrimResult` as JSON on stdout. Progress events will be emitted as JSON lines on stderr. This protocol is not implemented in v1 but is enabled by the service-layer and serialization contracts.

### 5.3 Service Layer Contract

The service layer is the boundary between presentation (CLI/GUI) and domain logic. Each Chopper subcommand maps to one service class with a single `execute` method.

```python
@dataclass(frozen=True)
class TrimRequest:
    domain_path: Path
    base_json: Path
    feature_jsons: tuple[Path, ...]
    project_json: Path | None = None      # set when --project is used
    project_name: str = ""                 # from project JSON "project" field
    project_owner: str = ""                # from project JSON "owner" field
    release_branch: str = ""               # from project JSON "release_branch" field
    project_notes: tuple[str, ...] = ()    # from project JSON "notes" field
    dry_run: bool = False
    mode: TrimMode = TrimMode.TRIM

@dataclass(frozen=True)
class TrimResult:
    run_id: str
    exit_code: ExitCode
    compiled_manifest: CompiledManifest
    diagnostics: tuple[Diagnostic, ...]
    trim_stats: TrimStats
    audit_artifacts: dict[str, Path]

class TrimService(Protocol):
    def execute(self, request: TrimRequest, progress: ProgressSink | None = None) -> TrimResult: ...
```

**Project JSON handling at the service boundary:**
- Chopper assumes it is invoked from the domain root. The CLI layer treats the current working directory as the domain root for resolving `base` and `features` from a project JSON.
- The service layer receives a fully resolved `TrimRequest` and does not re-parse the project JSON. It treats `base_json` and `feature_jsons` identically regardless of whether they originated from `--base`/`--features` or `--project`.
- The project JSON `domain` field is a required identifier for audit and consistency; it does not become an alternate path-resolution root.
- The `project_json`, `project_name`, `project_owner`, `release_branch`, and `project_notes` fields are passed through to audit artifacts (`chopper_run.json`, `compiled_manifest.json`) for traceability.

Equivalent request/result pairs exist for `ScanService`, `ValidateService`, and `CleanupService`. This gives CLI, GUI, and test harnesses a single contract to program against.

Rules:
- Services accept typed request objects and return typed result objects.
- Services never print to stdout/stderr directly.
- Services accept an optional `ProgressSink` for streaming progress.
- Services raise `ChopperError` subclasses for expected errors.

### 5.4 Progress Event Model

Progress events allow CLI and future GUI to report operation status.

```python
class ProgressEvent(Protocol):
    phase: str          # "parse", "compile", "trace", "build", "validate"
    current: int        # current item number
    total: int          # total items (0 if unknown)
    message: str        # human-readable status

class ProgressSink(Protocol):
    def on_progress(self, event: ProgressEvent) -> None: ...
    def on_diagnostic(self, diagnostic: Diagnostic) -> None: ...

# Lightweight diagnostic callback for internal modules (parser, tracer).
# Modules that are NOT top-level services use this instead of ProgressSink.
DiagnosticCollector = Callable[[Diagnostic], None]
```

The CLI creates a `RichProgressSink` (or `PlainProgressSink` for CI). Service code accepts a `ProgressSink` parameter and emits events at phase transitions and during long-running operations (file processing, trace expansion).

**Internal module diagnostic pattern:** Lower-level modules (parser, tracer) are not service endpoints. They accept an optional `DiagnosticCollector` callback instead of `ProgressSink`. The calling service (compiler) bridges the two by passing `progress.on_diagnostic` as the collector. When no collector is provided, diagnostics are silently discarded (useful for unit testing the parser in isolation).

```python
# Example: compiler bridges ProgressSink to parser's DiagnosticCollector
def _compile_phase_parse(domain: Path, progress: ProgressSink) -> dict[str, ProcEntry]:
    proc_index = {}
    for tcl_file in sorted(domain.rglob("*.tcl")):
        entries = parse_file(domain, tcl_file, on_diagnostic=progress.on_diagnostic)
        for entry in entries:
            proc_index[entry.canonical_name] = entry
    return proc_index
```

### 5.5 Extension Points

Three customization seams enable domain-specific behavior without modifying core code:

**1. Post-Trim Script Hook (`options.template_script`):**

`options.template_script` is not a Python plugin interface. It is an optional domain-relative path to an existing script under the selected domain root. Chopper resolves it against the domain root, preserves the referenced file in the trimmed domain, and executes it exactly once at the end of a successful `trim` run before the process exits.

**2. Custom Validator Protocol:**
```python
class CustomValidator(Protocol):
    def validate(self, domain_path: Path, manifest: CompiledManifest) -> list[Diagnostic]: ...
```
Allows domain-specific post-trim checks beyond standard validation.

**3. Output Formatter Protocol:**
```python
class OutputFormatter(Protocol):
    def format_report(self, result: TrimResult) -> str: ...
    def format_diagnostics(self, diagnostics: Sequence[Diagnostic]) -> str: ...
```
Separates output formatting from service logic. CLI and GUI implement different formatters.

#### 5.5.1 Post-Trim Script and Extension Registration

- `options.template_script` is a path relative to the selected domain root.
- The path must remain inside the domain. Absolute paths and `..` traversal outside the domain are invalid.
- Users are expected to invoke Chopper from the domain directory, but correctness does not depend on ambient shell state; Chopper resolves the path against the selected domain root explicitly.
- The referenced script is treated as a required kept file with keep reason `template` so it is available in the trimmed domain when executed.
- Chopper executes the script exactly once after a successful live `trim` run, after the normal trim pipeline has completed and before the process exits.
- Chopper does not execute `template_script` during `scan`, `validate`, `trim --dry-run`, or `cleanup`.
- The process working directory for the script is the active trimmed domain root.
- The field is a path, not a shell command string. Inline arguments, shell metacharacter expansion, and paths outside the domain are not supported in v1.
- **Execution behavior (A-05):** Chopper executes the script and always exits successfully (exit code 0) regardless of the script's exit code. If the script cannot be resolved or found, Chopper logs a WARNING and continues normally (does not fail the trim). If the script cannot be executed (permissions, etc.), log WARNING and continue. The script's success or failure is NOT a trim failure condition.

- Chopper discovers Python extension implementations through `importlib.metadata.entry_points()`, not `pkg_resources`.
- Extension groups are versioned and named explicitly:

| Entry point group | Interface |
|---|---|
| `chopper.validators` | `CustomValidator` |
| `chopper.output_formatters` | `OutputFormatter` |

- Extension names are matched exactly; there is no fuzzy matching or partial-name resolution.
- Extension load failures are fatal only when the selected config explicitly references the extension; otherwise undiscovered optional plugins are ignored.
- Entry point names should use only letters, numbers, underscores, dots, and dashes.
- Do not rely on entry-point extras for behavior selection; installation-time optional dependencies belong in normal package extras and deployment documentation.

### 5.6 Renderer Adapter Interface

All CLI presentation goes through renderer adapters. Service code never imports from `ui/`.

```python
# src/chopper/ui/protocols.py
from typing import Protocol, Sequence

class TableRenderer(Protocol):
    def render_table(self, headers: Sequence[str], rows: Sequence[Sequence[str]], title: str = "") -> str: ...

class DiagnosticRenderer(Protocol):
    def render_diagnostics(self, diagnostics: Sequence[Diagnostic]) -> str: ...

class ProgressRenderer(Protocol):
    def start(self, total: int, description: str) -> None: ...
    def advance(self, amount: int = 1) -> None: ...
    def finish(self) -> None: ...
```

- `src/chopper/ui/rich_renderer.py` — implements above using Rich (when available)
- `src/chopper/ui/plain_renderer.py` — implements above using plain text (fallback)

The CLI creates the appropriate renderer based on TTY detection and `--plain`/`--no-color` flags.

### 5.7 Feature List View Readiness

Feature catalog and selection UIs are a foreseeable need.

Technical requirement:
- provide a queryable feature model with name, description, origin, ordering, and selection state
- renderer adapters must support list/table/tree presentation without changing the underlying service contract
- JSON output mode must expose the same information that a future GUI would need

---

## 6. Configuration, Paths, and Schemas

### 6.1 Configuration Precedence

Configuration precedence must be deterministic:

1. CLI arguments
2. environment overrides
3. project selection file
4. workspace-level config (`.chopper.config` in the working directory)
5. built-in defaults

#### 6.1.1 Workspace Configuration File

For power users, Chopper supports an optional hidden configuration file `.chopper.config` in the working directory where Chopper is invoked. This is a TOML file.

**Location:** `.chopper.config` in the current working directory (same directory the user invokes `chopper` from).

**All settings are optional.** Chopper works with sensible defaults and does not require a config file. The config file is for power users who want to override defaults.

```toml
# .chopper.config — optional workspace-level overrides

[logging]
log_level = "WARNING"            # WARNING (default), INFO, DEBUG
log_file = ".chopper/chopper.log"  # optional JSON lines log file

[display]
color = "auto"                   # auto (default), always, never
plain = false                    # disable Rich rendering
progress = true                  # show progress bars on TTY

[paths]
schemas_path = "schemas"           # path to JSON schema files

[validation]
cross_validate = true            # cross-validate F3 output against F1/F2
strict = false                   # treat warnings as errors

[locking]
stale_timeout_seconds = 7200     # age threshold for classifying recovered abandoned lock metadata as stale
```

**Environment overrides:**

| Environment Variable | Config Key | Description |
|---|---|---|
| `CHOPPER_LOG_LEVEL` | `logging.log_level` | Log level override |
| `CHOPPER_NO_COLOR` | `display.color` | Set to `1` to disable color |
| `CHOPPER_COMMON_PATH` | `paths.common_path` | Override common/ path |
| `CHOPPER_PLAIN` | `display.plain` | Set to `1` for plain output |
| `CHOPPER_LOCK_STALE_TIMEOUT` | `locking.stale_timeout_seconds` | Override abandoned-lock stale classification threshold in seconds |

CLI always wins over environment, which wins over config file, which wins over defaults.

#### 6.1.2 Merge and Validation Rules

- Configuration is loaded once at CLI startup and treated as immutable thereafter.
- Relative paths in `.chopper.config` are resolved relative to the directory containing the config file.
- Malformed TOML, unknown keys, or type mismatches in `.chopper.config` are CLI usage errors (exit code 2), not warnings.
- Higher-precedence scalar values replace lower-precedence values. Higher-precedence lists and mappings replace the whole lower-precedence value unless the option explicitly defines merge semantics.
- Feature lists provided on the CLI replace project-selected feature lists; they are not concatenated.
- Boolean environment overrides accept `1`/`0`, `true`/`false`, and `yes`/`no` case-insensitively.

### 6.2 No Hardcoded Paths

- Never hardcode repo-local or site-local paths in code.
- Use config and runtime resolution for any environment-specific path.
- Represent file system paths with `pathlib.Path` internally.
- Normalize to domain-relative POSIX strings at manifest and diagnostic boundaries.

### 6.3 Schema and Input Contracts

- Base, feature, and project JSONs must each have explicit schema files.
- Structural validation belongs in schema validation.
- Semantic validation belongs in Chopper code.
- Schema versioning must remain explicit and stable.

### 6.4 Path and Glob Semantics

Moved from the architecture document.

Hard rules:
- Paths in JSON are relative to the domain root, which in normal v1 operation is the current working directory.
- Paths use forward slashes (Unix/POSIX style).
- Absolute paths and `..` traversal outside the domain root are validation errors.
- Matches are collected, normalized, deduplicated, and sorted in lexicographic order before compilation.
- Final manifests store concrete files, not unresolved globs.

#### 6.4.1 Supported Glob Pattern Syntax

Three special characters support glob expansion in `files.include` and `files.exclude`:

| Pattern | Scope | Matches | Does NOT Match |
|---------|-------|---------|----------------|
| `*` | Single directory level (does not cross `/`) | Any number of characters within one directory | Characters in subdirectories |
| `?` | Single directory level (does not cross `/`) | Exactly one character within one directory | Multiple characters or characters in subdirectories |
| `**` | Multiple levels and nested directories (recursive) | Any number of directories and subdirectories | Nothing — always matches all depths |

**Examples:**

| Pattern | Matches | Does Not Match | Explanation |
|---------|---------|----------------|-------------|
| `*.tcl` | `foo.tcl`, `bar.tcl` | `sub/foo.tcl` | `*` stays within domain root (no `/`) |
| `procs/*.tcl` | `procs/core.tcl`, `procs/rules.tcl` | `procs/sub/deep.tcl` | `*` stops at first `/` boundary |
| `utils/*.py` | `utils/helper.py` | `utils/sub/deep.py` | `*` does not cross subdirectories |
| `reports/**` | `reports/a.txt`, `reports/sub/b.csv`, `reports/a/b/c.txt` | `other/a.txt` | `**` matches at any depth within `reports/` |
| `**/*.tcl` | `a.tcl`, `sub/b.tcl`, `a/b/c.tcl` | `a.py` | `**` combined with `*` finds `.tcl` files at any depth |
| `procs/**/*.tcl` | `procs/a.tcl`, `procs/sub/b.tcl`, `procs/a/b/c.tcl` | `rules/a.tcl` | `**` finds nested `.tcl` files under `procs/` only |
| `pre_*.tcl` | `pre_setup.tcl`, `pre_load.tcl` (at domain root) | `setup.tcl`, `procs/pre_setup.tcl` | `*` matches filename pattern, not path separators |
| `step_?.tcl` | `step_a.tcl`, `step_1.tcl` | `step_ab.tcl`, `step__.tcl` | `?` matches exactly one character |
| `rule?.fm.tcl` | `rule1.fm.tcl`, `rule2.fm.tcl`, `rulex.fm.tcl` | `rule12.fm.tcl`, `rule.fm.tcl` | `?` matches any single char (no multiple or none) |

**Implementation details:**
- Glob expansion uses `pathlib.Path.glob()` with POSIX-path normalization.
- The `**` pattern requires `pathlib.Path.glob("**/...")` semantics.
- Patterns are **case-sensitive**.
- When a glob pattern expands to zero files, it is silently ignored (no error raised).
- Glob expansion happens **before** Decision 5 (include-wins) rules are applied.

**Decision 5 interaction with glob patterns:**
- Literal file paths in `files.include` (no special characters) **always survive**, even if they match `files.exclude` patterns.
- Wildcard-expanded `files.include` candidates **are pruned** by matching `files.exclude` patterns (standard set subtraction).
- Both literal and wildcard expansions are normalized and deduplicated before this rule is applied.

Glob expansion uses `pathlib.Path.glob()` with POSIX-path normalization. The `**` pattern requires `pathlib.Path.glob("**/...")` semantics.

---

## 7. Runtime and File-System Contracts

### 7.1 Internal Compilation Contract

Chopper normalizes all user inputs into one immutable run plan before any live file writes occur.

| Model | Purpose |
|---|---|
| `RunSelection` | Domain path, execution mode, selected base, ordered features, and run options |
| `CompiledFiles` | Final file treatment set: full copy, proc-trim, remove, generated |
| `CompiledProcedures` | Explicit, traced, replaced, and removed proc decisions |
| `CompiledFlow` | Resolved stage/step graph after all `flow_actions` are applied |
| `Diagnostic` | Stable machine-readable warning/error record with severity, code, location, and hint |

Hard rules:
- Feature order from CLI or project JSON is authoritative.
- Within a single feature JSON, `flow_actions` are applied top-to-bottom.
- Later selected features operate on the already-modified result produced by earlier features.
- The compiled plan is frozen before live trim begins and is serialized into `compiled_manifest.json`.

#### 7.1.1 Compilation Algorithm

The compilation algorithm receives a resolved base JSON and an ordered list of feature JSONs. When `--project` is used, the CLI layer resolves the project JSON into a base path and feature paths before invoking the compiler. Equivalent resolved selections must produce identical results regardless of input mode.

```python
def compile(base: BaseJSON, features: list[FeatureJSON], domain: Path) -> CompiledPlan:
    base_files = base.files or EmptyFileRules()
    base_procedures = base.procedures or EmptyProcedureRules()

    # Phase 1: Collect file rules (literal paths vs broad glob candidates)
    fi_explicit, fi_glob = partition_file_includes(base_files.include or (), domain)
    fe = expand_globs(base_files.exclude or (), domain)
    for feature in features:  # ordered
        feature_files = feature.files or EmptyFileRules()
        feature_fi_explicit, feature_fi_glob = partition_file_includes(feature_files.include or (), domain)
        fi_explicit |= feature_fi_explicit
        fi_glob |= feature_fi_glob
        fe |= expand_globs(feature_files.exclude or (), domain)

    # Phase 2: Collect proc rules
    pi = collect_proc_entries(base_procedures.include or ())
    pe = collect_proc_entries(base_procedures.exclude or ())
    for feature in features:  # ordered
        feature_procedures = feature.procedures or EmptyProcedureRules()
        pi |= collect_proc_entries(feature_procedures.include or ())
        pe |= collect_proc_entries(feature_procedures.exclude or ())

    # Phase 3: Trace expansion (PI -> PI+)
    # Parser contract: parse_file() returns list[ProcEntry], emits diagnostics
    # via optional on_diagnostic callback (DiagnosticCollector). The compiler
    # passes progress.on_diagnostic as the callback to collect parser diagnostics
    # into the manifest's diagnostics tuple.
    proc_index = build_proc_index(domain)  # parse all Tcl files
    pi_plus = trace_expand(pi, proc_index)

    # Phase 4: Apply Decision 5 (explicit include wins)
    pt = pi_plus - pi  # traced-only proc keeps
    surviving_files = fi_explicit | (fi_glob - fe)
    surviving_procs = pi | (pt - pe)

    # Phase 5: Determine file treatments
    for file in domain_files:
        if file in surviving_files:
            treatment = FileTreatment.FULL_COPY
        elif file has procs in surviving_procs:
            treatment = FileTreatment.PROC_TRIM
        else:
            treatment = FileTreatment.REMOVE

    # Phase 6: Apply flow_actions (features in order, actions top-to-bottom)
    flow = copy(base.stages)
    for feature in features:
        for action in feature.flow_actions:
            apply_flow_action(flow, action)

    # Phase 7: Freeze
    return CompiledPlan(files=..., procs=..., flow=..., diagnostics=...)
```

Key implementation notes:
- `partition_file_includes()` treats literal file paths as explicit keeps and wildcard patterns as broad candidate generation.
- Glob expansion uses `pathlib.Path.glob()` with POSIX-path normalization.
- Glob patterns support `*`, `?`, and `**` (see §6.4.1 for syntax).
- All glob results are sorted lexicographically after expansion.
- `files.exclude` prunes only wildcard-expanded file candidates; it never removes a literal file include.
- `procedures.exclude` prunes only trace-derived proc candidates; it never removes an explicit `procedures.include` entry.
- Feature file/proc rules are unioned across all features (order-independent for the explicit and derived keep sets).
- `flow_actions` are order-dependent: later features see results of earlier features.

**Trace domain-boundary enforcement:** A proc is considered "inside the domain" when its resolved path is relative to the resolved domain path:

```python
proc_path_resolved = Path(proc_file_path).resolve()
domain_path_resolved = Path(domain_path).resolve()
is_in_domain = proc_path_resolved.is_relative_to(domain_path_resolved)
```

- `Path.resolve()` follows symlinks and canonicalizes the path.
- A resolved proc path that is NOT relative to the resolved domain path triggers `TRACE-CROSS-DOMAIN-01`.
- File dependencies (`source`, `iproc_source`) follow the same rule.
- This prevents symlink-based domain escape during tracing.

> **v1 Limitation — No Checkpointing:** The compilation pipeline is not checkpointed in v1. A crash during Phase 5 (file copy / proc deletion in the trimmer) requires a full restart from Phase 1. For very large domains (>10 GB), this may waste substantial runtime. Mitigation: run on a fast local disk; ensure trim operations complete within the advisory lock window. v2 enhancement opportunity: emit `compiled_plan.json` after Phase 4 to enable Phase 5 resumption on re-run.

#### 7.1.2 Concrete Data Models

All core models are frozen dataclasses in `src/chopper/core/models.py`:

```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath


class ExitCode(Enum):
    SUCCESS = 0
    VALIDATION_FAILURE = 1
    CLI_ERROR = 2
    WRITE_FAILED_RESTORED = 3
    INTERNAL_ERROR = 4


class FileTreatment(Enum):
    FULL_COPY = "full-copy"
    PROC_TRIM = "proc-trim"
    REMOVE = "remove"
    GENERATED = "generated"


class KeepReason(Enum):
    EXPLICIT_FILE = "explicit-file"
    EXPLICIT_PROC = "explicit-proc"
    TRACED = "traced"
    FLOW_ACTION = "flow-action"
    TEMPLATE = "template"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticSource(Enum):
    SCHEMA = "schema"
    COMPILER = "compiler"
    PARSER = "parser"
    TRIMMER = "trimmer"
    VALIDATOR = "validator"
    AUDIT = "audit"


class TrimMode(Enum):
    SCAN = "scan"
    VALIDATE = "validate"
    TRIM = "trim"
    CLEANUP = "cleanup"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str              # e.g., "V-09", "TRACE-AMBIG-01"
    message: str
    location: str
    hint: str
    source: DiagnosticSource


@dataclass(frozen=True)
class ProcEntry:
    canonical_name: str          # "relative/path.tcl::qualified_name"
    short_name: str              # As authored in JSON
    qualified_name: str          # Namespace-qualified, leading :: stripped
    source_file: PurePosixPath
    start_line: int
    end_line: int
    body_start_line: int
    body_end_line: int
    namespace_path: str
    # --- Span extensions (TCL_PARSER_SPEC §4.6–§4.7) ---
    dpa_start_line: int | None = None      # define_proc_attributes block start
    dpa_end_line: int | None = None        # define_proc_attributes block end
    comment_start_line: int | None = None  # doc-comment banner start
    comment_end_line: int | None = None    # doc-comment banner end
    # --- Call graph data (TCL_PARSER_SPEC §5.3–§5.4) ---
    calls: tuple[str, ...] = ()            # raw call tokens, deduplicated + sorted
    source_refs: tuple[str, ...] = ()      # literal source/iproc_source paths


@dataclass(frozen=True)
class FileEntry:
    path: PurePosixPath
    treatment: FileTreatment
    reason: KeepReason


@dataclass(frozen=True)
class ProcDecision:
    canonical_name: str
    source_file: PurePosixPath
    reason: KeepReason
    incoming_edges: tuple[str, ...]


@dataclass(frozen=True)
class StageDefinition:
    name: str
    load_from: str
    command: str = ""                   # Optional — empty string when not provided
    inputs: tuple[str, ...] = ()        # Optional — empty tuple when not provided
    outputs: tuple[str, ...] = ()       # Optional — empty tuple when not provided
    run_mode: str = "serial"            # "serial" or "parallel"
    steps: tuple[str, ...]


@dataclass(frozen=True)
class TrimStats:
    files_before: int
    files_after: int
    procs_before: int
    procs_after: int
    loc_removed: int  # LOC excludes blank lines and comment-only lines


@dataclass(frozen=True)
class RunSelection:
    domain_path: PurePosixPath
    mode: TrimMode
    base_json: PurePosixPath
    feature_jsons: tuple[PurePosixPath, ...]
    dry_run: bool = False
    run_id: str = ""
    project_json: PurePosixPath | None = None      # set when --project is used
    project_name: str = ""                          # from project JSON "project" field
    project_owner: str = ""                         # from project JSON "owner" field
    release_branch: str = ""                        # from project JSON "release_branch" field
    project_notes: tuple[str, ...] = ()             # from project JSON "notes" field


@dataclass(frozen=True)
class CompiledManifest:
    run_id: str                                     # Unique run identifier
    domain_path: PurePosixPath                      # Domain root path
    base_json_path: PurePosixPath                   # Path to selected base JSON
    feature_json_paths: tuple[PurePosixPath, ...]  # Ordered list of selected feature JSONs
    project_json_path: PurePosixPath | None        # Path to project JSON (None if not used)
    project_name: str                              # Project identifier (empty if not used)
    project_notes: tuple[str, ...]                 # Selection rationale notes (empty if not used)
    files: tuple[FileEntry, ...]                   # All file treatment decisions
    procs: tuple[ProcDecision, ...]                # All proc-level decisions (including traced)
    flow_stages: tuple[StageDefinition, ...]       # Resolved F3 stages (may be empty if F3 not used)
    diagnostics: tuple[Diagnostic, ...]            # All warnings/errors during compilation
    trim_stats: TrimStats                          # Before/after file/proc/LOC counts
    timestamp: str                                 # ISO 8601 UTC (e.g., "2026-04-05T10:30:00Z")
    command_line_args: str                         # Full CLI invocation for reproducibility
    chopper_version: str                           # Software version that produced this manifest
```

Key design rules:
- `frozen=True` on all models representing compiled state (immutability per §7.1)
- `tuple` instead of `list` for frozen dataclass fields (lists are mutable)
- `PurePosixPath` for all domain-relative paths (per §6.2 forward-slash normalization)
- `Enum` for all constrained vocabularies (per §3.3)
- No `Optional` fields without explicit defaults — every field is required or has a clear default

### 7.2 Audit Artifact Contract

This section freezes the machine-readable contract for both live-run artifacts and `scan` output artifacts.

Only JSON documents that are themselves user-facing configuration payloads carry formal `$schema` IDs in v1: base JSON, feature JSON, project JSON, and scan-generated `draft_base.json`.

Operational artifacts such as `compiled_manifest.json`, `chopper_run.json`, `dependency_graph.json`, `trim_report.json`, `diagnostics.json`, `trim_stats.json`, `file_inventory.json`, `proc_inventory.json`, and `scan_report.json` do NOT carry formal schema IDs in v1. They are governed by the field-level contracts in this section and by `chopper_version`.

Machine-readable artifacts carry `"chopper_version": "0.1.0"` at top level.

`draft_base.json` reuses `chopper/base/v1` and MUST also carry the architecture-defined `"_draft": true` marker because it is itself a Base JSON document.

Text reports do not carry schema IDs:
- `trim_report.txt` is the human-readable projection of `trim_report.json`
- `scan_report.txt` is the human-readable projection of `scan_report.json`
- Text reports must not contain facts absent from their corresponding JSON artifact

| Artifact | Minimum required content |
|---|---|
| `chopper_run.json` | Run ID, command/subcommand, mode (`scan` / `validate` / `trim` / `cleanup`), domain, source root, backup root, timestamps, exit code, and when `--project` is used: `project_json_path`, `project_name`, `project_owner`, `release_branch` |
| `input_base.json` | Exact copy of the resolved base JSON used for the live trim run |
| `input_features/` | Exact copies of the resolved feature JSONs used for the live trim run, preserving selected feature order |
| `input_project.json` | Exact copy of the selected project JSON when `--project` mode is used |
| `compiled_manifest.json` | Selected base, ordered features, resolved file actions, resolved proc actions, resolved flow actions, normalized options |
| `dependency_graph.json` | Shared schema for scan and trim output. Must contain proc nodes, proc edges, file edges, unresolved references, and resolution reasons. |
| `trim_report.json` | Summary counts, validation results, diagnostics, before/after file stats, before/after proc stats |
| `trim_report.txt` | Human-readable summary aligned with `trim_report.json` |
| `draft_base.json` | Valid `chopper/base/v1` payload plus `"_draft": true`; produced only by `scan` as a starting point for owner curation |
| `file_inventory.json` | Domain identifier, scan timestamp, and one sorted entry per discovered file including at least `path`, `language`, `classification`, and `proc_count` |
| `proc_inventory.json` | Domain identifier, scan timestamp, and one sorted entry per discovered proc including at least `canonical_name`, `short_name`, `source_file`, `start_line`, `end_line`, and `namespace_path` |
| `scan_report.json` | Summary counts, diagnostics, generated artifact list, and explicit owner follow-up items or manual-review notes |
| `scan_report.txt` | Human-readable summary aligned with `scan_report.json` |

`compiled_manifest.json` file entries must carry at least:
- `path`: Domain-relative path
- `treatment`: FileTreatment enum value ("full-copy", "proc-trim", "remove", "generated")
- `reason`: KeepReason enum value

#### 7.2.1 Audit Directory Structure (Live Trim Run)

When Chopper executes a live `trim` run, it creates a `.chopper/` directory in the domain root with the following structure:

```
domain/.chopper/
├── chopper_run.json              # Run metadata (command, mode, timestamps, exit code)
├── input_base.json               # Exact base JSON used for the live trim
├── input_features/               # Exact feature JSONs used for the live trim
├── input_project.json            # Optional: exact project JSON when --project is used
├── compiled_manifest.json        # Complete compilation result (files, procs, flow, diagnostics)
├── trim_report.json              # Human-readable summary (counts, before/after, validation)
├── trim_report.txt               # Text version aligned with JSON
├── dependency_graph.json         # Proc call graph + unresolved references
├── diagnostics.json              # All warnings/errors with location context
├── trim_stats.json               # Numbers: files before/after, procs before/after, LOC removed
└── run_id                        # Plain text file containing UUID for log correlation
```

#### 7.2.2 Audit Directory Structure (Scan Run)

When Chopper executes `scan`, output artifacts go to a user-specified directory (not committed to domain):

```
scan_output/
├── draft_base.json               # Generated base JSON (marked with _draft=true) for owner curation
├── scan_report.json              # Machine-readable summary: discovered files, procs, dependencies
├── scan_report.txt               # Human-readable version
├── file_inventory.json           # All discovered files with metadata (language, classification, proc_count)
├── proc_inventory.json           # All discovered procs with metadata (canonical_name, source_file, lines)
├── dependency_graph.json         # Source/iproc_source file dependencies + proc call edges
├── diff_report.json              # (Optional) Changes from previous scan (if jsons/base.json exists)
└── diagnostics.json              # Warnings/errors encountered during scanning
```

#### 7.2.2.1 Scan Diff Report Contract (`diff_report.json`)

When `jsons/base.json` exists in the domain at scan time, Chopper produces a `diff_report.json` showing what has changed since that base was authored. This artifact is machine-readable and must conform to the following minimum-field contract:

```json
{
  "chopper_version": "0.1.0",
  "scan_date": "2026-04-05T10:30:00Z",
  "base_json_path": "jsons/base.json",
  "base_json_mtime": "2026-03-28T14:00:00Z",
  "comparison": {
    "new_files": ["new_util.tcl", "addon/new_feature.tcl"],
    "removed_files": ["old_legacy.tcl"],
    "new_procs": [
      {"file": "flow_procs.tcl", "canonical_name": "flow_procs.tcl::new_check_fn"}
    ],
    "removed_procs": [
      {"file": "old_legacy.tcl", "canonical_name": "old_legacy.tcl::deprecated_fn"}
    ]
  },
  "summary": {
    "files_added": 2,
    "files_removed": 1,
    "procs_added": 1,
    "procs_removed": 1
  }
}
```

**Rules:**
- `new_files` = files found on disk but not referenced in the existing base JSON `files.include`.
- `removed_files` = files referenced in the existing base JSON but no longer present on disk.
- `new_procs` = procs found on disk but not referenced in the existing base JSON `procedures.include`.
- `removed_procs` = procs referenced in the existing base JSON but whose source file or proc definition no longer exists.
- All arrays are lexicographically sorted (files by path, procs by canonical name).
- If `jsons/base.json` does not exist, `diff_report.json` is not emitted.

**Production conditions:** `diff_report.json` is produced by `chopper scan` **only** when ALL of the following are true:

1. `jsons/base.json` exists in the domain at scan time
2. `jsons/base.json` passes `chopper/base/v1` schema validation

If `jsons/base.json` exists but is malformed (fails schema validation), `diff_report.json` is NOT produced. Instead, a `PARSE-ENCODING-01`-style warning is emitted noting that the existing base JSON could not be loaded for comparison.

**Comparison semantics:**
- Compare by `canonical_name` (`file.tcl::proc_name`), not by `short_name`
- If a proc is removed from file A and re-added in file B with the same short name, it appears in both `removed_procs` and `new_procs`
- All arrays in the diff report are sorted lexicographically (files by path, procs by canonical name)

#### 7.2.3 Machine-Readable Artifact Minimum Fields

| Artifact | Chopper Version | Minimum Content |
|----------|-----------------|----------|
| `chopper_run.json` | ✅ | run_id, command, mode, domain, timestamps, exit_code |
| `input_base.json` | n/a | exact base JSON copy used for the live trim |
| `input_features/` | n/a | exact feature JSON copies used for the live trim |
| `input_project.json` | n/a | exact project JSON copy when `--project` is used |
| `compiled_manifest.json` | ✅ | all CompiledManifest fields |
| `trim_report.json` | ✅ | diagnostics, file stats, proc stats, validation results |
| `trim_report.txt` | (none) | Human-readable projection of trim_report.json |
| `dependency_graph.json` | ✅ | proc nodes, proc edges, file edges, unresolved refs |
| `diagnostics.json` | ✅ | Array of {severity, code, message, location, hint} |
| `trim_stats.json` | ✅ | files_before, files_after, procs_before, procs_after, loc_removed |
| `draft_base.json` | n/a | valid base JSON + `"_draft": true` |
| `file_inventory.json` | ✅ | stable array of {path, language, classification, proc_count} |
| `proc_inventory.json` | ✅ | stable array of {canonical_name, source_file, start_line, end_line, namespace_path} |
| `scan_report.json` | ✅ | file count, proc count, diagnostics, owner follow-up items |
| `scan_report.txt` | (none) | Human-readable projection of scan_report.json |

**Key Invariants:**
- Operational JSON artifacts MUST have `"chopper_version"` at top level
- `draft_base.json` MUST have `"$schema": "chopper/base/v1"` because it is itself a base JSON document
- User-authored ordered collections MUST preserve authored order (selected features, stages, stage steps, flow actions)
- Discovery-derived or set-like collections MUST use a stable deterministic order
- Text reports (`*.txt`) are human-readable projections only; JSON is source of truth
- Artifacts produced by `scan` live outside the domain (not committed)
- Artifacts produced by `trim` live in `.chopper/` in the domain and ARE committed
- `treatment` (`full-copy`, `proc-trim`, `remove`, `generated`)
- `reason` (`explicit-file`, `explicit-proc`, `traced`, `flow-action`, `template`)

`compiled_manifest.json` proc entries must carry at least:
- `canonical_name`
- `source_file`
- `reason`
- `incoming_edges`

`file_inventory.json` file entries must carry at least:
- `path`
- `language`
- `classification`
- `proc_count`

`proc_inventory.json` proc entries must carry at least:
- `canonical_name`
- `short_name`
- `source_file`
- `start_line`
- `end_line`
- `namespace_path`

`scan_report.json` must carry at least:
- `summary`
- `diagnostics`
- `generated_artifacts`
- `owner_actions`

### 7.3 Determinism, Staging, and Failure Recovery

Hard rules:
- All paths are normalized to domain-relative POSIX form before comparison or manifest emission.
- All directory walks, glob results, file inventories, proc inventories, and emitted graph nodes are sorted lexicographically before further processing.
- User-authored ordered collections are never re-sorted; preserve selected feature order, stage order, step order, and `flow_actions` order exactly as supplied.

#### Deterministic Sort Keys for Artifacts

| Artifact | Sort Key | Order |
|---|---|---|
| `file_inventory.json` | `path` field | Lexicographic, POSIX case-sensitive |
| `proc_inventory.json` | `canonical_name` field | Lexicographic, POSIX case-sensitive |
| `dependency_graph.json` nodes | node identifier (canonical name or file path) | Lexicographic |
| `dependency_graph.json` edges | `(source, target)` tuple | Lexicographic by source, then target |
| `diagnostics.json` | `(severity, code, location)` tuple | Severity: ERROR > WARNING > INFO; then code; then location |
| `compiled_manifest.json` files | `path` field | Lexicographic |
| `compiled_manifest.json` procs | `canonical_name` field | Lexicographic |

- JSON artifacts are emitted as UTF-8 with a trailing newline, stable indentation, and deterministic key ordering.
- Live trim builds into a same-filesystem staging directory named `<domain_parent>/<domain_name>_staging/` and promotes only after validation passes.
- The staging directory naming convention mirrors the backup convention: `domain_backup/` for backup, `domain_staging/` for in-progress trim output.
- `_backup` is read-only input during trim and re-trim.
- Generated files and rewritten artifacts are written through temp files and promoted with same-filesystem atomic replace/rename behavior.

Failure recovery rules:
- On first-trim failure after rename to `_backup`, restore `_backup` back to the active domain path.
- On re-trim failure, preserve the last good active domain and discard failed staging output.
- A live run may end only in a fully promoted validated state or a restored pre-run state.

#### 7.3.1 Atomic File Update Contract

1. Create the temporary file in the same directory as the final target using `tempfile.NamedTemporaryFile(delete=False)` or `tempfile.mkstemp()`.
2. Write the full content, flush Python buffers, and call `os.fsync()` on the temporary file descriptor before promotion.
3. Promote only with `os.replace()`; never copy across filesystems during live trim.
4. After `os.replace()`, fsync the containing directory on POSIX for audit artifacts, generated files, and final promoted outputs when durability matters. If the filesystem does not support directory fsync, emit a debug log and continue.
5. Permission and existence handling follows EAFP: perform the open/replace/remove operation directly and handle `OSError`; do not preflight with `os.access()`.

#### 7.3.2 Concurrent Invocation Lock Contract

1. Mutating commands (`trim`, `cleanup`) acquire a sibling lock file at `<domain_parent>/<domain_name>.chopper.lock`.
2. On Linux/Unix, acquire an exclusive non-blocking advisory lock via `fcntl.flock(LOCK_EX | LOCK_NB)` on a file descriptor opened for writing.
3. After lock acquisition, truncate the file, write lock metadata JSON containing at least `run_id`, `pid`, `hostname`, `user`, `command`, `domain`, and `started_at`, and keep the descriptor open until command exit.

**Lock file metadata format:**

File path: `<domain_parent>/<domain_name>.chopper.lock`

Content: Single JSON object (compact, not pretty-printed during live use):

```json
{
  "run_id": "abc123-def456-...",
  "pid": 12345,
  "hostname": "build-host-01",
  "user": "domain_owner",
  "command": "chopper trim --base jsons/base.json",
  "domain": "fev_formality",
  "started_at": "2026-04-05T10:30:00Z"
}
```

Field types:
- `run_id`: string (UUID)
- `pid`: integer (process ID)
- `hostname`: string (`socket.gethostname()`)
- `user`: string (`getpass.getuser()`)
- `command`: string (full CLI invocation)
- `domain`: string (domain basename)
- `started_at`: string (ISO 8601 UTC with trailing `Z`)

4. If lock acquisition fails with `EACCES` or `EAGAIN`, treat the lock as active. Read holder metadata on a best-effort basis and fail fast with a user-facing diagnostic. `--force` never bypasses a currently held advisory `flock()`.
5. A pre-existing lock path that still allows successful `flock()` acquisition is not an active lock. It is treated as abandoned metadata or an orphaned lock file; Chopper rewrites it with fresh metadata before continuing.
6. The default stale threshold is `locking.stale_timeout_seconds` (7200). It applies only to recovered abandoned lock metadata: if the recovered file's recorded `started_at` or file mtime is older than the threshold, classify it as stale, emit a warning, and record an audit event before replacing it.
7. If recovered abandoned lock metadata is missing or malformed, handle malformed JSON gracefully — log a warning and proceed with lock acquisition. `--force` may suppress that warning and allow cleanup of the abandoned file, but only after the current process has already acquired the advisory lock itself.
8. In a `finally` block, release the advisory lock, close the descriptor, and remove the lock file.

### 7.4 F2 Proc Deletion Algorithm

When a file is treated as `PROC_TRIM`, Chopper removes unwanted proc definitions while preserving all other content.

#### Deletion Contract

1. Read file as text, split into lines.
2. For each proc span to remove (identified by `[start_line, end_line]` inclusive):
   a. Scan backwards from `start_line - 1` looking for contiguous comment lines (lines starting with optional whitespace then `#`).
   b. If comment lines are found immediately before the proc with no blank line separating them from the proc, include those comment lines as part of the proc's removal span — they are the proc's documentation header.
   c. Remove lines `[adjusted_start_line, end_line]` inclusive.
3. After all removals, collapse excessive blank lines: for every run of 4 or more consecutive blank lines, reduce to 2 blank lines.
4. Preserve top-of-file content (shebang, copyright headers, package require statements, variable assignments) byte-for-byte — these are above the first proc and are never touched.
5. Output file ends with exactly one newline character (`\n`).
6. If the file becomes empty after removal (no non-whitespace non-comment content remains and no surviving proc definitions), keep the remaining blank/comment-only file content, write exactly one trailing newline, and flag as V-24.

#### Comment Association Rule

Comments immediately preceding a proc (with no blank line between the comment block and the `proc` keyword) are considered part of the proc and are removed with it. Comments separated from a proc by one or more blank lines are independent and are preserved.

```
# This comment is independent (blank line follows)

# This comment belongs to foo (no blank line before proc)
# It documents what foo does
proc foo {args} {
    ...
}
```

If `foo` is removed, both `# This comment belongs to foo` lines are also removed, but `# This comment is independent` is preserved.

#### Determinism

The deletion algorithm produces deterministic, reviewable diffs. The same input file with the same procs removed always produces the same output.

---

## 8. Validation, Diagnostics, and Exit Behavior

### 8.1 Diagnostic Record Contract

Diagnostics are stable machine-readable records with the following minimum fields:

| Field | Meaning |
|---|---|
| `severity` | `info`, `warning`, or `error` |
| `code` | Stable identifier such as `V-09` or `TRACE-AMBIG-01` |
| `message` | Human-readable summary |
| `location` | File, line, proc, stage, or JSON path when available |
| `hint` | Suggested user action |
| `source` | `schema`, `compiler`, `parser`, `trimmer`, `validator`, or `audit` |

### 8.2 Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success; warnings may still be present |
| `1` | User-visible validation or trim failure |
| `2` | CLI usage error or invalid invocation |
| `3` | Live write failed but state was restored successfully |
| `4` | Internal error or unhandled exception |

### 8.3 Validation Phases

#### Phase 1: Pre-Trim Validation

Runs before any files are touched.

| ID | Check | Severity | Description |
|---|---|---|---|
| V-01 | Schema compliance | **Error** | Every JSON must carry a valid `$schema` field matching a known Chopper schema version. |
| V-02 | Required fields present | **Error** | Base JSON must have `domain`. Feature JSON must have `name`. Project JSON must have `project`, `domain`, `base`. |
| V-03 | Empty procs array | **Error** | `procedures.include` entry with `"procs": []` is a hard error. Suggest moving the file to `files.include`. |
| V-04 | Duplicate file entries | **Warning** | Same file listed in both `files.include` and `procedures.include`. When `--strict` mode is enabled (via CLI flag or `validation.strict = true` in `.chopper.config`), this is escalated to **Error**. |
| V-05 | Duplicate proc entries | **Warning** | Same proc listed in both include and exclude across selected inputs. |
| V-06 | Unknown action keyword | **Error** | `flow_actions` entry with an unsupported `action` value. |
| V-07 | Missing reference target | **Error** | `add_*`, `replace_*`, or `remove_*` actions reference a missing target. |

V-07 applies to ALL flow action types:

| Action | `reference` Must Exist | Additional Conditions |
|---|---|---|
| `add_step_before` | Stage must exist, reference step must exist in that stage | — |
| `add_step_after` | Stage must exist, reference step must exist in that stage | — |
| `remove_step` | Stage must exist, reference step must exist (with `@n` if specified) | — |
| `replace_step` | Stage must exist, reference step must exist (with `@n` if specified) | — |
| `add_stage_before` | Reference stage must exist | New stage `name` must NOT already exist |
| `add_stage_after` | Reference stage must exist | New stage `name` must NOT already exist |
| `remove_stage` | Reference stage must exist | — |
| `replace_stage` | Reference stage must exist | — |
| `load_from` | Stage must exist, reference (the new `load_from` target) must be a known stage name | — |

If a stage exists but has an empty `steps` array, any step-targeting action (`add_step_before`, `add_step_after`, `remove_step`, `replace_step`) that references a step string in that stage emits V-07 because the reference cannot be found.

| V-08 | File existence check | **Error** | Files listed in include rules do not exist in the domain or `_backup`. |
| V-09 | Proc existence check | **Error** | Procs listed in `procedures.include` cannot be found in the referenced file. |
| V-10 | Stage name uniqueness | **Error** | Duplicate stage names after applying all stage actions. |
| V-11 | Glob pattern validity | **Error** | Malformed glob patterns in file rules. |
| V-12 | `@n` instance out of range | **Error** | `@n` on `replace_step` / `remove_step` / `add_step_before` / `add_step_after` where `n` exceeds actual occurrence count. |
| V-13 | Project JSON mutual exclusivity | **Error** (exit 2) | `--project` provided alongside `--base` or `--features`. |
| V-14 | Project JSON schema compliance | **Error** | Project JSON must carry `$schema: chopper/project/v1` and required fields `project`, `domain`, `base`. |
| V-15 | Project JSON path resolution | **Error** | `base` or `features` paths in project JSON cannot be resolved relative to the current working directory, which is the domain root in normal v1 operation. Each path must resolve to an existing readable file. Each `features[]` entry must pass `feature-v1.schema` validation once loaded. |
| V-16 | Empty glob result | **Warning** | A glob pattern in `files.include` resolved to zero files. Escalated to **Error** in `--strict` mode. Suggests the pattern may have no effect. |
| V-17 | Empty base JSON | **Info** | Base JSON has no `files`, `procedures`, or `stages` blocks. May indicate an incomplete draft or an intentional feature-driven flow. Escalated to **Warning** in `--strict` mode. |
| V-18 | Feature name uniqueness | **Error** | Two or more selected feature JSONs have the same `name` field. Feature names must be unique within a project to ensure unambiguous audit trails and diagnostics. |

#### Phase 2: Post-Trim Validation

Runs after the trim pipeline completes.

| ID | Check | Severity | Description |
|---|---|---|---|
| V-20 | Tcl syntax check | **Error** | Every surviving `.tcl` file must parse without brace-matching errors. |
| V-21 | Dangling proc references | **Warning** | Surviving procs call other procs not present in trimmed output or `common/`. |
| V-22 | Dangling file references | **Warning** | `iproc_source` / `source` calls point to files that were removed. |
| V-23 | F3 step file existence | **Warning** | F3-generated run files reference step files that were trimmed away. |
| V-24 | Empty proc-trimmed file | **Warning** | A file went through F2, lost all proc definitions, and survives only as blank/comment-only content. |
| V-25 | Preamble-only file | **Info** | A file survives F2 with only top-level Tcl and no proc definitions. |
| V-26 | Template script boundary check | **Error** | `options.template_script` path, after resolving symlinks via `Path.resolve()`, points outside the domain root boundary. This prevents symlink-based domain escape. Also emitted as **Error** if the resolved script does not exist in the trimmed domain at execution time. In dry-run mode, V-26 is skipped entirely (template_script is not checked for existence or executed). |

#### Phase 3: Dry-Run Simulation

`chopper trim --dry-run` executes the full pipeline without writing files.

It runs:
1. all Phase 1 checks
2. full compilation
3. full trace expansion
4. simulated output planning
5. Phase 2 checks against the simulated output
6. summary reporting

`chopper validate` runs Phase 1 only.

---

## 9. CLI Usability and Presentation Requirements

### 9.1 CLI Parser and Command Model

- Use `argparse` subcommands for `scan`, `validate`, `trim`, and `cleanup`.
- Keep parser construction separate from command execution.
- Keep command handlers thin; real behavior belongs in services.

#### 9.1.1 Argparse Implementation Contract

- Use one shared parent parser for global options such as `-v`, `--debug`, `--plain`, `--no-color`, `--json`, `--strict`, and common path selectors.
- Use `add_subparsers(dest="command", required=True)`.
- Each subparser binds its command function via `set_defaults(handler=...)`; the top-level CLI then calls exactly one handler after parsing.
- Set `allow_abbrev=False` to avoid ambiguous long-option prefixes.
- Use `exit_on_error=False` and convert parser failures into stable exit code 2 diagnostics.
- Do not use `argparse.FileType`; parse filenames as `Path` objects or strings and open them later with explicit error handling.
- Use `action="count"` for `-v`; `--debug` overrides any verbosity count.
- Do not depend on Python 3.14-only argparse features such as `color=` or `suggest_on_error`; enable them only conditionally when available at runtime.

### 9.1.2 Input Modes

Chopper accepts input in three distinct modes. Exactly one mode must be used per invocation.

| Mode | CLI Form | Description |
|---|---|---|
| **Base-only** | `--base jsons/base.json` | Minimal: trim using only the base JSON with no features |
| **Base + Features** | `--base jsons/base.json --features jsons/features/f1.json,jsons/features/f2.json` | Standard: trim using a base JSON with one or more feature overlays |
| **Project** | `--project <path-to-project.json>` | Single-file packaging: a project JSON that bundles the same base path, ordered feature paths, project metadata, and selection rationale |

Default expected curated JSON locations under the current working directory, which is the domain root in normal v1 operation, are `jsons/base.json` for the base JSON and `jsons/features/*.json` for feature JSONs. Project JSON has no fixed default location; the user passes its path explicitly to `--project`.

**Mutual exclusivity:** `--project` is mutually exclusive with `--base` and `--features`. If `--project` is provided alongside `--base` or `--features`, Chopper rejects the invocation with exit code 2 and an actionable error message.

**Project JSON resolution:** When `--project` is provided, Chopper assumes it is being run from the domain root. The current working directory is therefore the root for resolving `base` and `features`, not the project JSON file location. The resolved base and features then enter the same compilation pipeline as if they had been passed via `--base` and `--features`.

**Domain consistency from project JSON:** When `--project` is used, the project JSON `domain` field is a required identifier for audit and consistency. It must match the basename of the current working directory. If `--domain` is also provided on the CLI, it must resolve to that same current working directory. A mismatch is a CLI usage error (exit code 2).

**Mode equivalence:** Given the same current working directory, base JSON, and ordered feature list, `--project` mode and `--base`/`--features` mode must produce identical compilation and trim results.

### 9.1.3 Complete CLI Reference

#### Top-Level Usage

```text
chopper [-h] [-v] [--debug] [--plain] [--no-color] [--json] [--strict]
        {scan,validate,trim,cleanup} ...
```

#### Global Options (Shared Across All Subcommands)

| Flag | Type | Default | Description |
|---|---|---|---|
| `-v` | count | 0 | Increase verbosity. `-v` = INFO, `-vv` = DEBUG. Overridden by `--debug`. |
| `--debug` | flag | off | Maximum verbosity (DEBUG level), full stack traces on errors. |
| `--plain` | flag | off | Disable Rich rendering; use plain text for all output. |
| `--no-color` | flag | off | Disable ANSI color codes in console output. |
| `--json` | flag | off | Emit machine-readable JSON to stdout (logs and progress go to stderr). |
| `--strict` | flag | off | Treat warnings as errors (escalates severity of non-fatal diagnostics). |

#### `chopper scan`

Scan a domain to generate draft JSONs, inventories, and dependency reports for owner curation.

```text
chopper scan [--domain <path>] [--output <dir>] [global options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--domain` | no | `.` | Optional explicit domain root path. Defaults to the current working directory. If provided, it must resolve to the same directory. |
| `--output` | no | `scan_output/` | Output directory for scan artifacts. Created if it does not exist. |

**Behavior:**
- Read-only operation; never modifies domain files.
- Does not require or use `--base`, `--features`, or `--project`.
- If `--output` directory already exists, overwrites previous scan output (scan is idempotent).
- Produces: `draft_base.json`, `file_inventory.json`, `proc_inventory.json`, `dependency_graph.json`, `scan_report.json`, `scan_report.txt`, `diagnostics.json`.
- If an existing `jsons/base.json` is found in the domain, also produces `diff_report.json` (A-02).
- Does not acquire the advisory lock (read-only).

**Example:**
```bash
chopper scan --output scan_output/
chopper scan --output sta_scan/ -v
```

#### `chopper validate`

Run Phase 1 structural validation against JSON inputs without touching domain source files.

```text
chopper validate [--domain <path>] (--base <path> [--features <paths>] | --project <path>)
                 [global options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--domain` | no | `.` | Optional explicit domain root path. Defaults to the current working directory. If provided, it must resolve to the same directory. |
| `--base` | conditional | — | Path to the base JSON. Required unless `--project` is used. Default expected location: `jsons/base.json` under the selected domain. |
| `--features` | no | — | Comma-separated ordered list of feature JSON paths. Default expected location pattern: `jsons/features/*.json`. |
| `--project` | conditional | — | Path to a project JSON supplied by the user. Mutually exclusive with `--base`/`--features`. |

**Behavior:**
- Read-only operation; never modifies domain files.
- Runs Phase 1 validation checks (V-01 through V-12) only.
- Does not build a proc index, run tracing, or simulate output.
- Validates schema compliance, required fields, file/proc existence against the domain, action targets, and glob patterns.
- When `--project` is used, Chopper loads the project JSON, verifies domain consistency, resolves the `base` and `features` paths from it, and validates all referenced JSONs.
- Does not acquire the advisory lock (read-only).
- Exits 0 if all checks pass, 1 if any error-severity diagnostic is emitted.

**Example:**
```bash
# Validate with base only
chopper validate --base jsons/base.json

# Validate with base + features
chopper validate --base jsons/base.json \
    --features jsons/features/feature_dft.json,jsons/features/feature_power.json

# Validate using a project JSON
chopper validate --project configs/project_abc.json
```

#### `chopper trim`

Execute the full trim pipeline: compile, trace, build output, validate, and emit audit trail.

```text
chopper trim [--domain <path>] (--base <path> [--features <paths>] | --project <path>)
             [--dry-run] [--force] [global options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--domain` | no | `.` | Optional explicit domain root path. Defaults to the current working directory. If provided, it must resolve to the same directory. |
| `--base` | conditional | — | Path to the base JSON. Required unless `--project` is used. Default expected location: `jsons/base.json` under the selected domain. |
| `--features` | no | — | Comma-separated ordered list of feature JSON paths. Default expected location pattern: `jsons/features/*.json`. Order is authoritative. |
| `--project` | conditional | — | Path to a project JSON supplied by the user. Mutually exclusive with `--base`/`--features`. |
| `--dry-run` | no | off | Run the full pipeline without writing files. Simulates the trim and reports what would happen. |
| `--force` | no | off | Clean up abandoned lock metadata (never breaks an active lock). |

**Behavior:**
- Detects domain lifecycle state (first trim vs re-trim).
- Acquires per-domain advisory lock for live runs (not for `--dry-run`).
- Full pipeline: read inputs → Phase 1 validate → compile → trace → build output → Phase 2 validate → emit audit trail.
- When `--project` is used, Chopper loads the project JSON, verifies domain consistency, resolves base and feature paths from it, and proceeds identically to `--base`/`--features` mode. The `project`, `owner`, `release_branch`, and `notes` metadata from the project JSON are recorded in `chopper_run.json` and `compiled_manifest.json` for audit traceability.
- `--dry-run` runs the full pipeline simulation (Phase 1 + compile + trace + simulated output + Phase 2) without writing files. Mandatory for domain owners to validate JSON files before live trim.
- First trim: renames `domain/` to `domain_backup/`, builds trimmed `domain/` from backup.
- Re-trim: rebuilds `domain/` from existing `domain_backup/`.
- On failure: restores pre-run state (see §7.3).

**Example:**
```bash
# Trim with base only (no features)
chopper trim --base jsons/base.json

# Trim with base + features
chopper trim --base jsons/base.json \
    --features jsons/features/feature_dft.json,jsons/features/feature_power.json

# Trim using a project JSON at a user-supplied path (same result as equivalent resolved --base/--features)
chopper trim --project configs/project_abc.json

# Dry-run first (always recommended before live trim)
chopper trim --dry-run --project configs/project_abc.json

# Verbose dry-run with JSON output for CI
chopper trim --dry-run --project configs/project_abc.json \
    --json -v
```

#### `chopper cleanup`

Remove `domain_backup/` after the trim window is complete. This is irreversible.

```text
chopper cleanup [--domain <path>] --confirm [--force] [global options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--domain` | no | `.` | Optional explicit domain root path. Defaults to the current working directory. If provided, it must resolve to the same directory. |
| `--confirm` | **yes** | — | Explicit confirmation flag. Chopper refuses to run cleanup without it. |
| `--force` | no | off | Clean up abandoned lock metadata (never breaks an active lock). |

**Behavior:**
- Removes `domain_backup/` permanently.
- Acquires per-domain advisory lock.
- Requires `--confirm` to prevent accidental deletion.
- Succeeds when domain is in the TRIMMED state.
- If the domain is already in the CLEANED state, emits an informational diagnostic and exits 0 without filesystem changes.
- Fails for VIRGIN, BACKUP_CREATED, or STAGING lifecycle states.
- Does not use or require `--base`, `--features`, or `--project`.
- Records cleanup event in `.chopper/chopper_run.json`.

**Example:**
```bash
chopper cleanup --confirm
```

### 9.1.4 Project JSON Workflow

Project JSON mode is the single-file packaging form of the same resolved selection used by direct `--base`/`--features` mode. It bundles all selection decisions into one auditable file without changing trim semantics.

#### When to Use Project JSON

| Scenario | Typical Packaging |
|---|---|
| Initial exploration / scan-to-trim authoring | `--base` (± `--features`) |
| One-off quick trim with known inputs | `--base` (± `--features`) |
| Reproducible trim for a project branch | `--project` |
| CI/CD automated trim pipeline | `--project` |
| Shared trim recipe across team members | `--project` |
| Audit trail showing exactly what was selected and why | `--project` |

#### Project JSON Lifecycle

```
1. chopper scan --output scan_output/
     → Owner reviews scan artifacts and curates `jsons/base.json` + feature JSONs under `jsons/features/`

2. Owner creates project JSON bundling the selection:
   {
     "$schema": "chopper/project/v1",
     "project": "PROJECT_ABC",
     "domain": "fev_formality",
     "owner": "domain_owner",
     "release_branch": "project_abc_rtm",
         "base": "jsons/base.json",
     "features": [
             "jsons/features/feature_dft.json",
             "jsons/features/feature_power.json"
     ],
     "notes": [
       "DFT ordered before power — DFT inserts steps into setup content"
     ]
   }

3. chopper validate --project configs/project_abc.json
   → Phase 1 structural validation

4. chopper trim --dry-run --project configs/project_abc.json
   → Full pipeline simulation without file writes

5. chopper trim --project configs/project_abc.json
   → Live trim

6. chopper cleanup --confirm
   → Last-day backup removal
```

#### Project JSON Path Resolution Rules

- Chopper assumes it is invoked from the domain root. `base` and `features` paths inside the project JSON are therefore resolved relative to the current working directory, not the project JSON file.
- This means a project JSON can live anywhere (e.g., `configs/`, `projects/`, or even outside the repo) and still correctly reference the domain's base and feature JSONs under the default `jsons/` layout.
- The default expected curated JSON layout under a domain is `jsons/base.json` and `jsons/features/*.json`.
- The project JSON `domain` field must match the basename of the current working directory. If `--domain` is also supplied, it must resolve to that same directory or the invocation fails with exit code 2.
- If a path cannot be resolved to an existing file under the current working directory (or `_backup` during re-trim), Phase 1 validation (V-15) catches it.

#### Audit Traceability for Project JSON Runs

When `--project` is used, the following additional fields are recorded in audit artifacts:

| Artifact | Additional Fields |
|---|---|
| `chopper_run.json` | `project_json_path`, `project_name`, `project_owner`, `release_branch` |
| `compiled_manifest.json` | `project_json_path`, `project_name`, `project_notes` |

This ensures that the audit trail captures not just what base and features were used, but the project-level context and rationale for the selection.

### 9.2 Operator Experience Requirements

The CLI must be production-usable, not merely script-callable.

Requirements:
- structured logging, not ad hoc print debugging
- graceful user-facing errors instead of raw stack traces
- progress indicators for long-running operations
- color and emphasis where useful
- automatic terminal width handling
- glyph support with safe fallback when the terminal cannot render fancy characters
- predictable quiet, verbose, debug, and machine-readable modes

Recommended presentation dependency:
- isolate terminal rendering behind a renderer adapter so a library such as `rich` can be used for tables, progress bars, width handling, and styled output without coupling the core engine to it

### 9.3 TTY and CI Behavior

- Progress bars and spinners appear only on interactive terminals.
- CI and redirected output default to plain, non-animated output.
- Provide `--no-color` and `--plain` flags.
- Provide a machine-readable output mode for automation.

### 9.4 Feature List and Inventory Views

Technical requirement:
- the CLI must be able to render discovered features, files, and diagnostics as tables or lists
- the underlying service must return data structures usable by a future GUI feature list view
- sorting, filtering, and grouping belong in the renderer or query layer, not in parser logic

### 9.5 Version Awareness and Update Guidance

Users benefit from version awareness, but enterprise tools must not silently modify themselves.

Requirement:
- support update awareness or version checking through a controlled mechanism
- do not require forced self-update behavior in offline or restricted environments
- make any version check disableable and environment-aware

Recommended behavior:
- notify about newer versions
- leave installation/update actions to the operator or deployment tooling

---

## 10. Testing and Quality Gates

### 10.1 Layered Test Strategy

| Layer | Focus | Minimum expectation |
|---|---|---|
| Unit tests | Compiler rules, action ordering, path normalization, diagnostic formatting | Fast deterministic coverage in CI |
| Parser fixture tests | Proc boundary detection, namespace handling, `source` / `iproc_source` extraction | Real Tcl fixture coverage for common and adversarial cases |
| Golden trim tests | End-to-end trimmed outputs and audit artifacts | Byte-stable fixture comparisons |
| Property-based tests | Span deletion safety, deterministic ordering, idempotent compilation, unresolved-reference handling | Hypothesis-style generated inputs for invariants |
| Integration tests | `scan`, `validate`, dry-run, and live trim flows over curated mini-domains | Command-level coverage with expected exit codes |
| Real-domain proving tests | Smoke validation on selected representative domains | Run outside the small-fixture CI set as a release gate |

#### 10.1.1 Test Fixture Specification

Minimum fixture set:

```
tests/fixtures/
├── mini_domain/                    # Minimal valid domain
│   ├── jsons/
│   │   ├── base.json
│   │   └── features/
│   │       └── feature_a.json
│   ├── main_flow.tcl              # 3 procs, 2 used by base
│   ├── helper_procs.tcl           # 2 procs, 1 calls the other
│   ├── utils.pl                   # Non-Tcl file (file-level only)
│   └── vars.tcl                   # Always-keep file
│
├── namespace_domain/              # Namespace stress tests
│   ├── nested_ns.tcl              # namespace eval a { namespace eval b { proc foo }}
│   └── ...
│
├── tracing_domain/                # Transitive trace scenarios
│   ├── chain.tcl                  # A→B→C→D call chain
│   ├── diamond.tcl                # A→B, A→C, B→D, C→D
│   ├── dynamic.tcl                # $cmd dispatch (should warn)
│   └── ...
│
├── hook_domain/                   # iproc_source -use_hooks
│   ├── main.tcl                   # iproc_source -file setup.tcl -use_hooks
│   ├── setup.tcl
│   ├── pre_setup.tcl
│   └── post_setup.tcl
│
├── edge_cases/                    # Parser adversarial inputs
│   ├── brace_in_string.tcl        # proc body contains "{" in string literal
│   ├── backslash_continuation.tcl # proc definition split across lines
│   ├── empty_file.tcl             # 0 procs, only comments
│   ├── duplicate_proc.tcl         # Same proc name defined twice
│   └── encoding_latin1.tcl        # Non-UTF8 content
│
├── f3_only_domain/                # F3-only capability (no trimming)
│   ├── jsons/
│   │   ├── base.json                  # stages only, no files.include/procedures.include
│   │   └── features/
│   │       └── feature_extra_stage.json  # Adds a stage via flow_actions
│   ├── run_setup.tcl              # Existing run file (not trimmed)
│   └── vars.tcl                   # Domain config file
│
├── project_domain/                # Project JSON input mode
│   ├── jsons/
│   │   ├── base.json                  # Standard base JSON
│   │   └── features/
│   │       ├── feature_a.json
│   │       └── feature_b.json
│   ├── configs/
│   │   └── project.json               # User-supplied project JSON referencing domain jsons/base + jsons/features/*
│   ├── main_procs.tcl             # Tcl file with procs
│   └── vars.tcl                   # Domain config file
│
└── golden/                        # Expected outputs
    ├── mini_domain_trim/          # Expected trim output
    │   ├── compiled_manifest.json
    │   └── ...
    └── ...
```

Golden output management:
1. First run generates golden outputs with `--update-golden` flag.
2. Subsequent runs compare byte-for-byte.
3. Any golden change requires explicit `--update-golden` and code review.

#### 10.1.2 Property-Based Test Invariants

Concrete Hypothesis-testable invariants:

| ID | Invariant | Description |
|---|---|---|
| PB-01 | Proc deletion preserves non-proc content | For any file F and any subset S of its procs, deleting S produces output where all non-proc lines from F appear (order preserved), no proc from S appears, and all procs NOT in S appear |
| PB-02 | Compilation is idempotent | `compile(base, features)` == `compile(base, features)` — running twice with same inputs produces identical CompiledManifest |
| PB-03 | Explicit include wins | For any proc P explicitly listed in PI and also listed in PE, P MUST appear in the compiled output |
| PB-04 | Feature ordering matters only for flow_actions | FI and PI are order-independent (union semantics); flow_actions are order-dependent |
| PB-05 | Trace expansion is monotonic | If PI ⊆ PI’, then trace(PI) ⊆ trace(PI’) — adding more seed procs never removes previously traced procs |
| PB-06 | Deterministic output | For any inputs I, `trim(I)` at time T1 == `trim(I)` at time T2 (file ordering, proc ordering, manifest key ordering all stable) |

#### 10.1.3 Integration Test Scenarios

Minimum integration test matrix:

| Scenario | Command | Expected Exit | Key Assertion |
|---|---|---|---|
| Valid trim | `chopper trim --base jsons/base.json` | 0 | trimmed domain exists, backup exists |
| Dry-run | `chopper trim --dry-run --base jsons/base.json` | 0 | no files modified |
| Schema error | `chopper validate --base jsons/bad_schema.json` | 1 | diagnostic V-01 emitted |
| Empty procs | `chopper validate --base jsons/empty_procs.json` | 1 | diagnostic V-03 emitted |
| Re-trim | `chopper trim` (with existing backup) | 0 | backup unchanged, domain rebuilt |
| Cleanup | `chopper cleanup --confirm` | 0 | backup removed |
| Missing file | `chopper trim --base jsons/refs_missing.json` | 1 | diagnostic V-08 emitted |
| Interrupt recovery | Kill during staging | varies | domain_backup intact, no half-state |
| `@n` targeting | `replace_step` with `step.tcl@2` | 0 | only second occurrence replaced |
| `@n` out of range | `replace_step` with `step.tcl@5` (only 2 exist) | 1 | diagnostic V-12 emitted |
| Project JSON trim | `chopper trim --project configs/project.json` | 0 | same result as equivalent --base/--features invocation |
| Project JSON validate | `chopper validate --project configs/project.json` | 0 | Phase 1 checks pass for all referenced JSONs |
| Project + base conflict | `chopper trim --project configs/p.json --base jsons/base.json` | 2 | CLI usage error: mutually exclusive |
| Project JSON dry-run | `chopper trim --dry-run --project configs/project.json` | 0 | no files modified, audit metadata includes project fields |
| Project JSON bad path | `chopper trim --project configs/missing_base.json` | 1 | diagnostic V-15: base path in project JSON does not exist |

### 10.2 Minimum Release Gate

1. Phase 1 validation tests pass against valid and invalid schema fixtures.
2. Parser and tracer fixture tests cover namespaces, bracketed calls, unresolved dynamic calls, and `iproc_source` flag combinations.
3. Dry-run and live trim produce equivalent manifests for the same inputs.
4. Re-running trim from `_backup` produces byte-identical output.
5. Failure-injection tests prove staging cleanup and restore behavior.

### 10.3 Additional Quality Gates

- Ruff must pass.
- Mypy must pass.
- Pytest must pass for unit and integration suites.
- Dependency review and vulnerability scanning must pass before release.
- Golden output changes must be reviewed as intentional artifact changes, not incidental drift.

#### 10.3.1 CI Commands

A `Makefile` at the repo root provides standard commands:

```bash
make check          # Pre-commit gate: lint + type-check + unit tests (fast)
make ci             # Full CI gate: lint + type-check + all tests
make lint           # ruff check
make format-check   # ruff format --check
make type-check     # mypy
make test-unit      # pytest tests/unit/
make test-integration  # pytest tests/integration/
make test-golden    # pytest tests/golden/
make test-property  # pytest tests/property/
make test           # all test suites
```

---

## 11. Additional Recommended Technical Requirements

Beyond the initial Python and CLI list, these should also be treated as technical requirements.

### 11.1 Compatibility Matrix

| Dimension | Requirement |
|---|---|
| Python runtime | Minimum supported Python is 3.9. Implementation code must not require features newer than 3.9 unless guarded behind compatibility checks. |
| CI interpreters | CI must run at least on Python 3.9 and one current approved interpreter from the deployment environment. |
| Operating system | Linux is the primary supported execution environment. Live `trim` and `cleanup` are release-gated on Linux only. |
| Filesystem behavior | Mutating commands assume source, staging, and destination live on the same mounted filesystem and that `os.replace()`/rename semantics are available there. |
| Terminal modes | Interactive TTY, non-interactive CI, and redirected stdout/stderr are all first-class supported modes. |

### 11.2 Interrupt and Signal Handling

- Install `SIGINT` and `SIGTERM` handlers only in the main thread.
- Signal handlers must not take locks, emit logs, mutate the filesystem, or raise business exceptions. They set a cancellation flag or wakeup mechanism only.
- Core services check cancellation between major phases and inside long file-processing loops.
- If cancellation occurs before any live mutation, exit with code 1 and emit a cancellation diagnostic.
- If cancellation occurs after `_backup` creation or during staging, run normal restore logic and exit with code 3.
- Catch `KeyboardInterrupt` at the CLI boundary only as a fallback; core logic must not rely on it as the primary graceful-shutdown mechanism.
- Interrupted runs must still produce enough diagnostics and audit context to explain what happened.

### 11.3 Machine-Readable Output Modes

- `--json` writes exactly one JSON document to stdout and nothing else.
- Logs, progress, warnings, and human-readable status go to stderr.
- The CLI JSON envelope is stable within schema version `chopper/cli-result/v1`:

```json
{
    "$schema": "chopper/cli-result/v1",
    "command": "trim",
    "run_id": "abc123",
    "exit_code": 0,
    "diagnostics": [],
    "result": {}
}
```

- On usage or early initialization failures, `result` may be `null`, but the envelope shape remains the same.
- Within `chopper/cli-result/v1`, new fields may be added but existing fields are not renamed or removed.

### 11.4 Dependency Policy

- Runtime dependencies must be reviewed for security, maintenance health, and license compatibility.
- Optional UX dependencies should remain isolated from the core engine.

### 11.5 Documentation and Examples

- Keep architecture, technical requirements, JSON schema examples, and CLI examples in sync.
- Maintain at least one small end-to-end sample domain fixture as technical documentation.

### 11.6 Evolution and Deprecation Policy

- Breaking changes to JSON inputs, audit artifacts, or CLI JSON output require a new schema version or a major release boundary.
- Additive fields may be introduced within a schema version only if older consumers can safely ignore them.
- Deprecated CLI flags and JSON fields must emit clear warnings for at least one release before removal.
- Migration notes must be recorded in the docs revision history and schema changelog.

---

## 12. Open Technical Decisions

| ID | Decision | Why it matters | Resolution |
|---|---|---|---|
| TD-01 | Authoritative line-length policy: 79 vs current Ruff 120 | Prevents permanent style drift between docs and tooling | **Closed Rev 2.** Keep Ruff 120 per `pyproject.toml`; aligns with team convention. |
| TD-02 | CLI renderer dependency choice (`rich` vs plain stdlib rendering) | Affects progress bars, color, tables, glyphs, and terminal width handling | **Closed Rev 2.** `rich` added as optional dependency (`pip install chopper[rich]`). Plain stdlib fallback is default; renderer adapter (§5.6) swaps at runtime. |
| TD-03 | User/global CLI config file format | Needed for default overrides without hardcoded paths | **Closed Rev 2.** `.chopper.config` TOML file in working directory (§6.1). All keys optional with sane defaults. |
| TD-04 | Version-check policy for restricted enterprise environments | Determines whether update awareness is online, offline, opt-in, or disabled by default | **Closed Rev 2.** Disabled by default. Air-gapped Intel environments have no outbound PyPI access; version checking is out-of-scope for v1. |

---

## 13. Revision History

| Date | Change |
|---|---|
| 2026-04-05 | **Rev 1:** created dedicated technical requirements baseline; moved implementation-level contracts, CLI/runtime requirements, diagnostics, Python guidance, and testing strategy out of `docs/ARCHITECTURE.md`. |
| 2026-04-05 | **Rev 2:** Closed GAPs 01-05, 07-28 from architecture review. Added: error hierarchy (§3.4.1), structured logging with `structlog` (§3.5), public API surface (§4.1), GUI data contract & wire protocol (§5.2), service layer (§5.3), progress events (§5.4), extension points (§5.5), renderer adapter (§5.6), `.chopper.config` resolution (§6.1), glob pattern syntax (§6.4.1), compilation algorithm (§7.1.1), concrete data models (§7.1.2), manifest versioning (§7.2), proc deletion algorithm (§7.4), test fixtures (§10.1.1), property-based invariants (§10.1.2), integration scenarios (§10.1.3), CI commands (§10.3.1). Removed all `replace_proc` references. Closed TD-01 through TD-04. Updated `pyproject.toml` dependencies. |
| 2026-04-05 | **Rev 3:** Added library logging rules (`NullHandler`, warning capture, UTC timestamps), explicit extension registration via `importlib.metadata`, configuration merge/validation rules, atomic temp-file durability requirements, per-domain advisory lock contract, concrete argparse implementation rules, a compatibility matrix, explicit signal-handling/cancellation behavior, a stable CLI JSON envelope, and schema/CLI deprecation policy. |
| 2026-04-05 | **Rev 4:** Corrected `options.template_script` semantics: it is a domain-relative post-trim script path, not a plugin identifier. Defined its resolution, execution timing, working directory, failure behavior, and the fact that Python entry-point discovery applies only to validators and output formatters. |
| 2026-04-05 | **Rev 5:** Froze minimum field contracts for `scan` artifacts (`draft_base.json`, inventories, dependency graph, scan reports) and tightened the advisory lock contract so stale/orphaned cleanup applies only after Chopper has proven no active `flock()` is held. |
| 2026-04-05 | **Rev 6:** Added comprehensive CLI reference (§9.1.2 Input Modes, §9.1.3 Complete CLI Reference, §9.1.4 Project JSON Workflow) covering all subcommands, arguments, flags, and per-mode examples. Added project JSON input mode support throughout: updated service layer contract (§5.3 `TrimRequest` with project fields), `RunSelection` and `CompiledManifest` data models (§7.1.2), compilation algorithm note (§7.1.1), `chopper_run.json` artifact fields (§7.2), Phase 1 validation checks V-13/V-14/V-15, integration test scenarios for project-mode, and test fixture `project_domain/`. Updated hook semantics to remove `HOOK_AUTO` keep reason. |
| 2026-04-05 | **Rev 7:** Made `files`, `procedures`, and F3 blocks optional where appropriate, treating omitted capability blocks as empty. Removed formal schema IDs from runtime and scan operational artifacts while keeping field-level contracts and `chopper_version`. Clarified that project JSON mode is single-file packaging of the same resolved selection as direct CLI mode, enforced effective-domain consistency between `--project` and `--domain`, preserved authored order for ordered collections, restored saved input copies to the audit contract, and made cleanup idempotent for already-cleaned domains. |
| 2026-04-05 | **Rev 8:** Standardized the default owner-curated JSON layout under each domain to `jsons/base.json` and `jsons/features/*.json`. Updated CLI mode examples, argument descriptions, project JSON workflow examples, fixture trees, scan diff expectations, and integration test scenarios. Clarified that project JSON remains a user-supplied path passed explicitly with `--project`. |
| 2026-04-05 | **Rev 9:** Aligned v1 operator guidance around running Chopper from the domain root and using the current working directory for project JSON path resolution. Updated the compiler contract so excludes prune only wildcard-expanded file candidates and trace-derived proc candidates while explicit includes remain authoritative. Changed empty F2 output to survive as blank/comment-only content with V-24, broadened V-12 to all `@n` step-targeting actions, and updated CLI examples and project workflow text to the domain-root invocation model. |
| 2026-04-05 | **Rev 10:** Integrated implementation clarifications for E-03, E-04, E-05, E-06, E-07 from the final production review inline into their respective sections. Scan diff_report production conditions and comparison semantics (§7.2.2.1), V-07 action coverage table with empty-stage handling (§8.3), inventory sort key table (§7.3), trace domain-boundary enforcement (§7.1.1), and lock file metadata format (§7.3.2). Resolved pre-coding review items B-07, B-10, H-10, H-11. Added scan diff report contract §7.2.2.1 with defined JSON schema for `diff_report.json` (B-10). Added V-16 (empty glob), V-17 (empty base JSON), V-18 (feature name uniqueness) to Phase 1 validation (H-11). Added V-26 (template_script symlink boundary check) to Phase 2 validation (H-10). Expanded V-15 to require path existence and feature schema validation. Added v1 no-checkpointing limitation note to §7.1.1 (B-07). |

