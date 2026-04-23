# Final Handoff Review: Chopper v2

**Date:** April 22, 2026
**Reviewer:** GitHub Copilot (Claude Opus 4.5), devil's-advocate review pass
**Review Type:** End-to-end technical review with compiler/Tcl expertise

---

## Executive Summary

After comprehensive analysis of all documentation, schemas, and project architecture, I sign off on the documentation readiness for agent buildout with **one critical fix applied** and **one design clarification required**.

**Overall Verdict:** APPROVED FOR BUILDOUT

---

## Scope of Review

This review covered:

- Product bible (`chopper_description.md`) and all subordinate architecture docs
- Implementation roadmap and testing strategy
- `json_kit/` schemas (base-v1, feature-v1, project-v1) and authoring guide
- TCL Parser Specification and RISKS_AND_PITFALLS.md
- Diagnostic codes registry (68 active codes across 6 families)
- Current `src/chopper/` implementation state (scaffold only)

---

## Critical Findings

### Finding 1: VW-10 vs VW-19 Code Mismatch (FIXED)

**Severity:** Critical (would cause documentation-implementation mismatch)

**Location:** `json_kit/schemas/feature-v1.schema.json` line 110

**Problem:** The schema referenced `VW-10 cross-source-fe-vetoed` but:
- `DIAGNOSTIC_CODES.md` shows VW-10 as **reserved**
- The actual code for `cross-source-fe-vetoed` is **VW-19**
- The revision history mentioned VW-10 was "un-retired" but the registry renumbering later changed this (this inconsistency is **closed** — the registry in `technical_docs/DIAGNOSTIC_CODES.md` is now the sole source of truth; the revision-history wording was a transient artifact of the renumbering sweep).

**Resolution:** Fixed in this review pass. The feature schema now correctly references VW-18 only for `procedures.exclude` (which is semantically correct — VW-19 applies to `files.exclude`, not `procedures.exclude`).

### Finding 2: procEntry.procs minItems:1 vs Spec Tolerance (FIXED)

**Severity:** Minor (schema stricter than spec)

**Location:** 
- `json_kit/schemas/base-v1.schema.json` line 123: `"minItems": 1` on `procEntry.procs`
- `chopper_description.md` line 447: Originally said empty procs in exclude was "silent no-op"

**Problem:** The spec previously said empty `procs` arrays in `procedures.exclude` should be tolerated as "silent no-op", but the schema enforces `minItems: 1` for both include and exclude.

**Resolution:** Fixed in this review pass. The spec now aligns with the schema — an empty procs array fires `VE-03` for both include and exclude. Rationale: empty procs is almost certainly an authoring error, and catching it at schema/validation time is helpful feedback. The diagnostic registry was also updated to reflect this unified behavior.

---

## Architecture Assessment

### 8-Phase Pipeline (P0-P7): SOUND

The pipeline architecture is well-designed:
- Clear separation of concerns between phases
- Deterministic execution order
- Phase gates prevent corrupted data from propagating
- `--dry-run` properly skips P5 writes while still running validation

### R1 Merge Algorithm (L1/L2/L3): SOUND

The provenance-aware cross-source aggregation is correctly specified:
- L1 (explicit include wins cross-source)
- L2 (same-source authoring conveniences)  
- L3 (base inviolable, features additive-only)

This is the correct design for a safety-critical trimming tool.

### Trace Is Reporting-Only: CRITICAL INVARIANT VERIFIED

The "trace is reporting-only" invariant is consistently documented:
- PI+ never adds to surviving sets
- Traced callees appear in `dependency_graph.json` only
- This is enforced by frozen `CompiledManifest` design

### Parser Spec: COMPREHENSIVE

The TCL parser spec (TCL_PARSER_SPEC.md) is thorough:
- State machine transitions documented (§3.0)
- Brace/quote context rules correct (Rule 6 handling)
- Namespace stack semantics specified
- 37 pitfalls documented with test fixtures

---

## Schema Assessment

### base-v1.schema.json: SOUND

- Correct `anyOf` constraint requiring at least one of files/procedures/stages
- Proper path patterns preventing `..` traversal
- Stage definition fields map correctly to stack file semantics

### feature-v1.schema.json: FIXED

- VW-10 reference corrected (see Finding 1)
- `flow_actions` vocabulary complete (add/remove/replace for steps and stages)
- `depends_on` uses feature names, not paths (correct)

### project-v1.schema.json: SOUND

- Required fields correct: `$schema`, `project`, `domain`, `base`
- Feature ordering documented as F3-authoritative only

