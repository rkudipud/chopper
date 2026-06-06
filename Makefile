.PHONY: lint format format-check type-check imports-check docs-gate test test-unit test-integration test-golden test-property test-all check ci install-dev install-all clean bundle clean-bundle release-cth clean-cth install-cth test-cth-ward

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
# coverage is checked against the union of covered statements, not re-checked
# per suite. The per-suite `test-*` targets above pass `--no-cov` for exactly
# this reason — running them individually would otherwise fail a green codebase
# because each suite exercises only part of src/.
#
# This target enforces 100% line+branch coverage across the board (overriding
# the per-invocation `--cov-fail-under=99` default in pyproject.toml, which is
# the floor for the fast unit-only `make check` gate). The full suite hits
# every reachable line, so the authoritative gate holds it at 100%.
test:
	pytest tests/unit/ tests/integration/ tests/golden/ tests/property/ -v --cov-fail-under=100

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
	rm -rf build
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
	@echo "[1/5] Staging package source, schemas, and pyproject.toml..."
	mkdir -p $(BUNDLE_DIR)/bin
	cp -r src            $(BUNDLE_DIR)/
	cp -r schemas        $(BUNDLE_DIR)/
	cp pyproject.toml    $(BUNDLE_DIR)/
	rm -rf $(BUNDLE_DIR)/schemas/scripts
	find $(BUNDLE_DIR)/src $(BUNDLE_DIR)/schemas -type d \( -name __pycache__ -o -name "*.egg-info" \) -exec rm -rf {} +
	@echo "[2/5] Writing requirements snippet and installing runtime deps into vendor/ via $(BUNDLE_PYTHON)..."
	@( echo "# Chopper runtime dependencies"; \
	   grep -E '^\s*"(jsonschema)' pyproject.toml | sed -E 's/^\s*"([^"]+)".*/\1/'; \
	) > $(BUNDLE_DIR)/requirements.chopper.txt
	@$(BUNDLE_PYTHON) -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" \
	    || (echo "ERROR: $(BUNDLE_PYTHON) is < 3.13. Activate setup.csh venv or set BUNDLE_PYTHON."; exit 1)
	$(BUNDLE_PYTHON) -m pip install \
	    --target $(BUNDLE_DIR)/vendor \
	    --no-compile \
	    --quiet \
	    .
	rm -rf build
	rm -rf $(BUNDLE_DIR)/vendor/chopper
	rm -rf $(BUNDLE_DIR)/vendor/chopper-*.dist-info
	@! ls $(BUNDLE_DIR)/vendor/ 2>/dev/null | grep -iqE '^(pytest|_pytest|hypothesis|mypy|ruff|coverage)' \
	    || (echo "ERROR: dev/test deps leaked into vendor/"; exit 1)
	@echo "[3/5] Installing tcsh launcher..."
	cp scripts/dist/chopper.launcher.csh $(BUNDLE_DIR)/bin/chopper
	chmod +x $(BUNDLE_DIR)/bin/chopper
	@echo "[4/5] Writing bundle manifest..."
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
	   echo "  requirements.chopper.txt    -> runtime dependency list"; \
	) > $(BUNDLE_DIR)/MANIFEST.txt
	@echo "[5/5] Smoke test: chopper --help"
	$(BUNDLE_DIR)/bin/chopper --help >/dev/null
	find $(BUNDLE_DIR) -type d -name __pycache__ -exec rm -rf {} +
	@echo ""
	@echo "Bundle ready: $(BUNDLE_DIR)/"
	@echo "Ship the entire $(BUNDLE_DIR)/ directory; users invoke $(BUNDLE_DIR)/bin/chopper"

