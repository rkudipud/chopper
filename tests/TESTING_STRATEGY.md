# Chopper — Testing Strategy

> **Scope:** §1–§3 apply from Stage 1 (Parser) onward; §4 applies from Stage 3 (Trimmer) onward.

Stage boundaries used throughout this document:

| Stage | Module(s) | Purpose |
|---|---|---|
| **Stage 0** | `core/` | Shared models, errors, diagnostics, protocols, serialization |
| **Stage 1** | `parser/` | Tcl tokenization, proc indexing |
| **Stage 2** | `config/`, `compiler/` | JSON schema loading, merge, BFS trace |
| **Stage 3** | `trimmer/`, `generators/`, `audit/` | Trim state machine, domain lifecycle, crash recovery, run-file generation |
| **Stage 4** | `validator/` | Pre- and post-trim validation, `--strict` escalation |
| **Stage 5** | `cli/` | Command-line interface, end-to-end integration wiring |

A scenario tagged with a stage must pass before that module is declared complete. Later stages may re-run earlier scenarios as regression gates.

---

## 1. Coverage Targets (by module / branch coverage)

| Module | Target | CI gate |
|---|---|---|
| `parser/` | ≥ 85% branch | ✅ enforced via `--cov-fail-under` |
| `compiler/` | ≥ 80% branch | ✅ |
| `trimmer/` | ≥ 80% branch | ✅ |
| `validator/` | ≥ 75% branch | ✅ |
| `core/` | ≥ 80% branch | ✅ |
| `config/` | ≥ 85% branch | ✅ |
| `ui/` | ≥ 70% line | ✅ |
| **Project-wide minimum** | **≥ 78% line** | ✅ `--cov-fail-under=78` |

Coverage is run with `--cov-branch` (configured in `pyproject.toml`).

---

## 2. Test Layers

### 2.1 Unit Tests (`tests/unit/`)

- Fast, isolated, no filesystem side effects beyond `tmp_path`.
- One test module per package module: `test_parser.py`, `test_compiler.py`, etc.
- Use `pytest-regressions` golden files for output contracts (see `tests/GOLDEN_FILE_GUIDE.md`).

### 2.2 Integration Tests (`tests/integration/`)

- Use the `ChopperSubprocess` harness (§4) and mini-domain fixtures (§3).
- Test full end-to-end pipelines: scan → validate → trim → cleanup.
- Named scenarios (see §5).

### 2.3 Property Tests (`tests/property/`)

- Use `hypothesis` (configured in `pyproject.toml` with `max_examples=500`).
- See §6 for property definitions.

---

## 3. Domain Fixture Setup

### 3.1 Virgin domain fixture

```python
import pytest
import shutil
from pathlib import Path

@pytest.fixture
def virgin_domain(tmp_path: Path) -> Path:
    """Create a minimal virgin domain with a few Tcl files and a base JSON."""
    domain = tmp_path / "test_domain"
    domain.mkdir()
    (domain / "main_procs.tcl").write_text(
        'proc entry_proc {} {\n    helper_proc\n}\n'
        'proc helper_proc {} {\n    return 1\n}\n'
    )
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text(
        '{\n'
        '  "$schema": "chopper/base/v1",\n'
        '  "domain": "test_domain",\n'
        '  "files": {"include": ["main_procs.tcl"]}\n'
        '}\n'
    )
    return domain
```

### 3.2 Trimmed domain fixture

```python
@pytest.fixture
def trimmed_domain(virgin_domain: Path, chopper_runner) -> Path:
    """Run a trim on the virgin domain; return the resulting trimmed domain path."""
    result = chopper_runner.trim(virgin_domain)
    assert result.exit_code == 0
    return virgin_domain
```

### 3.3 Large domain fixture (performance tests)

