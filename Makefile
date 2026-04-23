.PHONY: lint format format-check type-check imports-check docs-gate test test-unit test-integration test-golden test-property test-all check ci install-dev install-all clean

# Determinism: pin the hash seed so dict/set iteration order is stable across
# runs. Any test that depends on hash ordering leaking into output is a
# determinism bug (technical_docs/FINAL_HANDOFF_REVIEW.md S-6).
export PYTHONHASHSEED := 0

# ────────────────────────────────────────────────────────────
# Code Quality
# ────────────────────────────────────────────────────────────

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

format-check:
	ruff format --check src/ tests/

type-check:
	mypy src/

imports-check:
	lint-imports --config pyproject.toml

# Doc ↔ code consistency gates. Catch the "agent invented a new diagnostic
# code" and "agent drifted a service signature" classes of defect at CI time.
# See technical_docs/FINAL_HANDOFF_REVIEW.md PR-4.
docs-gate:
	python scripts/check_diagnostic_registry.py
	python scripts/check_service_signatures.py

# ────────────────────────────────────────────────────────────
# Testing
# ────────────────────────────────────────────────────────────

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v --no-cov

test-golden:
	pytest tests/golden/ -v --no-cov

test-property:
	pytest tests/property/ -v --no-cov

# Aggregate test target: runs every suite in a single pytest invocation so
# the `--cov-fail-under=78` threshold in pyproject.toml is checked against
# the union of covered statements, not re-checked per suite. The per-suite
# `test-*` targets above pass `--no-cov` for exactly this reason — running
# them individually would otherwise fail a green codebase because each
# suite exercises only part of src/.
test:
	pytest tests/unit/ tests/integration/ tests/golden/ tests/property/ -v

test-all: test

# ────────────────────────────────────────────────────────────
# Combined Gates
# ────────────────────────────────────────────────────────────

# Pre-commit gate (fast)
check: lint format-check type-check imports-check docs-gate test-unit

# Full CI gate
ci: lint format-check type-check imports-check docs-gate test

# ────────────────────────────────────────────────────────────
# Development Helpers
# ────────────────────────────────────────────────────────────

install-dev:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[dev,rich]"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
