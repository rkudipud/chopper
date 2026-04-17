####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


puts "=I= running pre_compile script for targeted synthesis eco flow ([date])"
   set cb [get_object_name [current_block]]
   puts "current_block = $cb"

puts "=I= disabling default_VA ([date])"
   # from ./global/snps/apr_fc/fc.app_options.global.tcl 
   if { $ivar(abutted_design) || [get_attribute [get_voltage_areas DEFAULT_VA] effective_shapes] == ""} {
      set_app_options  -name opt.common.blocked_vas               -value {DEFAULT_VA}
      set_app_options  -name opt.common.no_new_cells_in_top       -value true
      set_app_options  -name hfb.infra.no_new_cells_in_default_VA -value true
      set_app_options  -name dft.no_new_cells_in_default_VA       -value true
   }

puts "=I= deleting filler cells ([date])"
   # from FC ECO Synopsys training
   set filler_cells [get_cells -hier -filter design_type==filler -quiet]
   puts "=I= deleting [sizeof $filler_cells] filler cells ([date])"
   eval_with_undo -disable {
      if {[sizeof $filler_cells] > 0} { remove_cells -force $filler_cells }
   }

puts "=I= deleting phys_only cells ([date])"
   # from ./global/snps/apr_fc/apr_eco_operations.tcl
   # remove_cells_xofiller
   set                  filler_cells [get_cells -hierarchical -quiet -filter "name =~*xofiller* && name !~ *tapfiller* && name !~ *postroute* && is_physical_only ==true"]
   append_to_collection filler_cells [get_cells -hierarchical -quiet -filter "name =~*flexfill* && name !~ *tapfiller* && name !~ *postroute* && ref_name !~ *ztp* && is_physical_only ==true"]
   # iakolmyc: Formality cannot link these cells (no ldb available), so deleting them
   append_to_collection filler_cells [get_cells -hierarchical -quiet -filter "name =~boundarycell_* && name !~ *tapfiller* && ref_name !~ *ztp* && is_physical_only ==true"]
   append_to_collection filler_cells [get_cells -hierarchical -quiet -filter "name =~postroute_* && name !~ *tapfiller* && ref_name !~ *ztp* && is_physical_only ==true"]
   puts "=I= deleting [sizeof $filler_cells] phys_only cells ([date])"
   if {[sizeof $filler_cells] > 0} { remove_cells $filler_cells }

puts "=I= applying ungroup prevention WA ([date])"
   # prevent errors
   # Error: The region defined by the constraints DEFAULT_VA & ts_par_ringft1 has zero area and 15 cells. (PLACE-019)
   # Error: Error in placement constraints. (PLACE-017)
   # Error: Optimization failed at create_placement
   set pd_elements [get_cells *SNPS_VAO_HIER* -hierarchical -filter "is_hierarchical==true"]
   if {[sizeof_collection $pd_elements] > 0} {
      puts "=I= disable ungroup on: [get_object_name $pd_elements]"
      set_ungroup $pd_elements false
   }

puts "=I= reducing number of timing corners ([date])"
   set ivar(task) compile_initial_opto
   set ivar(FTAT_flow) 1
   set ivar(freq_based_cmax_override) 0
   iproc_source -file modes_corners_scenarios.tcl -optional
   set ivar(task) targeted_synth

puts "=I= applying scan constraints ([date])"
   # iproc_source -file dft_input_mapping.tcl
   # iproc_source -file dft_pre_compile.tcl
   source -verbose $ivar(dft_pre_compile_setup_file)
   set nonscan_cells ""
   set all_cells [get_cells -hierarchical]
   foreach module $::dft::nonscan_designs {
      set local_nonscan_cell [get_object_name [filter_collection $all_cells "ref_name =~ $module"]]
      lappend nonscan_cells $local_nonscan_cell
      lappend nonscan_cells [get_object_name [get_flat_cells -quiet -of_objects [get_cells -quiet $local_nonscan_cell -filter "is_hierarchical == true"] -filter "is_sequential == true"]]
   }
   set nonscan_cells [lsort -uniq $nonscan_cells]
   foreach instance $::dft::nonscan_instances {
      lappend nonscan_cells [get_object_name [filter_collection $all_cells "full_name =~ $instance && (is_hierarchical == true || is_sequential == true)"]]
   }
   set nonscan_cells [join $nonscan_cells]
   puts "=I= setting scan_element=false on [llength $nonscan_cells] cells ([date])"
   if {[llength $nonscan_cells] > 0} {
      set_scan_element false $nonscan_cells
   }

puts "=I= disable MBIT per Synopsys recommendation"
   set_app_option -name compile.flow.enable_multibit -value false

puts "=I= saving pre-synth block ([date])"
   save_block -as [regsub {:} $cb {:pre_}]
   write_verilog -compress gzip -exclude {supply_statements pg_netlist physical_only_cells} $ivar(dst_dir)/$ivar(design_name).pre_compile.pt_nonpg.v.gz

