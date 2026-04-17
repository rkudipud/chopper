####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


set env(vendor) "snps"
set env(flow) "fev_formality"
array set FEV_iDATA {}
global task ivar env
set ivar($task,hook_files) "fev_fm_pre_read_lib.tcl fev_fm_pre_read_design.tcl fev_fm_post_read_upf.tcl fev_fm_post_setup.tcl fev_fm_pre_compare.tcl fev_fm_post_compare.tcl"

set ivar($task,audit_files) "default_fm_procs.tcl addon_fm_procs.tcl project_fm_procs.tcl addon_fev_fm_pre_read_lib.tcl  project_fev_fm_pre_read_lib.tcl  addon_fev_fm_pre_read_design.tcl project_fev_fm_pre_read_design.tcl addon_fev_fm_post_read_upf.tcl  project_fev_fm_post_read_upf.tcl  addon_fev_fm_post_setup.tcl  project_fev_fm_post_setup.tcl addon_fev_fm_pre_compare.tcl project_fev_fm_pre_compare.tcl addon_fev_fm_post_compare.tcl project_fev_fm_post_compare.tcl"
####---------------FEV---------------#### 
set ivar($task,scenario_name) ""
set ivar_desc($task,scenario_name) "For specifying one scenario to run fev"
set ivar_type($task,scenario_name) "da"
set ivar_used_by($task,scenario_name) "fev_formality"
lappend ivar(fev,required_ivars) "$task,scenario_name"
####---------------FEV---------------####
set ivar($task,golden_v2k_config) 1
set ivar_desc($task,golden_v2k_config) "Used for enabling elaboration through v2k cfg for reference side" 
set ivar_type($task,golden_v2k_config) "user"
set ivar_used_by($task,golden_v2k_config) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_v2k_config"
####---------------FEV---------------####
set ivar($task,revised_v2k_config) 1
set ivar_desc($task,revised_v2k_config) "Used for enabling elaboration through v2k cfg for implementation side" 
set ivar_type($task,revised_v2k_config) "user"
set ivar_used_by($task,revised_v2k_config) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_v2k_config"
####---------------FEV---------------####
set ivar($task,cfg_file) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name)_cfg.sv"
set ivar_desc($task,cfg_file) "Used for setting path to v2k cfg file " 
set ivar_type($task,cfg_file) "user"
set ivar_used_by($task,cfg_file) "fev_formality"
lappend ivar(fev,required_ivars) "$task,cfg_file"
####---------------FEV---------------####
set ivar(elab_params) ""
set ivar_desc(elab_params) "Used for providing params"
set ivar_type(elab_params) "user"
set ivar_used_by(elab_params) "fev_formality"
lappend ivar(fev,required_ivars) "elab_params"
####---------------FEV---------------####
set ivar(design_name_rtl) ""
set ivar_desc(design_name_rtl) "Used for providing top module name"
set ivar_type(design_name_rtl) "user"
set ivar_used_by(design_name_rtl) "fev_formality"
lappend ivar(fev,required_ivars) "design_name_rtl"
####---------------FEV---------------####
set ivar($task,golden_user_remove_defines) ""
set ivar_desc($task,golden_user_remove_defines) "For removing user defines while reading golden rtl"
set ivar_type($task,golden_user_remove_defines) "project"
set ivar_used_by($task,golden_user_remove_defines) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_user_remove_defines"
####---------------FEV---------------####
set ivar($task,revised_user_remove_defines) ""
set ivar_desc($task,revised_user_remove_defines) "For removing user defines while reading revised rtl"
set ivar_type($task,revised_user_remove_defines) "project"
set ivar_used_by($task,revised_user_remove_defines) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_user_remove_defines"
####---------------FEV---------------####
set ivar($task,golden_user_defines) ""
set ivar_desc($task,golden_user_defines) "For adding user defines while reading golden rtl"
set ivar_type($task,golden_user_defines) "project"
set ivar_used_by($task,golden_user_defines) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_user_defines"
####---------------FEV---------------####
set ivar($task,revised_user_defines) ""
set ivar_desc($task,revised_user_defines) "For adding user defines while reading revised rtl"
set ivar_type($task,revised_user_defines) "project"
set ivar_used_by($task,revised_user_defines) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_user_defines"
####---------------FEV---------------####
set ivar($task,upf_all_state_verify) 0 
set ivar_desc($task,upf_all_state_verify) "For adding user defines while reading revised rtl"
set ivar_type($task,upf_all_state_verify) "project"
set ivar_used_by($task,upf_all_state_verify) "fev_formality"
lappend ivar(fev,required_ivars) "$task,upf_all_state_verify"
####---------------FEV---------------####
set ivar($task,enable_meta_check) 1  
set ivar_desc($task,enable_meta_check) "To enable metaflop check"
set ivar_type($task,enable_meta_check) "project"
set ivar_used_by($task,enable_meta_check) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_meta_check"
####---------------FEV---------------####
set ivar($task,verify_unread_meta) 1  
set ivar_desc($task,verify_unread_meta) "to enable verification of unread metaflops"
set ivar_type($task,verify_unread_meta) "project"
set ivar_used_by($task,verify_unread_meta) "fev_formality"
lappend ivar(fev,required_ivars) "$task,verify_unread_meta"
####---------------FEV---------------####
set ivar($task,seq_const_check) 1  
set ivar_desc($task,seq_const_check) "to enable sequential constant verification"
set ivar_type($task,seq_const_check) "project"
set ivar_used_by($task,seq_const_check) "fev_formality"
lappend ivar(fev,required_ivars) "$task,seq_const_check"
####---------------FEV---------------####
set ivar($task,gen_hier_upf_rtl) 0 
set ivar_desc($task,gen_hier_upf_rtl) "To enable hier UPF generation for RTL"
set ivar_type($task,gen_hier_upf_rtl) "project"
set ivar_used_by($task,gen_hier_upf_rtl) "fev_formality"
lappend ivar(fev,required_ivars) "$task,gen_hier_upf_rtl"
####---------------FEV---------------####
set ivar($task,child,golden_upf_extn) ".upf"
set ivar_desc($task,child,golden_upf_extn) "For providing golden upf extension"
set ivar_type($task,child,golden_upf_extn) "user"
set ivar_used_by($task,child,golden_upf_extn) "fev_formality"
lappend ivar(fev,required_ivars) "$task,child,golden_upf_extn"
####---------------FEV---------------####
set ivar($task,eco_upf) ""
set ivar_desc($task,eco_upf) "For providing ECO UPF in ECO run"
set ivar_type($task,eco_upf) "user"
set ivar_used_by($task,eco_upf) "fev_formality"
lappend ivar(fev,required_ivars) "$task,eco_upf"
####---------------FEV---------------####
set ivar($task,orig_upf) ""
set ivar_desc($task,orig_upf) "For providing original UPF in ECO run"
set ivar_type($task,orig_upf) "user"
set ivar_used_by($task,orig_upf) "fev_formality"
lappend ivar(fev,required_ivars) "$task,orig_upf"
####---------------FEV---------------####
set ivar($task,child,revised_upf_extn) ".upf"
set ivar_desc($task,child,revised_upf_extn) "For providing upf extension on the revised side"
set ivar_type($task,child,revised_upf_extn) "user"
set ivar_used_by($task,child,revised_upf_extn) "fev_formality"
lappend ivar(fev,required_ivars) "$task,child,revised_upf_extn"
####---------------FEV---------------####
set ivar($task,all,golden_path) ""
set ivar_desc($task,all,golden_path) "If all the child partition netlist and UPF are available in same path, this ivar should be used to provide the golden path"
set ivar_type($task,all,golden_path) "user"
set ivar_used_by($task,all,golden_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,all,golden_path"
####---------------FEV---------------####
set ivar($task,all,revised_path) ""
set ivar_desc($task,all,revised_path) "If all the child partition netlist and UPF are available in same path, this ivar should be used to provide the revised path"
set ivar_type($task,all,revised_path) "user"
set ivar_used_by($task,all,revised_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,all,revised_path"
####---------------FEV---------------####
set ivar($task,$ivar(design_name),fev_dot_tcl_path) ""
set ivar_desc($task,$ivar(design_name),fev_dot_tcl_path) "For providing the fev.tcl path for parent block"
set ivar_type($task,$ivar(design_name),fev_dot_tcl_path) "user"
set ivar_used_by($task,$ivar(design_name),fev_dot_tcl_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,$ivar(design_name),fev_dot_tcl_path"
####---------------FEV---------------####
set ivar($task,$ivar(design_name),child_fev_dot_tcl_path) ""
set ivar_desc($task,$ivar(design_name),child_fev_dot_tcl_path) "For providing fev.tcl path for child blocks"
set ivar_type($task,$ivar(design_name),child_fev_dot_tcl_path) "user"
set ivar_used_by($task,$ivar(design_name),child_fev_dot_tcl_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,$ivar(design_name),child_fev_dot_tcl_path"
####---------------FEV---------------####
set ivar($task,child,golden_fev_dot_tcl_path) ""
set ivar_desc($task,child,golden_fev_dot_tcl_path) "For providing fev.tcl path for child blocks"
set ivar_type($task,child,golden_fev_dot_tcl_path) "user"
set ivar_used_by($task,child,golden_fev_dot_tcl_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,child,golden_fev_dot_tcl_path"
####---------------FEV---------------####
set ivar($task,child,revised_fev_dot_tcl_path) ""
set ivar_desc($task,child,revised_fev_dot_tcl_path) "For providing fev.tcl path for child blocks"
set ivar_type($task,child,revised_fev_dot_tcl_path) "user"
set ivar_used_by($task,child,revised_fev_dot_tcl_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,child,revised_fev_dot_tcl_path"
####---------------FEV---------------####
set ivar($task,r2r_register_mapping) "$env(ward)/runs/$block/$env(tech)/fev_formality/fev_fm_ctechverif/reports/$block.register_mapping.rpt"
set ivar_desc($task,r2r_register_mapping) "For providing r2r register mapping when generating the sigtable"
set ivar_type($task,r2r_register_mapping) "project"
set ivar_used_by($task,r2r_register_mapping) "fev_formality"
lappend ivar(fev,required_ivars) "$task,r2r_register_mapping"
####---------------FEV---------------####
set ivar($task,gen_sig_table) 1 
set ivar_desc($task,gen_sig_table) "For enabling the generation of sigtable"
set ivar_type($task,gen_sig_table) "project"
set ivar_used_by($task,gen_sig_table) "fev_formality"
lappend ivar(fev,required_ivars) "$task,gen_sig_table"
####---------------FEV---------------####
set ivar($task,enable_read_libs) 1 
set ivar_desc($task,enable_read_libs) "Ability to control reading of STD libs for various tasks"
set ivar_type($task,enable_read_libs) "project"
set ivar_used_by($task,enable_read_libs) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_read_libs"
####---------------FEV---------------####
set ivar($task,scan_constraints) 1
set ivar_desc($task,scan_constraints) "For enabling the addition of scan constraints"
set ivar_type($task,scan_constraints) "project"
set ivar_used_by($task,scan_constraints) "fev_formality"
lappend ivar(fev,required_ivars) "$task,scan_constraints"
####---------------FEV---------------####
set ivar($task,lcp_constraints) 1
set ivar_desc($task,lcp_constraints) "For enabling the addition of LCP constraints"
set ivar_type($task,lcp_constraints) "project"
set ivar_used_by($task,lcp_constraints) "fev_formality"
lappend ivar(fev,required_ivars) "$task,lcp_constraints"
####---------------FEV---------------####
set ivar($task,lp) 1
set ivar_desc($task,lp) "For enabling reading of UPF in FM run"
set ivar_type($task,lp) "project"
set ivar_used_by($task,lp) "fev_formality"
lappend ivar(fev,required_ivars) "$task,lp"
####---------------FEV---------------####
set ivar($task,enable_compare_lp) 1
set ivar_desc($task,enable_compare_lp) "For enabling LP compare"
set ivar_type($task,enable_compare_lp) "project"
set ivar_used_by($task,enable_compare_lp) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_compare_lp"
####---------------FEV---------------####
set ivar($task,td_constraints) 1
set ivar_desc($task,td_constraints) "For enabling the addition of feedthrough constraints"
set ivar_type($task,td_constraints) "project"
set ivar_used_by($task,td_constraints) "fev_formality"
lappend ivar(fev,required_ivars) "$task,td_constraints"
####---------------FEV---------------####
set ivar($task,read_rtl_proc_golden) ""
set ivar_desc($task,read_rtl_proc_golden) "For providing the proc used for reading the rtl format(2stage/1stage/dotf) on golden side-default is read_rtl_2stage for rtl_list_2stage.tcl"
set ivar_type($task,read_rtl_proc_golden) "project"
set ivar_used_by($task,read_rtl_proc_golden) "fev_formality"
lappend ivar(fev,required_ivars) "$task,read_rtl_proc_golden"
####---------------FEV---------------####
set ivar($task,read_rtl_proc_revised) ""
set ivar_desc($task,read_rtl_proc_revised) "For providing the proc used for reading the rtl format(2stage/1stage/dotf) on revised side-default is read_rtl_2stage for rtl_list_2stage.tcl"
set ivar_type($task,read_rtl_proc_revised) "project"
set ivar_used_by($task,read_rtl_proc_revised) "fev_formality"
lappend ivar(fev,required_ivars) "$task,read_rtl_proc_revised"
####---------------FEV---------------####
set ivar($task,golden_target) "rtl"
set ivar_desc($task,golden_target) "For specifying the UPF target on the golden side"
set ivar_type($task,golden_target) "project"
set ivar_used_by($task,golden_target) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_target"
####---------------FEV---------------####
set ivar($task,revised_target) "final_pg_netlist"
set ivar_desc($task,revised_target) "For specifying the UPF target on the impl side"
set ivar_type($task,revised_target) "project"
set ivar_used_by($task,revised_target) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_target"
####---------------FEV---------------####
set ivar($task,vclp_path) "/p/hdk/cad/vc_static/V-2023.12-SP2-8"
set ivar_desc($task,vclp_path) "For overriding VCLP version"
set ivar_type($task,vclp_path) "project"
set ivar_used_by($task,vclp_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,vclp_path"
####---------------FEV---------------####
set ivar($task,read_svf_info) 1
set ivar_desc($task,read_svf_info) "For enabling reading of SVF"
set ivar_type($task,read_svf_info) "project"
set ivar_used_by($task,read_svf_info) "fev_formality"
lappend ivar(fev,required_ivars) "$task,read_svf_info"
####---------------FEV---------------####
set ivar($task,map_clk_dops) 1
set ivar_desc($task,map_clk_dops) "For enabling clk dop mapping"
set ivar_type($task,map_clk_dops) "project"
set ivar_used_by($task,map_clk_dops) "fev_formality"
lappend ivar(fev,required_ivars) "$task,map_clk_dops"
####---------------FEV---------------####
set ivar(cth_metric_upload) 1
set ivar_desc(cth_metric_upload) "upload metrics into splunk"
set ivar_type(cth_metric_upload) "user"
set ivar_used_by(cth_metric_upload) "fev_formality"
lappend ivar(fev,required_ivars) "cth_metric_upload"
####---------------FEV---------------####
set ivar(IF_use_md5sum) 0
set ivar_desc(IF_use_md5sum) "change default hash generator for inspectFEV"
set ivar_type(IF_use_md5sum) "user"
set ivar_used_by(IF_use_md5sum) "fev_formality"
lappend ivar(fev,required_ivars) "IF_use_md5sum"
####---------------FEV---------------####
set ivar($task,orig_ref_impl_compare) 1 
set ivar_desc($task,orig_ref_impl_compare) "Enable orig ref vs impl compare in eco pre synth"
set ivar_type($task,orig_ref_impl_compare) "user"
set ivar_used_by($task,orig_ref_impl_compare) "fev_formality"
lappend ivar(fev,required_ivars) "$task,orig_ref_impl_compare"
####---------------FEV---------------####
set ivar($task,metaflop_pattrn_rtl) "*ctech_lib_doublesync* *ctech_lib_triplesync*"
set ivar_desc($task,metaflop_pattrn_rtl) "For providing the metaflop pattern on the rtl side"
set ivar_type($task,metaflop_pattrn_rtl) "user"
set ivar_used_by($task,metaflop_pattrn_rtl) "fev_formality"
lappend ivar(fev,required_ivars) "$task,metaflop_pattrn_rtl"
####---------------FEV---------------####
set ivar($task,metaflop_pattrn_gate) ""
set ivar_desc($task,metaflop_pattrn_gate) "For providing the metaflop pattern on the gate side"
set ivar_type($task,metaflop_pattrn_gate) "user"
set ivar_used_by($task,metaflop_pattrn_gate) "fev_formality"
lappend ivar(fev,required_ivars) "$task,metaflop_pattrn_gate"
####---------------FEV---------------####
set ivar($task,limit_fail_points) 1 
set ivar_desc($task,limit_fail_points) "Limit number of failing points to enable cone size calculation in save session"
set ivar_type($task,limit_fail_points) "user/project"
set ivar_used_by($task,limit_fail_points) "fev_formality"
lappend ivar(fev,required_ivars) "$task,limit_fail_points"
####---------------FEV---------------####
set ivar($task,blackbox_hips) 1 
set ivar_desc($task,blackbox_hips) "Enable Black boxing of HIPS"
set ivar_type($task,blackbox_hips) "user/project"
set ivar_used_by($task,blackbox_hips) "fev_formality"
lappend ivar(fev,required_ivars) "$task,blackbox_hips"
####---------------FEV---------------####
set ivar($task,rtl_list_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_2stage.tcl"
set ivar_desc($task,rtl_list_golden) "For providing file path for rtl list on golden side"
set ivar_type($task,rtl_list_golden) "user"
set ivar_used_by($task,rtl_list_golden) "fev_formality"
lappend ivar(fev,required_ivars) "$task,rtl_list_golden"
####---------------FEV---------------####
set ivar($task,rtl_list_revised) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_2stage.tcl"
set ivar_desc($task,rtl_list_revised) "For providing file path for rtl list on revised side"
set ivar_type($task,rtl_list_revised) "user"
set ivar_used_by($task,rtl_list_revised) "fev_formality"
lappend ivar(fev,required_ivars) "$task,rtl_list_revised"
####---------------FEV---------------####
set ivar($task,rtl_list_f_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_f.tcl"
set ivar_desc($task,rtl_list_f_golden) "For specifying the path of the golden side rtl list"
set ivar_type($task,rtl_list_f_golden) "project"
set ivar_used_by($task,rtl_list_f_golden) "fev_formality"
lappend ivar(fev,required_ivars) "$task,rtl_list_f_golden"
####---------------FEV---------------####
set ivar($task,rtl_list_f_revised) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_f.tcl"
set ivar_desc($task,rtl_list_f_revised) "For specifying the path of the revised side rtl list"
set ivar_type($task,rtl_list_f_revised) "project"
set ivar_used_by($task,rtl_list_f_revised) "fev_formality"
lappend ivar(fev,required_ivars) "$task,rtl_list_f_revised"
####---------------FEV---------------####
set ivar($task,revised_gate) ""
set ivar_desc($task,revised_gate) "For providing file path for revised side netlist"
set ivar_type($task,revised_gate) "user"
set ivar_used_by($task,revised_gate) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_gate"
####---------------FEV---------------####
set ivar($task,golden_gate) ""
set ivar_desc($task,golden_gate) "For providing file path for golden side netlist"
set ivar_type($task,golden_gate) "user"
set ivar_used_by($task,golden_gate) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_gate"
####---------------FEV---------------####
set ivar($task,revised_upf) ""
set ivar_desc($task,revised_upf) "For providing file path for revised side upf"
set ivar_type($task,revised_upf) "user"
set ivar_used_by($task,revised_upf) "fev_formality"
lappend ivar(fev,required_ivars) "$task,revised_upf"
####---------------FEV---------------####
set ivar($task,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name).upf"
set ivar_desc($task,golden_upf) "For providing file path for golden side upf"
set ivar_type($task,golden_upf) "user"
set ivar_used_by($task,golden_upf) "fev_formality"
lappend ivar(fev,required_ivars) "$task,golden_upf"
####---------------FEV---------------####
set ivar($task,guidance_file_path) ""
set ivar_desc($task,guidance_file_path) "For providing file path for guidance file"
set ivar_type($task,guidance_file_path) "user"
set ivar_used_by($task,guidance_file_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,guidance_file_path"
####---------------FEV---------------####
set ivar($task,clk_dop_map_file) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2/$ivar(design_name).fev_map"
set ivar_desc($task,clk_dop_map_file) "For providing file path for clock dop map file"
set ivar_type($task,clk_dop_map_file) "user"
set ivar_used_by($task,clk_dop_map_file) "fev_formality"
lappend ivar(fev,required_ivars) "$task,clk_dop_map_file"
####---------------FEV---------------####
set ivar($task,fev_dot_tcl_path) ""
set ivar_desc($task,fev_dot_tcl_path) "For providing file path for guidance file"
set ivar_type($task,fev_dot_tcl_path) "user"
set ivar_used_by($task,fev_dot_tcl_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,fev_dot_tcl_path"
####---------------FEV---------------###
set ivar($task,eco_rtl) ""
set ivar_desc($task,eco_rtl) "For providing file path for post eco rtl list"
set ivar_type($task,eco_rtl) "user"
set ivar_used_by($task,eco_rtl) "fev_formality"
lappend ivar(fev,required_ivars) "$task,eco_rtl"
####---------------FEV---------------####
set ivar($task,orig_rtl) ""
set ivar_desc($task,orig_rtl) "For providing file path for pre eco rtl list"
set ivar_type($task,orig_rtl) "user"
set ivar_used_by($task,orig_rtl) "fev_formality"
lappend ivar(fev,required_ivars) "$task,orig_rtl"
####---------------FEV---------------####
set ivar($task,orig_netl) ""
set ivar_desc($task,orig_netl) "For providing file path for pre eco netlist"
set ivar_type($task,orig_netl) "user"
set ivar_used_by($task,orig_netl) "fev_formality"
lappend ivar(fev,required_ivars) "$task,orig_netl"
####---------------FEV---------------####
set ivar($task,orig_ndm) ""
set ivar_desc($task,orig_ndm) "For providing file path for pre eco ndm"
set ivar_type($task,orig_ndm) "user"
set ivar_used_by($task,orig_ndm) "fev_formality"
lappend ivar(fev,required_ivars) "$task,orig_ndm"
####---------------FEV---------------####
set ivar($task,targ_syn_svf) ""
set ivar_desc($task,targ_syn_svf) "For providing file path for targeted synthesis svf"
set ivar_type($task,targ_syn_svf) "user"
set ivar_used_by($task,targ_syn_svf) "fev_formality"
lappend ivar(fev,required_ivars) "$task,targ_syn_svf"
####---------------FEV---------------####
set ivar($task,targ_syn_gate) ""
set ivar_desc($task,targ_syn_gate) "For providing file path for targeted synthesis netlist"
set ivar_type($task,targ_syn_gate) "user"
set ivar_used_by($task,targ_syn_gate) "fev_formality"
lappend ivar(fev,required_ivars) "$task,targ_syn_gate"
####---------------FEV---------------####
set ivar($task,targ_syn_ndm) ""
set ivar_desc($task,targ_syn_ndm) "For providing file path for targeted synthesis ndm"
set ivar_type($task,targ_syn_ndm) "user"
set ivar_used_by($task,targ_syn_ndm) "fev_formality"
lappend ivar(fev,required_ivars) "$task,targ_syn_ndm"
####---------------FEV---------------####
set ivar($task,fm_path) ""
set ivar_desc($task,fm_path) "For providing formality tool version path"
set ivar_type($task,fm_path) "user"
set ivar_used_by($task,fm_path) "fev_formality"
lappend ivar(fev,required_ivars) "$task,fm_path"
####---------------FEV---------------####
set ivar($task,enable_dpx) 0 
set ivar_desc($task,enable_dpx) "Enable DPX"
set ivar_type($task,enable_dpx) "user/project"
set ivar_used_by($task,enable_dpx) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_dpx"
####---------------FEV---------------####
set ivar($task,dpx_batch) 1 
set ivar_desc($task,dpx_batch) "To run DPX on Netbatch"
set ivar_type($task,dpx_batch) "user/project"
set ivar_used_by($task,dpx_batch) "fev_formality"
lappend ivar(fev,required_ivars) "$task,dpx_batch"
####---------------FEV---------------####
set ivar(fev,waived_ivars) "scenario_name enable_dpx dpx_batch limit_fail_points"
set ivar_desc(fev,waived_ivars) "List of ivars to be auto waived from ReportUserIvarOverride audit"
set ivar_type(fev,waived_ivars) "project"
set ivar_used_by(fev,waived_ivars) "fev_formality"
lappend ivar(fev,required_ivars) "fev,waived_ivars"
####---------------FEV---------------####
set ivar($task,enable_unoptimized_patch) 0 
set ivar_desc($task,enable_unoptimized_patch) "To generate unoptimied patch in eco pre synth"
set ivar_type($task,enable_unoptimized_patch) "user/project"
set ivar_used_by($task,enable_unoptimized_patch) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_unoptimized_patch"
####---------------FEV---------------####
set ivar($task,enable_ML_dpx) 0 
set ivar_desc($task,enable_ML_dpx) "Enable ML DPX"
set ivar_type($task,enable_ML_dpx) "user/project"
set ivar_used_by($task,enable_ML_dpx) "fev_formality"
lappend ivar(fev,required_ivars) "$task,enable_ML_dpx"
####---------------FEV---------------####
set ivar($task,FM_ML_HOME) "/p/hdk/cad/cmlp/T-2022.03"
set ivar_desc($task,FM_ML_HOME) "For setting ML DPX version"
set ivar_type($task,FM_ML_HOME) "project"
set ivar_used_by($task,FM_ML_HOME) "fev_formality"
lappend ivar(fev,required_ivars) "$task,FM_ML_HOME"
####---------------FEV---------------####
set ivar($task,generate_checkpt) 1
set ivar_desc($task,generate_checkpt) "For enabling/disabling save session generation, by default save session generation is on"
set ivar_type($task,generate_checkpt) "project"
set ivar_used_by($task,generate_checkpt) "fev_conformal"
lappend ivar(fev,required_ivars) "$task,generate_checkpt"
####---------------FEV---------------####

#-- fev_retime
set ivar(fev_retime,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/retime/$ivar(design_name).pt.v.gz"
set ivar(fev_retime,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/retime/$ivar(design_name).upf"
set ivar(fev_retime,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(fev_retime,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/retime/$ivar(design_name).svf"


#-- fev_fm_rtl2apr
set ivar(fev_fm_rtl2apr,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_rtl2apr,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/$ivar(design_name).upf"
set ivar(fev_fm_rtl2apr,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/$ivar(design_name).svf"
set ivar(fev_fm_rtl2apr,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(fev_fm_rtl2apr,frd_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/fm_eco_region.frd"

#-- fev_fm_rtl2syn
set ivar(fev_fm_rtl2syn,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_initial_opto/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_rtl2syn,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_initial_opto/$ivar(design_name).upf"
set ivar(fev_fm_rtl2syn,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_initial_opto/$ivar(design_name).svf"
set ivar(fev_fm_rtl2syn,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(fev_fm_rtl2syn,frd_file_path) ""

#-- fev_fm_syn2apr
set ivar(fev_fm_syn2apr,golden_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_initial_opto/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_syn2apr,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_syn2apr,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_initial_opto/$ivar(design_name).upf"
set ivar(fev_fm_syn2apr,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/finish/$ivar(design_name).upf"
set ivar(fev_fm_syn2apr,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(fev_fm_syn2apr,golden_target) "final_pg_netlist"
set ivar(fev_fm_syn2apr,revised_target) "final_pg_netlist"

#-- fev_fm_rtl2logicopto 
set ivar(fev_fm_rtl2logicopto,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/logic_opto/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_rtl2logicopto,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/logic_opto/$ivar(design_name).upf"
set ivar(fev_fm_rtl2logicopto,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/logic_opto/$ivar(design_name).svf"
set ivar(fev_fm_rtl2logicopto,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"


#-- fev_fm_full_febe
set ivar(fev_fm_full_febe,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_full_febe/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_full_febe,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_full_febe/$ivar(design_name).upf"
set ivar(fev_fm_full_febe,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_full_febe/$ivar(design_name).svf"
set ivar(fev_fm_full_febe,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"


#-- fev_fm_quick_febe
set ivar(fev_fm_quick_febe,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_quick_febe/$ivar(design_name).pt.v.gz"
set ivar(fev_fm_quick_febe,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_quick_febe/$ivar(design_name).upf"
set ivar(fev_fm_quick_febe,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/compile_quick_febe/$ivar(design_name).svf"
set ivar(fev_fm_quick_febe,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"


#-- fev_fm_rtl2rtl
set ivar(fev_fm_rtl2rtl,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name).upf"
set ivar(fev_fm_rtl2rtl,revised_target) "rtl"
set ivar(fev_fm_rtl2rtl,lp) 1 

#-- fev_fm_fcl
set ivar(fev_fm_fcl,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/self_collateral/icc2/$ivar(design_name)_td.v"
set ivar(fev_fm_fcl,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(fev_fm_fcl,lp) 0 
set ivar(fev_fm_fcl,read_svf_info) 0

#-- fev_fm_lite
set ivar(fev_fm_lite,lp) 1
set ivar(fev_fm_lite,enable_compare_lp) 0 
set ivar(fev_fm_lite,read_svf_info) 0 

#-- fev_fm_sim2syn
set ivar(fev_fm_sim2syn,rtl_list_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_2stage_sim.tcl"
set ivar(fev_fm_sim2syn,rtl_list_f_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_2stage_sim.tcl"
set ivar(fev_fm_sim2syn,rtl_list_f_revised) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/rtl_list_2stage.tcl"
set ivar(fev_fm_sim2syn,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name)_sim.upf"
set ivar(fev_fm_sim2syn,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name).upf"
set ivar(fev_fm_sim2syn,revised_target) "rtl"
set ivar(fev_fm_sim2syn,lp) 0

#-- fev_fm_ctechverif
set ivar(fev_fm_ctechverif,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name).upf"
set ivar(fev_fm_ctechverif,revised_target) "rtl"
set ivar(fev_fm_ctechverif,lp) 0

#-- fev_fm_hier2flat_upf
set ivar(fev_fm_hier2flat_upf,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name)_hier.upf"
set ivar(fev_fm_hier2flat_upf,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/fe_collateral/$ivar(design_name).upf"
set ivar(fev_fm_hier2flat_upf,revised_target) "rtl"
set ivar(fev_fm_hier2flat_upf,lp) 1

#-- fev_eco_pre_synth
set ivar(eco_pre_synth,lp) 0
set ivar(eco_pre_synth,orig_rtl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_pre_synth,orig_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_pre_synth,orig_netl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).pt_nonpg.v.gz"
set ivar(eco_pre_synth,orig_ndm) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).ndm"
set ivar(eco_pre_synth,frd_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/fm_eco_region.frd"
set ivar(eco_pre_synth,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).svf"
set ivar(eco_pre_synth,eco_rtl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_pre_synth,eco_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_pre_synth,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"

#-- fev_eco_post_synth
set ivar(eco_post_synth,lp) 0
set ivar(eco_post_synth,eco_rtl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_post_synth,eco_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/$ivar(design_name).upf" 
set ivar(eco_post_synth,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(eco_post_synth,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).svf"
set ivar(eco_post_synth,targ_syn_svf) "$env(ward)/runs/$block/$env(tech)/apr_fc/eco_ts_flow.svf"
set ivar(eco_post_synth,targ_syn_gate) "$env(ward)/runs/$block/$env(tech)/apr_fc/outputs/targeted_synth/$ivar(design_name).pt_nonpg.v.gz"
set ivar(eco_post_synth,targ_syn_ndm) "$env(ward)/runs/$block/$env(tech)/apr_fc/outputs/targeted_synth/$ivar(design_name).ndm"

#-- fev_eco_confirm_patch
set ivar(eco_confirm_patch,lp) 0
set ivar(eco_confirm_patch,eco_rtl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_confirm_path,eco_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_confirm_patch,orig_netl) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).pt_nonpg.v.gz"
set ivar(eco_confirm_patch,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).svf"
set ivar(eco_confirm_patch,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"

#-- eco_pre_rtl_to_post_rtl
set ivar(eco_pre_rtl_to_post_rtl,rtl_list_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_pre_rtl_to_post_rtl,rtl_list_revised) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_pre_rtl_to_post_rtl,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_pre_rtl_to_post_rtl,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_pre_rtl_to_post_rtl,revised_target) "rtl"
set ivar(eco_pre_rtl_to_post_rtl,lp) 1 
set ivar(eco_pre_rtl_to_post_rtl,gen_sig_table) 0 

#-- eco_pre_rtl_to_pre_net
set ivar(eco_pre_rtl_to_pre_net,rtl_list_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_pre_rtl_to_pre_net,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).pt.v.gz"
set ivar(eco_pre_rtl_to_pre_net,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_pre_rtl_to_pre_net,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).upf"
set ivar(eco_pre_rtl_to_pre_net,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).svf"
set ivar(eco_pre_rtl_to_pre_net,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(eco_pre_rtl_to_pre_net,frd_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/fm_eco_region.frd"
set ivar(eco_pre_rtl_to_pre_net,gen_sig_table) 0 

#-- eco_post_rtl_to_eco_net
set ivar(eco_post_rtl_to_eco_net,rtl_list_golden) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/rtl_list_2stage.tcl"
set ivar(eco_post_rtl_to_eco_net,revised_gate) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/eco_patched_design/$ivar(design_name).pt.v.gz"
set ivar(eco_post_rtl_to_eco_net,golden_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/post_eco_fe_collateral/$ivar(design_name).upf"
set ivar(eco_post_rtl_to_eco_net,revised_upf) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/eco_patched_design/$ivar(design_name).upf"
set ivar(eco_post_rtl_to_eco_net,guidance_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/pre_eco_design/$ivar(design_name).svf"
set ivar(eco_post_rtl_to_eco_net,fev_dot_tcl_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/td_collateral/icc2"
set ivar(eco_post_rtl_to_eco_net,frd_file_path) "$env(ward)/runs/$block/$env(tech)/release/$env(tag)/eco_patched_design/fm_eco_region.frd"
set ivar(eco_post_rtl_to_eco_net,gen_sig_table) 0 

##Global ivars related to stdcell libs and HIP libs:
lappend ivar(fev,required_ivars) "link_libs"
lappend ivar(fev,required_ivars) "mcmm,scenario_dc_all"
foreach linkLib $ivar(link_libs) {
	lappend ivar(fev,required_ivars) "lib,$linkLib,use_ccs"
	lappend ivar(fev,required_ivars) "lib,$linkLib,db_nldm_filelist,*"
	lappend ivar(fev,required_ivars) "lib,$linkLib,db_ccs_filelist,*"
	lappend ivar(fev,required_ivars) "lib,$linkLib,verilog_default_filelist"
}	

#setting metaflop_pattrn_gate based on ivar LIB_NAME

set libtype ""
if {[info exists ivar(params,LIB_NAME)] && ($ivar(params,LIB_NAME) ne "") } {
    if {[regexp {_} $ivar(params,LIB_NAME) match]} {
        regsub -all {_} $ivar(params,LIB_NAME) " " libtype
    } else {
        set libtype $ivar(params,LIB_NAME)
    }

    foreach lib $libtype {
        lappend ivar($task,metaflop_pattrn_gate) "${lib}fmn*"
        lappend ivar($task,metaflop_pattrn_gate) "${lib}fmz*"
    }

} else {
    iproc_msg -warning "ivar(params,LIB_NAME) is not defined, ivar($task,metaflop_pattrn_gate) is set to empty. Metaflop verification will fail." 
}

################################################################################################################
################################################################################################################
##Avoid duplication of dumping of ivars
set ivar(fev,required_ivars) [lsort -unique $ivar(fev,required_ivars)]

################################################################################################################

