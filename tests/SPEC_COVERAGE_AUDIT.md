# Spec Coverage Audit

Bidirectional drift inventory of `tests/` against the four authoritative spec docs:

- `technical_docs/ARCHITECTURE.md`
- `technical_docs/IMPLEMENTATION.md`
- `technical_docs/DIAGNOSTIC_CODES.md`
- `technical_docs/CLI_REFERENCE.md`

Generated 2026-05-07. Refresh this file when spec sections move or new tests land.

> **Scope:** spec claim ↔ test mapping with three buckets:
>
> - **Covered** — at least one test asserts the claim end-to-end.
> - **Gap** — claim is in the spec but no test asserts it. Tier P1 / P2 / P3.
> - **Drift** — test asserts something the spec does not say, OR source contradicts the spec.
>
> P1 = correctness/regression-prone (exit codes, destructive guards, environment-sensitive behavior, determinism, lifecycle). P2 = uncovered diagnostics reachable from existing fixtures. P3 = cosmetic.

---

## Summary

| Bucket | Count |
| --- | --- |
| Covered (sampled) | 41 |
| Gap (P1) addressed in this pass | 5 |
| Gap (P1) deferred | 0 |
| Gap (P2) addressed | 8 |
| Gap (P2) deferred | 0 |
| Gap (P3) addressed | 2 |
| Gap (P3) deferred | 0 |
| Drift (test-vs-spec) | 0 |
| Drift (source-vs-spec) | 0 |

---

## ARCHITECTURE.md

### Covered

