# Graph Report - chopper  (2026-11-03)

## Corpus Check
- 393 files · ~458,043 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 90 file(s) not represented in the graph (top: .tcl 67, (none) 9, .commands 6)

## Summary
- 7285 nodes · 17325 edges · 381 communities (298 shown, 83 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 2906 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c81ae4c1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RunConfig
- check_v2.py
- test_commands_coverage.py
- tokenize
- CompilerService
- make_ctx
- InMemoryFS
- NamespaceTracker
- Diagnostic
- merge_service.py
- _ctx
- writers.py
- test_audit.py
- functions.py
- _calls
- test_commands.py
- test_cloc_backend_coverage.py
- test_validator.py
- extract_procs
- _run
- TracerService
- _StubFS
- proc_extractor.py
- pathlib
- TestCompanionSyncService
- _collect
- CaptureFixture
- ConfigService
- reference
- commands.py
- Phase
- reference
- properties
- properties
- make_ctx
- test_runner_localfs_e2e.py
- resolve_domain
- properties
- ChopperContext
- test_proc_dropper.py
- internal_error.py
- schema.py
- test_indentation.py
- flow_resolver.py
- FileOutcome
- DomainState
- scan.py
- render.py
- properties
- _brace_delta
- test_p4_commands.py
- _StubFS
- crash_harness.py
- FileTreatment
- properties
- test_stack_graph.py
- test_v2_check_script.py
- ChopperRunner
- Path
- properties
- TestLoadFeature
- ExtractorDiagnostic
- type
- properties
- simulate_trim_in_memory
- StageDefinition
- ParsedFile
- properties
- type
- file_bug_report.py
- test_cli_chained_actions.py
- _make_ctx
- $defs
- TrimReport
- generators/test_service.py
- DomainStateService
- LocalFS
- test_sloc_coverage.py
- test_service_feature_procs.py
- .build
- properties
- ProcRemoval
- properties
- properties
- resolve_feature_names
- pytest
- test_bug_report_regressions.py
- ParserService
- feature-v1.schema.json
- parse_file
- properties
- test_files_exclude_p4.py
- extract_body_refs
- Chopper Agent Memory
- ProcEntry
- build_parser
- 07_base_full/jsons/base.json
- domain
- RichProgress
- Providers / default_providers
- properties
- properties
- feature-v2.schema.json
- properties
- Path
- properties
- properties
- test_call_extractor_sources.py
- test_count_tree_skips_unreadable_and_non_sloc_files
- count_sloc
- test_fs_walk_coverage.py
- test_audit_artifacts_golden.py
- type
- procs
- properties
- cloc_backend.py
- LocReport
- Parser Module Specification
- intel_header_text
- parser/test_service_coverage.py
- chopper/__init__.py
- 08_base_plus_one_feature/jsons/features/dft.feature.json
- pipeline_signoff.feature.json
- Acquire Codebase Knowledge Skill
- run-result-v1.schema.json
- exclude
- exclude
- properties
- exclude
- exclude
- test_tool_commands.py
- StageSpec
- CaptureFixture
- _key
- config/test_service.py
- properties
- render_p4_checkout_notice
- test_trace_service_coverage.py
- emit_stage_tcl
- _warn_if_cwd_will_be_renamed
- power_analysis.feature.json
- 10_chained_features_depends_on/project.json
- TestChopperContext
- source
- file
- procEntry
- trace_service.py
- topo_sort_features
- AuditManifest
- FileSystemPort
- _make_ctx
- _make_glob_ctx
- load_base
- dft_support.feature.json
- 08_base_plus_one_feature/project.json
- Rule R1 (Ordered Overlay, Last Mention Wins)
- internal_error
- artifacts_present
- test_determinism.py
- P4CheckoutResult
- chopper.app Application Layer
- test_models.py
- _InMemoryFS
- Project JSON
- GitNexus Guide Skill
- 09_base_plus_multiple_features/jsons/features/dft.feature.json
- 09_base_plus_multiple_features/jsons/features/power.feature.json
- coverage_reporting.feature.json
- 14_cross_feature_skip_if_no_stage/jsons/features/dft.feature.json
- main
- properties
- diagnostic-v1.schema.json
- stageDefinition
- type
- Future Considerations (FD Ledger)
- render_p4_checkout_opened
- test_input_preserver_coverage.py
- CompiledManifest
- 14_cross_feature_skip_if_no_stage/jsons/features/power.feature.json
- _collect_base
- lookup
- base-v2.schema.json
- _filter_csv
- _NullFS
- 01_base_files_only/jsons/base.json
- 04_base_files_and_procs/jsons/base.json
- 05_base_files_and_stages/jsons/base.json
- properties
- top_codes
- procs
- phase
- exit_code
- SilentProgress
- test_render_files_removed_shadowed_by_label
- test_loaders.py
- header.py
- _filter_milestone
- stack_emitter.py
- header_domain/.chopper/input_base.json
- TokenKind
- header_domain/jsons/base.json
- Chopper onboarding brochure
- 08_base_plus_one_feature/jsons/base.json
- 09_base_plus_multiple_features/jsons/base.json
- 10_chained_features_depends_on/jsons/base.json
- 11_project_base_only/jsons/base.json
- 14_cross_feature_skip_if_no_stage/jsons/base.json
- check_service_signatures.py
- .chopper/ Audit Bundle
- TestGlobFilesIncludeRegression
- test_missing_inputs.py
- expand_vars_entry
- base-v1.schema.json
- test_call_extractor.py
- test_file_writer.py
- stageDefinition
- test_cli_loc.py
- test_runner_coverage.py
- _codes
- with
- 15_stage_reference_file/jsons/base.json
- 16_feature_vars/project.json
- mini_domain/jsons/features/feature_a.json
- mini_domain/jsons/base.json
- test_main_coverage.py
- _source_refs
- ProcEntryRef
- glob_match
- _parser_fixtures
- 03_base_stages_only/jsons/base.json
- 06_base_procs_and_stages/jsons/base.json
- 11_project_base_only/project.json
- 15_stage_reference_file/jsons/features/dft.feature.json
- apr_fc.json
- TestMissingBuiltins
- overlay_replace/jsons/features/feature_a.json
- post_check.feature.json
- plan_p4_sync.py
- 01_base_files_only/.chopper/input_base.json
- 02_base_procs_only/.chopper/input_base.json
- load_pool
- 09_base_plus_multiple_features/project.json
- gen_large_domain.py
- TestMixedStageFormats
- _redistribute_coverage_tests.py
- test_file_bug_report.py
- Real-world bug-report fixtures README
- 02_base_procs_only/jsons/base.json
- 12_base_with_aggregate_stack/jsons/base.json
- 13_base_with_standalone_stack/jsons/base.json
- project_dft_only.json
- GitHub API Push Skill
- validate_jsons.py
- Chopper runtime architecture diagram
- overlay_no_op_exclude/project.json
- overlay_remove_only/jsons/base.json
- severity
- project_full.json
- progress-event-v1.schema.json
- check_diagnostic_registry.py
- AuditArtifact
- README Changelog
- test_sink_collecting.py
- steps
- by_family
- TestRunConfig
- TestEscapedBracketCalls
- overlay_remove_only/project.json
- TestSwitchBracePatterns
- event
- overlay_no_op_exclude/jsons/base.json
- feature_typo.json
- overlay_two_features_same_file/jsons/base.json
- run_mode
- language
- R5 Backup-and-Rebuild
- .test_audit_exception_is_swallowed
- PresentationConfig
- .test_p3_error_aborts_pipeline_with_exit_1
- FileStat
- feature_drop.json
- overlay_replace/jsons/base.json
- detail
- overlay_replace/project.json
- overlay_two_features_same_file/project.json
- stages_domain/jsons/base.json
- chopper_run.json golden shape
- test_cli_e2e.py
- test_feature_vars.py
- test_ascii_only.py
- test_p4_sync_planner.py
- dop.feature.json
- fdr.feature.json
- check_v2.py reference
- v1 → v2 interview question bank
- slug
- property/test_smoke.py
- RichUnavailableError
- create_latin1_fixture.py
- overlay_two_features_same_file/jsons/features/feature_a.json
- feature_b.json
- exit_codes
- reference_file
- exit_codes
- elapsed_seconds
- language
- phase_index
- run_mode
- Trim Report JSON Shape Golden File
- vars
- assert_domain_recoverable
- _patch_coverage_imports.py
- test_doc_links.py
- TestRealWorldNestedProcCalls
- cloc.pl vendored tool
- options.generate_stack Aggregate Stack Contract
- json
- code
- TestBracketCalls
- dedupe_bucket
- message
- outputs
- phase_total
- context
- line_no
- properties
- phase
- run_id
- schema
- step_index
- step_total
- re
- Example 14 README — Cross-Feature skip_if_no_stage
- Agent Local Memory Files (README)
- die
- ARCHITECTURE.md (Architecture Doc)
- timestamp
- schema
- TestDeterminism
- presentation/chopper_onboarding.html (Deployed Onboarding Page)
- dependency_graph.json artifact schema (pi_plus, pi_seeds, pt, edges, unresolved)
- P4 File Exclusion List
- TestControlFlowBodies
- pull_request_template.md
- test_walk_files_oserror_on_stat_skips_entry
- bisect-feature-breakage/SKILL.md
- Assign Bug Issues GitHub Actions Workflow
- chopper
- bootstrap-domain/SKILL.md
- explain-last-run/SKILL.md
- package-bug-artifacts/SKILL.md
- Removed Files Provenance Manifest
- report-chopper-bug/SKILL.md
- validate-my-jsons/SKILL.md
- why-was-dropped/SKILL.md
- TFM (Tool Flow Manager, CTH R2G)

## God Nodes (most connected - your core abstractions)
1. `ChopperContext` - 294 edges
2. `FileTreatment` - 266 edges
3. `InMemoryFS` - 210 edges
4. `Diagnostic` - 185 edges
5. `Phase` - 168 edges
6. `make_ctx()` - 160 edges
7. `CompiledManifest` - 120 edges
8. `_ctx()` - 104 edges
9. `RunConfig` - 101 edges
10. `ConfigService` - 100 edges

## Surprising Connections (you probably didn't know these)
- `test_expand_feature_dirs_preserves_empty_segments()` --calls--> `expand_feature_dirs()`  [INFERRED]
  tests/unit/cli/test_commands_coverage.py → src/chopper/app/catalog.py
- `test_expand_feature_dirs_returns_input_when_empty()` --calls--> `expand_feature_dirs()`  [INFERRED]
  tests/unit/cli/test_commands_coverage.py → src/chopper/app/catalog.py
- `test_internal_error_rejects_empty_kind()` --uses--> `InternalError`  [INFERRED]
  tests/unit/core/test_models_audit_coverage.py → src/chopper/core/models_audit.py
- `default_state()` --uses--> `DomainState`  [INFERRED]
  tests/unit/compiler/_helpers.py → src/chopper/core/models_common.py
- `test_py_eval_braced_python_payload_is_opaque()` --calls--> `parse_file()`  [INFERRED]
  tests/unit/parser/test_call_extractor.py → src/chopper/parser/service.py

## Import Cycles
- 4-file cycle: `src/chopper/audit/__init__.py -> src/chopper/audit/service.py -> src/chopper/audit/writers.py -> src/chopper/audit/sloc.py -> src/chopper/audit/__init__.py`

## Hyperedges (group relationships)
- **Seven-Template Population Workflow** — github_skills_acquire_codebase_knowledge_skill_skill, github_skills_acquire_codebase_knowledge_assets_templates_stack_template, github_skills_acquire_codebase_knowledge_assets_templates_structure_template, github_skills_acquire_codebase_knowledge_assets_templates_architecture_template, github_skills_acquire_codebase_knowledge_assets_templates_conventions_template, github_skills_acquire_codebase_knowledge_assets_templates_integrations_template, github_skills_acquire_codebase_knowledge_assets_templates_testing_template, github_skills_acquire_codebase_knowledge_assets_templates_concerns_template [EXTRACTED 1.00]
- **run_id-correlated .chopper/ audit bundle artifacts** — technical_docs_architecture_chopper_run_json, technical_docs_architecture_compiled_manifest, technical_docs_architecture_dependency_graph, technical_docs_architecture_diagnostics_json, technical_docs_architecture_trim_report, technical_docs_architecture_p4_commands_txt, technical_docs_architecture_run_id [EXTRACTED 1.00]
- **GitNexus Investigation Navigation** — claude_skills_gitnexus_gitnexus_guide_skill_query_tool, claude_skills_gitnexus_gitnexus_guide_skill_context_tool, claude_skills_gitnexus_gitnexus_guide_skill_process_resource [EXTRACTED 1.00]
- **Import-linter layered architecture (cli > app > orchestrator > services > adapters > core)** — technical_docs_architecture_cli_layer, technical_docs_engineering_app_layer, technical_docs_architecture_orchestrator_layer, technical_docs_architecture_services_layer, technical_docs_architecture_adapters_layer, technical_docs_architecture_core_layer [EXTRACTED 1.00]
- **P0-P7 Pipeline Service Sequence** — technical_docs_engineering_domainstateservice, technical_docs_engineering_configservice, technical_docs_engineering_validate_pre, technical_docs_engineering_parserservice, technical_docs_engineering_compilerservice, technical_docs_engineering_tracerservice, technical_docs_engineering_trimmerservice, technical_docs_engineering_generatorservice, technical_docs_engineering_tclindentationservice, technical_docs_engineering_companionsyncservice, technical_docs_engineering_validate_post, technical_docs_engineering_auditservice [EXTRACTED 1.00]
- **Eight-phase P0-P7 pipeline** — technical_docs_architecture_p0_domain_state, technical_docs_architecture_p1_config_prevalidate, technical_docs_architecture_p2_parse, technical_docs_architecture_p3_compile, technical_docs_architecture_p4_trace, technical_docs_architecture_p5_build_output, technical_docs_architecture_p6_post_validate, technical_docs_architecture_p7_audit [EXTRACTED 1.00]
- **Ports and Adapters Bindings** — technical_docs_engineering_filesystemport, technical_docs_engineering_diagnosticsink, technical_docs_engineering_progresssink, technical_docs_engineering_localfs, technical_docs_engineering_inmemoryfs, technical_docs_engineering_collectingsink, technical_docs_engineering_richprogress, technical_docs_engineering_silentprogress [EXTRACTED 1.00]
- **F3 Stage-Generation JSON Example Pattern** — examples_12_base_with_aggregate_stack_readme_generate_stack, examples_13_base_with_standalone_stack_readme_standalone_stack, examples_14_cross_feature_skip_if_no_stage_readme_skip_if_no_stage [INFERRED 0.85]

## Communities (381 total, 83 thin omitted)

### Community 0 - "RunConfig"
Cohesion: 0.05
Nodes (46): build_trim_stats(), RunConfig, _glob_has_matches(), test_audit_service_emits_vw20_on_write_failure(), test_audit_service_safe_read_returns_none_on_oserror(), test_format_exclusion_path_falls_back_to_ctx_ward_root(), test_p4_commands_ctx_ward_root_fallback(), test_p4_commands_ward_prefix_valueerror_falls_back_to_domain_relative() (+38 more)

### Community 1 - "check_v2.py"
Cohesion: 0.06
Nodes (40): _adoption(), build(), Bundle, _candidates(), _delta(), file_change(), _expand(), _gate() (+32 more)

### Community 2 - "test_commands_coverage.py"
Cohesion: 0.02
Nodes (58): failed_domain_summary(), _split_domain_csv(), test_autodiscover_base_returns_first_candidate(), test_autodiscover_base_returns_second_candidate(), test_check_project_paths_emits_ve13_for_missing_base(), test_check_project_paths_resolvable_missing_base_returns_2(), test_check_project_paths_resolvable_raw_not_dict(), test_check_project_paths_resolvable_returns_none_when_no_project() (+50 more)

### Community 3 - "tokenize"
Cohesion: 0.04
Nodes (19): tokenize(), _flush_word(), test_tokenizer_backslash_continuation_increments_line_no(), test_tokenizer_command_position_backslash_newline_advances_line(), test_tokenizer_comment_backslash_newline_advances_line_count(), test_tokenizer_comment_with_backslash_newline_continuation(), test_tokenizer_handles_backslash_line_continuation(), _kinds() (+11 more)

### Community 4 - "CompilerService"
Cohesion: 0.08
Nodes (48): CompilerService, default_state(), files_section(), make_base(), make_feature(), make_loaded(), make_parsed(), proc_ref() (+40 more)

### Community 5 - "make_ctx"
Cohesion: 0.08
Nodes (57): resolve_stages(), AddStepAction, RemoveStepAction, ReplaceStepAction, _escape(), marker_pair(), make_ctx(), _make_feature() (+49 more)

### Community 6 - "InMemoryFS"
Cohesion: 0.05
Nodes (52): InMemoryFS, test_fs_memory_copy_file_adds_parent_dirs(), test_fs_memory_copy_file_into_directory_raises(), test_fs_memory_copy_file_missing_source_raises(), test_fs_memory_copy_file_raises_when_dst_is_directory(), test_fs_memory_copy_tree_excludes_chopper_subtree(), test_fs_memory_copy_tree_missing_source_raises(), test_fs_memory_copy_tree_nested_dirs_preserved() (+44 more)

### Community 7 - "NamespaceTracker"
Cohesion: 0.04
Nodes (18): ContextFrame, ContextKind, _looks_computed(), NamespaceTracker, _strip_leading_colons(), TrackerDiagnostic, test_namespace_tracker_post_init_skips_push_when_stack_nonempty(), test_namespace_tracker_rbrace_at_file_root_does_not_pop() (+10 more)

### Community 8 - "Diagnostic"
Cohesion: 0.03
Nodes (22): CollectingSink, Diagnostic, DiagnosticSummary, DiagnosticSink, _noop_diagnostic(), _Sink, _Sink, _BrokenSink (+14 more)

### Community 9 - "merge_service.py"
Cohesion: 0.08
Nodes (31): _apply_layer(), _build_short_to_canonical(), _build_source_facts(), _classify_layer_intent(), _collect_universe(), _derive_manifest(), _emit_ve27_fe_literal(), _emit_ve27_glob() (+23 more)

### Community 10 - "_ctx"
Cohesion: 0.04
Nodes (56): _empty_config(), BaseJson, BaseOptions, FeatureJson, FilesSection, LoadedConfig, test_collect_input_jsons_returns_empty_when_loaded_is_none(), test_copy_inputs_feature_with_none_text_continues() (+48 more)

### Community 11 - "writers.py"
Cohesion: 0.05
Nodes (37): sha256_hex(), _before_root(), _build_diag_entries(), _build_file_report(), _build_proc_report(), _build_summary(), _compute_excluded_paths(), _compute_line_counts() (+29 more)

### Community 12 - "test_audit.py"
Cohesion: 0.07
Nodes (44): AuditService, render_files_removed(), _make_provenance(), FileProvenance, _build_rich_record(), _make_ctx(), _project_loaded(), _record() (+36 more)

### Community 13 - "functions.py"
Cohesion: 0.07
Nodes (29): _check_brace_balance(), _check_dangling_refs(), _check_empty_base(), _check_feature_domain(), _check_literal_path(), _check_paths(), _check_pattern(), _check_project_level() (+21 more)

### Community 14 - "_calls"
Cohesion: 0.17
Nodes (3): _calls(), TestBasicCalls, TestSuppression

### Community 15 - "test_commands.py"
Cohesion: 0.07
Nodes (32): expand_feature_dirs(), _resolve_domain_root(), _ns(), test_build_run_config_defaults_p4_checkout_false_when_absent(), test_build_run_config_parses_comma_separated_features(), test_build_run_config_skips_empty_feature_segments(), test_build_run_config_threads_p4_checkout_flag(), test_build_run_config_with_project_ignores_base_and_features() (+24 more)

### Community 16 - "test_cloc_backend_coverage.py"
Cohesion: 0.04
Nodes (31): test_cloc_backend_returns_code_on_success(), test_cloc_backend_returns_none_on_json_decode_error(), test_cloc_backend_returns_none_on_nonzero_exit(), test_cloc_backend_returns_none_on_subprocess_error(), test_cloc_backend_returns_none_on_tmpfile_write_error(), test_cloc_backend_returns_none_when_code_not_int(), test_cloc_backend_returns_none_when_no_sum_key(), test_cloc_backend_returns_none_when_unavailable() (+23 more)

### Community 17 - "test_validator.py"
Cohesion: 0.06
Nodes (76): DependencyGraph, Edge, ProcDecision, ProjectJson, validate_post(), validate_pre(), TestDependencyGraphInvariants, TestEdgeClass (+68 more)

### Community 18 - "extract_procs"
Cohesion: 0.05
Nodes (13): extract_procs(), _diag_kinds(), _procs_by_short(), TestBasic, TestBodyEdgeCases, TestCommentBanner, TestContextSuppression, TestContinuation (+5 more)

### Community 19 - "_run"
Cohesion: 0.23
Nodes (16): _procs_domain(), test_generated_sourcing_files_are_aggregate_stack_inputs(), test_generated_sourcing_files_flow_to_p4_audit_and_loc(), test_missing_and_duplicate_procs_warn(), test_procs_generated_path_collision(), test_procs_generation_and_f1_preservation(), test_v2_without_procs_writes_header_only_file(), test_every_project_base_feature_version_combination() (+8 more)

### Community 20 - "TracerService"
Cohesion: 0.10
Nodes (17): TracerService, make_proc(), _loaded_with_pool(), _manifest_with_seeds(), _parse(), TestAmbiguousMatch, TestArchitectureDocWorkedExample, TestCycleDetection (+9 more)

### Community 21 - "_StubFS"
Cohesion: 0.20
Nodes (4): _MissingWriteFS, _StubFS, test_incomplete_stub_fails_protocol(), test_stub_fs_satisfies_protocol()

### Community 22 - "proc_extractor.py"
Cohesion: 0.06
Nodes (18): _build_entry(), _consume_brace_block(), _consume_element(), _detect_non_brace_body(), _extract_dpa_proc_name(), ExtractorResult, _is_computed_name(), _line_ends_with_continuation() (+10 more)

### Community 23 - "pathlib"
Cohesion: 0.05
Nodes (6): base_candidates(), find_base(), find_project_config(), Severity, DomainRunResult, test_array_set_braced_keys_are_not_calls()

### Community 24 - "TestCompanionSyncService"
Cohesion: 0.10
Nodes (4): CompanionSyncService, _manifest_with_proc_trim(), TestCompanionSyncService, _trim_report()

### Community 25 - "_collect"
Cohesion: 0.07
Nodes (10): _collect(), _shipped_chopper_jsons(), test_every_shipped_chopper_json_is_schema_valid(), test_shipped_json_validation_includes_v2_examples(), test_v2_preserves_every_v1_schema_field_except_version_and_pointers(), TestBaseSchema, TestFeatureSchema, TestProjectSchema (+2 more)

### Community 26 - "CaptureFixture"
Cohesion: 0.09
Nodes (15): selected_feature_paths(), _print_domain_header(), _make_ctx_for_header(), test_build_run_config_ve35_auto_discovery_fails(), test_build_run_config_ve36_no_suggestion_hint(), test_build_run_config_ve36_unresolved_feature_name(), test_build_run_config_ve36_unresolved_feature_with_suggestion(), test_print_domain_header_base_no_features() (+7 more)

### Community 27 - "ConfigService"
Cohesion: 0.11
Nodes (8): ConfigService, _default_state(), TestAddStepActionReferenceFile, TestFeatureFlowActionReferenceFile, TestDeterminism, TestDirectMode, TestProjectMode, TestSurfaceFiles

### Community 28 - "reference"
Cohesion: 0.05
Nodes (47): const, enum, type, loadFromAction, removeStageAction, removeStepAction, replaceStageAction, replaceStepAction (+39 more)

### Community 29 - "commands.py"
Cohesion: 0.05
Nodes (32): DomainLookupResult, DomainTarget, _resolve_by_name(), resolve_target(), AppError, AppIssue, build_run_config(), check_project_paths() (+24 more)

### Community 30 - "Phase"
Cohesion: 0.04
Nodes (20): open_context(), _emit_ve30(), _emit_ve31(), _extract_cycle(), Phase, ProgressSink, _Progress, _Progress (+12 more)

### Community 31 - "reference"
Cohesion: 0.07
Nodes (37): const, enum, type, loadFromAction, removeStageAction, removeStepAction, replaceStepAction, additionalProperties (+29 more)

### Community 32 - "properties"
Cohesion: 0.05
Nodes (41): additionalProperties, description, minLength, pattern, type, description, description, minLength (+33 more)

### Community 33 - "properties"
Cohesion: 0.05
Nodes (41): additionalProperties, description, minLength, pattern, type, description, description, minLength (+33 more)

### Community 34 - "make_ctx"
Cohesion: 0.09
Nodes (30): _rollback_late_failure(), make_ctx(), _manifest(), _state(), test_compute_p4_edit_paths_includes_regenerate_in_place_generated_file(), test_dry_run_never_touches_p4_even_with_flag_on(), test_later_dispatch_failure_after_checkout_success_restores_domain_immediately(), test_p4_attempted_but_no_edit_paths_short_circuits_checkout_call() (+22 more)

### Community 35 - "test_runner_localfs_e2e.py"
Cohesion: 0.09
Nodes (23): _as_p1_reads(), _copy_fixture_jsons(), _domain_payload_hashes(), _make_ctx(), _make_overlay_ctx(), test_runner_localfs_dry_live_dry_sequence_keeps_domain_payload_stable(), test_runner_localfs_dry_run_emits_p4_commands_txt(), test_runner_localfs_dry_run_manifest_matches_live_trim_outputs_1_to_1() (+15 more)

### Community 36 - "resolve_domain"
Cohesion: 0.14
Nodes (8): resolve_domain(), _collect_errors(), emit(), _Error, TestBareNameOSError, TestNameModeBareName, TestNameModeVendorQualified, TestPathMode

### Community 37 - "properties"
Cohesion: 0.06
Nodes (37): properties, description, minLength, type, description, items, minItems, type (+29 more)

### Community 38 - "ChopperContext"
Cohesion: 0.06
Nodes (18): _dropped_rows(), ChopperContext, copy_tree(), iter_domain_files(), walk_files(), source_root(), _build_report(), _compute_p4_edit_paths() (+10 more)

### Community 39 - "test_proc_dropper.py"
Cohesion: 0.17
Nodes (26): annotate_procs(), ProcDropError, _kept_marker(), _mk(), _removed_marker(), _source_of(), test_adjacent_ranges_each_get_own_marker(), test_comment_and_dpa_included_in_span() (+18 more)

### Community 40 - "internal_error.py"
Cohesion: 0.11
Nodes (15): record_crash(), _format_diagnostics(), _format_runconfig(), _format_traceback(), _render(), _resolve_audit_root(), write_internal_error_log(), _ContextWithBrokenConfig (+7 more)

### Community 41 - "schema.py"
Cohesion: 0.06
Nodes (19): _get_validator(), _load_schema(), _schema_dir(), validate_json(), _collect_surface_files(), _add_literal(), _is_glob_pattern(), _match_glob_against() (+11 more)

### Community 42 - "test_indentation.py"
Cohesion: 0.08
Nodes (22): format_tcl_indentation(), test_format_tcl_indentation_empty_returns_empty(), _manifest(), _outcome(), _report(), test_format_tcl_indentation_backslash_continuation(), test_format_tcl_indentation_blank_lines_no_trailing_whitespace(), test_format_tcl_indentation_comment_continuation_not_propagated() (+14 more)

### Community 43 - "flow_resolver.py"
Cohesion: 0.06
Nodes (39): _apply_action(), _apply_add_stage(), _apply_add_step(), _apply_load_from(), _apply_remove_stage(), _apply_remove_step(), _apply_replace_stage(), _apply_replace_step() (+31 more)

### Community 44 - "FileOutcome"
Cohesion: 0.08
Nodes (16): ensure_executable(), mirror_perms_plus_exec(), FileOutcome, _backup_path(), _domain_path(), full_copy_file(), proc_trim_file(), remove_file() (+8 more)

### Community 45 - "DomainState"
Cohesion: 0.07
Nodes (15): DomainState, dump_model(), _encode(), loads(), TestDomainState, test_serialization_encodes_intenum_via_value(), test_serialization_encodes_timedelta_as_seconds(), TestCollections (+7 more)

### Community 46 - "scan.py"
Cohesion: 0.07
Nodes (21): collect_code_metrics(), detect_ci_cd_pipelines(), detect_containers(), detect_monorepo(), detect_performance_markers(), detect_security_configs(), find_entry_points(), find_env_templates() (+13 more)

### Community 47 - "render.py"
Cohesion: 0.07
Nodes (18): TrimStats, _fmt_int(), _fmt_pair(), render_app_error(), render_audit_bundle_locations(), render_p4_branch_analysis(), render_p4_checkout_enabled_notice(), _render_table() (+10 more)

### Community 48 - "properties"
Cohesion: 0.06
Nodes (33): default, description, type, description, minimum, type, description, format (+25 more)

### Community 49 - "_brace_delta"
Cohesion: 0.10
Nodes (10): _brace_delta(), _check_generated_brace_balance(), test_brace_delta_braced_word_quote_space_quote_is_literal(), test_brace_delta_full_line_comment_skipped(), test_brace_delta_prev_open_brace_quote_is_literal(), test_brace_delta_quoted_string_with_escaped_quote(), test_brace_delta_regression_guards_for_legal_quote_constructs(), test_brace_delta_repro_fixture_yields_zero() (+2 more)

### Community 50 - "test_p4_commands.py"
Cohesion: 0.16
Nodes (25): render_p4_commands(), _data_lines(), _make_ctx(), _make_manifest(), _prov(), _record(), _Sink, test_banner_comments_are_present_and_trailing_newline() (+17 more)

### Community 52 - "crash_harness.py"
Cohesion: 0.12
Nodes (7): CrashAt, _get_active_point(), inject_crash_at(), decorator(), wrapper(), maybe_crash(), _set_active_point()

### Community 53 - "FileTreatment"
Cohesion: 0.09
Nodes (37): FileTreatment, TrimmerService, _CopyFailingFS, _ExplodingFS, _manifest(), _manifest_full_copy_then_proc_trim_then_remove(), _parsed(), _proc() (+29 more)

### Community 54 - "properties"
Cohesion: 0.06
Nodes (37): properties, description, minLength, type, description, items, minItems, type (+29 more)

### Community 55 - "test_stack_graph.py"
Cohesion: 0.09
Nodes (29): compute_stack_order(), _base(), _empty_parsed(), _stage(), test_compiled_manifest_accepts_empty_stack_order_with_any_stages(), test_compiled_manifest_accepts_valid_topological_stack_order(), test_compiled_manifest_rejects_duplicate_names_in_stack_order(), test_compiled_manifest_rejects_stack_order_not_permutation_of_stages() (+21 more)

### Community 56 - "test_v2_check_script.py"
Cohesion: 0.07
Nodes (30): check_p4_available(), checkout_files(), revert_files(), _check(), _flawed_layers(), _gate(), _good_layers(), _slugs() (+22 more)

### Community 57 - "ChopperRunner"
Cohesion: 0.11
Nodes (4): ChopperRunner, _seed_stages_domain(), TestGenerateStackPipeline, TestP1ConfigGate

### Community 58 - "Path"
Cohesion: 0.15
Nodes (3): _seed_valid_domain(), TestTrimSubcommand, _write_base_json()

### Community 59 - "properties"
Cohesion: 0.06
Nodes (35): minimum, type, minimum, type, minimum, type, minimum, type (+27 more)

### Community 61 - "ExtractorDiagnostic"
Cohesion: 0.11
Nodes (8): _deduplicate_short_names(), ExtractorDiagnostic, _message_for(), TestPrivateHelperBranches, test_parser_message_for_dpa_name_mismatch(), test_parser_message_for_dpa_orphan(), test_parser_message_for_non_brace_body(), test_parser_message_for_raises_assertion_on_unmapped_kind()

### Community 62 - "type"
Cohesion: 0.08
Nodes (32): description, items, minItems, type, description, items, minItems, type (+24 more)

### Community 63 - "properties"
Cohesion: 0.06
Nodes (34): minimum, type, minimum, type, minimum, type, minimum, type (+26 more)

### Community 64 - "simulate_trim_in_memory"
Cohesion: 0.09
Nodes (16): _read_text(), simulate_trim_in_memory(), SimulatedTrim, _ctx(), _fake_ctx(), _FakeFS, _Progress, test_read_text_latin1_fallback_oserror_returns_none() (+8 more)

### Community 65 - "StageDefinition"
Cohesion: 0.08
Nodes (21): ChopperError, UnknownDiagnosticCodeError, StageDefinition, _base(), _empty_parsed(), test_aggregate_and_standalone_together(), test_aggregate_stack_registered_when_generate_stack_on(), test_no_aggregate_when_generate_stack_off() (+13 more)

### Community 66 - "ParsedFile"
Cohesion: 0.12
Nodes (6): ParsedFile, _make_proc(), TestParsedFile, TestParseResult, TestProcEntryCallsContract, TestProcEntryLineInvariants

### Community 67 - "properties"
Cohesion: 0.10
Nodes (20): description, minLength, type, description, minItems, type, description, type (+12 more)

### Community 68 - "type"
Cohesion: 0.21
Nodes (15): description, items, minItems, type, items, items, items, minLength (+7 more)

### Community 69 - "file_bug_report.py"
Cohesion: 0.07
Nodes (40): Bug Report issue template, .chopper/chopper_run.json artifact, chopper trim, chopper trim --dry-run, chopper validate, .chopper/diagnostics.json artifact, EC site / zone field, PE-02 diagnostic example (unbalanced braces) (+32 more)

### Community 70 - "test_cli_chained_actions.py"
Cohesion: 0.29
Nodes (25): _base_with_main_only(), _run_pipeline(), _stage_by_name(), test_action_plus_fe_in_later_layer_downgrades_f1_with_vw21(), test_action_step_references_pe_dropped_proc_stages_unchanged(), test_add_stage_after_registers_generated_tcl_and_orders_stage(), test_add_stage_before_inserts_ahead_of_anchor(), test_add_step_after_same_anchor_three_features_preserve_order() (+17 more)

### Community 71 - "_make_ctx"
Cohesion: 0.12
Nodes (11): _make_ctx(), _seed_good_domain(), test_runner_accepts_command_label(), test_runner_case4_exits_with_code_2(), test_runner_full_dry_run_happy_path(), test_runner_returns_run_result_with_summary(), test_runner_uses_injected_providers(), test_runner_writes_audit_bundle_in_dry_run() (+3 more)

### Community 72 - "$defs"
Cohesion: 0.13
Nodes (15): additionalProperties, oneOf, required, type, $defs, addStageAction, flowAction, stageDefinition (+7 more)

### Community 73 - "TrimReport"
Cohesion: 0.08
Nodes (15): p4_opened_paths(), TrimReport, _with_updated_companion_bytes(), _build_report(), _mark_interrupted(), tcl_output_paths(), _tcl_output_paths(), _with_updated_artifacts() (+7 more)

### Community 74 - "generators/test_service.py"
Cohesion: 0.19
Nodes (12): _make_ctx(), _manifest_with_stages(), _manifest_with_stages_and_stack(), test_service_does_not_emit_stack_files_when_flag_off(), test_service_dry_run_builds_artifacts_but_writes_nothing(), test_service_dry_run_builds_stack_artifacts_but_writes_nothing(), test_service_emits_aggregate_and_standalone_together(), test_service_emits_aggregate_stack_when_flag_on() (+4 more)

### Community 75 - "DomainStateService"
Cohesion: 0.22
Nodes (9): DomainStateService, test_case_1_domain_only(), test_case_2_both_present(), test_case_3_backup_only(), test_case_4_emits_ve21_and_returns_state(), test_custom_roots_are_honoured(), test_domain_state_carries_no_hand_edit_detection(), test_dry_run_does_not_affect_classification() (+1 more)

### Community 76 - "LocalFS"
Cohesion: 0.09
Nodes (30): LocalFS, _build_cli_args(), _run_pipeline(), test_cmd_loc_baseline_fallback_when_pipeline_aborts_before_p3(), test_cmd_validate_trim_loc_chain_on_real_overlay(), test_fe_glob_matching_base_files_removes_each_with_vw21(), test_feature_fe_glob_matches_nothing_emits_ve27(), test_glob_fi_matches_subdir_files() (+22 more)

### Community 77 - "test_sloc_coverage.py"
Cohesion: 0.11
Nodes (11): test_sloc_csv_branch_counts_only_data_rows(), test_sloc_csv_skips_comma_only_rows(), test_sloc_hash_comment_blank_line_skipped(), test_sloc_json_extension_counts_nonblank_lines(), test_sloc_many_batch_path_uses_python_fallback_when_env_set(), test_sloc_many_cloc_batch_falls_back_per_slot_when_cloc_unavailable(), test_sloc_many_empty_list_returns_empty(), test_sloc_python_backend_json_extension() (+3 more)

### Community 78 - "test_service_feature_procs.py"
Cohesion: 0.18
Nodes (9): test_absent_procs_pointer_preserves_version_behavior(), test_procs_existence_uses_backup_on_retrim(), test_procs_resolved_order_partial_duplicates_and_independent_vars(), test_procs_schema_path_and_version_contract(), _base(), _feature(), _fpath(), TestFeatureVarsResolution (+1 more)

### Community 79 - ".build"
Cohesion: 0.07
Nodes (15): _emit_ve10(), _emit_ve19(), _emit_ve20(), _emit_ve25(), _emit_ve23(), _emit_ve37(), test_render_diagnostics_includes_path_and_lineno(), test_render_diagnostics_suppresses_ti01() (+7 more)

### Community 80 - "properties"
Cohesion: 0.10
Nodes (20): description, type, description, minLength, type, additionalProperties, description, type (+12 more)

### Community 81 - "ProcRemoval"
Cohesion: 0.20
Nodes (4): ProcRemoval, _make_provenance(), TestCompiledManifest, TestProcRemoval

### Community 82 - "properties"
Cohesion: 0.08
Nodes (25): description, minLength, type, description, minItems, type, description, type (+17 more)

### Community 83 - "properties"
Cohesion: 0.10
Nodes (20): description, type, description, minLength, type, description, type, properties (+12 more)

### Community 84 - "resolve_feature_names"
Cohesion: 0.14
Nodes (4): FeatureLookupResult, resolve_feature_names(), _make_domain(), TestResolveFeatureNames

### Community 85 - "pytest"
Cohesion: 0.05
Nodes (12): test_replace_stage_with_identical_name_skips_load_from_rewrite(), test_schema_dir_raises_when_missing(), test_source_root_is_domain_without_backup(), test_source_root_prefers_backup_once_it_exists_on_disk(), test_source_root_tracks_a_backup_created_mid_run(), test_internal_error_rejects_empty_kind(), test_shadow_event_rejects_empty_layer(), test_shadow_event_rejects_empty_prior_layer() (+4 more)

### Community 86 - "test_bug_report_regressions.py"
Cohesion: 0.10
Nodes (7): _calls_by_proc(), _diagnostic_kinds(), TestDpaMultilineContinuation, TestNonTclSkippedAtEnumeration, TestQuotedSemicolon, TestRegexLiteralOpacity, TestSwitchPatternLabels

### Community 87 - "ParserService"
Cohesion: 0.06
Nodes (16): ParserService, test_proc_extractor_handles_unclosed_body(), test_proc_extractor_newline_between_args_and_body(), test_proc_extractor_skips_computed_proc_name(), test_proc_extractor_unclosed_brace_entry_none_pw03_none(), _make_ctx(), TestDeterminism, TestDiagnosticForwarding (+8 more)

### Community 88 - "feature-v1.schema.json"
Cohesion: 0.08
Nodes (25): additionalProperties, description, description, type, description, minLength, type, description (+17 more)

### Community 89 - "parse_file"
Cohesion: 0.15
Nodes (5): parse_file(), _translate_extractor_diagnostic(), test_edge_case_fixture_parses_without_crashing(), test_parse_file_unbalanced_braces_no_diagnostic_callback(), TestParseFile

### Community 90 - "properties"
Cohesion: 0.09
Nodes (23): additionalProperties, description, properties, type, description, type, metadata, owner (+15 more)

### Community 91 - "test_files_exclude_p4.py"
Cohesion: 0.29
Nodes (13): render_files_exclude_p4(), _data_lines(), _make_ctx(), _make_manifest(), _prov(), _record(), test_banner_present_and_trailing_newline(), test_empty_record_produces_no_op_marker() (+5 more)

### Community 92 - "extract_body_refs"
Cohesion: 0.12
Nodes (6): _bracket_is_escaped(), extract_body_refs(), classify_call_candidate(), should_suppress_first_word(), _body_refs(), TestDirectBodyExtractor

### Community 93 - "Chopper Agent Memory"
Cohesion: 0.27
Nodes (9): Chopper Agent Memory, Base Under 5000 SLOC Target (4858/4398), cdns Conformal Domain (42 features), Individual and Leave-One-Out Feature Matrix, Report Initialization Source-Partition Regression, September FEV JSON Resynthesis, CLI_REFERENCE SLOC Counted-Types Drift, snps Formality Domain (23 features) (+1 more)

### Community 94 - "ProcEntry"
Cohesion: 0.13
Nodes (7): ProcEntry, _Range, _span_for(), TestProcEntryCanonicalName, TestProcEntryOptionalSpans, test_proc_dropper_includes_leading_comment_in_drop_range(), test_proc_dropper_span_for_absorbs_dpa_and_comment()

### Community 95 - "build_parser"
Cohesion: 0.13
Nodes (15): _add_input_args(), build_parser(), test_build_parser_has_four_subcommands(), test_global_flags_are_parsed_before_subcommand(), test_main_pre_runner_exception_writes_internal_error(), _fake_internal_error(), test_missing_subcommand_is_error(), test_p4_flag_not_available_on_other_subcommands() (+7 more)

### Community 96 - "07_base_full/jsons/base.json"
Cohesion: 0.12
Nodes (16): description, domain, files, exclude, include, options, cross_validate, generate_stack (+8 more)

### Community 97 - "domain"
Cohesion: 0.13
Nodes (15): additionalProperties, properties, required, type, description, type, domain, name (+7 more)

### Community 98 - "RichProgress"
Cohesion: 0.13
Nodes (3): RichProgress, TestRichProgressAvailable, TestRichUnavailableFallback

### Community 99 - "Providers / default_providers"
Cohesion: 0.13
Nodes (22): Release 4.11.0 (one composer, chopper.app layer), AuditService (P7), ChopperRunner, CompanionSyncService (P5d), CompilerService (P3 ordered overlay), ConfigService (P1), DomainStateService (P0), execute_output() P5 Sequence (+14 more)

### Community 100 - "properties"
Cohesion: 0.10
Nodes (21): default, description, type, default, description, type, default, description (+13 more)

### Community 101 - "properties"
Cohesion: 0.10
Nodes (21): default, description, type, default, description, type, default, description (+13 more)

### Community 102 - "feature-v2.schema.json"
Cohesion: 0.08
Nodes (24): additionalProperties, additionalProperties, oneOf, required, type, $defs, addStageAction, flowAction (+16 more)

### Community 103 - "properties"
Cohesion: 0.12
Nodes (17): additionalProperties, properties, required, type, minimum, type, minimum, type (+9 more)

### Community 105 - "properties"
Cohesion: 0.09
Nodes (22): description, type, additionalProperties, description, properties, required, type, description (+14 more)

### Community 106 - "properties"
Cohesion: 0.08
Nodes (25): description, type, description, minLength, type, description, type, properties (+17 more)

### Community 107 - "test_call_extractor_sources.py"
Cohesion: 0.14
Nodes (15): is_dynamic_path(), strip_quotes(), test_call_extractor_strip_quotes_braces(), test_strip_quotes_returns_value_unchanged_when_short(), _extract(), test_bracket_dynamic_source_path_is_consumed_but_not_returned(), test_dynamic_path_helper_detects_variables_and_brackets(), test_dynamic_source_path_is_consumed_but_not_returned() (+7 more)

### Community 109 - "count_sloc"
Cohesion: 0.07
Nodes (22): _generated_rows(), _is_excluded_artifact(), _outcome_rows(), _safe_sloc(), TrimStatRow, _count_csv(), _count_hash_comment(), count_raw() (+14 more)

### Community 110 - "test_fs_walk_coverage.py"
Cohesion: 0.06
Nodes (15): _enumerate_domain_files(), test_config_enumerate_handles_list_oserror(), test_config_enumerate_handles_stat_oserror(), stat(), test_enumerate_domain_files_skips_child_outside_domain(), test_load_and_hydrate_feature_raw_none_returns_none(), test_every_domain_walk_shares_one_exclusion_rule(), test_walk_files_chopper_direct_child_of_root_skipped() (+7 more)

### Community 111 - "test_audit_artifacts_golden.py"
Cohesion: 0.18
Nodes (8): _load_artifact(), _normalize(), _seed_valid_domain(), test_chopper_run_json_shape(), test_compiled_manifest_json_shape(), test_dependency_graph_json_shape(), test_trim_report_json_shape(), trimmed_domain()

### Community 112 - "type"
Cohesion: 0.09
Nodes (28): description, items, minItems, type, items, items, items, minLength (+20 more)

### Community 113 - "procs"
Cohesion: 0.12
Nodes (16): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+8 more)

