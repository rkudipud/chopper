# Chopper — Engineering Team Handoff Checklist

**Date:** April 5, 2026  
**Status:** ✅ PRODUCTION-READY — Multi-Agent Review Complete, Ready for Day 0 Coding  
**Execution Model:** AI-Assisted Sprint Development (days, not weeks)  

---

## Pre-Sprint Sign-Off Checklist

### Documentation Review by Engineering Lead

- [x] ARCHITECTURE.md reviewed and approved (Rev 22 — no open questions) ✅
- [x] TCL_PARSER_SPEC.md reviewed and understood (Rev 6 — 15 edge cases all mapped to fixtures) ✅
- [x] TECHNICAL_REQUIREMENTS.md reviewed (Rev 10 — all constraints understood) ✅
- [x] JSON schemas validation (base-v1, feature-v1, project-v1 — all aligned with arch docs) ✅
- [x] FINAL_PRODUCTION_REVIEW.md reviewed (GO verdict, 0 blockers) ✅
- [x] IMPLEMENTATION_PITFALLS_GUIDE.md distributed and understood (P-01 through P-31 reviewed) ✅

### Architecture Clarifications Completed

- [x] GAP-01: `_draft` metadata added to base-v1.schema.json
- [x] GAP-02: CompiledManifest dataclass finalized and documented
- [x] GAP-03: Audit artifact JSON structure defined
- [x] GAP-04: F3 flow_action merge semantics clarified
- [x] Ambiguities A-01 through A-05 resolved (hook semantics, scan diff format, etc.)
- [x] Three input modes defined (base-only, base+features, project JSON) — ARCHITECTURE.md §5.1 ✅
- [x] Project JSON path resolution rules understood (CWD/domain root, not project-file-relative) — §6.6 ✅
- [x] Default curated JSON layout understood: `<domain>/jsons/base.json` and `<domain>/jsons/features/*.json` ✅
- [x] Hook file semantics: discovery-only from `-use_hooks`; must be in `files.include` to copy — §4.1, §4.3 ✅
- [x] FR-35 (project JSON input) and FR-36 (mutual exclusivity) reviewed ✅
- [x] V-13, V-14, V-15 validation checks for project JSON reviewed — TECHNICAL_REQUIREMENTS.md §8.3 ✅
- [x] `--strict` flag behavior understood (escalates warnings to errors, changes exit code) ✅
- [x] `--confirm` requirement for `chopper cleanup` understood (irreversible operation guard) ✅
- [x] GAP-05: Parser return type ambiguity resolved — `parse_file()` returns `list[ProcEntry]`, diagnostics via `on_diagnostic: DiagnosticCollector` callback (TCL_PARSER_SPEC Rev 7, TRQ §5.4) ✅
- [x] Doc-driven development lifecycle rules added to copilot-instructions.md and workspace instruction files ✅

### Team Preparation

- [x] Engineering team allocated — AI-assisted multi-agent development (parser, compiler, trimmer, validator, CLI agents) ✅
- [x] Roles & responsibilities assigned — per DEVELOPER_KICKOFF.md module assignments ✅
- [x] Kick-off meeting completed (parser logic, compiler algorithm, state machine reviewed) ✅
- [x] Development environment set up (Python 3.9+, pytest, Ruff, structlog — pyproject.toml verified) ✅
- [x] Repository structure created (pyproject.toml, Makefile, setup.csh, test scaffolding, fixtures) ✅

---

## Development Environment Setup

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.9+ | Runtime |
| **pytest** | 7.0+ | Testing framework |
| **Ruff** | 0.4+ | Linting + formatting |
| **structlog** | 24.1.0+ | Structured logging |
| **jsonschema** | 4.0+ | JSON schema validation |
| **hypothesis** | 6.0+ | Property-based testing |
| **mypy** | 1.0+ | Static type checking |
| **pathlib** | builtin | Cross-platform paths |

> **Note:** The authoritative dependency versions are in `pyproject.toml` at the repo root. The table above is a summary for quick reference.

### Repository Structure (Create Now)

