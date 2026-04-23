# Chopper v2 Buildout Command Center

This document provides activation prompts for the Chopper v2 buildout agents.

---

## Agent Roster

| Agent | Purpose | Use For |
|-------|---------|---------|
| **Chopper Buildout Agent** | Master orchestrator | Planning, milestone tracking, drift detection |
| **Chopper Stage Builder** | Implementation agent | Actual code writing, test-first development |
| **Devils Advocate** | Quality challenger | Final review before milestone sign-off |

---

## Activation Prompts

### Start Fresh Buildout

```
@workspace /chopper-buildout

Begin Chopper v2 Stage 0 implementation.

1. Query Memory Palace for current state
2. Read technical_docs/chopper_description.md §5.12 and §8.1
3. Create todo list for Stage 0 (core/ module)
4. Implement frozen dataclasses per ARCHITECTURE_PLAN.md §9.1
5. Run `make check` after each file
6. Log progress to Memory Palace

Quality gates:
- 85% coverage for core/
- mypy --strict clean
- All models JSON round-trip deterministically
```

### Continue From Last Session

```
@workspace /chopper-buildout

Resume Chopper v2 buildout.

1. Query Memory Palace: mempalace_kg_query("chopper_v2 current focus")
2. Identify last completed milestone
3. Continue from next incomplete stage
4. Do not stop until current stage complete
```

### Stage-Specific Implementation

```
@workspace /chopper-stage-builder

Implement Stage [N]: [module name]

Bible reference: technical_docs/chopper_description.md §[X.X]

Pre-implementation:
1. Read bible section and quote requirements
2. Check DIAGNOSTIC_CODES.md for needed codes
3. Check RISKS_AND_PITFALLS.md for pitfalls P-XX

Implementation:
1. Write test skeleton FIRST
2. Implement core logic incrementally
3. Run tests after each function
4. `make check` before commit

Post-implementation:
1. Verify coverage >= [threshold]%
2. Run drift detection checklist
3. Update Memory Palace
```

### Milestone Quality Review

```
@workspace /devils-advocate

Review Stage [N] implementation for Chopper v2.

1. Verify all code traces to bible sections
2. Check for scope-lock violations
3. Identify any over-engineering
4. Verify diagnostic codes match registry
5. Stress-test edge cases
6. Sign off or block with specific issues
```

---

## Stage Implementation Order

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: core/     →  Stage 1: parser/   →  Stage 2: compiler/ │
│  (Foundation)          (Tcl Analysis)         (Merge + Trace)   │
│                                                                  │
│  Stage 3: trimmer/  →  Stage 4: validator/ →  Stage 5: cli/     │
│  (Trim + Audit)        (Pre/Post Checks)      (User Interface)  │
└─────────────────────────────────────────────────────────────────┘
```

### Stage Dependencies

- Stage 1 depends on Stage 0 (uses `core/models.py`)
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
|----------|---------|-----------|
| `technical_docs/chopper_description.md` | **THE BIBLE** | Requirements, FR-xx, §x.x |
| `technical_docs/ARCHITECTURE_PLAN.md` | How to build | Module structure, §9.x models |
| `technical_docs/TCL_PARSER_SPEC.md` | Parser rules | State machine, §3.0 |
| `technical_docs/DIAGNOSTIC_CODES.md` | Error codes | VE-xx, VW-xx, PE-xx, etc. |
| `technical_docs/RISKS_AND_PITFALLS.md` | Gotchas | P-xx pitfalls, TC-xx risks |
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
- [ ] Every public function traces to bible §x.x
- [ ] Diagnostic codes exist in DIAGNOSTIC_CODES.md
- [ ] Exit codes follow bible §5.10
- [ ] File treatments match bible §4 vocabulary

### Test Alignment
- [ ] Tests verify spec behavior, not implementation
- [ ] Edge cases from RISKS_AND_PITFALLS.md covered
- [ ] Golden files test determinism, not specific values
```

---

## Emergency Protocols

### If Stuck

```
1. STOP coding
2. Re-read the bible section
3. Check RISKS_AND_PITFALLS.md for relevant pitfall
4. Check ARCHITECTURE_PLAN.md for structural guidance
5. If still stuck: ask user for clarification
```

### If Tests Fail

```
1. Read failure message carefully
2. Check if spec misunderstanding (re-read bible)
3. Check if edge case (look in pitfalls)
4. Fix ROOT CAUSE, not symptom
5. Re-run FULL test suite
```

### If Drift Detected

```
1. STOP immediately
2. Identify what was added beyond spec
3. DELETE the extra code
4. Re-verify against bible §x.x
5. Continue only after drift resolved
```

---

## Memory Palace Integration

### Session Start

```python
mempalace_status()
mempalace_kg_query("chopper_v2 active-context")
mempalace_kg_timeline(limit=5)
```

### After Milestone

```python
mempalace_diary_write(
    agent_name="Chopper Buildout Agent",
    topic="milestone",
    entry="STAGE:0|core.complete+all.gates.pass|⭐⭐⭐"
)
mempalace_kg_add(
    entity="chopper-stage-0-complete",
    fact="Core models implemented. Coverage 87%. All quality gates pass.",
    timestamp="2026-04-22"
)
```

---

## Success Definition

**Buildout is COMPLETE when:**

1. All 6 stages implemented (core → parser → compiler → trimmer → validator → cli)
2. `make ci` passes consistently
3. All 25 active integration scenarios pass
4. `fev_formality_real` acceptance trim succeeds
5. Coverage thresholds met (parser 85%, compiler 80%, trimmer 80%, overall 78%)
6. Zero drift from spec
7. Devils Advocate sign-off obtained

---

**Begin with:** `@workspace /chopper-buildout` and state which stage to implement.
