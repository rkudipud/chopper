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
iproc_msg -info "Sourcing Formality procs [date]"
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
set_app_var verification_set_undriven_signals 0
set_app_var verification_clock_gate_reverse_gating true
set fm_guide_reg_suppress_rcg_graph_reduction true
set_host_option -max_cores 8
set_app_var verification_timeout_limit "48:00:00"
set_app_var verification_failing_point_limit 0 
set_app_var verification_datapath_effort_level high
set_app_var svf_scan false
set_app_var fm_error_on_obsolete_generate_block_construct false
set hdlin_dwroot $env(FUSIONCOMPILER_DIR)
set_app_var svf_checkpoint_stop_when_rejected ckpt_pre_retime
set_app_var svf_checkpoint_format_verilog true
set_app_var hdlin_intermediate_file_method none
set_app_var svf_report_guidance_write_design_data false
set fm_ndm_preserve_supply_constants true
set fm_eco_debug_targeted_synthesis true
set fm_eco_enable_packaging true
set fm_find_eco_region_use_net_boundaries true 
set fm_match_eco_region_use_find_equiv_nets true 
set fm_eco_auto_apply_frd_files true
# disabling new feature till FC support it (star=4794767)
# update: commented next line as FC support is enabled 2024.09
# set fm_eco_enable_synthesis_directives false
set fm_eco_enable_synthesis_directives true
set fm_eco_enable_synthesis_directives_techmapping Auto
set fm_eco_enable_synthesis_directives_pcg false
set fm_compact_indexed_part_select_read_implementation true
set fm_enhanced_hier_map true
set fm_svf_reuse_skip_diff_via_name true
set fm_disable_removing_of_parallel_instances true
set_app_var hdlin_db_precedence true
set_app_var hdlin_filter_netlist_supply_statements true
set_app_var svf_datapath false
set_app_var user_match_enable_many_to_many_matching true
set_app_var upf_bbox_related_supplies_only true
set_app_var hdlin_unresolved_module_severity error 
set_app_var collection_result_display_limit -1
#app vars required for W branch
set_app_var fmlp_supply_check_all_black_boxes true
set fm_guide_constants_use_sat false
set_app_var svf_guide_constant_force_single_core true

if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
	iproc_msg -info "Generating save session checkpoint is enabled"
	set fm_eco_save_session true
}

if { [info exists ivar($task,seq_const_check)] && $ivar($task,seq_const_check) } {
	set verification_assume_reg_init None
}

fev_setup_commands
iproc_msg -info "Black boxing modules"
add_blackbox_mods $design_name

puts "################################################################"
iproc_msg -info "Reading SVF [date]"
puts "################################################################"
exec rm -rf $fm_work_path/fm_eco_region_frd
if { [info exists ivar($task,frd_file_path)] && [file exists $ivar($task,frd_file_path)] } {
   set_eco_data $ivar($task,frd_file_path)
   report_eco_data $ivar($task,frd_file_path)
   read_svf
} else {
   read_svf
}

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

read_rtl_2stage $ivar($task,eco_rtl) $design_name
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
write_container -replace -container r outputs/ertl.fsc
remove_container r
set_app_var search_path ""
#puts [date]
iproc_msg -info "STEP DONE: read_ertl"

iproc_msg -info "Stage_for_runtime_aggregation write_container_E_RTL"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Reference Design - Original RTL [date]"
puts "################################################################"
read_rtl_2stage $ivar($task,orig_rtl) $design_name
if { [info exists ivar($task,orig_upf)] && [file exists $ivar($task,orig_upf)] } {
	if { ![load_upf -target power_switch_only -r $ivar($task,orig_upf)] } {
		iproc_msg -error "load_upf failed"
		exit -1
	}
	iproc_msg -info "Stage_for_runtime_aggregation upf_O_RTL"
	iproc_msg -info "Elapse_time : [elapsed_time]"
	iproc_msg -info "Memory usage : [memory -format -units mB]"
}

current_container r
apply_eco_data -regions
write_container -replace -container r outputs/ortl.fsc

iproc_msg -info "Stage_for_runtime_aggregation write_container_O_RTL"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reading Implementation Design - Original Netlist [date]"
puts "################################################################"
#read_gate $ivar($task,orig_netl) $design_name IMPL 
read_ndm -i -no_upf -format non_pg_netlist -preserve_supply_constant -block $design_name $ivar($task,orig_ndm)
set_top $design_name

iproc_msg -info "Stage_for_runtime_aggregation read_ndm_onet"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

constrain_low_power_intent $impl
write_container -replace -container i outputs/onet.fsc

