# Chopper -- Testing Strategy

> **Scope:** Sec.1-Sec.3 apply from Stage 1 (Parser) onward; Sec.4 applies from Stage 3 (Trimmer) onward.

Stage boundaries used throughout this document:

| Stage | Module(s) | Purpose |
| --- | --- | --- |
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
| --- | --- | --- |
| All runtime modules | 100% line + branch under the full suite | Aggregate coverage gate below; no separate lower per-module thresholds |
| **Full suite (`make ci`)** | **100% line + branch** | [OK] `--cov-fail-under=100` on the aggregate `test` target |
| **Fast unit-only gate (`make check`)** | **>= 99.8% line** | [OK] `--cov-fail-under=99.8` (pyproject default) |

Coverage is run with `--cov-branch` (configured in `pyproject.toml`). Do not lower
the threshold, exclude reachable lines, or skip a failing test to make the gate
green. Platform skips must explain the unavailable host capability.

---

## 2. Test Layers

### 2.1 Unit Tests (`tests/unit/`)

- Fast, isolated, no filesystem side effects beyond `tmp_path`.
- One test module per package module: `test_parser.py`, `test_compiler.py`, etc.
- Audit-artifact output contracts are pinned with `pytest-regressions` golden files (Sec.7).

### 2.2 Integration Tests (`tests/integration/`)

- Use the `ChopperSubprocess` harness (Sec.4) and mini-domain fixtures (Sec.3).
- Test full end-to-end pipelines: validate -> trim -> cleanup.
- Named scenarios (see Sec.5).

### 2.3 Property Tests (`tests/property/`)

- Use Hypothesis with executable settings; the sourcing properties explicitly
  run 500 examples each. A `[tool.hypothesis]` TOML entry alone does not configure
  Hypothesis at runtime.
- See Sec.6 for property definitions.

### 2.4 V2 sourcing regression matrix

| Contract | Executable check |
|---|---|
| All 16 combinations of `cross_validate`, `generate_stack`, `indent`, `insert_markers`, in v1/v2, dry/live, Tcl/standalone modes (128 cases) | `integration/test_feature_sourcing_options.py` |
| No features, single features, both orders; base pointers never listed; optional variants | `integration/test_feature_sourcing_options.py`, `integration/test_feature_vars.py`, `integration/test_feature_procs.py` |
| Every project/base/feature version combination; mixed versions rejected | `integration/test_feature_sourcing_options.py` |
| Missing pointers under strict/non-strict policy without severity rewriting | `integration/test_feature_sourcing_options.py` |
| Whole-file keeps, R1 overrides, dependency order, duplicates, collisions, and pristine re-trim | `unit/config/test_service_feature_vars.py`, `unit/config/test_service_feature_procs.py`, `integration/test_feature_procs.py` |
| p4 add/edit, audit lists, LoC GENERATED bucket, and aggregate input deduplication | `integration/test_feature_procs.py`, `unit/generators/test_stack_emitter.py` |
| Every shipped v1/v2 JSON, v2 field compatibility, and validator CLI schema discovery | `unit/config/test_schema.py`, `unit/test_validate_jsons_script.py` |
| Migration-skill checker: gate, adoption level, generated-file preview and on-disk match, baseline delta classes, JSON-edit suggestions | `integration/test_v2_check_script.py` |
| Runnable example through validate, loc, dry-run, live trim, re-trim, cleanup | `integration/test_feature_sourcing_options.py` |
| Pointer expansion and vars/procs emission, 500 generated examples each | `property/test_feature_sourcing.py` |

This matrix exhausts the listed switch combinations, not every possible Tcl
program or feature permutation. Full coverage is a regression gate, not proof
of EDA runtime equivalence. Vendor-tool execution remains domain-owner testing.

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
        "proc entry_proc {} {\n    helper_proc\n}\nproc helper_proc {} {\n    return 1\n}\n"
    )
    (domain / "jsons").mkdir()
    (domain / "jsons" / "base.json").write_text(
        '{\n  "$schema": "base-v1",\n  "domain": "test_domain",\n  "files": {"include": ["main_procs.tcl"]}\n}\n'
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
            f"Chopper exited with code {self.exit_code}\nSTDOUT:\n{self.stdout}\nSTDERR:\n{self.stderr}"
        )
        return self

    def assert_exit_code(self, expected: int) -> "RunResult":
        assert self.exit_code == expected, (
            f"Expected exit code {expected}, got {self.exit_code}\nSTDOUT:\n{self.stdout}\nSTDERR:\n{self.stderr}"
        )
        return self