### Community 114 - "properties"
Cohesion: 0.11
Nodes (19): properties, description, type, owner, related_appvars, related_ivars, tags, wiki (+11 more)

### Community 115 - "cloc_backend.py"
Cohesion: 0.19
Nodes (8): cloc_script_path(), count_sloc_via_cloc(), count_sloc_via_cloc_batch(), is_available(), _perl_executable(), _selftest(), test_count_sloc_via_cloc_batch_returns_nones_on_json_decode_error(), test_count_sloc_via_cloc_batch_returns_nones_on_subprocess_failure()

### Community 116 - "LocReport"
Cohesion: 0.15
Nodes (9): _fmt_pct(), render_loc_report(), LocReport, TreatmentBucket, build_loc_report_baseline_only(), test_render_loc_report_writes_note_when_no_lines(), _empty_buckets(), TestLocReportPercents (+1 more)

### Community 117 - "Parser Module Specification"
Cohesion: 0.12
Nodes (20): ChopperContext, CollectingSink, DiagnosticSink, FileSystemPort, InMemoryFS, LocalFS, make_test_context() Test Helper, PresentationConfig (+12 more)

### Community 118 - "intel_header_text"
Cohesion: 0.12
Nodes (11): intel_header_text(), emit_standalone_stack(), test_intel_header_text_explicit_year_skips_datetime_now(), test_intel_header_text_uses_current_year_when_none(), test_intel_header_text_year_none_derives_current_year(), test_emit_flow_stack_full_record_line_order(), test_emit_standalone_stack_basic_shape(), test_emit_standalone_stack_existing_copyright_is_not_duplicated() (+3 more)

