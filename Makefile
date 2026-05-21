.PHONY: lint format format-check type-check imports-check docs-gate test test-unit test-integration test-golden test-property test-all check ci install-dev install-all clean bundle clean-bundle

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
	python schemas/scripts/check_diagnostic_registry.py
	python schemas/scripts/check_service_signatures.py

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

# ────────────────────────────────────────────────────────────
# Distribution Bundle (for TFM / EC ship)
# ────────────────────────────────────────────────────────────
# Produces a self-contained directory under dist/chopper-bundle/ that runs
# directly on EC systems using /usr/intel/bin/python3.13.2 — no venv,
# no pip install required at the deploy site.
#
#   make bundle           # build dist/chopper-bundle/
#   dist/chopper-bundle/bin/chopper --help
#
# Run before every cth release; ship dist/chopper-bundle/ alongside the TFM.

BUNDLE_DIR := dist/chopper-bundle
# BUNDLE_PYTHON: the interpreter used to populate vendor/ wheels. Defaults to
# whatever 'python' is active in the current env (so the dev's setup.csh-
# resolved Python is used and no path is baked in). The runtime launcher in
# scripts/dist/chopper.launcher.csh resolves Python independently at deploy
# time and does NOT depend on this value.
BUNDLE_PYTHON ?= python

clean-bundle:
	rm -rf $(BUNDLE_DIR)

bundle: clean-bundle
	@echo "[1/6] Staging package source, schemas, technical_docs, pyproject.toml..."
	mkdir -p $(BUNDLE_DIR)/bin
	cp -r src            $(BUNDLE_DIR)/
	cp -r schemas        $(BUNDLE_DIR)/
	cp -r technical_docs $(BUNDLE_DIR)/
	cp pyproject.toml    $(BUNDLE_DIR)/
	@echo "[2/6] Installing runtime deps into vendor/ via $(BUNDLE_PYTHON)..."
	@$(BUNDLE_PYTHON) -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" \
	    || (echo "ERROR: $(BUNDLE_PYTHON) is < 3.13. Activate setup.csh venv or set BUNDLE_PYTHON."; exit 1)
	$(BUNDLE_PYTHON) -m pip install \
	    --target $(BUNDLE_DIR)/vendor \
	    --no-compile \
	    --quiet \
	    .
	rm -rf $(BUNDLE_DIR)/vendor/chopper
	rm -rf $(BUNDLE_DIR)/vendor/chopper-*.dist-info
	@! ls $(BUNDLE_DIR)/vendor/ 2>/dev/null | grep -iqE '^(pytest|_pytest|hypothesis|mypy|ruff|coverage)' \
	    || (echo "ERROR: dev/test deps leaked into vendor/"; exit 1)
	@echo "[3/6] Installing tcsh launcher..."
	cp scripts/dist/chopper.launcher.csh $(BUNDLE_DIR)/bin/chopper
	chmod +x $(BUNDLE_DIR)/bin/chopper
	@echo "[4/6] Staging Copilot agent overlay (agent + prompts + skills + instructions)..."
	mkdir -p $(BUNDLE_DIR)/copilot/.github/agents
	mkdir -p $(BUNDLE_DIR)/copilot/.github/prompts
	mkdir -p $(BUNDLE_DIR)/copilot/.github/instructions
	mkdir -p $(BUNDLE_DIR)/copilot/.github/skills
	cp .github/agents/chopper-agent.agent.md $(BUNDLE_DIR)/copilot/.github/agents/
	cp .github/prompts/bisect-feature-breakage.prompt.md  $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/bootstrap-domain.prompt.md         $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/explain-last-run.prompt.md         $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/package-bug-artifacts.prompt.md    $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/report-chopper-bug.prompt.md       $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/validate-my-jsons.prompt.md        $(BUNDLE_DIR)/copilot/.github/prompts/
	cp .github/prompts/why-was-dropped.prompt.md          $(BUNDLE_DIR)/copilot/.github/prompts/
	cp scripts/dist/chopper.instructions.md $(BUNDLE_DIR)/copilot/.github/instructions/
	cp -r .github/skills/acquire-codebase-knowledge $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/context-map                $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-cli               $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-debugging         $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-exploring         $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-guide             $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-impact-analysis   $(BUNDLE_DIR)/copilot/.github/skills/
	cp -r .github/skills/gitnexus-refactoring       $(BUNDLE_DIR)/copilot/.github/skills/
	@echo "[5/6] Writing bundle manifest..."
	@( echo "Chopper bundle manifest"; \
	   echo "built: $$(date -u +%Y-%m-%dT%H:%M:%SZ)"; \
	   echo "version: $$(grep -E '^version' pyproject.toml | head -1)"; \
	   echo "build_python: $(BUNDLE_PYTHON)"; \
	   echo ""; \
	   echo "Layout:"; \
	   echo "  bin/chopper                 -> tcsh launcher"; \
	   echo "  src/                        -> chopper package source"; \
	   echo "  vendor/                     -> runtime deps (no test packages)"; \
	   echo "  schemas/                    -> JSON schemas"; \
	   echo "  technical_docs/             -> reference docs incl. DIAGNOSTIC_CODES.md"; \
	   echo "  copilot/.github/agents/     -> Chopper Agent (single user-facing agent)"; \
	   echo "  copilot/.github/prompts/    -> 7 user-facing prompts"; \
	   echo "  copilot/.github/instructions/ -> chopper.instructions.md (user-facing)"; \
	   echo "  copilot/.github/skills/     -> Chopper-relevant skills"; \
	) > $(BUNDLE_DIR)/MANIFEST.txt
	@echo "[6/6] Smoke test: chopper --help"
	$(BUNDLE_DIR)/bin/chopper --help >/dev/null
	@echo ""
	@echo "Bundle ready: $(BUNDLE_DIR)/"
	@echo "Ship the entire $(BUNDLE_DIR)/ directory; users invoke $(BUNDLE_DIR)/bin/chopper"
	@echo "Copilot users: copy $(BUNDLE_DIR)/copilot/.github/ contents into their workspace .github/"