# ────────────────────────────────────────────────────────────
# CTH Ward Release (FB-style: shared py-flow venv, no vendoring)
# ────────────────────────────────────────────────────────────
# Produces dist/chopper-cth/ mirroring the CTH ward subtree so it can be
# dropped straight into a ward checkout and submitted (eou_sandbox_pydev).
# This is the deployment model described for the flow team:
#
#   * code  -> $ward/global/common/chopper/        (like global/common/flow_builder)
#   * exec  -> $ward/global/eouFW/bin/chopper       (on $PATH, like flow_builder.py)
#   * venv  -> reuse the shared py-flow venv; ADD deps to its requirements.txt
#             (deps are NOT vendored here — see requirements.chopper.txt)
#
# Usage:
#   make release-cth                 # stage dist/chopper-cth/ + review it
#   make install-cth WARD=/path/ward # rsync the staged tree into a ward
#
# CTH_DIR  : staging tree (ward subtree mirror)
# FLOW_DIR : the chopper code dir inside the staging tree
CTH_DIR  := dist/chopper-cth
FLOW_DIR := $(CTH_DIR)/global/common/chopper
BIN_DIR  := $(CTH_DIR)/global/eouFW/bin
# Interpreter used ONLY for the build-time smoke test below. The installed
# launcher resolves Python from the active py-flow venv at run time and never
# uses this value. It must have chopper's runtime deps (jsonschema), so
# it defaults to the repo dev venv when present. Override as needed.
CTH_SMOKE_PYTHON ?= $(firstword $(wildcard .venv/bin/python) python)

clean-cth:
	rm -rf $(CTH_DIR)

release-cth: clean-cth
	@echo "[1/5] Staging chopper package into global/common/chopper/..."
	mkdir -p $(FLOW_DIR)
	mkdir -p $(BIN_DIR)
	cp -r src            $(FLOW_DIR)/
	cp -r schemas        $(FLOW_DIR)/
	cp pyproject.toml    $(FLOW_DIR)/
	rm -rf $(FLOW_DIR)/schemas/scripts
	find $(FLOW_DIR)/src $(FLOW_DIR)/schemas -type d \( -name __pycache__ -o -name "*.egg-info" \) -exec rm -rf {} +
	@echo "[2/5] Emitting requirements snippet for the py-flow venv..."
	@( echo "# Chopper runtime dependencies — merge into the py-flow requirements.txt"; \
	   echo "# (chopper itself is NOT pip-installed; it runs from"; \
	   echo "#  global/common/chopper/src via PYTHONPATH set by the launcher)"; \
	   grep -E '^\s*"(jsonschema)' pyproject.toml | sed -E 's/^\s*"([^"]+)".*/\1/'; \
	) > $(CTH_DIR)/requirements.chopper.txt
	@echo "[3/5] Installing tcsh launcher..."
	cp scripts/dist/chopper.cth.csh $(BIN_DIR)/chopper
	chmod +x $(BIN_DIR)/chopper
	@echo "[4/5] Writing release manifest + submit notes..."
	@( echo "Chopper CTH release"; \
	   echo "built:   $$(date -u +%Y-%m-%dT%H:%M:%SZ)"; \
	   echo "version: $$(grep -E '^version' pyproject.toml | head -1)"; \
	   echo ""; \
	   echo "Ward subtree staged under $(CTH_DIR)/global/ :"; \
	   echo "  global/common/chopper/src/            -> chopper package source"; \
	   echo "  global/common/chopper/schemas/        -> JSON schemas"; \
	   echo "  global/common/chopper/pyproject.toml  -> package metadata"; \
	   echo "  global/eouFW/bin/chopper              -> tcsh launcher (on \$$PATH)"; \
	   echo ""; \
	   echo "Release steps:"; \
	   echo "  1. make install-cth WARD=\$$ward    (rsync global/ into your ward)"; \
	   echo "     -- or copy $(CTH_DIR)/global/ into your ward checkout by hand."; \
	   echo "  2. Append requirements.chopper.txt entries to the py-flow"; \
	   echo "     requirements.txt and rebuild/refresh that shared venv."; \
	   echo "  3. Submit the changelist to eou_sandbox_pydev."; \
	   echo "  4. Verify on a flow host:  rehash ; chopper --version"; \
	) > $(CTH_DIR)/RELEASE_CTH.txt
	@echo "[5/5] Smoke test: chopper --version (via staged layout)"
	CHOPPER_PYTHON=$(CTH_SMOKE_PYTHON) $(BIN_DIR)/chopper --version
	find $(CTH_DIR) -type d -name __pycache__ -exec rm -rf {} +
	@echo ""
	@echo "CTH release staged: $(CTH_DIR)/"
	@echo "  Review $(CTH_DIR)/RELEASE_CTH.txt, then:  make install-cth WARD=<your-ward>"
	@echo "  Remember to merge $(CTH_DIR)/requirements.chopper.txt into the py-flow requirements.txt"