### Community 119 - "parser/test_service_coverage.py"
Cohesion: 0.13
Nodes (10): test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror(), __init__(), test_parser_enumerate_skips_files_with_bad_stat(), __init__(), stat(), test_parser_full_domain_walk_skips_paths_outside_source_root(), test_parser_normalize_absolute_path_outside_domain_returned_as_is(), test_parser_normalize_windows_absolute_outside_domain_returned_as_is() (+2 more)

### Community 120 - "chopper/__init__.py"
Cohesion: 0.13
Nodes (4): _pyproject_version(), test_package_version_falls_back_to_pyproject(), _missing(), test_package_version_uses_unknown_when_pyproject_unreadable()

### Community 121 - "08_base_plus_one_feature/jsons/features/dft.feature.json"
Cohesion: 0.14
Nodes (13): description, domain, files, include, flow_actions, metadata, owner, tags (+5 more)

### Community 122 - "pipeline_signoff.feature.json"
Cohesion: 0.17
Nodes (11): depends_on, description, domain, files, include, flow_actions, metadata, owner (+3 more)

### Community 123 - "Acquire Codebase Knowledge Skill"
Cohesion: 0.16
Nodes (16): ARCHITECTURE.md Template, CONCERNS.md Template, CONVENTIONS.md Template, INTEGRATIONS.md Template, STACK.md Template, STRUCTURE.md Template, TESTING.md Template, Inquiry Checkpoints Reference (+8 more)

