####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


################# BLOCK SETTINGS #################
set block $env(block)
set task $env(task)
global fev_type
set fev_type r2r
set LOGFILE logs/fm.log
puts [date]
set sh_allow_tcl_with_set_app_var true
set sh_allow_tcl_with_set_app_var_no_message_list sh_output_log_file

puts "INTEL_INFO   : ivar logger"
source $env(ward)/global/common/variable_logger.tcl
set ::track_variable_history 1

puts "INTEL_INFO   : Static interface"
source $env(ward)/global/common/setup.tcl
set design_name $ivar(design_name)

puts "################################################################"
iproc_msg -info "Sourcing Formality procs ([date])"
puts "################################################################"
iproc_msg -info "Sourcing the Default Formality procs"
iproc_source -file default_fm_procs.tcl
modify_search_path
iproc_msg -info "Sourcing the Addon Formality procs"
iproc_source -file addon_fm_procs.tcl -optional
iproc_msg -info "Sourcing the Project Formality procs"
iproc_source -file project_fm_procs.tcl -optional
iproc_msg -info "Sourcing the User Formaity procs"
iproc_source -file user_fm_procs.tcl -optional

puts "################################################################"
iproc_msg -info "Setting the required app_vars([date])"
puts "################################################################"
annotate_trace -start
set_app_var synopsys_auto_setup true
set_mismatch_message_filter -warn
set_app_var verification_set_undriven_signals BINARY:X
set_app_var verification_verify_directly_undriven_output true
set_host_option -max_cores 8
set_app_var verification_timeout_limit "48:00:00"
set_app_var verification_datapath_effort_level high
set_app_var upf_use_library_cells_for_retention true
iproc_msg -info "Enabling SVF Auto setup"
set_app_var svf_scan false
set_app_var fm_error_on_obsolete_generate_block_construct false
set_app_var upf_warn_on_undriven_backup_pgpin true
set_app_var upf_warn_on_failed_port_attribute_check true
set_app_var upf_warn_on_missing_csn_object true
set upf_warn_on_missing_retention_element true
set mv_allow_pg_pin_reconnection true
set hdlin_dwroot $env(FUSIONCOMPILER_DIR)
set_app_var svf_checkpoint_stop_when_rejected ckpt_pre_retime
set_app_var svf_checkpoint_format_verilog true
set fm_ndm_preserve_supply_constants true
set_app_var hdlin_intermediate_file_method none
set_app_var signature_analysis false
set_app_var name_match_use_filter false
set_app_var verification_auto_session off
set_app_var svf_report_guidance_write_design_data false
#Following app vars are to ensure strict name mapping for PI/PO
set_app_var name_match strict_ports_pins
set_app_var signature_analysis_match_blackbox_input false
set_app_var signature_analysis_match_blackbox_output false
set_app_var signature_analysis_match_primary_input false
set_app_var signature_analysis_match_primary_output false
set fm_compact_indexed_part_select_read_implementation true
set fm_enhanced_hier_map true
set fm_svf_reuse_skip_diff_via_name true
set fm_disable_removing_of_parallel_instances true
set_app_var hdlin_db_precedence true
set_app_var hdlin_filter_netlist_supply_statements true
set_app_var user_match_enable_many_to_many_matching true
set_app_var upf_bbox_related_supplies_only true
set_app_var hdlin_unresolved_module_severity error 
set_app_var collection_result_display_limit -1
set_app_var verification_verify_unread_tech_cell_pg_pins false
set_vclp_setup_commands {configure_lp_tag -tag "DIFF_MACRO_SUPPLY DIFF_PST_EXIST DIFF_PST_STATE DIFF_PST_SUPPLY DIFF_REGISTER_SUPPLY DIFF_POWERSTATE_EXIST DIFF_PSW_LOGIC DIFF_SUPPLY_STATE DIFF_MACRO_NOPG" -severity error}
#app vars required for W branch
set_app_var fmlp_supply_check_all_black_boxes true
set fm_guide_constants_use_sat false
set_app_var svf_guide_constant_force_single_core true
set fmlp_include_info_messages true
set fmlp_continue_on_error false
set_app_var verification_insert_upf_isolation_cutpoints false
set_app_var verification_mark_verify_unread_as_read true
set_app_var verification_set_undriven_analog_inputs_binary true
set enable_verdi_debug false

if { [info exists ivar($task,enable_ML_dpx)] && $ivar($task,enable_ML_dpx) } {
    set dpx_enable_ml_strategy_prediction true
}


