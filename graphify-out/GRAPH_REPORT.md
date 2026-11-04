# Graph Report - chopper  (2026-11-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 7281 nodes · 17325 edges · 371 communities (291 shown, 80 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 2906 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c81ae4c1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pathlib
- test_audit.py
- ChopperContext
- ConfigService
- CompilerService
- CompiledManifest
- Diagnostic
- make_ctx
- tokenize
- InMemoryFS
- Path
- test_cloc_backend_coverage.py
- _ctx
- NamespaceTracker
- extract_procs
- RunConfig
- _calls
- check_v2.py
- TracerService
- Phase
- test_proc_dropper.py
- make_ctx
- ARCHITECTURE.md (Architecture Doc)
- LocalFS
- FileTreatment
- test_commands.py
- models_config.py
- merge_service.py
- $defs
- test_validator.py
- flow_resolver.py
- ProcEntry
- _collect
- dump_model
- reference
- Rule R1 (Ordered Overlay, Last Mention Wins)
- test_runner_localfs_e2e.py
- cloc_backend.py
- StageDefinition
- test_stack_graph.py
- TokenKind
- functions.py
- _Sink
- StageSpec
- scan.py
- parse_file
- test_indentation.py
- .chopper/ Audit Bundle
- properties
- properties
- properties
- test_commands_coverage.py
- _coverage_helpers.py
- resolve_domain
- write_internal_error_log
- test_p4_commands.py
- TestCompanionSyncService
- properties
- DependencyGraph
- TestLoadFeature
- LoadedConfig
- trim_stats.py
- re
- properties
- generators/test_service.py
- ParserService
- properties
- tokenizer.py
- checkout_files
- _build_run_config
- properties
- Path
- type
- chopper.app Application Layer
- properties
- type
- resolve_feature_names
- test_cli_chained_actions.py
- test_v2_check_script.py
- header.py
- type
- test_files_exclude_p4.py
- test_cli_chained_overlay.py
- build_parser
- Providers / default_providers
- FeatureJson
- test_sloc_coverage.py
- properties
- call_extractor_body.py
- _make_ctx
- test_bug_report_regressions.py
- type
- properties
- properties
- generators/service.py
- test_fs_walk_coverage.py
- _make_proc
- properties
- fs_memory.py
- Project JSON
- Future Considerations (FD Ledger)
- TrimReport
- _key
- RichProgress
- properties
- properties
- properties
- properties
- LocReport
- ParseResult
- ChopperRunner
- Parser Module Specification
- properties
- properties
- Path
- feature-v1.schema.json
- file_bug_report.py
- indentation.py
- test_audit_artifacts_golden.py
- Acquire Codebase Knowledge Skill
- exclude
- exclude
- exclude
- exclude
- properties
- _warn_if_cwd_will_be_renamed
- topo_sort_features
- _brace_delta
- 07_base_full/jsons/base.json
- properties
- CaptureFixture
- render_p4_checkout_notice
- test_trace_service_coverage.py
- AuditManifest
- ProcRemoval
- FileSystemPort
- test_tool_commands.py
- base-v1.schema.json
- base-v2.schema.json
- procs
- procs
- FileProvenance
- P4CheckoutResult
- _StubFS
- Bug Report issue template
- schema.py
- $defs
- procEntry
- artifacts_present
- domain
- config/test_service_coverage.py
- test_models.py
- .test_p3_error_aborts_pipeline_with_exit_1
- _CollectingSink
- _InMemoryFS
- gh_api_push.py
- GitNexus Guide Skill
- .run
- 08_base_plus_one_feature/jsons/features/dft.feature.json
- test_package_smoke.py
- internal_error
- main
- GeneratedArtifact
- plan_p4_sync.py
- package_bug_report.py
- expand_feature_dirs
- render_p4_checkout_opened
- render_p4_branch_analysis
- glob_match
- lookup
- _filter_csv
- _NullFS
- check_service_signatures.py
- dft_support.feature.json
- pipeline_signoff.feature.json
- power_analysis.feature.json
- cmd_cleanup
- _filter_milestone
- _StubFS
- 09_base_plus_multiple_features/jsons/features/dft.feature.json
- 09_base_plus_multiple_features/jsons/features/power.feature.json
- coverage_reporting.feature.json
- 14_cross_feature_skip_if_no_stage/jsons/features/dft.feature.json
- 14_cross_feature_skip_if_no_stage/jsons/features/power.feature.json
- Chopper Agent Memory
- properties
- intel_header_text
- header_domain/.chopper/input_base.json
- header_domain/jsons/base.json
- TestGlobFilesIncludeRegression
- test_missing_inputs.py
- test_vars_emitter.py
- 04_base_files_and_procs/jsons/base.json
- validate_jsons.py
- gen_large_domain.py
- procEntry
- addStageAction
- top_codes
- FileOutcome
- TestChopperContext
- _source_refs
- test_input_preserver_coverage.py
- 03_base_stages_only/jsons/base.json
- 05_base_files_and_stages/jsons/base.json
- 06_base_procs_and_stages/jsons/base.json
- 15_stage_reference_file/jsons/base.json
- apr_fc.json
- items
- progress-event-v1.schema.json
- expand_vars_entry
- subprocess
- mini_domain/jsons/features/feature_a.json
- .test_loc_reflects_excluded_file_in_remove_bucket
- test_file_bug_report.py
- Real-world bug-report fixtures README
- 01_base_files_only/.chopper/input_base.json
- 01_base_files_only/jsons/base.json
- 02_base_procs_only/.chopper/input_base.json
- 02_base_procs_only/jsons/base.json
- 08_base_plus_one_feature/jsons/base.json
- 08_base_plus_one_feature/project.json
- 09_base_plus_multiple_features/jsons/base.json
- 09_base_plus_multiple_features/project.json
- 10_chained_features_depends_on/jsons/base.json
- 10_chained_features_depends_on/project.json
- 11_project_base_only/jsons/base.json
- 12_base_with_aggregate_stack/jsons/base.json
- 13_base_with_standalone_stack/jsons/base.json
- 14_cross_feature_skip_if_no_stage/jsons/base.json
- project_dft_only.json
- project_full.json
- 15_stage_reference_file/jsons/features/dft.feature.json
- README Changelog
- GitHub API Push Skill
- diagnostic-v1.schema.json
- run-result-v1.schema.json
- by_family
- AuditArtifact
- post_check.feature.json
- mini_domain/jsons/base.json
- test_sink_collecting.py
- test_cmd_trim_multi_domain_live_calls_render_trim_stats
- .test_audit_exception_is_swallowed
- test_edge_case_fixture_parses_without_crashing
- _CopyFailingFS
- 11_project_base_only/project.json
- 16_feature_vars/project.json
- properties
- ProcDecision
- R5 Backup-and-Rebuild
- overlay_replace/jsons/features/feature_a.json
- stages_domain/jsons/base.json
- chopper_run.json golden shape
- .test_non_surfaced_file_is_not_copied
- TestRealWorldMessyFormatting
- dop.feature.json
- fdr.feature.json
- slug
- PresentationConfig
- FileStat
- create_latin1_fixture.py
- overlay_no_op_exclude/jsons/base.json
- feature_typo.json
- overlay_no_op_exclude/project.json
- overlay_remove_only/jsons/base.json
- feature_drop.json
- overlay_remove_only/project.json
- overlay_replace/jsons/base.json
- overlay_replace/project.json
- overlay_two_features_same_file/jsons/base.json
- overlay_two_features_same_file/jsons/features/feature_a.json
- feature_b.json
- overlay_two_features_same_file/project.json
- test_count_tree_skips_unreadable_and_non_sloc_files
- test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror
- TestRealWorldScenarios
- test_ascii_only.py
- check_v2.py reference
- v1 → v2 interview question bank
- exit_codes
- language
- reference_file
- reference_file
- vars
- stageDefinition
- phase_index
- Trim Report JSON Shape Golden File
- .test_base_json_missing_domain_file_emits_ve06_aborts
- TestConstants
- test_package_bug_report.py
- cloc.pl vendored tool
- options.generate_stack Aggregate Stack Contract
- dependencies
- steps
- code
- context
- dedupe_bucket
- exit_code
- line_no
- message
- phase
- severity
- source
- detail
- elapsed_seconds
- event
- properties
- phase
- phase_total
- run_id
- schema
- step_index
- step_total
- timestamp
- schema
- _NullProgress
- test_mirror_perms_plus_exec_swallows_chmod_failures
- _Progress
- Path
- _Sink
- Example 14 README — Cross-Feature skip_if_no_stage
- Agent Local Memory Files (README)
- pull_request_template.md
- Chopper onboarding brochure
- Chopper runtime architecture diagram
- _tree
- die
- test_walk_files_oserror_on_list_skips_directory
- test_walk_files_oserror_on_stat_skips_entry
- test_parser_full_domain_walk_skips_paths_outside_source_root
- test_validator_finds_bundled_schemas_from_another_working_directory
- bisect-feature-breakage/SKILL.md
- bootstrap-domain/SKILL.md
- explain-last-run/SKILL.md
- package-bug-artifacts/SKILL.md
- report-chopper-bug/SKILL.md
- validate-my-jsons/SKILL.md
- why-was-dropped/SKILL.md
- presentation/chopper_onboarding.html (Deployed Onboarding Page)
- dependency_graph.json artifact schema (pi_plus, pi_seeds, pt, edges, unresolved)
- P4 File Exclusion List
- test_merge_vw21_action_replace_trim_to_whole_shows_prior_keep
- test_parser_run_skips_files_that_vanish_during_full_domain_walk
- Assign Bug Issues GitHub Actions Workflow
- chopper
- TFM (Tool Flow Manager, CTH R2G)
- Removed Files Provenance Manifest

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
- `default_state()` --uses--> `DomainState`  [INFERRED]
  tests/unit/compiler/_helpers.py → src/chopper/core/models_common.py