### Community 124 - "run-result-v1.schema.json"
Cohesion: 0.25
Nodes (7): additionalProperties, description, $id, required, $schema, title, type

### Community 125 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 126 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 127 - "properties"
Cohesion: 0.29
Nodes (7): description, type, description, type, properties, hint, path

### Community 128 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 129 - "exclude"
Cohesion: 0.08
Nodes (27): description, items, minItems, type, additionalProperties, minProperties, properties, type (+19 more)

### Community 130 - "test_tool_commands.py"
Cohesion: 0.19
Nodes (6): _Entry, _Package, test_load_pool_reads_user_files(), test_load_pool_reports_missing_user_file(), test_load_pool_treats_missing_builtin_package_as_empty(), test_load_pool_unions_sorted_builtin_command_files()

### Community 131 - "StageSpec"
Cohesion: 0.18
Nodes (16): StageSpec, emit_flow_stack(), TestStageSpec, test_emit_flow_stack_dependencies_override_load_from(), test_emit_flow_stack_empty_command_omits_j_line(), test_emit_flow_stack_empty_exit_codes_omits_l_line(), test_emit_flow_stack_extra_inputs_follow_authored_inputs_on_every_record(), test_emit_flow_stack_header_is_unconditional() (+8 more)

### Community 133 - "_key"
Cohesion: 0.17
Nodes (4): _is_descendant(), _key(), _rebase(), test_copy_tree_recursively_copies_nested_subdirectory()

