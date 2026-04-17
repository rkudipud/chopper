# Chopper — Golden File Guide

> **Resolves:** H-14 (PRE_CODING_REVIEW.md)  
> **Applies to:** Sprint 1 onwards  
> **Owner:** QA lead

This guide defines the format, naming, comparison mechanism, and update process for all golden (expected-output) files used in Chopper regression tests.

---

## 1. Format

All golden files use **JSON** format. JSON is:
- Deterministic (stable key ordering enforced at write time)
- Human-readable in `git diff`
- Machine-parseable for assertions

**Do NOT use plain text, YAML, or pickled objects** as golden file formats.

---

## 2. Naming Convention

```
tests/golden/<module>__<fixture_name>.json
```

Examples:
- `tests/golden/parser__basic_single_proc.json`
- `tests/golden/parser__namespace_reset_after_block.json`
- `tests/golden/compiler__include_wins_over_exclude.json`
- `tests/golden/trimmer__proc_trim_comment_association.json`

**Rules:**
- Double underscore `__` separates module name from fixture name.
- `<module>` is the Python module under test (e.g., `parser`, `compiler`, `trimmer`).
- `<fixture_name>` matches the test fixture file stem (without `.tcl` or `.json`).
- Use `snake_case` only — no uppercase, no hyphens.

---

## 3. Comparison Mechanism

Use the `pytest-regressions` library (`DataRegressionFixture`) or the custom helper below.

### 3.1 Preferred: `pytest-regressions`

```python
def test_parser_basic_single_proc(data_regression):
    result = parse_file("tests/fixtures/edge_cases/parser_basic_single_proc.tcl")
    data_regression.check(result.to_dict())
```

`data_regression.check()` automatically:
- Writes a new golden file on first run (or `--force-regen`)
- Asserts exact match on subsequent runs
- Normalizes Python types to JSON-serializable primitives

### 3.2 Alternative: Custom helper

```python
# tests/conftest.py
import json
from pathlib import Path

def assert_json_matches_golden(actual: dict, name: str) -> None:
    """Assert actual matches golden file; create golden if absent."""
    golden_path = Path("tests/golden") / f"{name}.json"
    if not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n",
            encoding="utf-8"
        )
        return  # First run — always passes
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert actual == expected, (
        f"Golden mismatch for {name!r}.\n"
        f"Run: pytest --golden-update to regenerate.\n"
        f"Then review: git diff tests/golden/{name}.json"
    )
```

---

## 4. Update Process

### 4.1 Updating a single golden file

```bash
pytest tests/unit/test_parser.py::test_basic_single_proc --force-regen
# or with the custom helper:
pytest tests/unit/test_parser.py::test_basic_single_proc --golden-update
```

### 4.2 Updating all golden files

```bash
pytest --force-regen
# or
pytest --golden-update
```

### 4.3 Reviewing changes

```bash
git diff tests/golden/
```

**Engineer must review every changed golden file before committing.** A golden update is a statement that "this new output is correct." Do not auto-commit golden updates without manual inspection.

### 4.4 CI gate

Golden updates are never auto-applied in CI. The `--force-regen` / `--golden-update` flag must be explicitly passed. If CI detects a golden mismatch without the flag, the test fails with an actionable message.

---

## 5. What Goes in Golden Files

Golden files capture the **stable output contract** of a function or pipeline:

| Module | Golden captures |
|---|---|
| `parser` | List of `ProcEntry` dicts: `canonical_name`, `start_line`, `end_line`, `body_start_line`, `body_end_line`, `qualified_name`, `namespace_path` |
| `compiler` | `CompiledManifest` summary dict: `files[].{path, treatment, reason}`, `procs[].{canonical_name, reason}` |
| `trimmer` | `TrimStats` dict: `files_before`, `files_after`, `procs_before`, `procs_after` |
| `audit` | `chopper_run.json` structure (with deterministic fields only; timestamps excluded) |

**Exclude from golden files:**
- Timestamps (`timestamp`, `started_at`, `scan_date`) — use `"<redacted>"` or omit.
- Run IDs (UUID) — use `"<run_id>"` or `""`.
- Absolute paths — use domain-relative paths only.

---

## 6. Golden File Registration

Maintain an index in this file (Section 7) so engineers can find golden files without scanning the directory.

---

## 7. Golden File Index

| Golden File | Module | Fixture | Added in Sprint |
|---|---|---|---|
| `parser__basic_single_proc.json` | parser | Fixture 1 | Sprint 1 |
| `parser__basic_multiple_procs.json` | parser | Fixture 2 | Sprint 1 |
| `parser__empty_file.json` | parser | Fixture 3 | Sprint 1 |
| `parser__brace_in_string_literal.json` | parser | Fixture 4 (error case) | Sprint 1 |
| `parser__backslash_line_continuation.json` | parser | Fixture 5 | Sprint 1 |
| `parser__nested_namespace_accumulates.json` | parser | Fixture 6 | Sprint 1 |
| `parser__namespace_reset_after_block.json` | parser | Fixture 7 (B-04) | Sprint 1 |
| `parser__computed_proc_name_skipped.json` | parser | Fixture 8 | Sprint 1 |
| `parser__duplicate_proc_definition_error.json` | parser | Fixture 9 | Sprint 1 |
| `parser__comment_with_braces_ignored.json` | parser | Fixture 10 | Sprint 1 |
| `parser__proc_inside_if_block.json` | parser | Fixture 11 | Sprint 1 |
| `parser__namespace_absolute_override.json` | parser | Fixture 12 | Sprint 1 |
| `parser__empty_proc_body_forms.json` | parser | Fixture 13 (B-02) | Sprint 1 |
| `parser__call_extraction.json` | parser | Fixture 14 | Sprint 1 |
| `parser__encoding_latin1_fallback.json` | parser | Fixture 15 | Sprint 1 |
| *(compiler golden files added in Sprint 2)* | — | — | Sprint 2 |
| *(trimmer golden files added in Sprint 3)* | — | — | Sprint 3 |
