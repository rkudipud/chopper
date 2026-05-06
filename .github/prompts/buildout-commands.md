# Chopper Buildout Command Center

This document provides activation prompts for the Chopper buildout agents.

---

## Agent Roster

| Agent | Purpose | Use For |
| --- | --- | --- |
| **Chopper Buildout Agent** | Master orchestrator | Planning, milestone tracking, drift detection, milestone sign-off (internalizes principal-engineer / SWE / devil's advocate / beast-mode personas) |
| **Chopper Stage Builder** | Implementation agent | Actual code writing, test-first development (same internalized personas) |
| **Chopper Agent** | User-facing companion | Domain analysis, JSON authoring, audit interpretation, bug/enhancement filing |

> Personas — **Principal Engineer**, **Senior SWE**, **Devil's Advocate**, **Beast Mode** — are internalized inside each agent; there are no separate persona agents to invoke.

---

## Activation Prompts

### Start Fresh Buildout

```text
@workspace /chopper-buildout

Begin Chopper Stage 0 implementation.

1. Read `.github/agent_memory/chopper-buildout.md` if present; otherwise create it from `.github/agent_memory/README.md`
2. Read technical_docs/ARCHITECTURE.md §5.12 and §8.1
3. Create todo list for Stage 0 (core/ module)
4. Implement frozen dataclasses per ENGINEERING.md §9.1
5. Run `make check` after each file
6. Update `.github/agent_memory/chopper-buildout.md`

Quality gates:
- 85% coverage for core/
- mypy --strict clean
- All models JSON round-trip deterministically
```

### Continue From Last Session

```text
@workspace /chopper-buildout

Resume Chopper buildout.

1. Read `.github/agent_memory/chopper-buildout.md`
2. Identify last completed milestone
3. Continue from next incomplete stage
4. Do not stop until current stage complete
```

### Stage-Specific Implementation

```text
@workspace /chopper-stage-builder

Implement Stage [N]: [module name]

Architecture Doc reference: technical_docs/ARCHITECTURE.md §[X.X]

Pre-implementation:
1. Ensure `.github/agent_memory/chopper-stage-builder.md` exists; if missing, create it from `.github/agent_memory/README.md`
2. Read architecture doc section and quote requirements
3. Check DIAGNOSTIC_CODES.md for needed codes
4. Check IMPLEMENTATION.md (pitfalls) for pitfalls P-XX

Implementation:
1. Write test skeleton FIRST
2. Implement core logic incrementally
3. Run tests after each function
4. `make check` before commit

Post-implementation:
1. Verify coverage >= [threshold]%
2. Run drift detection checklist
3. Update `.github/agent_memory/chopper-stage-builder.md`
```

### Milestone Quality Review

The milestone review is part of the Chopper Buildout Agent's own duties (devil's-advocate persona) — there is no separate review agent.

```text
@workspace /chopper-buildout

Milestone review for Stage [N].

1. Verify all code traces to architecture doc sections
2. Check for scope-lock violations
3. Identify any over-engineering
4. Verify diagnostic codes match registry
5. Stress-test edge cases (devil's-advocate pass)
6. Sign off or block with specific issues
```

---

## Stage Implementation Order

```text
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: core/     →  Stage 1: parser/   →  Stage 2: compiler/ │
│  (Foundation)          (Tcl Analysis)         (Merge + Trace)   │
│                                                                  │
│  Stage 3: trimmer/  →  Stage 4: validator/ →  Stage 5: cli/     │
│  (Trim + Audit)        (Pre/Post Checks)      (User Interface)  │
└─────────────────────────────────────────────────────────────────┘
```

### Stage Dependencies

- Stage 1 depends on Stage 0 (uses the phase-owned `core/models_*.py` definitions)
- Stage 2 depends on Stage 0, Stage 1 (uses models + parser output)
- Stage 3 depends on Stage 0, Stage 2 (uses models + compiled manifest)
- Stage 4 depends on Stage 0, Stage 1, Stage 3 (uses models + parser + trimmer)
- Stage 5 depends on ALL previous stages

**Rule:** Never start Stage N+1 until Stage N passes its quality gate.

---

## Quality Gate Commands

### Fast Check (Before Commit)