- `test_internal_error_rejects_empty_kind()` --uses--> `InternalError`  [INFERRED]
  tests/unit/core/test_models_audit_coverage.py → src/chopper/core/models_audit.py
- `test_sloc_json_path_uses_count_raw()` --calls--> `count_sloc()`  [INFERRED]
  tests/unit/audit/test_sloc_coverage.py → src/chopper/audit/sloc.py
- `test_sloc_unknown_extension_falls_back_to_count_raw()` --calls--> `count_sloc()`  [INFERRED]
  tests/unit/audit/test_sloc_coverage.py → src/chopper/audit/sloc.py
- `Release 4.9.0 (opt-in insert_markers)` --semantically_similar_to--> `FD-17 Opt-In Provenance Markers insert_markers (adopted 4.9.0)`  [INFERRED] [semantically similar]
  README.md → technical_docs/IMPLEMENTATION.md

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

## Communities (371 total, 80 thin omitted)

### Community 0 - "pathlib"
Cohesion: 0.02
Nodes (46): base_candidates(), find_base(), find_project_config(), selected_feature_paths(), DomainLookupResult, DomainTarget, _resolve_by_name(), resolve_target() (+38 more)

### Community 1 - "test_audit.py"
Cohesion: 0.04
Nodes (78): sha256_hex(), AuditService, count_raw(), _before_root(), _build_diag_entries(), _build_file_report(), _build_proc_report(), _build_summary() (+70 more)

### Community 2 - "ChopperContext"
Cohesion: 0.03
Nodes (51): _emit_ve08(), _emit_ve10(), _emit_ve19(), _emit_ve20(), _emit_vw23(), _emit_ve30(), _emit_ve31(), _emit_cycle_diagnostics() (+43 more)

### Community 3 - "ConfigService"
Cohesion: 0.05
Nodes (31): ConfigService, _CollectingSink, _default_state(), test_absent_procs_pointer_preserves_version_behavior(), test_procs_existence_uses_backup_on_retrim(), test_procs_resolved_order_partial_duplicates_and_independent_vars(), test_procs_schema_path_and_version_contract(), _base() (+23 more)

### Community 4 - "CompilerService"
Cohesion: 0.08
Nodes (48): CompilerService, default_state(), files_section(), make_base(), make_feature(), make_loaded(), make_parsed(), proc_ref() (+40 more)

### Community 5 - "CompiledManifest"
Cohesion: 0.04
Nodes (36): loc_report(), _render_loc_table(), copy_tree(), iter_domain_files(), walk_files(), RunResult, DomainState, CompiledManifest (+28 more)

### Community 6 - "Diagnostic"
Cohesion: 0.03
Nodes (20): CollectingSink, Severity, Diagnostic, DiagnosticSummary, DiagnosticSink, _noop_diagnostic(), _Sink, _Sink (+12 more)

### Community 7 - "make_ctx"
Cohesion: 0.08
Nodes (57): resolve_stages(), AddStepAction, RemoveStepAction, ReplaceStepAction, _escape(), marker_pair(), make_ctx(), _make_feature() (+49 more)

### Community 8 - "tokenize"
Cohesion: 0.05
Nodes (18): tokenize(), test_tokenizer_backslash_continuation_increments_line_no(), test_tokenizer_command_position_backslash_newline_advances_line(), test_tokenizer_comment_backslash_newline_advances_line_count(), test_tokenizer_comment_with_backslash_newline_continuation(), test_tokenizer_handles_backslash_line_continuation(), _kinds(), TestBackslashContinuation (+10 more)

### Community 9 - "InMemoryFS"
Cohesion: 0.04
Nodes (62): InMemoryFS, test_fs_memory_copy_file_adds_parent_dirs(), test_fs_memory_copy_file_into_directory_raises(), test_fs_memory_copy_file_missing_source_raises(), test_fs_memory_copy_file_raises_when_dst_is_directory(), test_fs_memory_copy_tree_excludes_chopper_subtree(), test_fs_memory_copy_tree_missing_source_raises(), test_fs_memory_copy_tree_nested_dirs_preserved() (+54 more)

### Community 10 - "Path"
Cohesion: 0.03
Nodes (29): test_autodiscover_base_returns_first_candidate(), test_autodiscover_base_returns_second_candidate(), test_cmd_cleanup_redirects_when_domain_ends_in_backup(), test_cmd_loc_multi_domain_check_project_fails(), test_cmd_loc_multi_domain_propagates_max_exit_code(), test_cmd_loc_returns_exit_2_when_project_paths_unresolvable(), test_cmd_loc_single_domain_project_none_expands_features(), test_cmd_loc_with_project_skips_feature_dir_expansion() (+21 more)

### Community 11 - "test_cloc_backend_coverage.py"
Cohesion: 0.04
Nodes (31): test_cloc_backend_returns_code_on_success(), test_cloc_backend_returns_none_on_json_decode_error(), test_cloc_backend_returns_none_on_nonzero_exit(), test_cloc_backend_returns_none_on_subprocess_error(), test_cloc_backend_returns_none_on_tmpfile_write_error(), test_cloc_backend_returns_none_when_code_not_int(), test_cloc_backend_returns_none_when_no_sum_key(), test_cloc_backend_returns_none_when_unavailable() (+23 more)

### Community 12 - "_ctx"
Cohesion: 0.06
Nodes (41): BaseJson, BaseOptions, _check_paths(), _check_pattern(), _is_glob(), test_emit_vw21_unknown_action_produces_generic_message(), test_emit_cycle_diagnostics_self_loop_emits_tw04(), _codes() (+33 more)

### Community 13 - "NamespaceTracker"
Cohesion: 0.05
Nodes (16): ContextFrame, ContextKind, _looks_computed(), NamespaceTracker, _strip_leading_colons(), TrackerDiagnostic, test_namespace_tracker_post_init_skips_push_when_stack_nonempty(), test_namespace_tracker_rbrace_at_file_root_does_not_pop() (+8 more)

### Community 14 - "extract_procs"
Cohesion: 0.05
Nodes (13): extract_procs(), _diag_kinds(), _procs_by_short(), TestBasic, TestBodyEdgeCases, TestCommentBanner, TestContextSuppression, TestContinuation (+5 more)

### Community 15 - "RunConfig"
Cohesion: 0.05
Nodes (25): RunConfig, _glob_has_matches(), test_format_exclusion_path_falls_back_to_ctx_ward_root(), test_p4_commands_ctx_ward_root_fallback(), test_p4_commands_ward_prefix_valueerror_falls_back_to_domain_relative(), test_p4_commands_ward_relative_exclude_paths(), test_render_files_removed_default_exclude_label(), test_walk_relative_files_list_raises_filenotfound() (+17 more)

### Community 16 - "_calls"
Cohesion: 0.05
Nodes (11): _calls(), TestBasicCalls, TestBracketCalls, TestControlFlowBodies, TestDeterminism, TestEDAFlowCommands, TestEscapedBracketCalls, TestMissingBuiltins (+3 more)

### Community 17 - "check_v2.py"
Cohesion: 0.06
Nodes (40): _adoption(), build(), Bundle, _candidates(), _delta(), file_change(), _expand(), _gate() (+32 more)

### Community 18 - "TracerService"
Cohesion: 0.08
Nodes (19): TracerService, load_pool(), parse_tokens(), make_proc(), _loaded_with_pool(), _manifest_with_seeds(), _parse(), TestAmbiguousMatch (+11 more)

### Community 19 - "Phase"
Cohesion: 0.04
Nodes (23): SilentProgress, open_context(), Phase, ProgressSink, has_errors(), _Progress, _Progress, test_render_diagnostics_includes_path_and_lineno() (+15 more)

### Community 20 - "test_proc_dropper.py"
Cohesion: 0.07
Nodes (41): _backup_path(), _domain_path(), full_copy_file(), proc_trim_file(), annotate_procs(), ProcDropError, _executable_mode(), _make_ctx() (+33 more)

### Community 21 - "make_ctx"
Cohesion: 0.07
Nodes (38): _rollback_late_failure(), test_case_1_domain_only(), test_case_2_both_present(), test_case_3_backup_only(), test_case_4_emits_ve21_and_returns_state(), test_custom_roots_are_honoured(), test_domain_state_carries_no_hand_edit_detection(), test_dry_run_does_not_affect_classification() (+30 more)

### Community 22 - "ARCHITECTURE.md (Architecture Doc)"
Cohesion: 0.08
Nodes (45): Contributing to Chopper, Pull Request Checklist, Stage Reference File Example, Stage Reference-File Sourcing, apr_fc example flow, DOP example feature, FDR example feature, Example 16: feature vars/procs sourcing (+37 more)

### Community 23 - "LocalFS"
Cohesion: 0.09
Nodes (30): LocalFS, _procs_domain(), test_generated_sourcing_files_are_aggregate_stack_inputs(), test_generated_sourcing_files_flow_to_p4_audit_and_loc(), test_missing_and_duplicate_procs_warn(), test_procs_generated_path_collision(), test_procs_generation_and_f1_preservation(), test_v2_without_procs_writes_header_only_file() (+22 more)

### Community 24 - "FileTreatment"
Cohesion: 0.11
Nodes (36): FileTreatment, TrimmerService, _manifest(), _manifest_full_copy_then_proc_trim_then_remove(), _parsed(), _proc(), _state(), test_case2_jsons_sync_oserror_is_suppressed() (+28 more)