# Install the staged ward subtree into a real ward checkout. Requires WARD=.
# Removes any previous Chopper installation before copying the fresh build.
install-cth:
	@test -n "$(WARD)" \
	    || (echo "ERROR: set WARD=/path/to/ward, e.g. make install-cth WARD=\$$ward"; exit 1)
	@test -d "$(CTH_DIR)/global" \
	    || (echo "ERROR: $(CTH_DIR)/global not found — run 'make release-cth' first."; exit 1)
	@test -d "$(WARD)/global/eouFW/bin" \
	    || (echo "ERROR: $(WARD)/global/eouFW/bin not found — is WARD a valid ward?"; exit 1)
	@echo "Removing previous Chopper installation from ward (if any)..."
	rm -rf  $(WARD)/global/common/chopper
	rm -f   $(WARD)/global/eouFW/bin/chopper
	@echo "Installing chopper into ward: $(WARD)"
	rsync -a $(CTH_DIR)/global/ $(WARD)/global/
	@echo "Done. On a flow host:  rehash ; chopper --version"
	@echo "Then merge requirements.chopper.txt into the py-flow requirements.txt and submit to eou_sandbox_pydev."

# Run the full pytest suite from the CTH ward against the installed Chopper source.
# Tests in tests/unit/scripts/ are excluded because schemas/scripts is a dev-only
# helper set that is intentionally not shipped in the CTH bundle.
# Requires WARD= (same path used for install-cth) and a dev venv at .venv/.
#
#   make test-cth-ward WARD=/path/to/ward
#
CTH_WARD_PYTHON ?= $(CURDIR)/.venv/bin/python

test-cth-ward:
	@test -n "$(WARD)" \
	    || (echo "ERROR: set WARD=/path/to/ward, e.g. make test-cth-ward WARD=\$$ward"; exit 1)
	@test -d "$(WARD)/global/common/chopper/src" \
	    || (echo "ERROR: Chopper not installed in $(WARD). Run make release-cth then make install-cth WARD=$(WARD) first."; exit 1)
	@test -f "$(CTH_WARD_PYTHON)" \
	    || (echo "ERROR: $(CTH_WARD_PYTHON) not found. Run 'source setup.csh' to create .venv, or set CTH_WARD_PYTHON=/path/to/python."; exit 1)
	@echo "[1/3] Copying test suite into ward Chopper package (temporary)..."
	rsync -a tests/ $(WARD)/global/common/chopper/tests/
	@echo "[2/3] Running pytest against ward-installed Chopper source..."
	@( cd $(WARD)/global/common/chopper && \
	   $(CTH_WARD_PYTHON) -m pytest tests \
	       -q \
	       --ignore=tests/unit/scripts \
	       --cov=src/chopper \
	       --cov-report=term-missing \
	       --cov-fail-under=99 \
	); STATUS=$$?; \
	rm -rf $(WARD)/global/common/chopper/tests; \
	find $(WARD)/global/common/chopper -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true; \
	echo "[3/3] Cleaned up test artifacts from ward."; \
	exit $$STATUS