```python
# In tests/conftest.py:
import pytest
from tests.fixtures.gen_large_domain import generate_large_domain

@pytest.fixture(scope="session")
def large_domain_60_files(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped 60-file synthetic domain for parser performance tests."""
    domain_dir = tmp_path_factory.mktemp("large_domain_60_files", numbered=False)
    generate_large_domain(domain_dir, num_files=60, procs_per_file=5)
    return domain_dir
```

---

## 4. ChopperSubprocess Integration Test Harness

The `ChopperSubprocess` class wraps CLI invocation and captures exit code, stdout, and stderr. It is named distinctly from the production `ChopperRunner` (in `src/chopper/orchestrator/`) to avoid confusion in imports, grep results, and error messages: `ChopperRunner` sequences phases in-process; `ChopperSubprocess` shells out to the installed CLI and observes its results.

```python
# tests/integration/runner.py
from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str

    def assert_success(self) -> "RunResult":
        assert self.exit_code == 0, (
            f"Chopper exited with code {self.exit_code}\n"
            f"STDOUT:\n{self.stdout}\n"
            f"STDERR:\n{self.stderr}"
        )
        return self

    def assert_exit_code(self, expected: int) -> "RunResult":
        assert self.exit_code == expected, (
            f"Expected exit code {expected}, got {self.exit_code}\n"
            f"STDOUT:\n{self.stdout}\n"
            f"STDERR:\n{self.stderr}"
        )
        return self


class ChopperSubprocess:
    """Wraps `chopper` CLI invocation for integration tests.

    Usage::

        runner = ChopperSubprocess(domain_path)
        result = runner.trim("--base", "jsons/base.json")
        result.assert_success()
    """

    def __init__(self, domain_path: Path) -> None:
        self.domain_path = domain_path

    def run(self, *args: str) -> RunResult:
        """Run `chopper <args>` with cwd=domain_path."""
        proc = subprocess.run(
            [sys.executable, "-m", "chopper", *args],
            cwd=self.domain_path,
            capture_output=True,
            text=True,
        )
        return RunResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def trim(self, *extra_args: str) -> RunResult:
        return self.run("trim", "--base", "jsons/base.json", *extra_args)

    def scan(self, *extra_args: str) -> RunResult:
        return self.run("scan", *extra_args)

    def validate(self, *extra_args: str) -> RunResult:
        return self.run("validate", "--base", "jsons/base.json", *extra_args)

    def cleanup(self) -> RunResult:
        return self.run("cleanup", "--confirm")


# Domain-state assertion helper
from chopper.core.models import DomainState  # type: ignore[attr-defined]


def assert_domain_state(domain_path: Path, expected: DomainState) -> None:
    """Assert the domain is in the expected DomainState."""
    from chopper.trimmer.lifecycle import detect_domain_state  # lazy import
    actual = detect_domain_state(domain_path)
    assert actual == expected, (
        f"Expected domain state {expected.value!r}, got {actual.value!r} "
        f"for domain {domain_path}"
    )
```

### 4.1 Template Integration Test Function

```python
# Template for integration scenario tests:
def test_scenario_XX_description(virgin_domain: Path) -> None:
    """Scenario XX: end-to-end integration scenario (see named scenarios table below)."""
    runner = ChopperSubprocess(virgin_domain)

    # Arrange: set up any additional domain state here

    # Act
    result = runner.trim()

    # Assert
    result.assert_success()
    assert_domain_state(virgin_domain, DomainState.TRIMMED)
    # Add scenario-specific assertions here
```

---

## 5. Named Integration Scenarios

Scenario numbering is stable within this document; each scenario below names the sprint it originates from.

