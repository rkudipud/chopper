# Chopper v2 Handoff Review

Date: 2026-04-21

## Scope

This review covered four surfaces together:

- the product bible and subordinate architecture docs
- the implementation roadmap and test strategy
- the current Python package and packaging metadata
- the `json_kit/` reorganization that changed JSON layout expectations

## Verdict

- Architecture and plan: conditional sign-off for agent-based buildout
- Implementation: not signed off
- Packaging and operator surface: not signed off until the package stops advertising a non-existent CLI

The architecture is strong enough to start implementation work, but only after the repo tells the truth about its current state and the JSON-authoring contract is internally consistent again.

## Critical Findings

1. The repository is still docs-first, not tool-complete. `src/chopper/` currently contains only `__init__.py`, so there is no parser, compiler, trimmer, validator, CLI, or orchestrator implementation to sign off.
2. The package metadata advertised a dead console entry point (`chopper.cli.main:main`). That made install-time behavior dishonest even though the implementation is not there yet.
3. The `json_kit/` layout contract changed, but the surrounding docs still referenced removed example bundles and deleted authoring-guide paths.
4. The named integration-scenario gate drifted after crash-injection scenarios `5-9` were explicitly deferred. The roadmap still said `30`; the live strategy table now represents `25` active scenarios.

## Sign-Off Boundary

What is signed off:

- the high-level pipeline shape (`P0`-`P7`)
- the parser/compiler/trimmer separation
- the additive merge model and reporting-only trace model
- the current JSON layout convention: `jsons/base.json`, `jsons/features/<feature>.feature.json`, `project.json`

What is not signed off:

- any executable parser behavior
- any executable compiler or trace behavior
- any live CLI contract
- any claim that the standalone JSON kit is fully self-contained in this checkout

## Stability Notes

### S-6 — Determinism Gate

Determinism is a release gate, not a nice-to-have. Hash-seed pinning, sorted traversal where specified, byte-stable manifests, and reproducible audit artifacts must stay enforced throughout implementation.

### S-7 — Edge Fixtures Stay In Scope

Comment-only, empty-file, and other adversarial parser fixtures remain part of the acceptance surface even before the full parser lands. Do not drop them during early scaffolding.

### S-9 — Conservative Property-Test Budget

The Hypothesis budget stays conservative until the core pipeline exists and CI runtime is measured on real fixtures. Raise budgets only after profiling, not by guesswork.

## Process Repairs

### PR-2 — Scenario Roster Lock

`tests/TESTING_STRATEGY.md` §5 is the source of truth for the named integration roster. The current active count is `25` because crash-injection scenarios `5-9` were intentionally deferred post-D0. Any future count change must update both the strategy document and roadmap milestone `M6` together.

### PR-4 — Docs-to-Code Guards

The docs/code guard scripts stay in place, but they are only meaningful once the corresponding services exist. Treat green results on an empty source tree as non-evidence.

## Minimum Gate Before Buildout

1. Keep the package surface honest. Do not advertise a live CLI until the CLI module exists.
2. Keep the JSON contract honest. If `json_kit/` does not ship schemas, examples, or analyzer docs in a checkout, no doc may claim that it does.
3. Land implementation vertically, not horizontally. The first agent milestone should prove one real end-to-end slice: config load, one parser path, one compile path, and one deterministic test fixture.

## Implementation Handoff

Recommended first implementation wave:

1. Stage 0 foundation modules and type surfaces
2. Stage 1 parser utility and parser service
3. Stage 2 config loading and compiler merge, with deterministic fixtures from the start

Do not start Stage 5 CLI buildout before the parser/config/compiler stack has at least one truthful vertical slice behind it.