### Community 25 - "test_commands.py"
Cohesion: 0.08
Nodes (30): _resolve_domain_root(), _ns(), test_build_run_config_defaults_p4_checkout_false_when_absent(), test_build_run_config_parses_comma_separated_features(), test_build_run_config_skips_empty_feature_segments(), test_build_run_config_threads_p4_checkout_flag(), test_build_run_config_with_project_ignores_base_and_features(), test_cmd_trim_does_not_expand_feature_directory() (+22 more)

### Community 26 - "models_config.py"
Cohesion: 0.07
Nodes (23): load_base(), load_feature(), _load_files_section(), _load_flow_action(), _load_procedures_section(), _entries(), load_project(), _load_stage_def() (+15 more)

### Community 27 - "merge_service.py"
Cohesion: 0.08
Nodes (29): _apply_layer(), _build_short_to_canonical(), _build_source_facts(), _classify_layer_intent(), _collect_universe(), _derive_manifest(), _emit_ve27_fe_literal(), _emit_ve27_glob() (+21 more)

### Community 28 - "$defs"
Cohesion: 0.05
Nodes (53): const, enum, type, additionalProperties, oneOf, properties, required, type (+45 more)

### Community 29 - "test_validator.py"
Cohesion: 0.19
Nodes (45): validate_post(), _codes(), _ctx(), _empty_graph(), _make_manifest(), _make_trim_report(), _source_edge(), _stage() (+37 more)

### Community 30 - "flow_resolver.py"
Cohesion: 0.09
Nodes (30): _apply_action(), _apply_add_stage(), _apply_add_step(), _apply_load_from(), _apply_remove_stage(), _apply_remove_step(), _apply_replace_stage(), _apply_replace_step() (+22 more)

### Community 31 - "ProcEntry"
Cohesion: 0.05
Nodes (23): ProcEntry, _build_entry(), _consume_brace_block(), _consume_element(), _deduplicate_short_names(), _detect_non_brace_body(), _extract_dpa_proc_name(), ExtractorResult (+15 more)

### Community 32 - "_collect"
Cohesion: 0.07
Nodes (9): _collect(), _shipped_chopper_jsons(), test_every_shipped_chopper_json_is_schema_valid(), test_shipped_json_validation_includes_v2_examples(), TestBaseSchema, TestFeatureSchema, TestProjectSchema, TestUnknownSchema (+1 more)

### Community 33 - "dump_model"
Cohesion: 0.07
Nodes (17): dump_model(), _encode(), loads(), _bfs_visit(), test_bfs_visit_is_deterministic_under_input_shuffling(), test_dump_model_is_idempotent(), test_dump_model_is_insertion_order_independent(), test_serialization_encodes_intenum_via_value() (+9 more)

### Community 34 - "reference"
Cohesion: 0.05
Nodes (47): const, enum, type, loadFromAction, removeStageAction, removeStepAction, replaceStageAction, replaceStepAction (+39 more)

### Community 35 - "Rule R1 (Ordered Overlay, Last Mention Wins)"
Cohesion: 0.07
Nodes (36): Action Vocabulary (FlowBuilder 7 + replace_step/replace_stage), Aggregate <domain>.stack, @n Instance Targeting, dependency_graph.json, F1 File-Level Trimming, F2 Proc-Level Trimming, F3 Run-File Generation, Feature vars/procs sourcing files (<flow>_feature_vars.tcl / <flow>_feature_procs.tcl) (+28 more)

### Community 36 - "test_runner_localfs_e2e.py"
Cohesion: 0.09
Nodes (23): _as_p1_reads(), _copy_fixture_jsons(), _domain_payload_hashes(), _make_ctx(), _make_overlay_ctx(), test_runner_localfs_dry_live_dry_sequence_keeps_domain_payload_stable(), test_runner_localfs_dry_run_emits_p4_commands_txt(), test_runner_localfs_dry_run_manifest_matches_live_trim_outputs_1_to_1() (+15 more)

### Community 37 - "cloc_backend.py"
Cohesion: 0.06
Nodes (17): cloc_script_path(), count_sloc_via_cloc(), count_sloc_via_cloc_batch(), is_available(), _perl_executable(), _selftest(), assert_domain_recoverable(), assert_domain_state() (+9 more)

### Community 38 - "StageDefinition"
Cohesion: 0.09
Nodes (20): ChopperError, UnknownDiagnosticCodeError, StageDefinition, _base(), _empty_parsed(), test_aggregate_and_standalone_together(), test_aggregate_stack_registered_when_generate_stack_on(), test_no_aggregate_when_generate_stack_off() (+12 more)

### Community 39 - "test_stack_graph.py"
Cohesion: 0.09
Nodes (30): compute_stack_order(), _extract_cycle(), _base(), _empty_parsed(), _stage(), test_compiled_manifest_accepts_empty_stack_order_with_any_stages(), test_compiled_manifest_accepts_valid_topological_stack_order(), test_compiled_manifest_rejects_duplicate_names_in_stack_order() (+22 more)

### Community 40 - "TokenKind"
Cohesion: 0.10
Nodes (24): classify_and_handle(), compute_skip_indices(), find_command_end(), is_array_set(), is_string_match(), last_lbrace_at_depth(), mark_opaque_arg_braces(), mark_switch_pattern_words() (+16 more)

### Community 41 - "functions.py"
Cohesion: 0.07
Nodes (24): _check_brace_balance(), _check_dangling_refs(), _check_manifest_vs_trim(), _check_stage_steps(), _check_trim_outputs(), _check_trimmed_proc_sets(), _classify_and_emit(), _emit_trim_output_mismatch() (+16 more)

### Community 42 - "_Sink"
Cohesion: 0.11
Nodes (20): build_trim_stats(), _make_file_outcome(), _make_run_result(), _make_trim_report(), test_fmt_pair_equal_values_omits_delta(), test_render_result_writes_summary_line(), test_render_trim_stats_artifact_oserror_falls_back_to_content(), test_render_trim_stats_dry_run_reads_domain_for_sloc_in() (+12 more)

### Community 43 - "StageSpec"
Cohesion: 0.10
Nodes (26): StageSpec, aggregate_stack_path(), emit_flow_stack(), emit_standalone_stack(), _render_record(), standalone_stack_path(), TestStageSpec, test_aggregate_stack_path_uses_domain_basename() (+18 more)

### Community 44 - "scan.py"
Cohesion: 0.07
Nodes (21): collect_code_metrics(), detect_ci_cd_pipelines(), detect_containers(), detect_monorepo(), detect_performance_markers(), detect_security_configs(), find_entry_points(), find_env_templates() (+13 more)

### Community 45 - "parse_file"
Cohesion: 0.07
Nodes (13): ExtractorDiagnostic, _message_for(), parse_file(), _translate_extractor_diagnostic(), test_array_set_braced_keys_are_not_calls(), test_py_eval_braced_python_payload_is_opaque(), TestPrivateHelperBranches, test_parse_file_unbalanced_braces_no_diagnostic_callback() (+5 more)

### Community 46 - "test_indentation.py"
Cohesion: 0.07
Nodes (23): format_tcl_indentation(), TclIndentationService, test_format_tcl_indentation_empty_returns_empty(), _manifest(), _outcome(), _report(), test_format_tcl_indentation_backslash_continuation(), test_format_tcl_indentation_blank_lines_no_trailing_whitespace() (+15 more)

### Community 47 - ".chopper/ Audit Bundle"
Cohesion: 0.07
Nodes (42): F1/F2/F3 Capability Classes, .chopper/ Audit Bundle, CLI Subcommands (validate, trim, loc, cleanup), BaseOptions (CompiledManifest.options), chopper cleanup, chopper loc, chopper_run.json, CLI_REFERENCE.md (+34 more)

### Community 48 - "properties"
Cohesion: 0.06
Nodes (42): properties, description, minLength, type, description, items, minItems, type (+34 more)

### Community 49 - "properties"
Cohesion: 0.05
Nodes (41): additionalProperties, description, minLength, pattern, type, description, description, minLength (+33 more)

### Community 50 - "properties"
Cohesion: 0.05
Nodes (41): additionalProperties, description, minLength, pattern, type, description, description, minLength (+33 more)

### Community 51 - "test_commands_coverage.py"
Cohesion: 0.07
Nodes (22): _split_domain_csv(), _make_ctx_for_header(), test_build_run_config_ve35_auto_discovery_fails(), test_build_run_config_ve36_no_suggestion_hint(), test_build_run_config_ve36_unresolved_feature_name(), test_build_run_config_ve36_unresolved_feature_with_suggestion(), test_p4_checked_out_abs_paths_empty_when_no_trim_report(), test_p4_checked_out_abs_paths_empty_when_p4_checkout_none() (+14 more)

### Community 52 - "_coverage_helpers.py"
Cohesion: 0.05
Nodes (11): test_flow_resolver_find_stage_index_returns_none_for_unknown(), test_flow_resolver_find_stage_returns_none_for_unknown(), test_load_procedures_section_exclude_with_procs_appends(), test_schema_dir_raises_when_missing(), test_internal_error_rejects_empty_kind(), test_shadow_event_rejects_empty_layer(), test_shadow_event_rejects_empty_prior_layer(), _make_file_outcome() (+3 more)

### Community 53 - "resolve_domain"
Cohesion: 0.14
Nodes (8): resolve_domain(), _collect_errors(), emit(), _Error, TestBareNameOSError, TestNameModeBareName, TestNameModeVendorQualified, TestPathMode

### Community 54 - "write_internal_error_log"
Cohesion: 0.08
Nodes (20): record_crash(), _format_diagnostics(), _format_runconfig(), _format_traceback(), _render(), _resolve_audit_root(), write_internal_error_log(), _BrokenSink (+12 more)