### Community 134 - "config/test_service.py"
Cohesion: 0.15
Nodes (6): _CollectingSink, _NullProgress, TestRealFilesystemEncoding, read_text(), read_text(), test_config_service_collects_surface_files_from_all_sections()

### Community 135 - "properties"
Cohesion: 0.11
Nodes (18): minimum, type, minimum, type, additionalProperties, description, properties, type (+10 more)

### Community 136 - "render_p4_checkout_notice"
Cohesion: 0.18
Nodes (5): render_p4_checkout_notice(), _FakeStream, TestColorBehavior, TestDefaultStream, TestMessageContent

### Community 137 - "test_trace_service_coverage.py"
Cohesion: 0.22
Nodes (5): _is_dynamic(), test_is_dynamic_true_for_variable_substitution(), test_path_from_canonical_no_separator_returns_none(), test_trace_dynamic_tokens_short_circuit(), test_trace_resolve_token_skipped_for_dynamic()

### Community 138 - "emit_stage_tcl"
Cohesion: 0.12
Nodes (11): intel_header_lines(), emit_stage_tcl(), stage_output_path(), test_emit_stage_tcl_existing_copyright_header_is_not_duplicated(), test_emit_stage_tcl_header_is_line_one_then_banner_then_steps(), test_emit_stage_tcl_includes_load_from_when_set(), test_emit_stage_tcl_preserves_steps_verbatim(), test_emit_stage_tcl_regeneration_from_own_output_is_idempotent() (+3 more)