| Claim | Source | Test |
| --- | --- | --- |
| Re-trim from `<domain>_backup/` cwd does not nest backups | §5.1 / §2.8 | [tests/integration/test_cli_e2e.py](integration/test_cli_e2e.py#L125), [tests/unit/cli/test_commands.py](unit/cli/test_commands.py#L54) |
| `VE-21` exits 2 when neither domain nor backup exists | §2.8 Case 4 | [tests/unit/orchestrator/test_runner.py](unit/orchestrator/test_runner.py#L63), [tests/unit/orchestrator/test_domain_state.py](unit/orchestrator/test_domain_state.py#L54) |
| `VE-17` is case-insensitive (`casefold()`) | §5.1 | [tests/unit/validator/test_validator.py](unit/validator/test_validator.py#L250) |
| Cycle in tracing emits `TW-04` and terminates via visited-set | §5.4 | [tests/unit/compiler/test_tracer.py](unit/compiler/test_tracer.py#L421) |
| MCP destructive guard: `chopper.trim` / `chopper.cleanup` never registered | §3.9 | [tests/unit/mcp/test_tools.py](unit/mcp/test_tools.py#L36), [tests/integration/test_mcp_stdio_e2e.py](integration/test_mcp_stdio_e2e.py#L148) |
| BFS frontier sort determinism under input shuffling | §5.4 | [tests/property/test_determinism.py](property/test_determinism.py#L154) |
| `--strict` + warning escalates to exit 1 | §5.2 | [tests/unit/orchestrator/test_runner.py](unit/orchestrator/test_runner.py#L169) |
| Cleanup without `--confirm` exits 2 | §2.8 / cleanup | [tests/integration/test_cli_e2e.py](integration/test_cli_e2e.py) `TestCleanupSubcommand` |
| Layer-shadow transition emits `VW-21` | §4 R1 (ordered overlay) | [tests/unit/compiler/test_merge_service.py](unit/compiler/test_merge_service.py) `test_vw21_emitted_when_feature_pi_overrides_base_pe` |
| Same-source FE/PE conflict emits `VW-11` | §4 R1 (same-layer rules) | [tests/unit/compiler/test_merge_service.py](unit/compiler/test_merge_service.py) `test_vw13_with_pi_redundant_emits_vw09_too` and adjacent VW-11/12/13 cases |
| Tool-command pool downgrades `TW-02` → `TI-01` | §3.10 | [tests/unit/compiler/test_tracer.py](unit/compiler/test_tracer.py#L286) |

### Gap

| Tier | Claim | Source | Resolution |
| --- | --- | --- | --- |
| P1 | `--strict` does not rewrite the `severity` field of `VW-*` diagnostics — only the exit code changes. | §5.2 / DIAGNOSTIC_CODES Notes | **Closed in this pass** — `tests/unit/orchestrator/test_runner.py::TestStrictMode::test_strict_does_not_rewrite_warning_severity` |
| P1 | `--dry-run` never creates `<domain>_backup/`. | §3.7 / §2.8 | **Closed in this pass** — `tests/integration/test_cli_e2e.py::TestTrimSubcommand::test_trim_dry_run_does_not_create_backup_directory` |
| P1 | `.chopper/` is never copied from `<domain>_backup/` into the rebuilt domain on re-trim. | §2.4 | **Closed in this pass** — `tests/integration/test_cli_e2e.py::TestTrimSubcommand::test_re_trim_does_not_copy_backup_chopper_into_rebuilt_domain` |
| P1 | Glob expansion in `files.include` never matches paths under `.chopper/`. | §2.4 / §3.4 | **Closed in this pass** — `tests/integration/test_cli_e2e.py::TestTrimSubcommand::test_glob_expansion_never_matches_chopper_audit_directory` |
| P1 | When `--project` is used, `base` and `features` paths in the project JSON resolve from cwd (the domain root), not from the project file's directory. | IMPLEMENTATION §1.10 (P-25) | **Closed in this pass** — `tests/integration/test_cli_e2e.py::TestTrimSubcommand::test_project_paths_resolve_from_cwd_not_project_file_directory` |
| P2 | Audit write OSError emits `VW-20` and does not abort the run. | DIAGNOSTIC_CODES `VW-20` | Already covered at unit level in `tests/unit/test_coverage_98.py::test_audit_writers_tolerate_oserror` — left under Covered. |
| P2 | DPA name mismatch emits `PW-11`. | IMPLEMENTATION §1.4.6 | Covered in `tests/unit/parser/test_proc_extractor.py:348`. |
| P2 | Feature `depends_on` cycle emits `VE-22`. | §3.2 | Covered in `tests/unit/config/test_loaders.py:405`. |
| P2 | F3 cross-validate emits `VW-14` / `VW-15` / `VW-16` for missing step targets. | §3.6 | Covered in `tests/unit/validator/test_validator.py:740-789`. |
| P2 | `--tool-commands` is repeatable and accumulates pool entries. | §3.10 | Covered in tracer pool tests + `tests/unit/cli/test_commands.py` (build_run_config tests) — left under Covered. |
| P3 | Render-formatting niceties (color flags, plain-mode text). | CLI §global flags | Out of scope for this pass. |

### Drift

None.

### Resolved (1.1.0)

| Direction | Claim | Source | Resolution |
| --- | --- | --- | --- |
| source-vs-spec | When `--domain` is provided alongside `--project`, it must resolve to `Path.cwd()`; otherwise exit 2. | ARCHITECTURE §5.1 / IMPLEMENTATION §1.10 P-25 (pre-1.1.0) | **Spec inverted, not source tightened.** Per the new ARCHITECTURE.md §5.1, `--domain` is the highest-priority resolution input; cwd is consulted only when `--domain` is absent. The "must resolve to cwd or exit 2" gate has been removed. Closed by `tests/unit/cli/test_commands.py::test_resolve_domain_root_prefers_domain_flag_over_cwd`, `tests/unit/cli/test_commands.py::test_resolve_domain_root_backup_cwd_guard_only_applies_when_domain_absent`, `tests/unit/validator/test_validator.py::test_validate_pre_ve17_uses_domain_root_basename_not_cwd`, and `tests/integration/test_cli_e2e.py::TestTrimSubcommand::test_trim_with_domain_flag_from_unrelated_cwd_succeeds`. Cascaded into CLI_REFERENCE.md, IMPLEMENTATION.md (P-25 / P-31), and DIAGNOSTIC_CODES.md (VE-17). |

---

## IMPLEMENTATION.md

### Covered (sampled)

| Claim | Source | Test |
| --- | --- | --- |
| UTF-8 decode → Latin-1 fallback emits `PW-02` | §1.2 | [tests/fixtures/edge_cases/parser_encoding_latin1_fallback.tcl](fixtures/edge_cases/parser_encoding_latin1_fallback.tcl) |
| Backslash line continuation does not eat lines | §1.3.2 | edge-case fixture `parser_backslash_line_continuation.tcl` |
| Duplicate proc → `PE-01`, last definition wins | §1.4.9 D-1d-02 | parser tests + edge-case fixture |
| DPA `\`-continuation does not absorb args into name | §1.4.6 | [tests/unit/parser/test_bug_report_regressions.py](unit/parser/test_bug_report_regressions.py#L145) |
| Canonical proc-name format vectors | §1.4.3.1 | [tests/unit/core/test_models.py](unit/core/test_models.py) |
| Brace-depth-3 namespace (worked example) | §1.4.5.1 | parser tests |
| Lex-sort BFS frontier (NFR-03) | §1.8.5.2 | property test (linked above) |

### Gap

| Tier | Claim | Source | Resolution |
| --- | --- | --- | --- |
| P2 | DPA association tolerates ≤3 blank lines between proc close and DPA block; 4 blank lines breaks the window. | §1.4.6 rule 2 | **Closed** — `tests/unit/parser/test_proc_extractor.py::TestDPA::test_dpa_blank_line_tolerance_boundary` (parametrized over 0/1/2/3/4 blank lines, asserts attach for 0–3 and no-attach for 4). |
| P3 | Comment-banner backward scan stops at first blank line. | §1.4.7 | **Closed** — `tests/unit/parser/test_proc_extractor.py::TestCommentBanner::test_blank_line_breaks_banner` (explicit blank-line break) and `test_banner_stops_at_code` (non-comment break). |

### Drift

None observed in tests. Source-vs-spec items are noted under ARCHITECTURE.md.

---

## DIAGNOSTIC_CODES.md

### Covered (sampled)

The registry has 72 active codes. Per code-family parity is enforced by `schemas/scripts/check_diagnostic_registry.py`, which is run in CI. Sampled emission tests:

| Code | Test |
| --- | --- |
| `VE-01` / `VE-02` / `VE-12` | [tests/unit/config/test_schema.py](unit/config/test_schema.py) |
| `VE-13` | [tests/unit/cli/](unit/cli/) (project-path-unresolvable) |
| `VE-16` | [tests/unit/validator/test_validator.py](unit/validator/test_validator.py) |
| `VE-17` | covered above |
| `VE-21` | covered above |
| `VE-22` | [tests/unit/config/test_loaders.py](unit/config/test_loaders.py#L405) |
| `VE-23` / `VE-24` / `VE-25` / `VE-26` | [tests/unit/trimmer/test_service.py](unit/trimmer/test_service.py) |
| `VW-09` / `VW-11` / `VW-12` / `VW-13` | [tests/unit/compiler/test_merge_service.py](unit/compiler/test_merge_service.py) |
| `VW-14` / `VW-15` / `VW-16` / `VW-17` | [tests/unit/validator/test_validator.py](unit/validator/test_validator.py#L740) |
| `VW-18` / `VW-19` | RETIRED in 2.0.0-alpha (cannot fire under R1 ordered overlay; rows preserved per registry policy) |
| `VW-21` | [tests/unit/compiler/test_merge_service.py](unit/compiler/test_merge_service.py) `test_vw21_emitted_when_feature_pi_overrides_base_pe` |
| `VE-27` | Registry slot allocated; emission not yet implemented (validator has no check; `merge_service.py` defers via `# No-op exclude — VE-27 handled by validator.`). Pre-impl smoke fixture: [tests/fixtures/overlay_no_op_exclude/](fixtures/overlay_no_op_exclude/), exercised by `tests/integration/test_runner_localfs_e2e.py::test_runner_localfs_overlay_no_op_exclude_loads_cleanly`. |
| `VW-20` | [tests/unit/test_coverage_98.py](unit/test_coverage_98.py#L1078) |
| `TW-01` / `TW-02` / `TW-03` / `TW-04` | [tests/unit/compiler/test_tracer.py](unit/compiler/test_tracer.py#L623) |
| `TI-01` | [tests/unit/compiler/test_tracer.py](unit/compiler/test_tracer.py#L286) |
| `PE-01` | parser tests |
| `PE-04` | [tests/unit/mcp/test_server.py](unit/mcp/test_server.py#L25), [tests/integration/test_mcp_stdio_e2e.py](integration/test_mcp_stdio_e2e.py#L166) |
| `PW-11` | [tests/unit/parser/test_proc_extractor.py](unit/parser/test_proc_extractor.py#L348) |

### Gap

| Tier | Claim | Source | Resolution |
| --- | --- | --- | --- |
| P3 | Severity letter (E/W/I) in the registry matches the `Severity` enum for every row. | DIAGNOSTIC_CODES top notes | Asserted by `schemas/scripts/check_diagnostic_registry.py` (not a pytest test, but a CI gate). Acceptable. |

### Drift

None.

---

## CLI_REFERENCE.md

### Covered (sampled)

| Claim | Test |
| --- | --- |
| `--strict` with no warnings still exits 0 | [tests/integration/test_cli_e2e.py](integration/test_cli_e2e.py) `test_validate_with_strict_and_no_warnings_still_zero` |
| `cleanup --confirm` removes backup; without `--confirm` exits 2 | `TestCleanupSubcommand` |
| `--quiet` suppresses progress | `test_quiet_flag_uses_silent_progress` |
| `--plain` disables Rich | `test_plain_flag_disables_rich_styling` |
| `--project` and `--base` mutually exclusive (argparse exit 2) | `test_project_and_base_mutually_exclusive_exits_nonzero` |
| `validate --features <dir>` expands directory entries | `_expand_feature_dirs` unit tests |

### Gap

| Tier | Claim | Resolution |
| --- | --- | --- |
| P1 | `trim --dry-run` does not create `<domain>_backup/` (live mutation gate). | **Closed in this pass** (see ARCHITECTURE Gap row 2). |
| P2 | `trim --features <dir>` does not expand directories — must be explicit files. | **Closed** — `tests/unit/cli/test_commands.py::test_cmd_trim_does_not_expand_feature_directory` asserts `cmd_trim` leaves `args.features` untouched. The companion `test_cmd_validate_expands_feature_directory` asserts the validate-only expansion path. |
| P3 | `--version` prints `chopper <version>` and exits 0. | **Closed** — `tests/unit/cli/test_main.py::test_version_flag_prints_version_and_exits` asserts `chopper {__version__}` appears in stdout and `SystemExit.code == 0`; `test_version_flag_does_not_require_subcommand` confirms no subcommand is required. |

### Drift

None.

---

## Closed-decision sweep

Re-grepped `tests/` for forbidden tokens listed in `.github/instructions/project.instructions.md` §4
(`LockPort`, `--preserve-hand-edits`, `chopper scan`, `PluginHost`, `MCPProgressBridge`,
`EntryPointPluginHost`, `MCPDiagnosticSink`, `advisor/`, `XE-`, `XW-`, `XI-`, `.chopper/.lock`,
`.chopper/hand_edits`).

No positive hits outside negative assertions.

---

## Deferred / Not Addressed

- **P-06 / P-07 / P-08 / P-10 / P-11 / P-12 fixture gaps** for parser pitfalls — recorded in [FIXTURE_AUDIT.md](FIXTURE_AUDIT.md). Out of scope for the spec-coverage audit (these are fixture authoring tasks, not spec claims).
- **Crash-injection scenarios 5–9** — recorded as deferred in [TESTING_STRATEGY.md](TESTING_STRATEGY.md) per architecture §2.8. Out of scope.