### Community 55 - "test_p4_commands.py"
Cohesion: 0.16
Nodes (25): render_p4_commands(), _data_lines(), _make_ctx(), _make_manifest(), _Progress, _prov(), _record(), test_banner_comments_are_present_and_trailing_newline() (+17 more)

### Community 56 - "TestCompanionSyncService"
Cohesion: 0.10
Nodes (4): CompanionSyncService, _manifest_with_proc_trim(), TestCompanionSyncService, _trim_report()

### Community 57 - "properties"
Cohesion: 0.06
Nodes (37): properties, description, minLength, type, description, items, minItems, type (+29 more)

### Community 58 - "DependencyGraph"
Cohesion: 0.09
Nodes (10): DependencyGraph, Edge, test_render_compiled_manifest_with_traced_proc_having_colon_colon(), test_render_dependency_graph_with_non_none_graph(), TestDependencyGraphInvariants, TestEdgeClass, TestDependencyGraph, TestEdge (+2 more)

### Community 59 - "TestLoadFeature"
Cohesion: 0.09
Nodes (4): _collect_base(), _collect_feat(), TestLoadBase, TestLoadFeature

### Community 60 - "LoadedConfig"
Cohesion: 0.14
Nodes (27): FilesSection, LoadedConfig, ProjectJson, _check_empty_base(), _check_feature_domain(), _check_project_level(), validate_pre(), _project_loaded() (+19 more)

### Community 61 - "trim_stats.py"
Cohesion: 0.09
Nodes (19): _dropped_rows(), _generated_rows(), _is_excluded_artifact(), _outcome_rows(), _safe_sloc(), TrimStatRow, _count_csv(), _count_hash_comment() (+11 more)

### Community 62 - "re"
Cohesion: 0.07
Nodes (13): collect_code_references(), load_active_codes(), main(), main(), patch_file(), _build_fleet_file(), _collect_imports(), main() (+5 more)

### Community 63 - "properties"
Cohesion: 0.06
Nodes (35): minimum, type, minimum, type, minimum, type, minimum, type (+27 more)

### Community 64 - "generators/test_service.py"
Cohesion: 0.11
Nodes (16): GeneratorService, _make_ctx(), _manifest_with_stages(), _manifest_with_stages_and_stack(), _Progress, _Sink, test_service_does_not_emit_stack_files_when_flag_off(), test_service_dry_run_builds_artifacts_but_writes_nothing() (+8 more)

### Community 65 - "ParserService"
Cohesion: 0.13
Nodes (9): ParserService, _make_ctx(), TestDeterminism, TestDiagnosticForwarding, TestEncoding, TestNonTclSkip, TestParserServiceBasic, TestPathNormalization (+1 more)

### Community 66 - "properties"
Cohesion: 0.06
Nodes (34): minimum, type, minimum, type, minimum, type, minimum, type (+26 more)

### Community 67 - "tokenizer.py"
Cohesion: 0.09
Nodes (20): extract_source_path_with_indices(), is_dynamic_path(), strip_quotes(), _is_escaped(), _preceding_backslashes(), TokenizerError, TokenizerResult, test_call_extractor_strip_quotes_braces() (+12 more)

### Community 68 - "checkout_files"
Cohesion: 0.11
Nodes (8): check_p4_available(), checkout_files(), revert_files(), _completed(), _p4_edit_ok(), TestCheckoutFiles, TestCheckP4Available, TestRevertFiles

### Community 69 - "_build_run_config"
Cohesion: 0.07
Nodes (17): _build_run_config(), _check_project_paths_resolvable(), _fail(), _make_context(), _make_progress(), _request(), test_build_run_config_auto_discovers_project_features_config(), test_build_run_config_auto_discovers_project_json() (+9 more)

### Community 70 - "properties"
Cohesion: 0.06
Nodes (33): default, description, type, description, minimum, type, description, format (+25 more)

### Community 71 - "Path"
Cohesion: 0.12
Nodes (3): _seed_valid_domain(), TestTrimSubcommand, _write_base_json()

### Community 72 - "type"
Cohesion: 0.08
Nodes (32): description, items, minItems, type, description, items, minItems, type (+24 more)

### Community 73 - "chopper.app Application Layer"
Cohesion: 0.09
Nodes (28): adapters/, AppError, ChopperError (exit code 3), ChopperRunner (orchestrator/runner.py, single composer), cli/ (thin adapter), core/, default_providers() / Providers bundle, DIAGNOSTIC_CODES.md (+20 more)

### Community 74 - "properties"
Cohesion: 0.07
Nodes (30): description, minLength, type, description, minItems, type, default, description (+22 more)

### Community 75 - "type"
Cohesion: 0.09
Nodes (30): description, items, minItems, type, items, items, description, items (+22 more)

### Community 76 - "resolve_feature_names"
Cohesion: 0.14
Nodes (4): FeatureLookupResult, resolve_feature_names(), _make_domain(), TestResolveFeatureNames

### Community 77 - "test_cli_chained_actions.py"
Cohesion: 0.29
Nodes (25): _base_with_main_only(), _run_pipeline(), _stage_by_name(), test_action_plus_fe_in_later_layer_downgrades_f1_with_vw21(), test_action_step_references_pe_dropped_proc_stages_unchanged(), test_add_stage_after_registers_generated_tcl_and_orders_stage(), test_add_stage_before_inserts_ahead_of_anchor(), test_add_step_after_same_anchor_three_features_preserve_order() (+17 more)

### Community 78 - "test_v2_check_script.py"
Cohesion: 0.23
Nodes (21): _check(), _flawed_layers(), _gate(), _good_layers(), _slugs(), snaps(), get(), _snapshot() (+13 more)

### Community 79 - "header.py"
Cohesion: 0.09
Nodes (14): _has_own_header(), intel_header_lines(), needs_header(), emit_stage_tcl(), stage_output_path(), test_needs_header_is_false_for_chopper_generated_output(), test_needs_header_vectors(), test_emit_stage_tcl_existing_copyright_header_is_not_duplicated() (+6 more)

### Community 80 - "type"
Cohesion: 0.09
Nodes (28): items, items, items, description, items, minItems, type, minLength (+20 more)

### Community 81 - "test_files_exclude_p4.py"
Cohesion: 0.16
Nodes (15): render_files_exclude_p4(), _data_lines(), _make_ctx(), _make_manifest(), _Progress, _prov(), _record(), _Sink (+7 more)

### Community 82 - "test_cli_chained_overlay.py"
Cohesion: 0.24
Nodes (19): _build_cli_args(), _run_pipeline(), test_cmd_loc_baseline_fallback_when_pipeline_aborts_before_p3(), test_cmd_validate_trim_loc_chain_on_real_overlay(), test_fe_glob_matching_base_files_removes_each_with_vw21(), test_feature_fe_glob_matches_nothing_emits_ve27(), test_glob_fi_matches_subdir_files(), test_multilayer_pe_remove_proc_emits_vw21_remove_proc() (+11 more)

### Community 83 - "build_parser"
Cohesion: 0.11
Nodes (16): _add_input_args(), build_parser(), InternalError, test_build_parser_has_four_subcommands(), test_global_flags_are_parsed_before_subcommand(), test_main_pre_runner_exception_writes_internal_error(), _fake_internal_error(), test_missing_subcommand_is_error() (+8 more)

### Community 84 - "Providers / default_providers"
Cohesion: 0.13
Nodes (22): Release 4.11.0 (one composer, chopper.app layer), AuditService (P7), ChopperRunner, CompanionSyncService (P5d), CompilerService (P3 ordered overlay), ConfigService (P1), DomainStateService (P0), execute_output() P5 Sequence (+14 more)

### Community 85 - "FeatureJson"
Cohesion: 0.09
Nodes (10): FeatureJson, test_audit_service_emits_vw20_on_write_failure(), test_audit_service_safe_read_returns_none_on_oserror(), test_collect_input_jsons_returns_empty_when_loaded_is_none(), test_copy_inputs_feature_with_none_text_continues(), test_copy_inputs_readable_feature_written(), test_copy_inputs_with_readable_base_and_unreadable_feature(), test_config_service_collects_surface_files_from_all_sections() (+2 more)

### Community 86 - "test_sloc_coverage.py"
Cohesion: 0.10
Nodes (13): test_sloc_csv_branch_counts_only_data_rows(), test_sloc_csv_skips_comma_only_rows(), test_sloc_hash_comment_blank_line_skipped(), test_sloc_json_extension_counts_nonblank_lines(), test_sloc_json_path_uses_count_raw(), test_sloc_many_batch_path_uses_python_fallback_when_env_set(), test_sloc_many_cloc_batch_falls_back_per_slot_when_cloc_unavailable(), test_sloc_many_empty_list_returns_empty() (+5 more)

### Community 87 - "properties"
Cohesion: 0.08
Nodes (25): description, type, description, minLength, type, description, minItems, type (+17 more)

### Community 88 - "call_extractor_body.py"
Cohesion: 0.12
Nodes (6): _bracket_is_escaped(), extract_body_refs(), classify_call_candidate(), should_suppress_first_word(), _body_refs(), TestDirectBodyExtractor

### Community 89 - "_make_ctx"
Cohesion: 0.11
Nodes (6): _make_ctx(), _seed_stages_domain(), test_runner_accepts_command_label(), test_runner_case4_exits_with_code_2(), test_runner_returns_run_result_with_summary(), TestGenerateStackPipeline

### Community 90 - "test_bug_report_regressions.py"
Cohesion: 0.10
Nodes (7): _calls_by_proc(), _diagnostic_kinds(), TestDpaMultilineContinuation, TestNonTclSkippedAtEnumeration, TestQuotedSemicolon, TestRegexLiteralOpacity, TestSwitchPatternLabels