```
chopper/
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
│       │   ├── loaders.py          # JSON schema loading and validation (base/feature/project)
│       │   └── settings.py         # .chopper.config TOML loading, env overrides, workspace config
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── errors.py
│       │   ├── diagnostics.py
│       │   ├── protocols.py
│       │   └── serialization.py
│       ├── compiler/
│       │   ├── __init__.py
│       │   ├── compiler.py
│       │   ├── tracer.py
│       │   └── manifest.py
│       ├── parser/
│       │   ├── __init__.py
│       │   └── tcl_parser.py
│       ├── trimmer/
│       │   ├── __init__.py
│       │   ├── lifecycle.py
│       │   ├── lock.py
│       │   └── trimmer.py
│       ├── validator/
│       │   ├── __init__.py
│       │   └── validator.py
│       ├── audit/
│       │   ├── __init__.py
│       │   └── audit.py
│       └── ui/
│           ├── __init__.py
│           ├── protocols.py
│           ├── rich_renderer.py
│           └── plain_renderer.py
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── edge_cases/             # Parser fixtures and adversarial Tcl inputs
│   │   ├── mini_domain/            # F1/F2 integration domain
│   │   ├── namespace_domain/       # Namespace resolution fixtures
│   │   └── tracing_domain/         # Trace-expansion fixtures
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_compiler.py
│   │   └── ...
│   ├── integration/
│   │   └── test_e2e.py
│   └── golden/                     # Expected outputs for regression
├── schemas/
│   ├── base-v1.schema.json
│   ├── feature-v1.schema.json
│   └── project-v1.schema.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TCL_PARSER_SPEC.md
│   ├── TECHNICAL_REQUIREMENTS.md
│   ├── FINAL_PRODUCTION_REVIEW.md
│   └── IMPLEMENTATION_PITFALLS_GUIDE.md   # NEW
├── pyproject.toml
├── Makefile
├── README.md
└── LICENSE
```

### pyproject.toml Configuration

> **Note:** The authoritative `pyproject.toml` is the file in the repo root. This example is illustrative only.

```toml
[project]
name = "chopper"
version = "0.1.0"
description = "EDA TFM Trimming Tool"
requires-python = ">=3.9"
dependencies = [
    "structlog>=24.1.0",
    "jsonschema>=4.0",
]

[project.optional-dependencies]
rich = [
    "rich>=13.0",
]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "hypothesis>=6.0",
    "mypy>=1.0",
    "ruff>=0.4",
]

[project.scripts]
chopper = "chopper.cli.main:main"

[tool.ruff]
line-length = 120
target-version = "py39"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```

---

## Sprint Planning

### Stage 1: Foundation Modules (Day 0–1)
**Goal:** Parser complete + core models + schema loading

**Tasks:**
- [ ] Set up repository + pyproject.toml
- [ ] Implement core/models.py (all dataclasses + enums)
- [ ] Implement core/errors.py (error hierarchy)
- [ ] Implement parser/tcl_parser.py with all 15 test fixtures
- [ ] Implement config/loaders.py (JSON schema validation)
- [ ] Verify parser passes all fixtures using bulk string operations (`str.find`)

**Acceptance Criteria:**
- [ ] All parser fixtures pass (see tests/FIXTURE_CATALOG.md for all 15)
- [ ] Parser runs on domain with 60+ Tcl files (pytest-benchmark test in large_domain_60_files fixture)
- [ ] Core models can be instantiated + serialized to JSON
- [ ] Schema validation rejects invalid JSON

---

### Stage 2: Compiler (Day 2)
**Goal:** Compilation pipeline + trace expansion

**Tasks:**
- [ ] Implement compiler/compiler.py (7-phase algorithm)
- [ ] Implement compiler/tracer.py (fixed-point trace expansion)
- [ ] Implement compiler/manifest.py (CompiledManifest serialization)
- [ ] Add unit tests for glob expansion, proc collection, trace ordering
- [ ] Verify determinism: same input → identical output

