####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


puts "=I= moving tracking of ivars from log to report ([date])"
source $env(ward)/global/common/variable_logger.tcl
namespace eval variable_logger { variable _quiet 1 }
set ::track_variable_history 1

puts "=I= define ivars ([date])"
  set ward                "$env(ward)"
  set ivar(src_task)      "pre_eco_design"
  set ivar(analysis_task) 0 
  source $ward/global/snps/$env(flow)/setup.tcl
  set ivar(outputs,backup_enable) 0
  set ivar(ndm_reset_refs) 0
  set ivar(nbatch_rpt_out) 0
  set ivar(parallel_rpt_out_no_nb) 0 
  set ivar(outputs,$ivar(task)) [list]
  set ivar(reports,$ivar(task)) [list]
  set ivar(svf_integrate_in_ndm) 0
  suppress_message {UPF-112}
  suppress_message {ATTR-3}
  suppress_message {PGR-599}
  suppress_message {NDMUI-669}
  suppress_message {FRAM-054}
  set suffix [regsub apply_patch $ivar(task) {}]

puts "=I= open design ([date])"
  iproc_source -file step_load.tcl
  sd_report_ivars

puts "=I= apply changelist ([date])"
  if { [file exists $ivar(build_dir)/fev_formality/fm_eco/outputs/fm_eco_edits$suffix.tcl] } {
  	source $ivar(build_dir)/fev_formality/fm_eco/outputs/fm_eco_edits$suffix.tcl
  } elseif { [file exists $ivar(build_dir)/fev_formality/fm_eco/outputs/fm_eco_edits.tcl] } {
	source $ivar(build_dir)/fev_formality/fm_eco/outputs/fm_eco_edits.tcl
  } else {
	puts "ERROR: fm_eco_edits.tcl file not found"
	exit 1
  } 
  create_mv_cells -all 
  connect_pg_net -auto
  iproc_source -file step_change_names.tcl

puts "=I= generate outputs ([date])"
  # do not use step_close.tcl to generate outputs
  # it will run update_timing and extraction. None of these needed for fev.
  write_verilog -compress gzip -exclude {empty_modules scalar_wire_declarations leaf_module_declarations supply_statements pg_netlist physical_only_cells} $ivar(dst_dir)/$ivar(design_name).pt_nonpg.v.gz
  write_verilog -compress gzip -exclude {empty_modules scalar_wire_declarations leaf_module_declarations physical_only_cells} $ivar(dst_dir)/$ivar(design_name).pt.v.gz
  save_upf $ivar(dst_dir)/$ivar(design_name).upf
  file copy -force $ivar(build_dir)/fev_formality/fm_eco/outputs/fm_eco_region.frd $ivar(dst_dir)/

puts "=I= renaming lib"
  save_block
  save_lib -all
  set cur_lib [get_attribute [current_lib] source_file_name]
  puts "  From: $cur_lib"
  puts "  To:   $ivar(dst_dir)/$ivar(design_name).ndm"
  if {"$cur_lib" != "$ivar(dst_dir)/$ivar(design_name).ndm"} {
    save_lib -as $ivar(dst_dir)/$ivar(design_name).ndm
    close_lib -all
    file delete -force $cur_lib
  } else {
    close_lib -all
  }  
  
puts "=I= promote results to $ivar(collateral_dir)/eco_patched_design$suffix"
  file delete "$ivar(collateral_dir)/eco_patched_design$suffix"
  file link -symbolic "$ivar(collateral_dir)/eco_patched_design$suffix" $ivar(dst_dir)

puts "=I= exit ([date])"
  exit
