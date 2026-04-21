# Chopper v2 - D0 QA Review Worksheet

This is a question-and-answer review worksheet for D0 findings.
Use each item block to review, approve/reject, and add your suggestion next to the proposed fix.

## Review Metadata

- Date: 2026-04-21
- Reviewer stance: Principal-level Python/compiler/Tcl reviewer with devil's-advocate posture
- Overall status at time of review: Architecture approved, conditional sign-off pending required clarifications

## Priority Legend

- P0: Must fix before Stage 0/Stage 1 handoff
- P1: Strongly recommended before implementation deepens
- P2: Important hardening, can run in parallel with coding

## How to Use This Worksheet

For each QA item below:

1. Read the question and context.
2. Review the proposed fix.
3. Fill Your Decision and Your Suggestion.
4. Mark status.

Status options:

- OPEN
- ACCEPTED
- MODIFIED
- REJECTED
- DONE

---

## QA-01 (F1) - ProcEntry model completeness

- Priority: P0
- Area: Core model contract
- Target file(s): docs/ARCHITECTURE_PLAN.md

Question:
Should the ProcEntry model contract explicitly include DPA/comment span fields required for parser/trimmer atomic drop behavior?

Issue found:
ProcEntry model catalog in architecture docs does not explicitly include DPA/comment span fields required by parser/trimmer atomic drop behavior.

Proposed fix:
Add fields to ProcEntry:
- dpa_start_line
- dpa_end_line
- comment_start_line
- comment_end_line

All fields should be optional integers with explicit semantics.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-02 (F2) - RunResult early-abort typing

- Priority: P0
- Area: Runner typing contract
- Target file(s): docs/ARCHITECTURE_PLAN.md

Question:
Should the run-result contract explicitly allow manifest/graph to be absent on early abort paths?

Issue found:
Runner abort paths can return before manifest/graph exist, but run-result model text reads like both are always present.

Proposed fix:
Update run-result contract to allow manifest and graph to be optional until produced.
Document renderer behavior for early-abort outputs.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-03 (F3) - Canonical path normalization ownership

- Priority: P0
- Area: Parser canonical naming boundary
- Target file(s): docs/ARCHITECTURE_PLAN.md

Question:
Should the service boundary explicitly state who performs path normalization for canonical names?

Issue found:
Canonical path normalization responsibility is split across docs and can be misimplemented by agents.

Proposed fix:
Add one explicit sentence that ParserService normalizes incoming file paths to domain-relative POSIX before parse_file(), and canonical prefixes are always domain-relative POSIX.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-04 (F4) - copy_tree contract for .chopper exclusion

- Priority: P0
- Area: Filesystem copy semantics
- Target file(s): docs/ARCHITECTURE_PLAN.md, adapter test specs

Question:
Should adapter copy semantics explicitly forbid copying .chopper from backup into rebuilt domain?

Issue found:
.chopper exclusion is specified in product docs but not pinned as an adapter-level copy contract.

Proposed fix:
Specify that copy_tree() must never copy .chopper from backup into rebuilt domain.
Add unit tests for local and in-memory FS adapters.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-05 (F5) - Trimmer deletion order requirement

- Priority: P0
- Area: Trimmer deletion correctness
- Target file(s): docs/IMPLEMENTATION_ROADMAP.md

Question:
Should bottom-up line-range deletion be explicitly mandated in roadmap guidance?

Issue found:
Bottom-up deletion order is implied but not stated as mandatory in roadmap-level implementation guidance.

Proposed fix:
Add explicit requirement: apply proc drop ranges in descending line order to preserve parser span validity.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-06 (F6) - Stage 1 real-domain gate

- Priority: P0
- Area: Stage exit gate realism
- Target file(s): docs/IMPLEMENTATION_ROADMAP.md

Question:
Should real-domain acceptance be a hard Stage 1 sign-off gate?

Issue found:
Real-domain acceptance signal is present in strategy, but stage closure text can be interpreted as fixture-only passing.

Proposed fix:
Make fev_formality_real acceptance a mandatory Stage 1 sign-off checkpoint, not optional late validation.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-07 (P1) - DPA forward scan cursor semantics

- Priority: P0
- Area: Parser DPA scan cursoring
- Target file(s): docs/TCL_PARSER_SPEC.md

Question:
Should cursor advance semantics for DPA scans explicitly reference physical lines consumed (including continuation lines)?

Issue found:
DPA forward scan behavior around backslash-continued DPA lines can be implemented with wrong cursor advance semantics.