| # | Name | Stage | Key Assertions |
|---|---|---|---|
| 1 | Full trim from virgin | Stage 3 | State=TRIMMED; proc count reduced; `.chopper/` created |
| 2 | Re-trim with same selection | Stage 3 | State=TRIMMED; output byte-identical to first trim |
| 3 | Re-trim with different features | Stage 3 | State=TRIMMED; new manifest differs from first |
| 4 | Cleanup after trim | Stage 3 | State=CLEANED; `domain_backup/` absent |
| ~~5–9~~ | ~~Crash at each of 5 state transitions~~ | *Deferred* | *See note below* |
| 10 | Dry-run produces no filesystem changes | Stage 3 | No `domain_backup/`; no `.chopper/` |
| 11a | `--project` path resolution is correct | Stage 5 | Resolved base/features match expected paths |
| 11b | `--project` trim file list matches `--base/--features` | Stage 5 | Identical file trees |
| 11c | `--project` audit artifact `input_project.json` present | Stage 5 | Exact copy of project JSON |
| 12 | Feature order preserved in manifest | Stage 5 | `feature_json_paths` in manifest matches CLI order |
| 13 | Include-wins enforcement | Stage 2 | PI+ always superset of PI |
| 14 | Trace cycle (A→B→A) | Stage 2 | `TW-04 cycle-in-call-graph` WARNING emitted listing the cycle path; BFS terminates via visited-set; cycle procs appear in `dependency_graph.json` only when already reachable from explicit PI — they are NOT auto-copied into the trimmed domain |
| 15 | Empty domain (no procs) | Stage 2 | 0 procs after trim; no error |
| 16 | NFS lock detection log | Stage 3 | WARNING logged when lock path is on NFS mount |
| 17 | `--strict` escalates `VW-16 step-source-missing` to ERROR | Stage 4 | exit code 1 when F3 references trimmed step file |
| 18 | Feature name uniqueness (`VE-14 duplicate-feature-name`) | Stage 4 | ERROR when two features share same `name` |
| 19 | Empty base JSON (`VI-01 empty-base-json`) | Stage 4 | INFO diagnostic; no crash |
| 20 | `template_script` field removed in v1 | Stage 4 | Schema rejects `options.template_script` as `additionalProperties: false`; domain owners run their own generation scripts outside Chopper (see `FD-12`) |
| 21 | Dry-run artifact set | Stage 2 | `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt` all emitted with documented fields; no domain files written |
| **22** | **Re-trim idempotency** | Stage 3 | `compiled_manifest.json` hash identical across two identical-input runs; trimmed files byte-identical |
| 23 | Additive model — cross-source FE veto | Stage 2 | Feature `procedures.exclude` cannot remove a base `procedures.include`; `VW-19 cross-source-fe-vetoed` warning emitted; proc retained |
| 24 | Additive model — cross-source PE veto | Stage 2 | Feature `procedures.exclude` cannot remove another feature's explicit `procedures.include`; `VW-18 cross-source-pe-vetoed` warning emitted; proc retained |
| 25 | Additive model — same-source FE/PE conflict | Stage 2 | Same feature lists a proc in both `procedures.include` and `procedures.exclude`; `VW-11 fe-pe-same-source-conflict` warning emitted; include wins |
| 26 | F3 `flow_actions` ordering authoritative | Stage 2 | Last feature's `flow_actions` append order is preserved in compiled manifest; reordering CLI features changes `flow_actions` but leaves F1/F2 merged sets unchanged |
| 27 | F1/F2 merge order-independence | Stage 2 | Swapping CLI feature order leaves `files.include`/`procedures.include` union identical (set equality) |
| 28 | Provenance recorded in manifest | Stage 2 | Each entry in `compiled_manifest.json` carries its origin (`base` or `feature:<name>`) for every `files.*` and `procedures.*` decision |

> **Deferred — Scenarios 5–9 (crash-injection).** Forcing failure at each of the 5 state transitions (P5/P6 boundary) and asserting `assert_domain_recoverable` is deferred post-D0. The backup/rebuild model (bible §2.8 Case 2) handles crash recovery at the operator level: a user rebuilds from `<domain>_backup/`. These tests may be added in a future hardening phase.

---

## 6. Property-Based Tests (Hypothesis)

Configure in `pyproject.toml`:
```toml
[tool.hypothesis]
max_examples = 500
print_blob = true
```