if { [info exists ivar($task,enable_dpx)] && $ivar($task,enable_dpx) } {
	if { [info exists ivar($task,dpx_batch)] && $ivar($task,dpx_batch) } {
		set_dpx_options -protocol custom -submit_command "$ivar(job_submission_cmd) run --target $ivar(NBPOOL) --qslot $ivar(NBQSLOT) --class '$ivar(NBCLASS)' $ivar(nb_cloud_options) $ivar(nb_prediction_options)" -max_workers 8 -max_cores 4
	} else {
		set_dpx_options -protocol SH -submit_command sh -max_workers 8 -max_cores 4 
	}
}

if { [info exists ivar($task,limit_fail_points)] && $ivar($task,limit_fail_points) } {
	set_app_var verification_failing_point_limit 10000
	set_app_var save_session_calculate_cone_sizes failing	
} else {
	set_app_var verification_failing_point_limit 0
}

iproc_msg -info "Black boxing modules"
add_blackbox_mods $design_name

fev_setup_commands
iproc_source -file addon_fev_fm_pre_read_lib.tcl -optional
iproc_source -file project_fev_fm_pre_read_lib.tcl -optional
iproc_source -file fev_fm_pre_read_lib.tcl -optional -verbose

if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
    set verification_static_low_power_compare true
}

puts "################################################################"
iproc_msg -info "Reading Standand Cells and HIP libs ([date])"
puts "################################################################"
read_libs 
#puts [date]
iproc_msg -info "STEP DONE: read_libs"

if { [info exists task ] && $task != "fev_fm_lite" } {
	check_metaflop_settings r2r $design_name 	
}

iproc_source -file addon_fev_fm_pre_read_design.tcl -optional
iproc_source -file project_fev_fm_pre_read_design.tcl -optional
iproc_source -file fev_fm_pre_read_design.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Reading Reference Design ([date])"
puts "################################################################"
if { [info exists task ] && $task == "fev_fm_ctechverif" } {
	set_app_var hdlin_ignore_translate true
	$ivar($task,read_rtl_proc_golden) $ivar($task,rtl_list_golden) $design_name r REM
	set_app_var hdlin_ignore_translate false
} else {
	$ivar($task,read_rtl_proc_golden) $ivar($task,rtl_list_golden) $design_name r REM
}
#puts [date]
iproc_msg -info "STEP DONE: read_rtl_r"

if { [info exists ivar($task,lp)] && $ivar($task,lp) } {
    puts "################################################################"
    iproc_msg -info "Reading Reference UPF"
    puts "################################################################"
    
	read_upf $ivar($task,golden_upf) $design_name rtl REF 
    #puts [date]
    iproc_msg -info "STEP DONE: load_upf_r"
} else {
	if { [info exists ivar($task,golden_upf)] && [file exists $ivar($task,golden_upf)] } {
		if { ![load_upf -target power_switch_only -r $ivar($task,golden_upf)] } {
			iproc_msg -error "load_upf failed"
			exit -1
		}
	}
}
iproc_msg -info "Stage_for_runtime_aggregation upf_stage_r"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Implementation Design ([date])"
puts "################################################################"
if { [info exists task ] && $task == "fev_fm_lite" } {
    read_dummy_gate ./outputs/buffer.v buffer i 
} elseif { [info exists task ] && $task == "fev_fm_ctechverif" } {
    $ivar($task,read_rtl_proc_revised) $ivar($task,rtl_list_revised) $design_name i ADD
} else {
    $ivar($task,read_rtl_proc_revised) $ivar($task,rtl_list_revised) $design_name i REM
}
#puts [date]
iproc_msg -info "STEP DONE: read_rtl_i"


if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists task] && $task != "fev_fm_lite" } {
    puts "################################################################"
    iproc_msg -info "Reading Implementation UPF ([date])"
    puts "################################################################"
	read_upf $ivar($task,revised_upf) $design_name rtl IMPL 
    puts [date]
    iproc_msg -info "STEP DONE: load_upf_i"
} else {
	if { [info exists ivar($task,revised_upf)] && [file exists $ivar($task,revised_upf)] } {
		if { ![load_upf -target power_switch_only -i $ivar($task,revised_upf)] } {
			iproc_msg -error "load_upf failed"
			exit -1
		}
	}
}
iproc_msg -info "Stage_for_runtime_aggregation upf_stage_i"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

