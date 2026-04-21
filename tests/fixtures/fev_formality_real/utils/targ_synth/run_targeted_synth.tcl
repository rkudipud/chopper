####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


set SCRIPT_DIR [file normalize [file dirname [info script]]]

puts "=I= moving tracking of ivars from log to report ([date])"
  source $env(ward)/global/common/variable_logger.tcl
  namespace eval variable_logger { variable _quiet 1 }
  set ::track_variable_history 1

puts "=I= define ivars ([date])"
  set ward                "$env(ward)"
  set ivar(task)          "targeted_synth"
  set ivar(src_task)      "pre_eco_design"
  set ivar(analysis_task) 0 
  source $ward/global/snps/$env(flow)/setup.tcl
  set ivar(rtl_list) $ivar(collateral_dir)/post_eco_fe_collateral/rtl_list_2stage.tcl
  set ivar(outputs,backup_enable) 0
  set ivar(svf_integrate_in_ndm) 0
  #set ivar(ndm_reset_refs) 1
  suppress_message {UIC-043 UIC-084}
  suppress_message {NEX-009 NEX-010}
  suppress_message {VER-936 VER-61 VER-708 VER-318}
  suppress_message {UPF-112}
  suppress_message {ELAB-193}
  suppress_message {ATTR-3}
  suppress_message {EMB-7000}
  suppress_message {NDMUI-669}
  set_app_option -name hdlin.report.level -value none

puts "=I= copy pre-eco ndm ([date])"
  iproc_source -file step_load.tcl
  #iakolmyc: WA set_fm_eco_mode will load design regardless, and if there is already design in memmory it will error out.
  close_blocks -save
  sd_report_ivars

puts "=I= load eco region file from FM ([date])"
  set_fm_eco_mode \
  -region $env(ward)/runs/$env(block)/$env(tech)/fev_formality/fm_eco/outputs/fm_eco_region.frd \
  -netlist [get_attribute [current_lib] source_file_name]:$ivar(design_name) \
  -compile_options {-to logic_opto} \
  -pre_compile_script  $SCRIPT_DIR/run_targeted_synth.pre.tcl \
  -post_compile_script $SCRIPT_DIR/run_targeted_synth.post.tcl

puts "=I= read rtl ([date])"
  iproc_source -file fc.app_options.rtl.tcl
  set_svf eco_ts_flow.svf
  iproc_source -file step_import_design_2stage.tcl -use_hooks
  iproc_source -file step_elaborate.tcl  -use_hooks