Proposed fix:
Clarify that cursor advance must be based on physical source lines consumed by the DPA block, including continuation lines.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-08 (P2) - foreach_in_collection assertion coverage

- Priority: P0
- Area: Fixture assertion gap
- Target file(s): tests/FIXTURE_CATALOG.md, parser test specs

Question:
Should the fixture catalog explicitly require assertion that proc declarations inside foreach_in_collection bodies are not indexed?

Issue found:
Current fixture catalog wording does not force explicit assertion that procs inside foreach_in_collection bodies are not indexed.

Proposed fix:
Add a direct assertion requirement (and fixture case if needed) that inner proc in control-flow context is skipped.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-09 (W1) - F1/F2 merge order-independence guardrail

- Priority: P1
- Area: Compiler merge determinism
- Target file(s): docs/ARCHITECTURE_PLAN.md

Question:
Should compiler guidance explicitly require two-pass per-source set collection and resolution to avoid accidental order-dependent F1/F2 outcomes?

Issue found:
Feature ordering semantics could be misapplied to F1/F2 if implemented as sequential mutating merge instead of per-source set resolution.

Proposed fix:
Document two-pass compile guidance: collect per-source contributions first, then apply L1/L2/L3 resolution; ensure F1/F2 output order-independence.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-10 (W2) - Retired diagnostic slot handling

- Priority: P1
- Area: Diagnostic registry parsing
- Target file(s): docs/DIAGNOSTIC_CODES.md, core test specs

Question:
Should registry parsing and tests explicitly enforce that retired codes are not treated as active?

Issue found:
Registry includes a retired slot (VW-10) and agents may accidentally treat retired rows as active if loader logic is naive.

Proposed fix:
Document and test registry loader rule to skip retired rows.
Add explicit negative test for VW-10 construction failure.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-11 (W3) - Crash-injection scenario completeness

- Priority: P1
- Area: Recovery confidence
- Target file(s): tests/TESTING_STRATEGY.md

Question:
Should testing strategy explicitly list forced-failure checkpoints across P5/P6 boundaries to validate recovery contract?

Issue found:
Crash/restart behavior is specified, but integration scenario list should explicitly enumerate forced-failure checkpoints in P5/P6 boundary windows.

Proposed fix:
Add crash-injection scenarios and expected recovery outcomes to testing strategy.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-12 (W4) - R1 property-test requirement

- Priority: P1
- Area: R1 property confidence
- Target file(s): tests/TESTING_STRATEGY.md

Question:
Should testing strategy include an explicit property-test requirement for F1/F2 manifest equivalence under valid feature permutations?

Issue found:
R1 order-independence requirement is documented, but no explicit property-test requirement is listed for feature-order permutations (F1/F2 only).

Proposed fix:
Add a property test requirement asserting F1/F2 manifest equivalence under feature permutation where dependencies permit reorder.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-13 (W5) - Adjacent drop-range normalization

- Priority: P2
- Area: Adjacent drop-range ergonomics
- Target file(s): docs/RISKS_AND_PITFALLS.md, trimmer test specs

Question:
Should guidance explicitly require coalescing overlapping/adjacent deletion ranges before writing rewritten files?

Issue found:
Adjacent proc/comment/DPA drop ranges can produce noisy formatting artifacts if not normalized before rewrite.

Proposed fix:
Add guidance to coalesce overlapping/adjacent deletion intervals before rendering rewritten files.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## QA-14 (W6) - Sorted list contract strictness

- Priority: P2
- Area: FS list determinism wording
- Target file(s): docs/ARCHITECTURE_PLAN.md, adapter test specs

Question:
Should lexicographic sorting guarantees for FileSystemPort.list() be stated as a strict contract for all adapters?

Issue found:
Sorted path-return behavior is mentioned but should be contractually explicit for all adapters.

Proposed fix:
Strengthen protocol wording that list() returns lexicographically sorted paths; verify adapter tests enforce this.

Your Decision:
- [ ] ACCEPT
- [ ] MODIFY
- [ ] REJECT

Your Suggestion:

Owner:

Status: OPEN

Notes:

---

## Rollup Tracker

| Priority | Total | OPEN | ACCEPTED | MODIFIED | REJECTED | DONE |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 8 | 8 | 0 | 0 | 0 | 0 |
| P1 | 4 | 4 | 0 | 0 | 0 | 0 |
| P2 | 2 | 2 | 0 | 0 | 0 | 0 |

## Final Approval Block

- Reviewer name:
- Review date:
- P0 all resolved: [ ] Yes  [ ] No
- Approved to start/continue implementation: [ ] Yes  [ ] No
- Final comments:
