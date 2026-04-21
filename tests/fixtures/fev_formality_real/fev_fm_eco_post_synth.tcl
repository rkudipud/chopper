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
set LOGFILE logs/fm_eco.log
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
iproc_msg -info "Sourcing the Formality procs [date]"
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
iproc_msg -info "Setting the required app_vars [date]"
puts "################################################################"
annotate_trace -start
set_app_var synopsys_auto_setup true
set_mismatch_message_filter -warn
set svf_debug false
set_app_var verification_set_undriven_signals 0
set_app_var verification_clock_gate_reverse_gating true
set fm_guide_reg_suppress_rcg_graph_reduction true
set_host_option -max_cores 8
set_app_var verification_timeout_limit "48:00:00"
set_app_var verification_failing_point_limit 0 
set_app_var verification_datapath_effort_level high
set_app_var upf_use_library_cells_for_retention true
set_app_var svf_scan false
set_app_var fm_error_on_obsolete_generate_block_construct false
set_app_var hdlin_unresolved_modules black_box
set hdlin_dwroot $env(FUSIONCOMPILER_DIR)
set_app_var svf_checkpoint_stop_when_rejected ckpt_pre_retime
set_app_var svf_checkpoint_format_verilog true
set_app_var hdlin_intermediate_file_method none
set_app_var svf_report_guidance_write_design_data false
set fm_ndm_preserve_supply_constants true
set fm_eco_enable_packaging true
set fm_eco_auto_apply_frd_files true
set fm_compact_indexed_part_select_read_implementation true
set fm_enhanced_hier_map true
set verification_effort_level super_low
set fm_svf_reuse_skip_diff_via_name true
set fm_disable_removing_of_parallel_instances true
set_app_var hdlin_db_precedence true
set_app_var hdlin_filter_netlist_supply_statements true
set_app_var user_match_enable_many_to_many_matching true
set_app_var upf_bbox_related_supplies_only true
set_app_var hdlin_unresolved_module_severity error 
set_app_var collection_result_display_limit -1
#app vars required for W branch
set_app_var fmlp_supply_check_all_black_boxes true
set fm_guide_constants_use_sat false
set_app_var svf_guide_constant_force_single_core true

if { [info exists ivar($task,seq_const_check)] && $ivar($task,seq_const_check) } {
	set verification_assume_reg_init None
}
fev_setup_commands
iproc_msg -info "Black boxing  modules"
add_blackbox_mods $design_name

puts "################################################################"
iproc_msg -info "Reading FRD+SVF [date]"
puts "################################################################"
set_eco_data outputs/fm_eco_region.frd
set_svf $ivar($task,guidance_file_path)
set_svf -append $ivar($task,targ_syn_svf)
iproc_msg -info "Stage_for_runtime_aggregation read_svf+frd"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Standand Cells and HIP libs [date]"
puts "################################################################"
iproc_source -file addon_fev_fm_pre_read_lib.tcl -optional
iproc_source -file project_fev_fm_pre_read_lib.tcl -optional
iproc_source -file fev_fm_pre_read_lib.tcl -optional -verbose
read_libs 
#puts [date]
iproc_msg -info "STEP DONE: read_libs"

# Metaflop settings 
check_metaflop_settings r2g $design_name

puts "################################################################"
iproc_msg -info "Reading Reference Design - ECO RTL [date]"
puts "################################################################"
iproc_source -file addon_fev_fm_pre_read_design.tcl -optional
iproc_source -file project_fev_fm_pre_read_design.tcl -optional
iproc_source -file fev_fm_pre_read_design.tcl -optional -verbose

read_rtl_2stage $ivar($task,eco_rtl) $design_name r

if { [info exists ivar($task,eco_upf)] && [file exists $ivar($task,eco_upf)] } {
	if { ![load_upf -target power_switch_only -r $ivar($task,eco_upf)] } {
		iproc_msg -error "load_upf failed"
		exit -1
	}
	iproc_msg -info "Stage_for_runtime_aggregation upf_ECO_RTL"
	iproc_msg -info "Elapse_time : [elapsed_time]"
	iproc_msg -info "Memory usage : [memory -format -units mB]"
}

current_container r
apply_eco_data -regions

iproc_msg -info "Stage_for_runtime_aggregation apply_ECO_data"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Implemented Design - targeted synthesis ndm from FC [date]"
puts "################################################################"
#read_gate $ivar($task,targ_syn_gate) $design_name i
read_ndm -i -no_upf -format non_pg_netlist -preserve_supply_constant -block ts_$design_name $ivar($task,targ_syn_ndm) 
set_top $design_name

constrain_low_power_intent $impl

iproc_msg -info "Stage_for_runtime_aggregation read_NDM_fc"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Implementation Design - original netlist [date]"
puts "################################################################"
read_container -container onet outputs/onet.fsc

iproc_msg -info "Stage_for_runtime_aggregation read_O_net"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Applying setup commands [date]"
puts "################################################################"
preverify
report_guidance -summary > reports/${design_name}.guidance.summary.rpt
iproc_msg -info "Stage_for_runtime_aggregation pre_verify"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

setup

iproc_msg -info "Applying LCP constraints"
add_fm_lcp_constraints $design_name

iproc_msg -info "Applying Feedthru and Clk TD Constraints"
add_fm_td_constraints impl r2g $design_name


iproc_msg -info "Applying Scan Constraints"
add_fm_scan_constraints onet $design_name

iproc_source -file addon_fev_fm_post_setup.tcl -optional
iproc_source -file project_fev_fm_post_setup.tcl -optional
iproc_source -file fev_fm_post_setup.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Matching [date]"
puts "################################################################"
iproc_msg -info "Applying clk_dop mapping"
add_fm_clk_dop_mapping $design_name

iproc_msg -info "Customize matching"
additional_matching $design_name

verify
if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
	iproc_msg -info "Generating save session checkpoint"
	save_session -replace $design_name.post_synth.fss
}
    
report_verify_results $task $design_name eco
report_unmatched_bboxes $design_name

iproc_msg -info "Stage_for_runtime_aggregation match"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

#puts [date]
#added indicator_data_extraction
generate_indicator_fm_eco  match ./reports/$design_name.$task.indicator.rpt
report_match_results $design_name
iproc_msg -info "STEP DONE: match"

puts "################################################################"
iproc_msg -info "Create Patch [date]"
puts "################################################################"
set_eco_reference r
set_eco_implementation i
set_orig_implementation onet

create_eco_patch -replace outputs/fm_eco_region
report_eco_impact > reports/$design_name.eco_impact.rpt
#added indicator_data_extraction
generate_indicator_fm_eco eco_impact ./reports/$design_name.$task.indicator.rpt

iproc_msg -info "Stage_for_runtime_aggregation create_ECO_patch"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Generating changelist for FC [date]"
puts "################################################################"
remove_container i
read_container -i outputs/onet.fsc -replace

apply_eco_data -patch
write_edits -replace outputs/fm_eco_edits.tcl

iproc_msg -info "Stage_for_runtime_aggregation write_edits"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

print_message_info -summary
elapsed_time

report_ivar_change $design_name
gen_runtime_summary $task $LOGFILE
iproc_msg -info "Generating Indicator data"
generate_indicator_fm_eco general ./reports/$design_name.$task.indicator.rpt

if { [info exists env(EXITSHELL)] } { exit 0 }