### Community 91 - "type"
Cohesion: 0.10
Nodes (24): description, items, minItems, type, items, description, items, minItems (+16 more)

### Community 92 - "properties"
Cohesion: 0.09
Nodes (23): additionalProperties, description, properties, type, description, type, metadata, owner (+15 more)

### Community 93 - "properties"
Cohesion: 0.09
Nodes (23): additionalProperties, description, properties, type, description, type, metadata, owner (+15 more)

### Community 94 - "generators/service.py"
Cohesion: 0.12
Nodes (7): ensure_executable(), mirror_perms_plus_exec(), test_ensure_executable_oserror_swallowed(), test_mirror_perms_plus_exec_calls_copymode_and_ensure_executable(), test_mirror_perms_plus_exec_noop_on_nonexistent_paths(), test_mirror_perms_plus_exec_tolerates_oserror(), test_generator_service_wraps_write_oserror()

### Community 95 - "test_fs_walk_coverage.py"
Cohesion: 0.09
Nodes (6): test_cli_main_last_resort_exception_writes_internal_log(), test_main_programmer_error_handler_returns_1(), test_main_propagates_systemexit(), test_main_returns_exit_code_on_success(), test_every_domain_walk_shares_one_exclusion_rule(), test_walk_files_relative_to_valueerror_skips_child()

### Community 96 - "_make_proc"
Cohesion: 0.14
Nodes (4): _make_proc(), TestProcEntryCallsContract, TestProcEntryLineInvariants, TestProcEntryOptionalSpans

### Community 97 - "properties"
Cohesion: 0.09
Nodes (22): description, type, additionalProperties, description, properties, required, type, description (+14 more)

### Community 98 - "fs_memory.py"
Cohesion: 0.09
Nodes (8): test_source_root_is_domain_without_backup(), test_source_root_prefers_backup_once_it_exists_on_disk(), test_source_root_tracks_a_backup_created_mid_run(), test_generator_service_mirrors_perms_when_backup_src_exists(), test_proc_extractor_handles_unclosed_body(), test_proc_extractor_newline_between_args_and_body(), test_proc_extractor_skips_computed_proc_name(), test_proc_extractor_unclosed_brace_entry_none_pw03_none()

### Community 99 - "Project JSON"
Cohesion: 0.14
Nodes (17): Chopper Agent Operating Guide, Portable domain-only agent kit, Claude Code Guide, Base JSON, depends_on (feature prerequisites), Domain, Domain Boundary, --domain Name Resolution via $ward (+9 more)

### Community 100 - "Future Considerations (FD Ledger)"
Cohesion: 0.12
Nodes (13): Release 4.9.0 (opt-in insert_markers), Diagnostic Dataclass and Dedupe Key, FD-01 Advanced Namespace Resolution, FD-02 Cross-Domain Dependency Awareness, FD-08 Feature Mutual-Incompatibility (incompatible_with, adopted 4.6.0), FD-09 Benchmark Harness + Phase Budgets, FD-10 Machine-Readable CLI Output (--json/--jsonl), FD-12 Template-Script Generation (+5 more)

### Community 101 - "TrimReport"
Cohesion: 0.17
Nodes (4): TrimReport, _with_updated_companion_bytes(), _make_outcome(), TestTrimReport

### Community 102 - "_key"
Cohesion: 0.17
Nodes (4): _is_descendant(), _key(), _rebase(), test_copy_tree_recursively_copies_nested_subdirectory()

### Community 103 - "RichProgress"
Cohesion: 0.12
Nodes (5): RichProgress, RichUnavailableError, TestRichProgressAvailable, TestRichUnavailableFallback, _exploding_init()

### Community 104 - "properties"
Cohesion: 0.10
Nodes (21): description, minLength, type, description, type, description, minLength, type (+13 more)

### Community 105 - "properties"
Cohesion: 0.10
Nodes (21): default, description, type, default, description, type, default, description (+13 more)

### Community 106 - "properties"
Cohesion: 0.10
Nodes (21): default, description, type, default, description, type, default, description (+13 more)

### Community 107 - "properties"
Cohesion: 0.10
Nodes (21): description, items, minItems, type, description, type, description, minLength (+13 more)

### Community 108 - "LocReport"
Cohesion: 0.16
Nodes (8): _fmt_pct(), render_loc_report(), LocReport, TreatmentBucket, test_render_loc_report_writes_note_when_no_lines(), _empty_buckets(), TestLocReportPercents, TestRenderLocReport

### Community 109 - "ParseResult"
Cohesion: 0.19
Nodes (4): ParsedFile, ParseResult, TestParsedFile, TestParseResult

### Community 110 - "ChopperRunner"
Cohesion: 0.13
Nodes (8): ChopperRunner, _seed_good_domain(), test_runner_full_dry_run_happy_path(), test_runner_uses_injected_providers(), test_runner_writes_audit_bundle_in_dry_run(), TestLiveTrimPath, TestP2ParseGate, TestStrictMode

### Community 111 - "Parser Module Specification"
Cohesion: 0.12
Nodes (20): ChopperContext, CollectingSink, DiagnosticSink, FileSystemPort, InMemoryFS, LocalFS, make_test_context() Test Helper, PresentationConfig (+12 more)

### Community 112 - "properties"
Cohesion: 0.10
Nodes (20): description, type, description, minLength, type, description, type, properties (+12 more)

### Community 113 - "properties"
Cohesion: 0.10
Nodes (20): description, type, description, minLength, type, description, type, properties (+12 more)

### Community 115 - "feature-v1.schema.json"
Cohesion: 0.11
Nodes (17): description, additionalProperties, description, $id, type, required, $schema, title (+9 more)

### Community 116 - "file_bug_report.py"
Cohesion: 0.26
Nodes (14): attachments_from_payload(), create_attachment_bundle(), create_issue(), discover_repo(), ensure_writable(), fallback_to_local_output(), issue_form_url(), load_payload() (+6 more)

### Community 117 - "indentation.py"
Cohesion: 0.19
Nodes (10): _build_report(), _emit_ve25(), _mark_interrupted(), tcl_output_paths(), _tcl_output_paths(), _with_updated_artifacts(), _with_updated_bytes(), _write_text_preserving_mode() (+2 more)

### Community 118 - "test_audit_artifacts_golden.py"
Cohesion: 0.18
Nodes (8): _load_artifact(), _normalize(), _seed_valid_domain(), test_chopper_run_json_shape(), test_compiled_manifest_json_shape(), test_dependency_graph_json_shape(), test_trim_report_json_shape(), trimmed_domain()

### Community 119 - "Acquire Codebase Knowledge Skill"
Cohesion: 0.16
Nodes (16): ARCHITECTURE.md Template, CONCERNS.md Template, CONVENTIONS.md Template, INTEGRATIONS.md Template, STACK.md Template, STRUCTURE.md Template, TESTING.md Template, Inquiry Checkpoints Reference (+8 more)

### Community 120 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 121 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 122 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 123 - "exclude"
Cohesion: 0.12
Nodes (18): description, minItems, type, additionalProperties, minProperties, properties, type, description (+10 more)

### Community 124 - "properties"
Cohesion: 0.11
Nodes (18): minimum, type, minimum, type, additionalProperties, description, properties, type (+10 more)

### Community 125 - "_warn_if_cwd_will_be_renamed"
Cohesion: 0.12
Nodes (8): _warn_if_cwd_will_be_renamed(), test_check_project_paths_resolvable_unresolvable_domain_exits_2(), test_resolve_domain_root_backup_redirect_from_name_mode(), test_warn_if_cwd_will_be_renamed_no_warning_when_cwd_outside(), test_warn_if_cwd_will_be_renamed_oserror_returns_silently(), test_warn_if_cwd_will_be_renamed_silent_when_backup_exists(), test_warn_if_cwd_will_be_renamed_silent_when_cwd_outside_domain(), test_warn_if_cwd_will_be_renamed_writes_to_stderr_when_cwd_inside_domain()

### Community 126 - "topo_sort_features"
Cohesion: 0.27
Nodes (3): topo_sort_features(), _make_feat(), TestTopoSort

### Community 127 - "_brace_delta"
Cohesion: 0.11
Nodes (9): _brace_delta(), test_brace_delta_braced_word_quote_space_quote_is_literal(), test_brace_delta_full_line_comment_skipped(), test_brace_delta_prev_open_brace_quote_is_literal(), test_brace_delta_quoted_string_with_escaped_quote(), test_brace_delta_regression_guards_for_legal_quote_constructs(), test_brace_delta_repro_fixture_yields_zero(), test_brace_delta_skips_braces_inside_quoted_strings() (+1 more)

### Community 128 - "07_base_full/jsons/base.json"
Cohesion: 0.12
Nodes (16): description, domain, files, exclude, include, options, cross_validate, generate_stack (+8 more)

### Community 129 - "properties"
Cohesion: 0.12
Nodes (17): additionalProperties, properties, required, type, minimum, type, minimum, type (+9 more)

### Community 130 - "CaptureFixture"
Cohesion: 0.17
Nodes (4): render_cleanup_message(), TestGlobalFlags, TestRenderDirect, test_render_cleanup_message_writes_to_stdout_by_default()

### Community 131 - "render_p4_checkout_notice"
Cohesion: 0.18
Nodes (5): render_p4_checkout_notice(), _FakeStream, TestColorBehavior, TestDefaultStream, TestMessageContent

### Community 132 - "test_trace_service_coverage.py"
Cohesion: 0.15
Nodes (9): _candidate_qnames(), _is_dynamic(), test_candidate_qnames_strips_leading_double_colon(), test_is_dynamic_true_for_variable_substitution(), test_path_from_canonical_no_separator_returns_none(), test_trace_dynamic_tokens_short_circuit(), test_trace_resolution_absolute_double_colon_strips_prefix(), test_trace_resolution_bare_token_no_namespace_returns_single() (+1 more)