---

## Testing Strategy Assessment

### Coverage Targets: APPROPRIATE

| Module | Target | Assessment |
|--------|--------|------------|
| parser | ≥ 85% branch | High bar appropriate for highest-risk module |
| compiler | ≥ 80% branch | Appropriate |
| trimmer | ≥ 80% branch | Appropriate |
| overall | ≥ 78% line | Reasonable floor |

### Named Scenarios: 25 ACTIVE VERIFIED

- Scenarios 1-4: Active (domain lifecycle)
- Scenarios 5-9: Deferred (crash injection)
- Scenarios 10-28 (including 11a, 11b, 11c): Active (validation, additive model, F3)

Count is correct: 25 active scenarios.

---

## Diagnostic Code Registry Assessment

### Code Space: WELL-ORGANIZED

| Family | Active | Reserved | Assessment |
|--------|--------|----------|------------|
| VE (Validation Errors) | 26 | 4 | Sufficient capacity |
| VW (Validation Warnings) | 18 | 2 | Appropriate |
| TW (Trace Warnings) | 4 | 6 | Good expansion room |
| PE (Parse Errors) | 3 | 7 | Good expansion room |
| PW (Parse Warnings) | 11 | 9 | Appropriate |
| PI (Parse Info) | 4 | 6 | Appropriate |

### Exit Code Policy: CORRECT

- Exit 0: No errors (optionally no warnings with `--strict`)
- Exit 1: Validation/parse failure or `--strict` with warnings
- Exit 2: CLI/pre-pipeline fatal (missing domain, conflicting options)
- Exit 3: Programmer error (internal exception)

---

## Risk Assessment

### High-Risk Areas for Implementation

1. **Tcl Parser (TC-01, TC-02):** Pitfalls P-01 through P-36 must be addressed
2. **Namespace Resolution:** LIFO stack semantics critical
3. **Brace Tracking:** In-body rule (§3.3.2) is the most common failure mode
4. **DPA Block Handling:** Must drop atomically with proc (P-33)

### Mitigations Already In Place

- 17 edge-case fixtures specified for parser
- Golden file tests for output contracts
- Property-based tests with Hypothesis
- Stage-gate DoD requirements

---

## Sign-Off Boundary

### SIGNED OFF FOR:

- Documentation completeness for agent buildout
- 8-phase pipeline architecture
- JSON schema contracts (after VW-10 fix)
- Diagnostic code registry
- Testing strategy and named scenarios
- Stage 0-5 build order

### NOT SIGNED OFF FOR:

- Any executable runtime (no implementation exists yet)
- Any claim that `chopper` command is runnable
- Any packaging or distribution claims

---

## Recommendations for Buildout Agents

### Stage 0 (core/) Priority

1. Implement frozen dataclasses exactly as specified in ARCHITECTURE_PLAN.md §9.1
2. Implement diagnostic registry guard that validates codes against DIAGNOSTIC_CODES.md
3. Ensure `dump_model()`/`load_model()` round-trips are deterministic

### Stage 1 (parser/) Priority

1. Implement state machine per TCL_PARSER_SPEC.md §3.0
2. Address P-01 (quote context in braces) FIRST — most common failure
3. Test against all 17 edge-case fixtures before moving on
4. Golden-test `ProcEntry` output for determinism

### Stage 2 (compiler/) Priority

1. Implement R1 L1/L2/L3 as a two-pass algorithm
2. Pass 1: Per-source contribution classification
3. Pass 2: Cross-source aggregation
4. Golden-test `compiled_manifest.json` for byte stability

---

## Minimum Gate Before Buildout

1. **Keep the package surface honest:** Do not advertise a live CLI until the CLI module exists
2. **Keep the JSON contract honest:** If a field or filename convention changes in `json_kit/`, cascade it through the bible and all subordinate docs in the same pass
3. **Land implementation vertically, not horizontally:** First milestone should prove one real slice: config load, one parser path, one compile path, and one deterministic test fixture

---

## Final Sign-Off

**Sign-off is granted** for agent-based buildout of the tool per Stage 0-5 sequence.

**Sign-off is not granted** for shipping, packaging, or claiming an implemented runtime.

---

## Revision History

| Date | Reviewer | Summary |
|------|----------|---------|
| 2026-04-22 | GitHub Copilot (Claude Opus 4.5) | Initial devil's advocate review. Fixed VW-10→VW-18 in feature schema. Fixed procEntry.procs minItems conflict (spec→schema alignment, VE-03 now fires for both include and exclude). Sign-off granted for buildout. |