iproc_source -file addon_fev_fm_post_read_upf.tcl -optional
iproc_source -file project_fev_fm_post_read_upf.tcl -optional
iproc_source -file fev_fm_post_read_upf.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Setup ([date])"
puts "################################################################"

setup

report_setup_status > reports/$design_name.setup_status.rpt
#puts [date]
iproc_msg -info "STEP DONE: setup"

iproc_source -file addon_fev_fm_post_setup.tcl -optional
iproc_source -file project_fev_fm_post_setup.tcl -optional
iproc_source -file fev_fm_post_setup.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Match ([date])"
puts "################################################################"
add_ctech_constraints $design_name

match
iproc_msg -info "Stage_for_runtime_aggregation match"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

additional_matching $design_name
#puts [date]
iproc_msg -info "STEP DONE: match"

if { [info exists task ] && $task == "fev_fm_lite" } {
    puts "################################################################"
    iproc_msg -info "fev_fm_lite Completed Successfully "
    puts "################################################################"
    create_inspectfev_config $task $design_name "fev_fm_lite"
	report_unmatched_points -status undriven -point_type cut -reference > reports/$design_name.RTL_undrivens.rpt
	report_constantx_registers -reason_type -reference > reports/$design_name.RTL_seq_constx.rpt 
	generate_indicator_stats_lite $design_name ./reports/$design_name.$task.indicator.rpt $LOGFILE
    if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
	    iproc_msg -info "Generating save session checkpoint"
	    save_session -replace $design_name.verify.fss
    }
	report_bboxes_parametrization "fev_fm_lite" $design_name
	report_unmatched_bboxes $design_name
    print_message_info -summary
    elapsed_time
    report_ivar_change $design_name
    gen_runtime_summary $task $LOGFILE
    if { [info exists env(EXITSHELL)] } { exit 0 }
}

iproc_source -file addon_fev_fm_pre_compare.tcl -optional
iproc_source -file project_fev_fm_pre_compare.tcl -optional
iproc_source -file fev_fm_pre_compare.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Verify ([date])"
puts "################################################################"
verify
#puts [date]

if { [info exists ivar($task,enable_dpx)] && $ivar($task,enable_dpx) } {
	stop_dpx_workers
}

iproc_msg -info "STEP DONE: verify"
iproc_msg -info "Stage_for_runtime_aggregation verify"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

check_metaflop r2r $design_name

iproc_source -file addon_fev_fm_post_compare.tcl -optional
iproc_source -file project_fev_fm_post_compare.tcl -optional
iproc_source -file fev_fm_post_compare.tcl -optional -verbose

if { [info exists ivar($task,lp)] && $ivar($task,lp) && [info exists ivar($task,enable_compare_lp)] && $ivar($task,enable_compare_lp) } {
    puts "################################################################"
    iproc_msg -info "Low Power Checks ([date])"
    puts "################################################################"
    compare_lp
    vclp_send "report_lp -limit 0 -all_tags -tag DIFF_* -verbose -file [pwd]/reports/$design_name.lp_violations.rpt"
    vclp_send "report_lp -all_tags -tag DIFF_* -verbose -only_waived -file [pwd]/reports/$design_name.lp_waived.rpt"
    vclp_send "save_session -session [pwd]/$design_name.compare_lp.fss"
    report_supply_check_results $design_name
    #puts [date]
    iproc_msg -info "STEP DONE: compare_lp"
    iproc_msg -info "Stage_for_runtime_aggregation compare_lp"
    iproc_msg -info "Elapse_time : [elapsed_time]"
    iproc_msg -info "Memory usage : [memory -format -units mB]"
}

puts "################################################################"
iproc_msg -info "Reports ([date])"
puts "################################################################"
if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
	iproc_msg -info "Generating save session checkpoint"
    save_session -replace $design_name.verify.fss
}

report_feedthrough_status > reports/$design_name.feedthrough_verif.rpt
report_match_results $design_name
report_verify_results $task $design_name r2r
report_unmatched_bboxes $design_name
#puts [date]
iproc_msg -info "STEP DONE: reports"

iproc_source -file addon_fev_fm_post_report.tcl -optional
iproc_source -file project_fev_fm_post_report.tcl -optional
iproc_source -file fev_fm_post_report.tcl -optional -verbose

print_message_info -summary
elapsed_time

report_ivar_change $design_name
gen_runtime_summary $task $LOGFILE
iproc_msg -info "Generating Indicator data"
generate_indicator_stats $design_name ./reports/$design_name.$task.indicator.rpt

if { [info exists env(EXITSHELL)] } { exit 0 }