```bash
make check   # Lint + format + types + unit tests
```

### Full CI (Before Milestone)

```bash
make ci      # All quality + all test suites
```

### Coverage Check

```bash
# Per-stage coverage
pytest tests/unit/core/ --cov=src/chopper/core --cov-fail-under=85
pytest tests/unit/parser/ --cov=src/chopper/parser --cov-fail-under=85
pytest tests/unit/compiler/ --cov=src/chopper/compiler --cov-fail-under=80
pytest tests/unit/trimmer/ --cov=src/chopper/trimmer --cov-fail-under=80
```

### Golden File Test

```bash
pytest tests/golden/ -v
git diff tests/golden/  # Must show NO changes
```

---

## Document Quick Reference

| Document | Purpose | Check For |
| --- | --- | --- |
| `technical_docs/ARCHITECTURE.md` | **THE ARCHITECTURE DOC** | Requirements, FR-xx, §x.x |
| `technical_docs/ENGINEERING.md` | How to build | Module structure, §9.x models |
| `technical_docs/IMPLEMENTATION.md` (parser section) | Parser rules | State machine, §1.3.0 |
| `technical_docs/DIAGNOSTIC_CODES.md` | Error codes | VE-xx, VW-xx, PE-xx, etc. |
| `technical_docs/IMPLEMENTATION.md` (pitfalls) | Gotchas | P-xx pitfalls, TC-xx risks |
| `technical_docs/IMPLEMENTATION_ROADMAP.md` | Build order | M1-M6 milestones |
| `technical_docs/FINAL_HANDOFF_REVIEW.md` | Sign-off status | Critical findings, fixes |

---

## Drift Detection Checklist

Run this after EVERY implementation:

```markdown
## Drift Detection

### Scope Check
- [ ] No forbidden concepts (LockPort, scan, plugins, MCP, advisor)
- [ ] No reserved seams or future hooks
- [ ] No abstract factories without spec requirement
- [ ] No "helper" classes beyond spec

### Spec Alignment
- [ ] Every public function traces to architecture doc §x.x
- [ ] Diagnostic codes exist in DIAGNOSTIC_CODES.md
- [ ] Exit codes follow architecture doc §5.10
- [ ] File treatments match architecture doc §4 vocabulary

### Test Alignment
- [ ] Tests verify spec behavior, not implementation
- [ ] Edge cases from IMPLEMENTATION.md (pitfalls) covered
- [ ] Golden files test determinism, not specific values
```

---

## Emergency Protocols

### If Stuck

```text
1. STOP coding
2. Re-read the architecture doc section
3. Check IMPLEMENTATION.md (pitfalls) for relevant pitfall
4. Check ENGINEERING.md for structural guidance
5. If still stuck: ask user for clarification
```

### If Tests Fail

```text
1. Read failure message carefully
2. Check if spec misunderstanding (re-read architecture doc)
3. Check if edge case (look in pitfalls)
4. Fix ROOT CAUSE, not symptom
5. Re-run FULL test suite
```

### If Drift Detected

```text
1. STOP immediately
2. Identify what was added beyond spec
3. DELETE the extra code
4. Re-verify against architecture doc §x.x
5. Continue only after drift resolved
```

---

## Local Memory File Workflow

### Session Start

1. Ensure `.github/agent_memory/` exists.
2. Use `.github/agent_memory/chopper-buildout.md` for the buildout agent.
3. If the file is missing, create it from `.github/agent_memory/README.md`.
4. Read it before planning or implementation.

### After Milestone

1. Update the same file with what completed.
2. Record the next concrete action.
3. Record the validation result and any blockers.

---

## Success Definition

**Buildout is COMPLETE when:**

1. All 6 stages implemented (core → parser → compiler → trimmer → validator → cli)
2. `make ci` passes consistently
3. All 25 active integration scenarios pass
4. `fev_formality_real` acceptance trim succeeds
5. Coverage thresholds met (parser 85%, compiler 80%, trimmer 80%, overall 78%)
6. Zero drift from spec
7. Devil's-advocate review (run by Chopper Buildout Agent itself) signs off

---

**Begin with:** `@workspace /chopper-buildout` and state which stage to implement.