class ChopperSubprocess:
    """Wraps `chopper` CLI invocation for integration tests.

    Usage::

        runner = ChopperSubprocess(domain_path)
        result = runner.trim()
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

    def validate(self, *extra_args: str) -> RunResult:
        return self.run("validate", "--base", "jsons/base.json", *extra_args)

    def cleanup(self) -> RunResult:
        return self.run("cleanup", "--confirm")


# Domain-state assertion helper
from chopper.core.models_common import DomainState


def assert_domain_state(domain_path: Path, expected: DomainState) -> None:
    """Assert the domain is in the expected DomainState."""
    from chopper.trimmer.lifecycle import detect_domain_state  # lazy import

    actual = detect_domain_state(domain_path)
    assert actual == expected, (
        f"Expected domain state {expected.value!r}, got {actual.value!r} for domain {domain_path}"
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
| --- | --- | --- | --- |
| 1 | Full trim from virgin | Stage 3 | State=TRIMMED; proc count reduced; `.chopper/` created |
| 2 | Re-trim with same selection | Stage 3 | State=TRIMMED; output byte-identical to first trim |
| 3 | Re-trim with different features | Stage 3 | State=TRIMMED; new manifest differs from first |
| 4 | Cleanup after trim | Stage 3 | State=CLEANED; `domain_backup/` absent |
| ~~5-9~~ | ~~Crash at each of 5 state transitions~~ | *Deferred* | *See note below* |
| 10 | Dry-run produces no filesystem changes | Stage 3 | No `domain_backup/`; no `.chopper/` |
| 11a | `--project` path resolution is correct | Stage 5 | Resolved base/features match expected paths |
| 11b | `--project` trim file list matches `--base/--features` | Stage 5 | Identical file trees |
| 11c | `--project` audit artifact `input_project.json` present | Stage 5 | Exact copy of project JSON |
| 12 | Feature order preserved in manifest | Stage 5 | `feature_json_paths` in manifest matches CLI order |
| 13 | Include-wins enforcement | Stage 2 | PI+ always superset of PI |
| 14 | Trace cycle (A->B->A) | Stage 2 | `TW-04 cycle-in-call-graph` WARNING emitted listing the cycle path; BFS terminates via visited-set; cycle procs appear in `dependency_graph.json` only when already reachable from explicit PI -- they are NOT auto-copied into the trimmed domain |
| 15 | Empty domain (no procs) | Stage 2 | 0 procs after trim; no error |
| 16 | Re-trim discards manual edits | Stage 3 | Fixed pre-flight warning emitted; rerun rebuilds from `<domain>_backup/` rather than preserving edits in `<domain>/` |
| 17 | `--strict` escalates `VW-16 step-source-missing` to ERROR | Stage 4 | exit code 1 when F3 references trimmed step file |
| 18 | Feature name uniqueness (`VE-14 duplicate-feature-name`) | Stage 4 | ERROR when two features share same `name` |
| 19 | Empty base JSON (`VI-01 empty-base-json`) | Stage 4 | INFO diagnostic; no crash |
| 20 | `template_script` field removed in v1 | Stage 4 | Schema rejects `options.template_script` as `additionalProperties: false`; domain owners run their own generation scripts outside Chopper (see `FD-12`) |
| 21 | Dry-run artifact set | Stage 2 | `compiled_manifest.json`, `dependency_graph.json`, `trim_report.json`, `trim_report.txt` all emitted with documented fields; no domain files written |
| **22** | **Re-trim idempotency** | Stage 3 | `compiled_manifest.json` hash identical across two identical-input runs; trimmed files byte-identical |
| 23 | Overlay model -- later layer's PE shadows base PI | Stage 2 | Base includes proc; later feature `procedures.exclude` removes it; final manifest drops the proc; `VW-21 layer-shadowed` warning emitted with `(layer, prior_layer, action="remove-proc")` provenance |
| 24 | Overlay model -- later layer's PI re-includes a previously-excluded proc | Stage 2 | Base PE excludes proc `foo`; later feature PI re-includes `foo`; final manifest keeps `foo`; `VW-21 layer-shadowed` warning emitted (the feature shadowed the base PE) |
| 25 | Overlay audit-trail visibility | Stage 2 | `compiled_manifest.json` records `contributed_by` (last winning layer) and `shadowed_by[]` (every transition); `files_kept.txt` shows the `contributed_by` token; `files_removed.txt` shows `removed-by:<layer>:files.exclude` for files removed by a later layer |
| 26 | `VE-27 no-op-exclude` catches typo-class excludes | Stage 4 | Feature lists `files.exclude` (or `procedures.exclude`) entry that matches nothing in any earlier layer's running set and matches nothing on disk via glob; validator emits `VE-27` and exits 1 |
| 27 | `project.json` features ordering authoritative for F1, F2, **and** F3 | Stage 2 | Swapping the order of two features in `project.features[]` changes the `compiled_manifest.json` for files/procs the two features touch in conflicting ways (was F3-only in 1.x); identical orderings yield byte-identical manifests |
| 28 | Same-layer rules unaffected by overlay model | Stage 2 | Within one JSON, `VW-09` / `VW-11` / `VW-12` / `VW-13` still fire for the same-source authoring conveniences they always covered; cross-layer transitions surface as `VW-21` instead |

> **Deferred -- Scenarios 5-9 (crash-injection).** Forcing failure at each of the 5 state transitions (P5/P6 boundary) and asserting `assert_domain_recoverable` is deferred post-D0. The backup/rebuild model (architecture doc Sec.2.8 Case 2) handles crash recovery at the operator level: a user rebuilds from `<domain>_backup/`. These tests may be added in a future hardening phase.

---

## 6. Property-Based Tests (Hypothesis)

Use an explicit test decorator (as in `property/test_feature_sourcing.py`) or
an explicitly registered and loaded Hypothesis profile:

```python
from hypothesis import settings

@settings(max_examples=500, print_blob=True)
@given(...)
def test_property(...):
    ...
```

The `.hypothesis/examples/` database is listed in `.gitignore`. Commit specific shrunk examples to `tests/fixtures/hypothesis_saved/` when they reveal regressions.

### 6.1 Parser Properties

Parser span, brace, namespace, and literal-body behavior is tested in
`unit/parser/` and fixture integration tests. Do not describe illustrative
pseudocode as an implemented Hypothesis suite. Actual property modules are
listed below.

### 6.2 Compiler Properties

`property/test_determinism.py` checks serializer stability and a pure BFS model;
the real tracer is covered by compiler unit tests and golden/integration tests.
`property/test_smoke.py` checks POSIX-shaped paths.
`property/test_feature_sourcing.py` exercises the production expansion and
emission helpers with explicit 500-example settings.

### 6.3 R1 Merge Order-Independence

**No global order-independence invariant exists.** R1 is last-layer-wins for
F1/F2 as well as F3. Features may have no `depends_on` relationship and still
conflict over a file, proc, or step. Tests must preserve the selected order
and assert its result; commuting overlays may be compared only when their
contributions are genuinely disjoint. The v2 selection tests check both
orders explicitly because source-block order is observable.

---

## 7. Golden Files

Golden files pin the **wire shape** of the four shipped `.chopper/` audit
artifacts (`chopper_run.json`, `compiled_manifest.json`,
`dependency_graph.json`, `trim_report.json`; architecture doc Sec.5.5.2-5.5.5)
so NFR-03 (byte-identical output on every run) is enforced end to end.

- **Location:** `tests/golden/test_audit_artifacts_golden.py` drives
  `chopper validate` and `chopper trim --dry-run` against a seeded minimal
  domain. Expected data lives beside it in
  `tests/golden/test_audit_artifacts_golden/<test_name>.yml`.
- **Mechanism:** `pytest-regressions` `data_regression.check()`. The first run
  writes the file; later runs assert an exact match.
- **Redaction:** strip legitimately variable fields before the check -- run ids,
  wall-clock timestamps, durations, and absolute or `tmp_path` paths. Keep
  every other field domain-relative and deterministic.
- **Unit-level contracts:** parser, compiler, and trimmer outputs are pinned
  by explicit assertions in `tests/unit/` against the fixtures in
  [FIXTURE_CATALOG.md](FIXTURE_CATALOG.md), not by golden files.

**Updating a golden.** Run `pytest tests/golden/ --force-regen` **only** when
the artifact shape change is already specified in the architecture doc and
cascaded per `.github/instructions/project.instructions.md` ("Cascading
Updates"). Review `git diff tests/golden/` line by line before committing --
a golden update asserts "this new output is correct". CI never regenerates;
a mismatch without `--force-regen` fails the run.