### Community 133 - "AuditManifest"
Cohesion: 0.21
Nodes (4): AuditManifest, _art(), TestAuditManifest, TestRunRecord

### Community 134 - "ProcRemoval"
Cohesion: 0.20
Nodes (4): ProcRemoval, _make_provenance(), TestCompiledManifest, TestProcRemoval

### Community 136 - "test_tool_commands.py"
Cohesion: 0.19
Nodes (6): _Entry, _Package, test_load_pool_reads_user_files(), test_load_pool_reports_missing_user_file(), test_load_pool_treats_missing_builtin_package_as_empty(), test_load_pool_unions_sorted_builtin_command_files()

### Community 137 - "base-v1.schema.json"
Cohesion: 0.12
Nodes (15): additionalProperties, anyOf, $defs, stageDefinition, description, $id, type, required (+7 more)

### Community 138 - "base-v2.schema.json"
Cohesion: 0.12
Nodes (15): additionalProperties, anyOf, $defs, stageDefinition, description, $id, type, required (+7 more)

### Community 139 - "procs"
Cohesion: 0.12
Nodes (16): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+8 more)

### Community 140 - "procs"
Cohesion: 0.12
Nodes (16): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+8 more)

### Community 141 - "FileProvenance"
Cohesion: 0.18
Nodes (6): _make_provenance(), FileProvenance, ShadowEvent, test_render_files_removed_shadowed_by_label(), test_render_files_removed_shadowed_by_pe_label(), TestFileProvenance

### Community 143 - "_StubFS"
Cohesion: 0.20
Nodes (4): _MissingWriteFS, _StubFS, test_incomplete_stub_fails_protocol(), test_stub_fs_satisfies_protocol()

### Community 144 - "Bug Report issue template"
Cohesion: 0.13
Nodes (15): Bug Report issue template, .chopper/chopper_run.json artifact, chopper trim, chopper trim --dry-run, chopper validate, .chopper/diagnostics.json artifact, EC site / zone field, PE-02 diagnostic example (unbalanced braces) (+7 more)

### Community 145 - "schema.py"
Cohesion: 0.19
Nodes (5): _get_validator(), _load_schema(), _schema_dir(), validate_json(), test_sourcing_pointers_reject_directory_and_drive_paths()

### Community 146 - "$defs"
Cohesion: 0.13
Nodes (15): additionalProperties, oneOf, required, type, $defs, addStageAction, flowAction, stageDefinition (+7 more)

### Community 147 - "procEntry"
Cohesion: 0.13
Nodes (15): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+7 more)

### Community 148 - "artifacts_present"
Cohesion: 0.13
Nodes (15): description, items, type, uniqueItems, description, items, type, pattern (+7 more)

### Community 149 - "domain"
Cohesion: 0.13
Nodes (15): additionalProperties, properties, required, type, description, type, domain, name (+7 more)

### Community 150 - "config/test_service_coverage.py"
Cohesion: 0.13
Nodes (7): test_config_enumerate_handles_list_oserror(), test_config_enumerate_handles_stat_oserror(), stat(), test_enumerate_domain_files_skips_child_outside_domain(), test_is_glob_pattern_returns_true_for_metachar(), test_load_and_hydrate_feature_raw_none_returns_none(), test_match_glob_against_exact_literal_match()

### Community 151 - "test_models.py"
Cohesion: 0.21
Nodes (10): _outcome(), test_file_outcome_rejects_full_copy_with_procs_removed(), test_file_outcome_rejects_negative_bytes(), test_file_outcome_rejects_remove_with_bytes_out(), test_file_outcome_rejects_unsorted_procs(), test_trim_report_accepts_consistent_totals(), test_trim_report_rejects_derived_count_drift(), test_trim_report_rejects_proc_count_drift() (+2 more)

### Community 152 - ".test_p3_error_aborts_pipeline_with_exit_1"
Cohesion: 0.16
Nodes (5): _inject_error_at(), _shim(), _shim(), _shim(), _shim()

### Community 153 - "_CollectingSink"
Cohesion: 0.15
Nodes (3): _CollectingSink, _NullProgress, TestFullDomainHarvest

### Community 155 - "gh_api_push.py"
Cohesion: 0.18
Nodes (3): _configure_proxy_bypass(), main(), _require_token()

### Community 156 - "GitNexus Guide Skill"
Cohesion: 0.22
Nodes (9): GitNexus CLI Skill, GitNexus Debugging Skill, GitNexus Exploring Skill, GitNexus Context Tool, GitNexus Guide Skill, GitNexus Process Resource, GitNexus Query Tool, GitNexus Impact Analysis Skill (+1 more)

### Community 158 - "08_base_plus_one_feature/jsons/features/dft.feature.json"
Cohesion: 0.14
Nodes (13): description, domain, files, include, flow_actions, metadata, owner, tags (+5 more)

### Community 159 - "test_package_smoke.py"
Cohesion: 0.18
Nodes (4): _pyproject_version(), test_package_version_falls_back_to_pyproject(), _missing(), test_package_version_uses_unknown_when_pyproject_unreadable()

### Community 160 - "internal_error"
Cohesion: 0.14
Nodes (14): additionalProperties, description, properties, required, type, description, type, description (+6 more)

### Community 161 - "main"
Cohesion: 0.19
Nodes (3): main(), TestCleanupSubcommand, TestValidateSubcommand

### Community 162 - "GeneratedArtifact"
Cohesion: 0.19
Nodes (4): GeneratedArtifact, emit_feature_vars(), TestGeneratedArtifact, TestEmitFeatureVars

### Community 163 - "plan_p4_sync.py"
Cohesion: 0.24
Nodes (5): _files_under(), main(), _parse_args(), _quoted(), _write_section()

### Community 164 - "package_bug_report.py"
Cohesion: 0.33
Nodes (9): archive_root(), build_manifest(), create_bundle(), default_output_path(), iter_files(), main(), parse_args(), resolve_output_path() (+1 more)

### Community 165 - "expand_feature_dirs"
Cohesion: 0.15
Nodes (8): expand_feature_dirs(), test_expand_feature_dirs_expands_directory(), test_expand_feature_dirs_expands_directory_to_json_children(), test_expand_feature_dirs_preserves_empty_segments(), test_expand_feature_dirs_returns_empty_when_features_is_empty(), test_expand_feature_dirs_returns_input_when_empty(), test_expand_feature_dirs_returns_none_when_features_is_none(), test_expand_feature_dirs_none_and_empty_pass_through()

### Community 166 - "render_p4_checkout_opened"
Cohesion: 0.24
Nodes (3): render_p4_checkout_opened(), TestMultiDomain, TestSingleDomain

### Community 167 - "render_p4_branch_analysis"
Cohesion: 0.28
Nodes (4): render_p4_branch_analysis(), _dr(), TestMultiDomain, TestSingleDomain

### Community 168 - "glob_match"
Cohesion: 0.19
Nodes (6): _match_glob(), glob_match(), test_merge_match_glob_double_star(), test_merge_match_glob_simple(), test_architecture_glob_examples(), test_segment_and_class_semantics()

### Community 169 - "lookup"
Cohesion: 0.21
Nodes (4): all_codes(), _Entry, lookup(), TestRegistry

### Community 172 - "check_service_signatures.py"
Cohesion: 0.24
Nodes (5): load_documented_signatures(), load_source_signatures(), main(), normalise_signature(), _signature()

### Community 173 - "dft_support.feature.json"
Cohesion: 0.17
Nodes (11): description, domain, files, include, metadata, owner, tags, name (+3 more)

### Community 174 - "pipeline_signoff.feature.json"
Cohesion: 0.17
Nodes (11): depends_on, description, domain, files, include, flow_actions, metadata, owner (+3 more)

### Community 175 - "power_analysis.feature.json"
Cohesion: 0.17
Nodes (11): depends_on, description, domain, files, include, flow_actions, metadata, owner (+3 more)

### Community 176 - "cmd_cleanup"
Cohesion: 0.17
Nodes (6): cmd_cleanup(), test_cmd_cleanup_refuses_without_confirm(), test_cmd_cleanup_removes_backup_with_confirm(), test_cmd_cleanup_removes_existing_backup(), test_cmd_cleanup_returns_0_when_no_backup_exists(), test_cmd_cleanup_returns_2_without_confirm()

### Community 179 - "09_base_plus_multiple_features/jsons/features/dft.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 180 - "09_base_plus_multiple_features/jsons/features/power.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 181 - "coverage_reporting.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 182 - "14_cross_feature_skip_if_no_stage/jsons/features/dft.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 183 - "14_cross_feature_skip_if_no_stage/jsons/features/power.feature.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, flow_actions, metadata, owner, tags (+2 more)

### Community 184 - "Chopper Agent Memory"
Cohesion: 0.27
Nodes (9): Chopper Agent Memory, Base Under 5000 SLOC Target (4858/4398), cdns Conformal Domain (42 features), Individual and Leave-One-Out Feature Matrix, Report Initialization Source-Partition Regression, September FEV JSON Resynthesis, CLI_REFERENCE SLOC Counted-Types Drift, snps Formality Domain (23 features) (+1 more)

### Community 185 - "properties"
Cohesion: 0.18
Nodes (11): additionalProperties, oneOf, properties, required, type, addStepAction, reference_file, description (+3 more)

### Community 186 - "intel_header_text"
Cohesion: 0.18
Nodes (7): intel_header_text(), test_intel_header_text_explicit_year_skips_datetime_now(), test_intel_header_text_uses_current_year_when_none(), test_intel_header_text_year_none_derives_current_year(), test_emit_stage_tcl_preserves_steps_verbatim(), test_emit_flow_stack_full_record_line_order(), test_emit_standalone_stack_single_step()