### Community 139 - "_warn_if_cwd_will_be_renamed"
Cohesion: 0.12
Nodes (8): _warn_if_cwd_will_be_renamed(), test_check_project_paths_resolvable_unresolvable_domain_exits_2(), test_resolve_domain_root_backup_redirect_from_name_mode(), test_warn_if_cwd_will_be_renamed_no_warning_when_cwd_outside(), test_warn_if_cwd_will_be_renamed_oserror_returns_silently(), test_warn_if_cwd_will_be_renamed_silent_when_backup_exists(), test_warn_if_cwd_will_be_renamed_silent_when_cwd_outside_domain(), test_warn_if_cwd_will_be_renamed_writes_to_stderr_when_cwd_inside_domain()

### Community 140 - "power_analysis.feature.json"
Cohesion: 0.17
Nodes (11): depends_on, description, domain, files, include, flow_actions, metadata, owner (+3 more)

### Community 141 - "10_chained_features_depends_on/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 142 - "TestChopperContext"
Cohesion: 0.24
Nodes (3): _make_ctx(), _StubProgress, TestChopperContext

### Community 143 - "source"
Cohesion: 0.50
Nodes (4): source, description, enum, type

### Community 144 - "file"
Cohesion: 0.20
Nodes (10): description, minLength, pattern, type, properties, description, minItems, type (+2 more)

### Community 145 - "procEntry"
Cohesion: 0.13
Nodes (15): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+7 more)

### Community 146 - "trace_service.py"
Cohesion: 0.14
Nodes (12): _candidate_qnames(), _emit_cycle_diagnostics(), _emit_ti01(), _emit_tw01(), _emit_tw02(), _emit_tw03(), _emit_tw04(), _path_from_canonical() (+4 more)

### Community 147 - "topo_sort_features"
Cohesion: 0.27
Nodes (3): topo_sort_features(), _make_feat(), TestTopoSort

### Community 148 - "AuditManifest"
Cohesion: 0.21
Nodes (4): AuditManifest, _art(), TestAuditManifest, TestRunRecord

### Community 150 - "_make_ctx"
Cohesion: 0.21
Nodes (6): _make_ctx(), _base_with_reference_file(), test_two_stages_sharing_one_reference_file_resolve_independently(), TestBaseStageReferenceFileHappyPath, TestReferenceFileBackupRootAware, TestReferenceFileVE39

### Community 152 - "load_base"
Cohesion: 0.20
Nodes (7): load_base(), load_feature(), _load_files_section(), _load_procedures_section(), _load_stage_def(), _schema_version(), test_load_procedures_section_exclude_with_procs_appends()

### Community 153 - "dft_support.feature.json"
Cohesion: 0.17
Nodes (11): description, domain, files, include, metadata, owner, tags, name (+3 more)

### Community 154 - "08_base_plus_one_feature/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 155 - "Rule R1 (Ordered Overlay, Last Mention Wins)"
Cohesion: 0.07
Nodes (36): Action Vocabulary (FlowBuilder 7 + replace_step/replace_stage), Aggregate <domain>.stack, @n Instance Targeting, dependency_graph.json, F1 File-Level Trimming, F2 Proc-Level Trimming, F3 Run-File Generation, Feature vars/procs sourcing files (<flow>_feature_vars.tcl / <flow>_feature_procs.tcl) (+28 more)

### Community 156 - "internal_error"
Cohesion: 0.14
Nodes (14): additionalProperties, description, properties, required, type, description, type, description (+6 more)

### Community 157 - "artifacts_present"
Cohesion: 0.13
Nodes (15): description, items, type, uniqueItems, description, items, type, pattern (+7 more)

### Community 158 - "test_determinism.py"
Cohesion: 0.16
Nodes (5): _bfs_visit(), test_bfs_visit_is_deterministic_under_input_shuffling(), test_dump_model_is_idempotent(), test_dump_model_is_insertion_order_independent(), _tree()

### Community 160 - "chopper.app Application Layer"
Cohesion: 0.09
Nodes (28): adapters/, AppError, ChopperError (exit code 3), ChopperRunner (orchestrator/runner.py, single composer), cli/ (thin adapter), core/, default_providers() / Providers bundle, DIAGNOSTIC_CODES.md (+20 more)

### Community 161 - "test_models.py"
Cohesion: 0.21
Nodes (10): _outcome(), test_file_outcome_rejects_full_copy_with_procs_removed(), test_file_outcome_rejects_negative_bytes(), test_file_outcome_rejects_remove_with_bytes_out(), test_file_outcome_rejects_unsorted_procs(), test_trim_report_accepts_consistent_totals(), test_trim_report_rejects_derived_count_drift(), test_trim_report_rejects_proc_count_drift() (+2 more)

### Community 163 - "Project JSON"
Cohesion: 0.14
Nodes (17): Chopper Agent Operating Guide, Portable domain-only agent kit, Claude Code Guide, Base JSON, depends_on (feature prerequisites), Domain, Domain Boundary, --domain Name Resolution via $ward (+9 more)

### Community 164 - "GitNexus Guide Skill"
Cohesion: 0.22
Nodes (9): GitNexus CLI Skill, GitNexus Debugging Skill, GitNexus Exploring Skill, GitNexus Context Tool, GitNexus Guide Skill, GitNexus Process Resource, GitNexus Query Tool, GitNexus Impact Analysis Skill (+1 more)

### Community 165 - "09_base_plus_multiple_features/jsons/features/dft.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 166 - "09_base_plus_multiple_features/jsons/features/power.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 167 - "coverage_reporting.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 168 - "14_cross_feature_skip_if_no_stage/jsons/features/dft.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 169 - "main"
Cohesion: 0.19
Nodes (3): main(), TestCleanupSubcommand, TestValidateSubcommand

### Community 170 - "properties"
Cohesion: 0.18
Nodes (11): additionalProperties, oneOf, properties, required, type, addStepAction, reference_file, description (+3 more)

### Community 171 - "diagnostic-v1.schema.json"
Cohesion: 0.25
Nodes (7): additionalProperties, description, $id, required, $schema, title, type

### Community 172 - "stageDefinition"
Cohesion: 0.20
Nodes (10): $defs, procEntry, stageDefinition, additionalProperties, required, type, additionalProperties, oneOf (+2 more)

### Community 173 - "type"
Cohesion: 0.07
Nodes (35): description, items, minItems, type, items, items, description, items (+27 more)

### Community 174 - "Future Considerations (FD Ledger)"
Cohesion: 0.12
Nodes (13): Release 4.9.0 (opt-in insert_markers), Diagnostic Dataclass and Dedupe Key, FD-01 Advanced Namespace Resolution, FD-02 Cross-Domain Dependency Awareness, FD-08 Feature Mutual-Incompatibility (incompatible_with, adopted 4.6.0), FD-09 Benchmark Harness + Phase Budgets, FD-10 Machine-Readable CLI Output (--json/--jsonl), FD-12 Template-Script Generation (+5 more)

### Community 175 - "render_p4_checkout_opened"
Cohesion: 0.23
Nodes (3): render_p4_checkout_opened(), TestMultiDomain, TestSingleDomain

### Community 176 - "test_input_preserver_coverage.py"
Cohesion: 0.21
Nodes (7): preserve_input_sources(), _anchored_ctx(), test_input_preserver_copies_jsons_dir_from_backup(), test_input_preserver_copies_out_of_tree_sources(), test_input_preserver_emits_vw20_on_mkdir_failure(), mkdir(), test_preserve_input_sources_project_and_features_appended()

### Community 177 - "CompiledManifest"
Cohesion: 0.06
Nodes (24): loc_report(), _render_loc_table(), InternalError, RunResult, CompiledManifest, ParseResult, GeneratedArtifact, GeneratorService (+16 more)

### Community 178 - "14_cross_feature_skip_if_no_stage/jsons/features/power.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 180 - "lookup"
Cohesion: 0.21
Nodes (4): all_codes(), _Entry, lookup(), TestRegistry

### Community 181 - "base-v2.schema.json"
Cohesion: 0.18
Nodes (10): additionalProperties, anyOf, description, $id, description, type, required, $schema (+2 more)

### Community 184 - "01_base_files_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, exclude, include, owner, $schema

### Community 185 - "04_base_files_and_procs/jsons/base.json"
Cohesion: 0.20
Nodes (9): description, domain, files, include, owner, procedures, exclude, include (+1 more)

### Community 186 - "05_base_files_and_stages/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, files, include, owner, $schema, stages, tool

### Community 187 - "properties"
Cohesion: 0.18
Nodes (11): additionalProperties, oneOf, properties, required, type, addStepAction, reference_file, description (+3 more)

### Community 188 - "top_codes"
Cohesion: 0.20
Nodes (10): additionalProperties, properties, required, code, count, top_codes, description, items (+2 more)

### Community 189 - "procs"
Cohesion: 0.17
Nodes (12): description, minLength, pattern, type, properties, description, minItems, minLength (+4 more)

### Community 190 - "phase"
Cohesion: 0.50
Nodes (4): description, enum, type, phase

### Community 191 - "exit_code"
Cohesion: 0.50
Nodes (4): description, enum, type, exit_code

### Community 192 - "SilentProgress"
Cohesion: 0.15
Nodes (5): SilentProgress, domain_summary(), test_make_domain_run_result_generated_and_remove(), test_render_loc_table_baseline_only_when_manifest_none(), test_render_loc_table_with_full_manifest()

### Community 193 - "test_render_files_removed_shadowed_by_label"
Cohesion: 0.20
Nodes (3): test_before_root_returns_domain_root_when_no_backup(), test_render_files_removed_shadowed_by_label(), test_render_files_removed_shadowed_by_pe_label()

### Community 194 - "test_loaders.py"
Cohesion: 0.22
Nodes (4): load_project(), test_load_base_emits_ve03_for_empty_procs_array_in_exclude(), test_load_flow_action_unmapped_action_raises(), TestLoadProject