The `.hypothesis/examples/` database is listed in `.gitignore`. Commit specific shrunk examples to `tests/fixtures/hypothesis_saved/` when they reveal regressions.

### 6.1 Parser Properties

```python
from hypothesis import given, strategies as st
from chopper.parser.tcl_parser import parse_file  # type: ignore

@given(st.builds(...))  # strategy: random proc definitions in valid Tcl
def test_parser_span_consistency(proc_entries):
    """Span invariant: start_line <= body_start_line <= body_end_line <= end_line."""
    for entry in proc_entries:
        assert entry.start_line <= entry.body_start_line
        assert entry.body_start_line <= entry.body_end_line
        assert entry.body_end_line <= entry.end_line

@given(...)
def test_parser_no_overlapping_spans(proc_entries):
    """No two ProcEntry spans in the same file overlap."""
    sorted_entries = sorted(proc_entries, key=lambda e: e.start_line)
    for i in range(len(sorted_entries) - 1):
        assert sorted_entries[i].end_line < sorted_entries[i + 1].start_line

@given(...)
def test_parser_canonical_name_uniqueness(proc_entries):
    """All canonical_name values are unique within one parse result."""
    names = [e.canonical_name for e in proc_entries]
    assert len(names) == len(set(names))
```

### 6.2 Compiler Properties

```python
@given(...)
def test_compiler_determinism(base_json, feature_jsons, domain):
    """Same selection → identical CompiledManifest (excluding timestamps)."""
    manifest1 = compile(base_json, feature_jsons, domain)
    manifest2 = compile(base_json, feature_jsons, domain)
    assert manifest1.files == manifest2.files
    assert manifest1.procs == manifest2.procs

@given(...)
def test_compiler_include_wins(base_json_with_explicit_includes, feature_json_with_excludes, domain):
    """PI+ is always a superset of PI (explicit includes are never dropped)."""
    manifest = compile(base_json_with_explicit_includes, [feature_json_with_excludes], domain)
    explicit_procs = {e.canonical_name for e in base_json_with_explicit_includes.procedures.include}
    surviving_procs = {d.canonical_name for d in manifest.procs}
    assert explicit_procs.issubset(surviving_procs), (
        f"Explicit includes were dropped: {explicit_procs - surviving_procs}"
    )
```

### 6.3 R1 Merge Order-Independence

**Contract:** For any set of feature JSONs whose `depends_on` graph permits reordering (i.e., no ordering constraint exists between them), `CompilerService.run()` must produce an identical `CompiledManifest` regardless of the order features appear in `LoadedConfig.features`. This applies to F1 (file decisions) and F2 (proc decisions) only. F3 `flow_actions` sequencing is explicitly order-dependent and is excluded from this invariant.

```python
from hypothesis import given, strategies as st
from itertools import permutations

@given(st.sampled_from(list(permutations(["feat_a", "feat_b", "feat_c"]))))
def test_compiler_f1_f2_order_independence(feature_order):
    """F1/F2 manifest is identical for any permutation of features with no ordering dependency."""
    # Load mini_domain or tracing_domain fixtures; features have no depends_on constraints.
    base = load_base("tests/fixtures/mini_domain/base.json")
    features = [load_feature(f"tests/fixtures/mini_domain/{f}.json") for f in feature_order]
    manifest = CompilerService().run(make_test_ctx(), LoadedConfig(base=base, features=tuple(features), ...), parsed)
    assert manifest.file_decisions == reference_manifest.file_decisions, (
        f"F1 decisions differ for order {feature_order}: {manifest.file_decisions}"
    )
    assert manifest.proc_decisions == reference_manifest.proc_decisions, (
        f"F2 decisions differ for order {feature_order}: {manifest.proc_decisions}"
    )
```

Parametrize over all permutations of 2–4 independent features drawn from `tracing_domain` or `mini_domain` fixtures. The reference manifest is produced by the canonical topo-sort order.