**Acceptance Criteria:**
- [ ] Compiler produces deterministic output
- [ ] Trace expansion handles ambiguous calls (logs WARNING, doesn't crash)
- [ ] Include-wins rule enforced (exclude cannot remove include)
- [ ] Feature ordering respected

---

### Stage 3: Trimming & Recovery (Day 3)
**Goal:** State machine + live file trimming

**Tasks:**
- [ ] Implement trimmer/lifecycle.py (5 domain states + transitions)
- [ ] Implement trimmer/lock.py (advisory locking with stale detection)
- [ ] Implement trimmer/trimmer.py (file & proc extraction)
- [ ] Add integration tests for state transitions + crash recovery
- [ ] Test re-trim scenario (crash mid-write, then re-run)

**Acceptance Criteria:**
- [ ] All state transitions atomic or safe-to-rerun
- [ ] Advisory lock correctly detects stale locks
- [ ] Proc trimming preserves surrounding context
- [ ] **H-16 — Crash recovery criteria (explicit):** For each of the 5 state transitions (TRANSITION_POINTS in `tests/integration/crash_harness.py`) inject a crash using `@inject_crash_at()` / `CrashAt`. Assert: (a) `assert_domain_recoverable()` passes — either `domain/` or `domain_backup/` is present; (b) re-running `chopper trim` with same selection completes without error; (c) resulting output matches a clean trim. All 5 transition crash tests must pass.
- [ ] **H-15 — Re-trim idempotency (Integration Scenario 22):** Run trim twice on identical inputs. Assert `compiled_manifest.json` hash (excluding `timestamp` and `run_id`) is identical across both runs. Assert trimmed file contents are byte-for-byte identical.

---

### Stage 4: Validation & Services (Day 4)
**Goal:** Cross-validation + service layer + audit + project JSON support

**Tasks:**
- [ ] Implement validator/validator.py (JSON reference checks, proc existence, etc.)
- [ ] Implement V-13 (project JSON mutual exclusivity), V-14 (project JSON schema), V-15 (project JSON path resolution)
- [ ] Implement service layer (ScanService, ValidateService, TrimService, CleanupService)
- [ ] Implement `TrimRequest` project fields (`project_json`, `project_name`, `project_owner`, `release_branch`, `project_notes`) — TECHNICAL_REQUIREMENTS.md §5.3
- [ ] Implement project metadata passthrough to `RunSelection`, `CompiledManifest`, `chopper_run.json`
- [ ] Implement audit/audit.py (artifact generation + trace report)
- [ ] Implement core/diagnostics.py (diagnostic collection + formatting)
- [ ] Add integration tests for full workflow (scan → validate → trim → cleanup)
- [ ] Add integration tests for project JSON mode (validate, trim, dry-run, mutual exclusivity check)

**Acceptance Criteria:**
- [ ] All JSON references validated before compilation
- [ ] V-13, V-14, V-15 pass for valid project JSON; fail with correct diagnostics for invalid
- [ ] Service protocol contracts satisfied
- [ ] `TrimRequest` project fields round-trip through service layer to audit artifacts
- [ ] Audit artifacts deterministic + reproducible
- [ ] Full workflow end-to-end passes (both CLI mode and project JSON mode)

---

### Stage 5: CLI & Polish (Day 5+)
**Goal:** Command-line interface + output rendering + project JSON CLI + end-to-end tests

**Tasks:**
- [ ] Implement cli/main.py (argparse + entry point + mutual exclusivity group for `--project` vs `--base`/`--features`)
- [ ] Implement cli/commands.py (scan, validate, trim, cleanup subcommands)
- [ ] Implement project JSON loading in CLI layer: parse project JSON, resolve paths relative to the current working directory / domain root, populate `TrimRequest` project fields
- [ ] Implement project-domain consistency checks: project JSON `domain` must match the current working directory basename, and optional `--domain` must resolve to the same directory
- [ ] Implement `--strict` flag (escalate warnings to errors, change exit code)
- [ ] Implement `--confirm` requirement for `chopper cleanup` (refuse without it)
- [ ] Implement cli/render.py + ui/*.py (output rendering)
- [ ] Add end-to-end integration tests (complex feature combinations + project JSON mode)
- [ ] Performance profiling + optimization

**Acceptance Criteria:**
- [ ] All CLI commands work end-to-end (base-only, base+features, project JSON modes)
- [ ] `--project` vs `--base`/`--features` mutual exclusivity enforced (exit code 2)
- [ ] Project JSON path resolution correct (relative to the current working directory / domain root)
- [ ] Project-domain consistency checks pass and mismatched CLI/project domains are rejected
- [ ] `--strict` flag tested (warnings → errors → exit 1)
- [ ] `--confirm` requirement for cleanup tested (without → exit 2)
- [ ] Help text + error messages user-friendly
- [ ] Output formatting works (--json, --plain, Color, tables)
- [ ] All performance targets met

---

## Code Review Gates

### Parser Module Code Review

Before merge to main:
- [ ] All 15 fixtures pass (see tests/FIXTURE_CATALOG.md)
- [ ] Performance reasonable on test domain (pytest-benchmark)
- [ ] Brace tracking correct (P-01 scenario tested)
- [ ] Line continuation preserves line numbers (P-02 scenario tested)
- [ ] Namespace LIFO stack correct (P-03 scenario tested, B-04 fixture passes)
- [ ] Edge cases P-04 through P-07 all pass
- [ ] Coverage ≥ 85% branch

### Compiler Module Code Review

Before merge to main:
- [ ] Glob expansion normalizes + deduplicates (P-11 scenario)
- [ ] Trace expansion deterministic (P-08 scenario)
- [ ] Include-wins enforced (P-09 scenario)
- [ ] Feature order respected (P-10 scenario)
- [ ] Determinism test: same input produces byte-identical output
- [ ] Coverage ≥ 80% branch

### Core / Config / UI Module Code Review (H-13)

Before merge to main:
- [ ] `core/` coverage ≥ 80% branch
- [ ] `config/loaders.py` coverage ≥ 85% branch
- [ ] `ui/` coverage ≥ 70% line
- [ ] Project-wide CI gate `--cov-fail-under=78` passes

### Trimmer Module Code Review

Before merge to main:
- [ ] All state transitions tested
- [ ] Crash recovery scenarios verified (P-13)
- [ ] Advisory lock behavior correct (P-14: non-blocking, stale detection)
- [ ] Proc trimming preserves context (P-15)
- [ ] No half-written output after failures
- [ ] Coverage >80%

### Validator & Service Layer Review

Before merge to main:
- [ ] All JSON references validated (P-16)
- [ ] V-13 (project JSON mutual exclusivity) implemented and tested
- [ ] V-14 (project JSON schema compliance) implemented and tested
- [ ] V-15 (project JSON path resolution) implemented and tested
- [ ] `--strict` mode escalates warnings to errors correctly
- [ ] Diagnostics include location (P-18)
- [ ] Service contracts honored
- [ ] `TrimRequest` project fields populated correctly from project JSON
- [ ] Project metadata flows to `chopper_run.json` and `compiled_manifest.json`
- [ ] Coverage >75%

### CLI & UI Review

Before merge to main:
- [ ] Dry-run doesn't modify filesystem (P-23)
- [ ] `--project` mutually exclusive with `--base`/`--features` — exit code 2 (P-26)
- [ ] Project JSON path resolution: relative to the current working directory / domain root (P-25)
- [ ] Project-domain consistency checks pass and mismatches are rejected (P-31)
- [ ] `--strict` flag changes exit behavior (P-27)
- [ ] `chopper cleanup` requires `--confirm` — exit code 2 without it (P-28)
- [ ] All commands work end-to-end
- [ ] Help text + error messages clear
- [ ] Coverage >70%

---

## Testing Checklist

### Unit Test Coverage Targets

| Module | Target | Metric | Notes |
|--------|--------|--------|-------|
| parser | ≥ 85% | branch | Parser is critical path |
| compiler | ≥ 80% | branch | Must be deterministic |
| trimmer | ≥ 80% | branch | State machine must be correct |
| validator | ≥ 75% | branch | Cross-validation logic |
| audit | ≥ 75% | branch | Artifact generation |
| core/ | ≥ 80% | branch | Models and error hierarchy (H-13) |
| config/ | ≥ 85% | branch | JSON schema loading (H-13) |
| ui/ | ≥ 70% | line | UI code can be lower (H-13) |
| **Project-wide** | **≥ 78%** | line | CI gate: `--cov-fail-under=78` |

### Integration Test Scenarios (Must Pass)

- [ ] **Scenario 1:** Scan domain → auto-generate draft_base.json
- [ ] **Scenario 2:** Validate `jsons/base.json` against domain (must catch missing procs)
- [ ] **Scenario 3:** Trim with F1 only (whole-file trimming)
- [ ] **Scenario 4:** Trim with F2 only (proc-level trimming)
- [ ] **Scenario 5:** Trim with F1 + F2 (mixed)
- [ ] **Scenario 6:** Trim with feature + base where base includes proc, feature excludes it (include wins)
- [ ] **Scenario 7:** Multi-feature trim (Feature A + B with flow actions)
- [ ] **Scenario 8:** Crash mid-trim on domain A, re-run recovers cleanly
- [ ] **Scenario 9:** Concurrent trim on different domains (locks work)
- [ ] **Scenario 10:** Cleanup removes backup + succeeds (with `--confirm`)
- [ ] **Scenario 11:** Trim using `--project <user-supplied-project.json>` — same result as equivalent `--base`/`--features`
- [ ] **Scenario 12:** Validate using `--project <user-supplied-project.json>` — Phase 1 checks pass for all referenced JSONs
- [ ] **Scenario 13:** `--project` + `--base` combined — exit code 2 (mutual exclusivity)
- [ ] **Scenario 14:** Dry-run with `--project` — no files modified, audit metadata includes project fields
- [ ] **Scenario 15:** Project JSON with invalid base path — diagnostic V-15 emitted, exit code 1
- [ ] **Scenario 16:** Cleanup without `--confirm` — exit code 2, backup untouched
- [ ] **Scenario 17:** Trim with `--strict` and V-04 duplicate file entry — exit code 1 (warning escalated)
- [ ] **Scenario 18:** Hook files discovered via `-use_hooks` but NOT in `files.include` — excluded from trim
- [ ] **Scenario 19:** Hook files discovered via `-use_hooks` AND in `files.include` — included in trim
- [ ] **Scenario 20:** Base-only trim (no features) — produces valid output with F1/F2/F3 as applicable
- [ ] **Scenario 21:** Cleanup on already-cleaned domain — exit code 0 with informational diagnostic, no filesystem changes
- [ ] **Scenario 22 (H-15 — Re-trim idempotency):** Run trim twice with identical `--base`/`--features`. Assert `compiled_manifest.json` content hash (excluding `timestamp` and `run_id`) is identical; assert trimmed file contents byte-for-byte identical.

### Regression Tests (Golden Outputs)

- [ ] Parser fixture: brace_in_string_literal → expected unbalanced-brace diagnostic
- [ ] Parser fixture: namespace_nesting → expected canonical names
- [ ] Parser fixture: comment_with_braces → expected proc boundaries
- [ ] Compiler: glob expansion + deduplication → expected file list
- [ ] Compiler: trace expansion → expected proc dependency graph
- [ ] Trimmer: proc removal → expected trimmed output (no context loss)
- [ ] End-to-end: full domain trim → expected manifest.json

---

## Release Gates

### Before v0.1.0 Alpha

- [ ] All unit tests pass (coverage ≥ 78% project-wide; see per-module targets above)
- [ ] All integration tests pass
- [ ] No CRITICAL severity bugs open
- [ ] Documentation complete (README, CLI help, examples)
- [ ] Performance acceptable for interactive use

### Before v0.2.0 Beta

- [ ] All MEDIUM severity bugs fixed
- [ ] Performance optimized (>10% improvement from alpha)
- [ ] Stress tests pass (large domains, 100+ features)
- [ ] Cross-platform testing (Windows, Linux, macOS)
- [ ] Security review completed

### Before v1.0.0 Release

- [ ] All known bugs fixed
- [ ] Production deployments (3+ customer projects trimmed successfully)
- [ ] Audit trail audit (verify reproducibility across re-trims)
- [ ] Operational runbook + troubleshooting guide
- [ ] GA support commitment

---

## Team Communication

### Daily Stand-Up

**When:** 10 AM daily (during the implementation window)  
**Duration:** 15 minutes  
**Topics:**
- What did you complete yesterday?
- What's blocking you?
- What's the plan for today?

### Weekly Technical Sync

**When:** Tuesday 2 PM (ongoing)  
**Duration:** 30–45 minutes  
**Topics:**
- Sprint progress vs. plan
- Risk mitigation (performance, bugs, dependencies)
- Architecture questions + decisions
- Code review feedback

### Code Review

**Standard:** All PRs reviewed by at least 1 other engineer before merge  
**Focus Areas:** (per module code review gates above)  
**Turnaround:** <24 hours

---

## Success Criteria

### Functionality

- [ ] All four subcommands work (scan, validate, trim, cleanup)
- [ ] Parser handles all edge cases (15 fixtures)
- [ ] Compiler produces deterministic output
- [ ] Trimmer recovers from crashes
- [ ] Validation catches errors before live trim
- [ ] FR-35: Project JSON accepted as input (all subcommands)
- [ ] FR-36: `--project` mutually exclusive with `--base`/`--features`
- [ ] `--strict` flag escalates warnings to errors
- [ ] `--confirm` required for irreversible cleanup
- [ ] Hook discovery populated in scan but hooks only copied when in `files.include`
- [ ] Project metadata flows to audit artifacts (`chopper_run.json`, `compiled_manifest.json`)

### Quality

- [ ] Unit test coverage >80% overall
- [ ] No CRITICAL bugs in production
- [ ] Performance reasonable for typical 60-file domain
- [ ] Cross-platform (Windows, Linux, macOS)

### Usability

- [ ] CLI help text is clear
- [ ] Error messages are actionable
- [ ] Dry-run allows safe preview
- [ ] Audit trail enables reproducibility

### Documentation

- [ ] README + installation instructions
- [ ] CLI reference (all options documented)
- [ ] Example workflows (scan → validate → trim)
- [ ] Troubleshooting guide
- [ ] Operational runbook (advisory locks, crash recovery, etc.)

---

## Risk Mitigation

### High Priority

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Parser correctness | MEDIUM | Test all 15 fixtures at the start of Stage 1 |
| Trace non-determinism | LOW | Implement determinism tests + sorting in Stage 2 |
| Audit corruption in crash | MEDIUM | Test all state transitions + recovery in Stage 3 |

### Medium Priority

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Performance regression | MEDIUM | Profile parser + compiler early, set targets in Stage 1 |
| Lock cleanup breaks concurrency | LOW | Real concurrency tests in Stage 3 |
| Cross-domain refs break assumption | LOW | Audit trail shows references; warn owner in Stage 4 |

---

## Contact & Escalation

**Project Lead:** [TBD]  
**Technical Lead:** [TBD]  
**Parser Owner:** [TBD]  
**Compiler Owner:** [TBD]  

**Escalation Path:**
- Technical issues → Technical Lead (24h response)
- Architecture questions → Project Lead (by EOD)
- Blocker bugs → Project Lead (immediate)

---

## Sign-Off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Architecture Lead | | | Approved architecture & decisions |
| Engineering Manager | | | Approved team + staffing |
| Project Lead | | | Approved schedule + scope |
| QA Lead | | | Approved test strategy |

---

**Handoff Status:** ✅ PRODUCTION-READY — MULTI-AGENT REVIEW COMPLETE  
**Review Date:** April 5, 2026  
**Review Method:** 5-perspective multi-agent review (Parser, Compiler/Tracer, Trimmer/Lifecycle, Validator/CLI, Project Structure)  
**Verdict:** GO — All specs aligned, no blockers, all fixtures ready  
**Next Milestone:** Day 0 — Foundation Scaffolding (create module directories + core models)