### Community 187 - "header_domain/.chopper/input_base.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, options, cross_validate, generate_stack, insert_markers (+2 more)

### Community 188 - "header_domain/jsons/base.json"
Cohesion: 0.18
Nodes (10): description, domain, files, include, options, cross_validate, generate_stack, insert_markers (+2 more)

### Community 190 - "test_missing_inputs.py"
Cohesion: 0.35
Nodes (6): test_absent_tcl_exclude_target_is_a_no_op_warning(), test_existing_tool_command_files_extend_the_pool(), test_invalid_tool_command_path_is_a_user_error(), test_json_only_examples_report_missing_domain_files(), test_missing_proc_file_is_a_p1_error(), test_proc_paths_are_literal_and_use_pristine_source()

### Community 191 - "test_vars_emitter.py"
Cohesion: 0.29
Nodes (3): _codes(), test_source_paths_are_one_literal_tcl_argument(), TestV2Schemas

### Community 192 - "04_base_files_and_procs/jsons/base.json"
Cohesion: 0.20
Nodes (9): description, domain, files, include, owner, procedures, exclude, include (+1 more)

### Community 193 - "validate_jsons.py"
Cohesion: 0.33
Nodes (5): iter_json_files(), load_schemas(), main(), parse_args(), validate_file()

### Community 194 - "gen_large_domain.py"
Cohesion: 0.27
Nodes (4): generate_large_domain(), main(), _make_ident(), pytest_large_domain_fixture()

### Community 195 - "procEntry"
Cohesion: 0.20
Nodes (10): procEntry, description, minLength, pattern, type, additionalProperties, properties, required (+2 more)

### Community 196 - "addStageAction"
Cohesion: 0.18
Nodes (10): additionalProperties, oneOf, required, type, addStageAction, with, description, minLength (+2 more)

### Community 197 - "top_codes"
Cohesion: 0.20
Nodes (10): additionalProperties, properties, required, code, count, top_codes, description, items (+2 more)

### Community 199 - "TestChopperContext"
Cohesion: 0.24
Nodes (3): _make_ctx(), _StubProgress, TestChopperContext

### Community 201 - "test_input_preserver_coverage.py"
Cohesion: 0.24
Nodes (5): _anchored_ctx(), test_input_preserver_copies_jsons_dir_from_backup(), test_input_preserver_emits_vw20_on_mkdir_failure(), mkdir(), test_preserve_input_sources_project_and_features_appended()

### Community 202 - "03_base_stages_only/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, options, generate_stack, owner, $schema, stages, tool

### Community 203 - "05_base_files_and_stages/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, files, include, owner, $schema, stages, tool

### Community 204 - "06_base_procs_and_stages/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, owner, procedures, exclude, include, $schema, stages

### Community 205 - "15_stage_reference_file/jsons/base.json"
Cohesion: 0.22
Nodes (8): description, domain, files, include, owner, $schema, stages, tool

### Community 206 - "apr_fc.json"
Cohesion: 0.22
Nodes (8): description, domain, options, generate_stack, procs, $schema, stages, vars

### Community 207 - "items"
Cohesion: 0.25
Nodes (9): items, items, pattern, $ref, stages, description, items, minItems (+1 more)

### Community 208 - "progress-event-v1.schema.json"
Cohesion: 0.22
Nodes (8): additionalProperties, description, $id, oneOf, required, $schema, title, type

### Community 209 - "expand_vars_entry"
Cohesion: 0.31
Nodes (4): expand_vars_entry(), test_emitter_keeps_block_order_and_emits_exactly_three_optional_lines(), test_pointer_expansion_preserves_parent_and_prefixes_only_basename(), TestExpandVarsEntry

### Community 211 - "mini_domain/jsons/features/feature_a.json"
Cohesion: 0.22
Nodes (8): description, files, include, name, procedures, exclude, include, $schema

### Community 213 - "test_file_bug_report.py"
Cohesion: 0.50
Nodes (6): _payload(), test_file_bug_report_create_falls_back_when_gh_is_missing(), test_file_bug_report_create_falls_back_when_gh_returns_error(), test_file_bug_report_create_uses_gh_issue_create(), test_file_bug_report_dry_run_writes_body_and_bundle(), test_file_bug_report_rejects_missing_required_fields()

### Community 214 - "Real-world bug-report fixtures README"
Cohesion: 0.43
Nodes (8): diagnostics_file_null_for_p4_p6.md bug, dpa_multiline.tcl fixture, python_braces.py fixture, quoted_semicolon.tcl fixture, regex_literals.tcl fixture, sta_pt production domain (Intel pesg_2026.06), switch_patterns.tcl fixture, Real-world bug-report fixtures README

### Community 215 - "01_base_files_only/.chopper/input_base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, exclude, include, owner, $schema

### Community 216 - "01_base_files_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, exclude, include, owner, $schema

### Community 217 - "02_base_procs_only/.chopper/input_base.json"
Cohesion: 0.25
Nodes (7): description, domain, owner, procedures, exclude, include, $schema

### Community 218 - "02_base_procs_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, owner, procedures, exclude, include, $schema

### Community 219 - "08_base_plus_one_feature/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 220 - "08_base_plus_one_feature/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 221 - "09_base_plus_multiple_features/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 222 - "09_base_plus_multiple_features/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 223 - "10_chained_features_depends_on/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 224 - "10_chained_features_depends_on/project.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 225 - "11_project_base_only/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 226 - "12_base_with_aggregate_stack/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, options, generate_stack, owner, $schema, stages

### Community 227 - "13_base_with_standalone_stack/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, options, generate_stack, owner, $schema, stages

### Community 228 - "14_cross_feature_skip_if_no_stage/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, owner, $schema, stages

### Community 229 - "project_dft_only.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 230 - "project_full.json"
Cohesion: 0.25
Nodes (7): base, domain, features, notes, owner, project, $schema

### Community 231 - "15_stage_reference_file/jsons/features/dft.feature.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, flow_actions, name, $schema

### Community 232 - "README Changelog"
Cohesion: 0.25
Nodes (7): README Changelog, Release 4.8.1 (no buried shebang / duplicate header), Release 4.9.1 (single-level * glob fix), Release 4.9.2 (project recorded in audit bundle), P-11 Glob Expansion Must Normalize Paths, P-30 Project Metadata Must Flow Through to Audit Artifacts, P-49 Generated Files Must Not Bury a Shebang or Duplicate a Header

### Community 233 - "GitHub API Push Skill"
Cohesion: 0.32
Nodes (6): setup.csh Bootstrap Script, Fallback Venv Skill, Intel EC/HPC URLfilter Policy 241, gh_api_push.py Script, GitHub API Push Skill, Token Acquisition Procedure

### Community 234 - "diagnostic-v1.schema.json"
Cohesion: 0.25
Nodes (7): additionalProperties, description, $id, required, $schema, title, type

### Community 235 - "run-result-v1.schema.json"
Cohesion: 0.25
Nodes (7): additionalProperties, description, $id, required, $schema, title, type

### Community 236 - "by_family"
Cohesion: 0.25
Nodes (8): additionalProperties, description, patternProperties, type, ^[VTP][EWI]$, by_family, minimum, type

### Community 238 - "post_check.feature.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, flow_actions, name, $schema

### Community 239 - "mini_domain/jsons/base.json"
Cohesion: 0.25
Nodes (7): description, domain, files, include, procedures, include, $schema

### Community 240 - "test_sink_collecting.py"
Cohesion: 0.36
Nodes (4): _diag(), test_emit_dedupe_replaces_in_place(), test_emit_preserves_insertion_order(), test_finalize_returns_severity_counts()

### Community 241 - "test_cmd_trim_multi_domain_live_calls_render_trim_stats"
Cohesion: 0.25
Nodes (3): test_cmd_trim_multi_domain_live_calls_render_trim_stats(), test_cmd_trim_single_domain_calls_render_trim_stats_on_live_run(), _fake_trim_stats()

### Community 242 - ".test_audit_exception_is_swallowed"
Cohesion: 0.29
Nodes (3): TestChopperErrorPath, _compile_boom(), _boom()

### Community 243 - "test_edge_case_fixture_parses_without_crashing"
Cohesion: 0.25
Nodes (3): _parser_fixtures(), test_edge_case_fixture_parses_without_crashing(), test_every_parser_fixture_is_covered()

### Community 245 - "11_project_base_only/project.json"
Cohesion: 0.29
Nodes (6): base, domain, notes, owner, project, $schema

### Community 246 - "16_feature_vars/project.json"
Cohesion: 0.29
Nodes (6): base, domain, features, notes, project, $schema

### Community 247 - "properties"
Cohesion: 0.29
Nodes (7): description, type, description, type, properties, hint, path

### Community 249 - "R5 Backup-and-Rebuild"
Cohesion: 0.29
Nodes (4): Byte-Identical Determinism Gate (mini_domain golden test), ENGINEERING.md, Non-Functional Requirements (NFR-01..NFR-15), RunConfig / PresentationConfig

### Community 250 - "overlay_replace/jsons/features/feature_a.json"
Cohesion: 0.29
Nodes (6): description, files, exclude, include, name, $schema

### Community 251 - "stages_domain/jsons/base.json"
Cohesion: 0.29
Nodes (6): description, domain, options, generate_stack, $schema, stages

### Community 252 - "chopper_run.json golden shape"
Cohesion: 0.29
Nodes (7): artifacts_present field, chopper_run.json golden shape, diagnostics_summary field, trim_state field, compiled_manifest.json golden shape, contributed_by field, treatment field (full-copy)

