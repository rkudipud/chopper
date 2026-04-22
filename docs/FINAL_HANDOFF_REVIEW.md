# Final Handoff Review: Chopper v2

**Date:** April 22, 2026
**Reviewer:** GitHub Copilot, devil's-advocate review pass

## Scope

This review covered five surfaces together:

- the product bible and subordinate architecture docs
- the implementation roadmap and test strategy
- the packaging and operator-facing setup surface
- the `json_kit/` schema and authoring contract
- the current `src/chopper/` implementation reality

## Verdict

- Architecture and plan: signed off for agent buildout
- `json_kit` contract: signed off after this sync pass
- Packaging and operator surface: signed off after this sync pass
- Runtime implementation: not signed off

The repository is now truthful enough to hand to buildout agents. It is not truthful enough to claim a working tool: `src/chopper/` still contains only `__init__.py`, so there is no executable parser, compiler, trimmer, validator, audit service, orchestrator, or CLI implementation yet.

## Critical Findings

1. The prior sign-off text was factually wrong. It claimed implementation and packaging states that the repository did not satisfy.
2. The package metadata had reintroduced a dead console entry point (`chopper.cli.main:main`) even though no CLI module exists.
3. The README and setup scripts had drifted into promising `chopper --help`, Python 3.8+, and a 7-phase pipeline, none of which matched the live repo contract.
4. The active integration gate drifted from 25 to 30 by counting deferred crash-injection scenarios as live acceptance work.
5. The `json_kit` base schema and authoring guide still exposed `options.template_script`, which is a scope-lock violation and contradicted the current bible and test strategy.
6. One live CLI example still used stale feature filenames (`jsons/features/f1.json`) instead of the current `<feature>.feature.json` convention.
7. The testing strategy still modeled forbidden behavior (`scan` and lock detection) instead of the v1 command surface and lifecycle policy.

## Sign-Off Boundary

What is signed off:

- the 8-phase pipeline (`P0`-`P7`)
- the parser / config / compiler / tracer / trimmer / generator / validator / audit / CLI module split
- the additive merge model and reporting-only trace model
- the current JSON layout convention: `jsons/base.json`, `jsons/features/<feature>.feature.json`, `project.json`
- the Stage 0 -> Stage 5 build order and the 25-scenario active gate

What is not signed off:

- any executable parser behavior
- any executable compiler or trace behavior
- any executable trimmer, validator, generator, audit, or CLI behavior
- any claim that `chopper` is runnable from package metadata today
- any milestone claim that depends on code not yet written

## Stability Notes

### S-6 — Determinism Gate

Determinism is a release gate, not a nice-to-have. Hash-seed pinning, sorted traversal where specified, byte-stable manifests, and reproducible audit artifacts must stay enforced throughout implementation.

### S-7 — Edge Fixtures Stay In Scope

Comment-only, empty-file, and other adversarial parser fixtures remain part of the acceptance surface even before the full parser lands. Do not drop them during scaffolding.

### S-9 — Conservative Property-Test Budget

The Hypothesis budget stays conservative at `max_examples = 200` until the core pipeline exists and CI runtime is measured on real fixtures. Raise budgets only after profiling, not by guesswork.

## Process Repairs

### PR-2 — Scenario Roster Lock

`tests/TESTING_STRATEGY.md` §5 is the source of truth for the active named integration roster. The current active count is 25 because crash-injection scenarios 5-9 remain explicitly deferred. Any future count change must update both the strategy document and roadmap milestone `M6` together.

### PR-4 — Docs-to-Code Guards

The docs/code guard scripts stay in place, but they are only meaningful once the corresponding services exist. Treat green results on an empty source tree as non-evidence.

## Minimum Gate Before Buildout

1. Keep the package surface honest. Do not advertise a live CLI until the CLI module exists.
2. Keep the JSON contract honest. If a field or filename convention changes in `json_kit/`, cascade it through the bible, the roadmap, and the testing strategy in the same pass.
3. Land implementation vertically, not horizontally. The first milestone should prove one real slice: config load, one parser path, one compile path, and one deterministic test fixture.

## Implementation Handoff

Recommended first implementation wave:

1. Stage 0 foundation modules and type surfaces
2. Stage 1 parser utility and parser service
3. Stage 2 config loading and compiler merge, with deterministic fixtures from the start

Do not start Stage 5 CLI buildout before the parser, config, and compiler stack has at least one truthful vertical slice behind it.

## Final Sign-Off

Sign-off is granted for agent-based buildout of the tool.

Sign-off is not granted for shipping, packaging, or claiming an implemented runtime.
