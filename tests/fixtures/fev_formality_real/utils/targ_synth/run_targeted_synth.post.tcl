####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


puts "=I= running post_compile script for targeted synthesis eco flow ([date])"
puts "current_block = [get_object_name [current_block]]"

puts "=I= running change_names ([date])" 
iproc_source -file step_change_names.tcl

puts "=I= saving block"
set_svf -off
save_block

puts "=I= saving eco netlist ([date])"
write_verilog -compress gzip -exclude {empty_modules scalar_wire_declarations leaf_module_declarations supply_statements pg_netlist physical_only_cells} $ivar(dst_dir)/$ivar(design_name).pt_nonpg.v.gz

puts "=I= renaming lib"
  set cur_lib [get_attribute [current_lib] source_file_name]
  puts "  From: $cur_lib"
  puts "  To:   $ivar(dst_dir)/$ivar(design_name).ndm"
  if {"$cur_lib" != "$ivar(dst_dir)/$ivar(design_name).ndm"} {
    save_lib -as $ivar(dst_dir)/$ivar(design_name).ndm
    file delete -force $cur_lib
  }
  #close_lib -all

puts "=I= mimicking correct exit message ([date])"
puts "Thank you for using Fusion Compiler."