### Community 195 - "header.py"
Cohesion: 0.20
Nodes (4): _has_own_header(), needs_header(), test_needs_header_is_false_for_chopper_generated_output(), test_needs_header_vectors()

### Community 197 - "stack_emitter.py"
Cohesion: 0.20
Nodes (5): aggregate_stack_path(), _render_record(), standalone_stack_path(), test_aggregate_stack_path_uses_domain_basename(), test_standalone_stack_path_uses_stage_name()

### Community 198 - "header_domain/.chopper/input_base.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, options, cross_validate, generate_stack, insert_markers (+2 more)

### Community 199 - "TokenKind"
Cohesion: 0.08
Nodes (25): extract_source_path_with_indices(), classify_and_handle(), compute_skip_indices(), find_command_end(), is_array_set(), is_string_match(), last_lbrace_at_depth(), mark_opaque_arg_braces() (+17 more)

### Community 200 - "header_domain/jsons/base.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, options, cross_validate, generate_stack, insert_markers (+2 more)

### Community 201 - "Chopper onboarding brochure"
Cohesion: 0.67
Nodes (3): Chopper onboarding brochure, Project branch trim window, SNORT

### Community 202 - "08_base_plus_one_feature/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 203 - "09_base_plus_multiple_features/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 204 - "10_chained_features_depends_on/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 205 - "11_project_base_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 206 - "14_cross_feature_skip_if_no_stage/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 207 - "check_service_signatures.py"
Cohesion: 0.24
Nodes (5): load_documented_signatures(), load_source_signatures(), main(), normalise_signature(), _signature()

### Community 208 - ".chopper/ Audit Bundle"
Cohesion: 0.07
Nodes (42): F1/F2/F3 Capability Classes, .chopper/ Audit Bundle, CLI Subcommands (validate, trim, loc, cleanup), BaseOptions (CompiledManifest.options), chopper cleanup, chopper loc, chopper_run.json, CLI_REFERENCE.md (+34 more)

### Community 210 - "test_missing_inputs.py"
Cohesion: 0.35
Nodes (6): test_absent_tcl_exclude_target_is_a_no_op_warning(), test_existing_tool_command_files_extend_the_pool(), test_invalid_tool_command_path_is_a_user_error(), test_json_only_examples_report_missing_domain_files(), test_missing_proc_file_is_a_p1_error(), test_proc_paths_are_literal_and_use_pristine_source()

### Community 211 - "expand_vars_entry"
Cohesion: 0.31
Nodes (4): expand_vars_entry(), test_emitter_keeps_block_order_and_emits_exactly_three_optional_lines(), test_pointer_expansion_preserves_parent_and_prefixes_only_basename(), TestExpandVarsEntry

### Community 212 - "base-v1.schema.json"
Cohesion: 0.18
Nodes (10): additionalProperties, anyOf, description, $id, description, type, required, $schema (+2 more)

### Community 213 - "test_call_extractor.py"
Cohesion: 0.18
Nodes (3): test_py_eval_braced_python_payload_is_opaque(), TestConstants, TestEDAFlowCommands

### Community 214 - "test_file_writer.py"
Cohesion: 0.22
Nodes (6): _proc(), test_full_copy_file_dry_run_reports_without_writing(), test_mirror_perms_plus_exec_swallows_chmod_failures(), test_proc_trim_file_dry_run_reports_without_writing(), test_proc_trim_file_sorts_kept_and_removed_proc_names(), test_remove_file_records_zero_bytes_when_backup_is_missing()

### Community 215 - "stageDefinition"
Cohesion: 0.20
Nodes (10): $defs, procEntry, stageDefinition, additionalProperties, required, type, additionalProperties, oneOf (+2 more)

### Community 217 - "test_runner_coverage.py"
Cohesion: 0.06
Nodes (13): test_internal_error_cwd_fallback_uses_tempdir(), test_write_internal_error_log_diagnostic_without_path(), test_write_internal_error_log_with_diagnostic_path_and_lineno(), test_write_internal_error_log_with_diagnostic_path_no_lineno(), test_ensure_executable_oserror_swallowed(), test_mirror_perms_plus_exec_calls_copymode_and_ensure_executable(), test_mirror_perms_plus_exec_noop_on_nonexistent_paths(), test_mirror_perms_plus_exec_tolerates_oserror() (+5 more)

### Community 218 - "_codes"
Cohesion: 0.33
Nodes (3): _codes(), test_source_paths_are_one_literal_tcl_argument(), TestV2Schemas

### Community 219 - "with"
Cohesion: 0.20
Nodes (10): replaceStageAction, with, additionalProperties, properties, required, type, description, minLength (+2 more)

### Community 220 - "15_stage_reference_file/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, files, include, owner, $schema, stages, tool

### Community 221 - "16_feature_vars/project.json"
Cohesion: 0.29
Nodes (6): base, domain, features, notes, project, $schema

### Community 222 - "mini_domain/jsons/features/feature_a.json"
Cohesion: 0.22
Nodes (8): description, files, include, name, procedures, exclude, include, $schema

### Community 223 - "mini_domain/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, procedures, include, $schema

### Community 224 - "test_main_coverage.py"
Cohesion: 0.15
Nodes (4): test_cli_main_last_resort_exception_writes_internal_log(), test_main_programmer_error_handler_returns_1(), test_main_propagates_systemexit(), test_main_returns_exit_code_on_success()

### Community 226 - "ProcEntryRef"
Cohesion: 0.38
Nodes (3): _entries(), ProcEntryRef, TestProcEntryRef

### Community 227 - "glob_match"
Cohesion: 0.31
Nodes (3): glob_match(), test_architecture_glob_examples(), test_segment_and_class_semantics()

### Community 229 - "03_base_stages_only/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, options, generate_stack, owner, $schema, stages, tool

### Community 230 - "06_base_procs_and_stages/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, owner, procedures, exclude, include, $schema, stages

### Community 231 - "11_project_base_only/project.json"
Cohesion: 0.29
Nodes (6): base, domain, notes, owner, project, $schema

### Community 232 - "15_stage_reference_file/jsons/features/dft.feature.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, flow_actions, name, $schema

### Community 233 - "apr_fc.json"
Cohesion: 0.22
Nodes (8): description, domain, options, generate_stack, procs, $schema, stages, vars

### Community 235 - "overlay_replace/jsons/features/feature_a.json"
Cohesion: 0.29
Nodes (6): description, files, exclude, include, name, $schema

### Community 236 - "post_check.feature.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, flow_actions, name, $schema

### Community 237 - "plan_p4_sync.py"
Cohesion: 0.27
Nodes (5): _files_under(), main(), _parse_args(), _quoted(), _write_section()

### Community 238 - "01_base_files_only/.chopper/input_base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, exclude, include, owner, $schema

### Community 239 - "02_base_procs_only/.chopper/input_base.json"
Cohesion: 0.25
Nodes (7): description, domain, owner, procedures, exclude, include, $schema

### Community 241 - "09_base_plus_multiple_features/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 242 - "gen_large_domain.py"
Cohesion: 0.27
Nodes (4): generate_large_domain(), main(), _make_ident(), pytest_large_domain_fixture()

### Community 244 - "_redistribute_coverage_tests.py"
Cohesion: 0.31
Nodes (4): _build_fleet_file(), _collect_imports(), main(), _split_into_sections()

### Community 245 - "test_file_bug_report.py"
Cohesion: 0.50
Nodes (6): _payload(), test_file_bug_report_create_falls_back_when_gh_is_missing(), test_file_bug_report_create_falls_back_when_gh_returns_error(), test_file_bug_report_create_uses_gh_issue_create(), test_file_bug_report_dry_run_writes_body_and_bundle(), test_file_bug_report_rejects_missing_required_fields()

### Community 246 - "Real-world bug-report fixtures README"
Cohesion: 0.43
Nodes (8): diagnostics_file_null_for_p4_p6.md bug, dpa_multiline.tcl fixture, python_braces.py fixture, quoted_semicolon.tcl fixture, regex_literals.tcl fixture, sta_pt production domain (Intel pesg_2026.06), switch_patterns.tcl fixture, Real-world bug-report fixtures README

### Community 247 - "02_base_procs_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, owner, procedures, exclude, include, $schema

### Community 248 - "12_base_with_aggregate_stack/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, options, generate_stack, owner, $schema, stages

### Community 249 - "13_base_with_standalone_stack/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, options, generate_stack, owner, $schema, stages

### Community 250 - "project_dft_only.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 251 - "GitHub API Push Skill"
Cohesion: 0.32
Nodes (6): setup.csh Bootstrap Script, Fallback Venv Skill, Intel EC/HPC URLfilter Policy 241, gh_api_push.py Script, GitHub API Push Skill, Token Acquisition Procedure

### Community 252 - "validate_jsons.py"
Cohesion: 0.33
Nodes (5): iter_json_files(), load_schemas(), main(), parse_args(), validate_file()

### Community 254 - "overlay_no_op_exclude/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 255 - "overlay_remove_only/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 256 - "severity"
Cohesion: 0.50
Nodes (4): severity, description, enum, type

### Community 257 - "project_full.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 258 - "progress-event-v1.schema.json"
Cohesion: 0.22
Nodes (8): additionalProperties, description, $id, oneOf, required, $schema, title, type

### Community 259 - "check_diagnostic_registry.py"
Cohesion: 0.32
Nodes (3): collect_code_references(), load_active_codes(), main()

### Community 261 - "README Changelog"
Cohesion: 0.25
Nodes (7): README Changelog, Release 4.8.1 (no buried shebang / duplicate header), Release 4.9.1 (single-level * glob fix), Release 4.9.2 (project recorded in audit bundle), P-11 Glob Expansion Must Normalize Paths, P-30 Project Metadata Must Flow Through to Audit Artifacts, P-49 Generated Files Must Not Bury a Shebang or Duplicate a Header

### Community 262 - "test_sink_collecting.py"
Cohesion: 0.36
Nodes (4): _diag(), test_emit_dedupe_replaces_in_place(), test_emit_preserves_insertion_order(), test_finalize_returns_severity_counts()

### Community 263 - "steps"
Cohesion: 0.50
Nodes (4): steps, description, minItems, type

### Community 264 - "by_family"
Cohesion: 0.25
Nodes (8): additionalProperties, description, patternProperties, type, ^[VTP][EWI]$, by_family, minimum, type

