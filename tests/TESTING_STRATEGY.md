# Chopper — Testing Strategy

> **Resolves:** H-17 (property-based testing scope), H-18 (integration test harness architecture)  
> **Status:** Sprint 1 required for §1–§3; Sprint 3 required for §4  
> **Owner:** QA lead

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

- Use the `ChopperRunner` harness (§4) and mini-domain fixtures (§3).
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

## 4. ChopperRunner Integration Test Harness

The `ChopperRunner` class wraps CLI invocation and captures exit code, stdout, and stderr.

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


class ChopperRunner:
    """Wraps `chopper` CLI invocation for integration tests.

    Usage::

        runner = ChopperRunner(domain_path)
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
    """Scenario XX: <description from ENGINEERING_HANDOFF_CHECKLIST.md>."""
    runner = ChopperRunner(virgin_domain)

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

Scenario numbering matches ENGINEERING_HANDOFF_CHECKLIST.md Sprint 4–5 integration scenarios.

| # | Name | Sprint | Key Assertions |
|---|---|---|---|
| 1 | Full trim from virgin | Sprint 3 | State=TRIMMED; proc count reduced; `.chopper/` created |
| 2 | Re-trim with same selection | Sprint 3 | State=TRIMMED; output byte-identical to first trim |
| 3 | Re-trim with different features | Sprint 3 | State=TRIMMED; new manifest differs from first |
| 4 | Cleanup after trim | Sprint 3 | State=CLEANED; `domain_backup/` absent |
| 5–9 | Crash at each of 5 state transitions | Sprint 3 | `assert_domain_recoverable`; re-run succeeds |
| 10 | Dry-run produces no filesystem changes | Sprint 3 | No `domain_backup/`; no `.chopper/` |
| 11a | `--project` path resolution is correct | Sprint 4 | Resolved base/features match expected paths |
| 11b | `--project` trim file list matches `--base/--features` | Sprint 4 | Identical file trees |
| 11c | `--project` audit artifact `input_project.json` present | Sprint 4 | Exact copy of project JSON |
| 12 | Feature order preserved in manifest | Sprint 4 | `feature_json_paths` in manifest matches CLI order |
| 13 | Include-wins enforcement | Sprint 2 | PI+ always superset of PI |
| 14 | Trace cycle (A→B→A) | Sprint 2 | Both procs included; TRACE-CYCLE-01 warning emitted |
| 15 | Empty domain (no procs) | Sprint 2 | 0 procs after trim; no error |
| 16 | NFS lock detection log | Sprint 3 | WARNING logged when lock path is on NFS mount |
| 17 | `--strict` escalates V-23 to ERROR | Sprint 4 | exit code 1 when F3 references trimmed step file |
| 18 | Feature name uniqueness (V-18) | Sprint 4 | ERROR when two features share same `name` |
| 19 | Empty base JSON (V-17) | Sprint 4 | INFO diagnostic; no crash |
| 20 | `template_script` not executed in dry-run | Sprint 4 | INFO logged; script not run |
| 21 | `diff_report.json` schema | Sprint 2 | Emitted with correct fields when base.json exists |
| **22** | **Re-trim idempotency** (H-15) | Sprint 3 | `compiled_manifest.json` hash identical across two identical-input runs; trimmed files byte-identical |

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