### Community 255 - "dop.feature.json"
Cohesion: 0.33
Nodes (5): description, name, procs, $schema, vars

### Community 256 - "fdr.feature.json"
Cohesion: 0.33
Nodes (5): description, name, procs, $schema, vars

### Community 257 - "slug"
Cohesion: 0.33
Nodes (6): slug, description, maxLength, minLength, pattern, type

### Community 260 - "create_latin1_fixture.py"
Cohesion: 0.47
Nodes (3): build_fixture_bytes(), main(), write_fixture()

### Community 261 - "overlay_no_op_exclude/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 262 - "feature_typo.json"
Cohesion: 0.33
Nodes (5): description, files, exclude, name, $schema

### Community 263 - "overlay_no_op_exclude/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 264 - "overlay_remove_only/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 265 - "feature_drop.json"
Cohesion: 0.33
Nodes (5): description, files, exclude, name, $schema

### Community 266 - "overlay_remove_only/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 267 - "overlay_replace/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 268 - "overlay_replace/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 269 - "overlay_two_features_same_file/jsons/base.json"
Cohesion: 0.33
Nodes (5): description, domain, files, include, $schema

### Community 270 - "overlay_two_features_same_file/jsons/features/feature_a.json"
Cohesion: 0.33
Nodes (5): description, name, procedures, exclude, $schema

### Community 271 - "feature_b.json"
Cohesion: 0.33
Nodes (5): description, name, procedures, include, $schema

### Community 272 - "overlay_two_features_same_file/project.json"
Cohesion: 0.33
Nodes (5): base, domain, features, project, $schema

### Community 274 - "test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror"
Cohesion: 0.33
Nodes (5): test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror(), __init__(), test_parser_enumerate_skips_files_with_bad_stat(), __init__(), stat()

### Community 276 - "test_ascii_only.py"
Cohesion: 0.47
Nodes (3): test_scan_covers_the_tree(), test_tree_is_ascii_only(), _text_files()

### Community 277 - "check_v2.py reference"
Cohesion: 0.40
Nodes (5): Adoption levels, check_v2.py reference, Delta classes (with `--baseline`), Gate, Suggestions

### Community 278 - "v1 → v2 interview question bank"
Cohesion: 0.40
Nodes (4): Round 1 — scope and infrastructure (before any edit), Round 2 — per layer (the base row first, then one row per feature in project order), Round 3 — opportunities (after the migration is green), v1 → v2 interview question bank

### Community 279 - "exit_codes"
Cohesion: 0.40
Nodes (5): description, items, minItems, type, exit_codes

### Community 280 - "language"
Cohesion: 0.40
Nodes (5): default, description, enum, type, language

### Community 281 - "reference_file"
Cohesion: 0.40
Nodes (5): reference_file, description, minLength, pattern, type

### Community 282 - "reference_file"
Cohesion: 0.40
Nodes (5): reference_file, description, minLength, pattern, type

### Community 283 - "vars"
Cohesion: 0.40
Nodes (5): vars, description, minLength, pattern, type

### Community 284 - "stageDefinition"
Cohesion: 0.40
Nodes (5): stageDefinition, additionalProperties, oneOf, required, type

### Community 285 - "phase_index"
Cohesion: 0.40
Nodes (5): description, maximum, minimum, type, phase_index

### Community 286 - "Trim Report JSON Shape Golden File"
Cohesion: 0.40
Nodes (5): Trim Report JSON Shape Golden File, trim_report file_report field, trim_report proc_report field, trim_report summary field block, trim_report validation_results field

### Community 290 - "cloc.pl vendored tool"
Cohesion: 0.50
Nodes (4): cloc.pl vendored tool, chopper.audit.cloc_backend module, GPL-2.0 license (vendored cloc), chopper.audit.sloc pure-Python fallback

### Community 291 - "options.generate_stack Aggregate Stack Contract"
Cohesion: 0.67
Nodes (4): Example 12 README — Aggregate Scheduler Stack, options.generate_stack Aggregate Stack Contract, Example 13 README — Aggregate + Standalone Stack, standalone_stack Per-Stage Verbatim File

### Community 292 - "dependencies"
Cohesion: 0.50
Nodes (4): description, minItems, type, dependencies

### Community 293 - "steps"
Cohesion: 0.50
Nodes (4): steps, description, minItems, type

### Community 294 - "code"
Cohesion: 0.50
Nodes (4): description, pattern, type, code

### Community 295 - "context"
Cohesion: 0.50
Nodes (4): additionalProperties, description, type, context

### Community 296 - "dedupe_bucket"
Cohesion: 0.50
Nodes (4): default, description, type, dedupe_bucket

### Community 297 - "exit_code"
Cohesion: 0.50
Nodes (4): description, enum, type, exit_code

### Community 298 - "line_no"
Cohesion: 0.50
Nodes (4): description, minimum, type, line_no

### Community 299 - "message"
Cohesion: 0.50
Nodes (4): description, minLength, type, message

### Community 300 - "phase"
Cohesion: 0.50
Nodes (4): description, enum, type, phase

### Community 301 - "severity"
Cohesion: 0.50
Nodes (4): severity, description, enum, type

### Community 302 - "source"
Cohesion: 0.50
Nodes (4): source, description, enum, type

### Community 303 - "detail"
Cohesion: 0.50
Nodes (4): additionalProperties, description, type, detail

### Community 304 - "elapsed_seconds"
Cohesion: 0.50
Nodes (4): description, minimum, type, elapsed_seconds

### Community 305 - "event"
Cohesion: 0.50
Nodes (4): description, enum, type, event

### Community 306 - "properties"
Cohesion: 0.50
Nodes (4): description, type, properties, message

### Community 307 - "phase"
Cohesion: 0.50
Nodes (4): description, enum, type, phase

### Community 308 - "phase_total"
Cohesion: 0.50
Nodes (4): description, enum, type, phase_total

### Community 309 - "run_id"
Cohesion: 0.50
Nodes (4): run_id, description, pattern, type

### Community 310 - "schema"
Cohesion: 0.50
Nodes (4): schema, const, description, type

### Community 311 - "step_index"
Cohesion: 0.50
Nodes (4): step_index, description, minimum, type

### Community 312 - "step_total"
Cohesion: 0.50
Nodes (4): step_total, description, minimum, type

### Community 313 - "timestamp"
Cohesion: 0.50
Nodes (4): timestamp, description, format, type

### Community 314 - "schema"
Cohesion: 0.50
Nodes (4): schema, const, description, type

### Community 321 - "Agent Local Memory Files (README)"
Cohesion: 0.67
Nodes (3): Agent Local Memory Files (README), Agent Local Memory Files convention, Minimum Template (agent memory)

### Community 323 - "Chopper onboarding brochure"
Cohesion: 0.67
Nodes (3): Chopper onboarding brochure, Project branch trim window, SNORT

## Ambiguous Edges - Review These
- `dpa_multiline.tcl fixture` → `diagnostics_file_null_for_p4_p6.md bug`  [AMBIGUOUS]
  tests/fixtures/bug_reports/README.md · relation: REUSES

## Knowledge Gaps
- **1275 isolated node(s):** `description`, `minLength`, `type`, `description`, `type` (+1270 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2962 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **80 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `dpa_multiline.tcl fixture` and `diagnostics_file_null_for_p4_p6.md bug`?**
  _Edge tagged AMBIGUOUS (relation: REUSES) - confidence is low._
- **Why does `ChopperContext` connect `ChopperContext` to `pathlib`, `test_audit.py`, `ConfigService`, `CompilerService`, `CompiledManifest`, `Diagnostic`, `make_ctx`, `FileSystemPort`, `Path`, `_ctx`, `RunConfig`, `TracerService`, `Phase`, `test_proc_dropper.py`, `make_ctx`, `config/test_service_coverage.py`, `LocalFS`, `FileTreatment`, `_CollectingSink`, `models_config.py`, `merge_service.py`, `.run`, `flow_resolver.py`, `test_validator.py`, `GeneratedArtifact`, `test_runner_localfs_e2e.py`, `test_stack_graph.py`, `functions.py`, `_Sink`, `test_indentation.py`, `test_commands_coverage.py`, `_coverage_helpers.py`, `write_internal_error_log`, `test_p4_commands.py`, `TestCompanionSyncService`, `DependencyGraph`, `LoadedConfig`, `trim_stats.py`, `generators/test_service.py`, `ParserService`, `_build_run_config`, `TestChopperContext`, `test_input_preserver_coverage.py`, `test_cli_chained_actions.py`, `test_files_exclude_p4.py`, `test_cli_chained_overlay.py`, `FeatureJson`, `_make_ctx`, `generators/service.py`, `fs_memory.py`, `TrimReport`, `ChopperRunner`, `indentation.py`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `Bug Report issue template` connect `Bug Report issue template` to `package_bug_report.py`, `.chopper/ Audit Bundle`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `chopper cleanup` connect `.chopper/ Audit Bundle` to `Bug Report issue template`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 228 inferred relationships involving `ChopperContext` (e.g. with `domain_summary()` and `loc_report()`) actually correct?**
  _`ChopperContext` has 228 INFERRED edges - model-reasoned connections that need verification._
- **Are the 249 inferred relationships involving `FileTreatment` (e.g. with `domain_summary()` and `_dropped_rows()`) actually correct?**
  _`FileTreatment` has 249 INFERRED edges - model-reasoned connections that need verification._
- **Are the 193 inferred relationships involving `InMemoryFS` (e.g. with `FileStat` and `SimulatedTrim`) actually correct?**
  _`InMemoryFS` has 193 INFERRED edges - model-reasoned connections that need verification._