#puts [date]
iproc_msg -info "STEP DONE: read_onet"

iproc_msg -info "Stage_for_runtime_aggregation write_container_O_net"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "preverify and setup constraints [date]"
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
add_fm_scan_constraints r2g $design_name

report_setup_status

iproc_source -file addon_fev_fm_post_setup.tcl -optional
iproc_source -file project_fev_fm_post_setup.tcl -optional
iproc_source -file fev_fm_post_setup.tcl -optional -verbose

puts "################################################################"
iproc_msg -info "Match [date]"
puts "################################################################"
read_container -container ertl outputs/ertl.fsc
read_container -container ortl outputs/ortl.fsc

iproc_msg -info "Stage_for_runtime_aggregation read_containers"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

iproc_msg -info "Applying clk_dop mapping"
add_fm_clk_dop_mapping $design_name

match

iproc_msg -info "Stage_for_runtime_aggregation match"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

iproc_msg -info "Customize matching"
additional_matching $design_name

report_match_results $design_name
generate_indicator_fm_eco match ./reports/$design_name.$task.indicator.rpt

puts "################################################################"
iproc_msg -info "generate ECO region [date]"
puts "################################################################"
iproc_source -file addon_fev_fm_pre_compare.tcl -optional
iproc_source -file project_fev_fm_pre_compare.tcl -optional
iproc_source -file fev_fm_pre_compare.tcl -optional -verbose

set_orig_reference ortl
set_orig_implementation i
set_eco_reference ertl

if { [info exists ivar($task,orig_ref_impl_compare)] && $ivar($task,orig_ref_impl_compare) } {
	set verification_effort_level super_low
	verify
	report_verify_results $task $design_name r2g
	report_unmatched_bboxes $design_name
	if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
		iproc_msg -info "Generating save session checkpoint"
	    save_session -replace $design_name.pre_synth_verif.fss
	}	
	#added indicator_data_extraction
	generate_indicator_fm_eco verify ./reports/$design_name.$task.indicator.rpt
	iproc_msg -info "Stage_for_runtime_aggregation verify_orig_ref_impl"
	iproc_msg -info "Elapse_time : [elapsed_time]"
	iproc_msg -info "Memory usage : [memory -format -units mB]"
}

match_eco_regions
write_eco_regions -replace outputs/fm_eco_region
generate_indicator_fm_eco regions ./reports/$design_name.$task.indicator.rpt $LOGFILE

iproc_msg -info "Stage_for_runtime_aggregation write_ECO_regions"
iproc_msg -info "Elapse_time : [elapsed_time]"
iproc_msg -info "Memory usage : [memory -format -units mB]"

puts "################################################################"
iproc_msg -info "Reports [date]"
puts "################################################################"

if { [info exists ivar($task,generate_checkpt)] && $ivar($task,generate_checkpt) } {
	iproc_msg -info "Generating save session checkpoint"
	save_session -replace $design_name.pre_synth.fss
}

if { [info exists ivar($task,enable_unoptimized_patch)] && $ivar($task,enable_unoptimized_patch) } {
	puts "################################################################"
	iproc_msg -info "create unoptimized patch file ([date])"
	puts "################################################################"
	create_eco_patch -replace -dont_use_name_pattern $ivar(redefine,clock_cell_list)
	set fm_eco_debug_targeted_synthesis false
	report_eco_impact > reports/$design_name.eco_impact.rpt
	report_eco_impact -reference -datapath >> reports/$design_name.eco_impact.rpt
	set fm_eco_debug_targeted_synthesis true
	#added indicator_data_extraction
	generate_indicator_fm_eco eco_impact ./reports/$design_name.$task.indicator.rpt

	iproc_msg -info "Stage_for_runtime_aggregation create_ECO_patch"
	iproc_msg -info "Elapse_time : [elapsed_time]"
	iproc_msg -info "Memory usage : [memory -format -units mB]"
	
	remove_container i
	read_container -i outputs/onet.fsc -replace
	apply_eco_data -patch
	write_edits -replace outputs/fm_eco_edits_unoptimized.tcl
	print_message_info -summary

	iproc_msg -info "Stage_for_runtime_aggregation write_unopt_edits"
	iproc_msg -info "Elapse_time : [elapsed_time]"
	iproc_msg -info "Memory usage : [memory -format -units mB]"
}

print_message_info -summary
elapsed_time

report_ivar_change $design_name
gen_runtime_summary $task $LOGFILE
iproc_msg -info "Generating Indicator data"
generate_indicator_fm_eco general ./reports/$design_name.$task.indicator.rpt

if { [info exists env(EXITSHELL)] } { exit 0 }