### Community 267 - "overlay_remove_only/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 269 - "event"
Cohesion: 0.50
Nodes (4): description, enum, type, event

### Community 270 - "overlay_no_op_exclude/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 271 - "feature_typo.json"
Cohesion: 0.33
Nodes (5): description, files, exclude, name, $schema

### Community 272 - "overlay_two_features_same_file/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 273 - "run_mode"
Cohesion: 0.40
Nodes (5): run_mode, default, description, enum, type

### Community 274 - "language"
Cohesion: 0.40
Nodes (5): default, description, enum, type, language

### Community 275 - "R5 Backup-and-Rebuild"
Cohesion: 0.29
Nodes (4): Byte-Identical Determinism Gate (mini_domain golden test), ENGINEERING.md, Non-Functional Requirements (NFR-01..NFR-15), RunConfig / PresentationConfig

### Community 278 - ".test_p3_error_aborts_pipeline_with_exit_1"
Cohesion: 0.13
Nodes (9): _inject_error_at(), _shim(), TestP3CompileGate, _shim(), TestP5TrimGate, _shim(), TestP6PostValidateGates, _shim() (+1 more)

### Community 281 - "feature_drop.json"
Cohesion: 0.33
Nodes (5): description, files, exclude, name, $schema

### Community 282 - "overlay_replace/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 283 - "detail"
Cohesion: 0.50
Nodes (4): additionalProperties, description, type, detail

### Community 284 - "overlay_replace/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 285 - "overlay_two_features_same_file/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 287 - "stages_domain/jsons/base.json"
Cohesion: 0.29
Nodes (6): description, domain, options, generate_stack, $schema, stages

### Community 288 - "chopper_run.json golden shape"
Cohesion: 0.29
Nodes (7): artifacts_present field, chopper_run.json golden shape, diagnostics_summary field, trim_state field, compiled_manifest.json golden shape, contributed_by field, treatment field (full-copy)

### Community 290 - "test_feature_vars.py"
Cohesion: 0.60
Nodes (3): _domain(), test_dry_run_plans_file_without_writing(), test_live_trim_writes_file_and_keeps_vars()

### Community 291 - "test_ascii_only.py"
Cohesion: 0.47
Nodes (3): test_scan_covers_the_tree(), test_tree_is_ascii_only(), _text_files()

### Community 293 - "dop.feature.json"
Cohesion: 0.33
Nodes (5): description, name, procs, $schema, vars

### Community 294 - "fdr.feature.json"
Cohesion: 0.33
Nodes (5): description, name, procs, $schema, vars

### Community 295 - "check_v2.py reference"
Cohesion: 0.40
Nodes (5): Adoption levels, check_v2.py reference, Delta classes (with `--baseline`), Gate, Suggestions

### Community 296 - "v1 → v2 interview question bank"
Cohesion: 0.40
Nodes (4): Round 1 — scope and infrastructure (before any edit), Round 2 — per layer (the base row first, then one row per feature in project order), Round 3 — opportunities (after the migration is green), v1 → v2 interview question bank

### Community 297 - "slug"
Cohesion: 0.33
Nodes (6): slug, description, maxLength, minLength, pattern, type

### Community 300 - "create_latin1_fixture.py"
Cohesion: 0.47
Nodes (3): build_fixture_bytes(), main(), write_fixture()

### Community 301 - "overlay_two_features_same_file/jsons/features/feature_a.json"
Cohesion: 0.33
Nodes (5): description, name, procedures, exclude, $schema

### Community 302 - "feature_b.json"
Cohesion: 0.33
Nodes (5): description, name, procedures, include, $schema

### Community 303 - "exit_codes"
Cohesion: 0.40
Nodes (5): description, items, minItems, type, exit_codes

### Community 304 - "reference_file"
Cohesion: 0.40
Nodes (5): reference_file, description, minLength, pattern, type

### Community 305 - "exit_codes"
Cohesion: 0.40
Nodes (5): description, items, minItems, type, exit_codes

### Community 306 - "elapsed_seconds"
Cohesion: 0.50
Nodes (4): description, minimum, type, elapsed_seconds

### Community 307 - "language"
Cohesion: 0.40
Nodes (5): default, description, enum, type, language

### Community 308 - "phase_index"
Cohesion: 0.40
Nodes (5): description, maximum, minimum, type, phase_index

### Community 309 - "run_mode"
Cohesion: 0.40
Nodes (5): run_mode, default, description, enum, type

### Community 310 - "Trim Report JSON Shape Golden File"
Cohesion: 0.40
Nodes (5): Trim Report JSON Shape Golden File, trim_report file_report field, trim_report proc_report field, trim_report summary field block, trim_report validation_results field

### Community 311 - "vars"
Cohesion: 0.40
Nodes (5): vars, description, minLength, pattern, type

### Community 316 - "cloc.pl vendored tool"
Cohesion: 0.50
Nodes (4): cloc.pl vendored tool, chopper.audit.cloc_backend module, GPL-2.0 license (vendored cloc), chopper.audit.sloc pure-Python fallback

### Community 317 - "options.generate_stack Aggregate Stack Contract"
Cohesion: 0.67
Nodes (4): Example 12 README — Aggregate Scheduler Stack, options.generate_stack Aggregate Stack Contract, Example 13 README — Aggregate + Standalone Stack, standalone_stack Per-Stage Verbatim File

### Community 318 - "json"
Cohesion: 0.16
Nodes (3): _configure_proxy_bypass(), main(), _require_token()

### Community 319 - "code"
Cohesion: 0.50
Nodes (4): description, pattern, type, code

### Community 321 - "dedupe_bucket"
Cohesion: 0.50
Nodes (4): default, description, type, dedupe_bucket

### Community 322 - "message"
Cohesion: 0.50
Nodes (4): description, minLength, type, message

### Community 323 - "outputs"
Cohesion: 0.50
Nodes (4): description, minItems, type, outputs

### Community 324 - "phase_total"
Cohesion: 0.50
Nodes (4): description, enum, type, phase_total

### Community 325 - "context"
Cohesion: 0.50
Nodes (4): additionalProperties, description, type, context

### Community 326 - "line_no"
Cohesion: 0.50
Nodes (4): description, minimum, type, line_no

### Community 327 - "properties"
Cohesion: 0.50
Nodes (4): description, type, properties, message

### Community 328 - "phase"
Cohesion: 0.50
Nodes (4): description, enum, type, phase

### Community 329 - "run_id"
Cohesion: 0.50
Nodes (4): run_id, description, pattern, type

### Community 330 - "schema"
Cohesion: 0.50
Nodes (4): schema, const, description, type

### Community 331 - "step_index"
Cohesion: 0.50
Nodes (4): step_index, description, minimum, type

### Community 332 - "step_total"
Cohesion: 0.50
Nodes (4): step_total, description, minimum, type

### Community 335 - "Agent Local Memory Files (README)"
Cohesion: 0.67
Nodes (3): Agent Local Memory Files (README), Agent Local Memory Files convention, Minimum Template (agent memory)

### Community 337 - "ARCHITECTURE.md (Architecture Doc)"
Cohesion: 0.08
Nodes (45): Contributing to Chopper, Pull Request Checklist, Stage Reference File Example, Stage Reference-File Sourcing, apr_fc example flow, DOP example feature, FDR example feature, Example 16: feature vars/procs sourcing (+37 more)

### Community 338 - "timestamp"
Cohesion: 0.50
Nodes (4): timestamp, description, format, type

### Community 339 - "schema"
Cohesion: 0.50
Nodes (4): schema, const, description, type

## Ambiguous Edges - Review These
- `dpa_multiline.tcl fixture` → `diagnostics_file_null_for_p4_p6.md bug`  [AMBIGUOUS]
  tests/fixtures/bug_reports/README.md · relation: REUSES

## Knowledge Gaps
- **1279 isolated node(s):** `$schema`, `domain`, `owner`, `description`, `include` (+1274 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2968 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **83 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `dpa_multiline.tcl fixture` and `diagnostics_file_null_for_p4_p6.md bug`?**
  _Edge tagged AMBIGUOUS (relation: REUSES) - confidence is low._
- **Why does `Bug Report issue template` connect `file_bug_report.py` to `.chopper/ Audit Bundle`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `chopper cleanup` connect `.chopper/ Audit Bundle` to `file_bug_report.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `ChopperContext` connect `ChopperContext` to `RunConfig`, `CompilerService`, `make_ctx`, `config/test_service.py`, `Diagnostic`, `merge_service.py`, `_ctx`, `writers.py`, `test_audit.py`, `functions.py`, `TestChopperContext`, `test_validator.py`, `trace_service.py`, `_run`, `TracerService`, `FileSystemPort`, `_make_ctx`, `pathlib`, `TestCompanionSyncService`, `_make_glob_ctx`, `CaptureFixture`, `ConfigService`, `commands.py`, `Phase`, `make_ctx`, `test_runner_localfs_e2e.py`, `internal_error.py`, `schema.py`, `flow_resolver.py`, `FileOutcome`, `DomainState`, `test_input_preserver_coverage.py`, `CompiledManifest`, `test_p4_commands.py`, `_brace_delta`, `FileTreatment`, `test_stack_graph.py`, `ChopperRunner`, `SilentProgress`, `simulate_trim_in_memory`, `test_cli_chained_actions.py`, `_make_ctx`, `TrimReport`, `generators/test_service.py`, `DomainStateService`, `LocalFS`, `.build`, `pytest`, `ParserService`, `test_runner_coverage.py`, `test_files_exclude_p4.py`, `count_sloc`, `test_fs_walk_coverage.py`, `LocReport`, `parser/test_service_coverage.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 228 inferred relationships involving `ChopperContext` (e.g. with `domain_summary()` and `loc_report()`) actually correct?**
  _`ChopperContext` has 228 INFERRED edges - model-reasoned connections that need verification._
- **Are the 249 inferred relationships involving `FileTreatment` (e.g. with `domain_summary()` and `_dropped_rows()`) actually correct?**
  _`FileTreatment` has 249 INFERRED edges - model-reasoned connections that need verification._
- **Are the 193 inferred relationships involving `InMemoryFS` (e.g. with `FileStat` and `SimulatedTrim`) actually correct?**
  _`InMemoryFS` has 193 INFERRED edges - model-reasoned connections that need verification._