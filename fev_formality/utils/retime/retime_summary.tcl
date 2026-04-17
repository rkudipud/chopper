####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


##Usage : retime_summary.tcl <partition block name> <fev task>
          set env(block) [lindex $argv 0]		
          set task [lindex $argv 1]
		  set ivar(src_dir) $task
		  source $env(ward)/global/common/setup.tcl
		  source $env(ward)/runs/$env(block)/$env(tech)/scripts/vars.tcl
		  set design_name $ivar(design_name)
		  array set status_arr {} 
		  array set status_string_arr {} 
		  array set logf_arr {} 
		  set status ""
		  set status_string ""
		  set logf ""
		  set fubs_final_status_flag ""
		  set design_final_status_flag ""
		  set fubs_final_status_temp 1

		  set par_pass "$env(ward)/runs/$env(block)/$env(tech)/fev_conformal/$task/logs/$task.pass"
		  set par_fail "$env(ward)/runs/$env(block)/$env(tech)/fev_conformal/$task/logs/$task.fail"

		  set header "-------- Summary of retime fubs and $design_name --------"
		  
		  set rpt "$env(ward)/runs/$env(block)/$env(tech)/fev_conformal/$task/${design_name}.retime.summary.rpt"
		  set rpt_fh [open "$rpt" w]

		  puts $rpt_fh "[string repeat - [string length $header]]" 
		  puts $rpt_fh $header 
		  puts $rpt_fh "[string repeat - [string length $header]]" 

		  if { ([file exists $par_pass] && [file exists $par_fail]) } {
					 set status "Abort"
					 set status_string "Either $task.pass or $task.fail files are present"
					 set logf $par_pass
		  } elseif { [file exists $par_pass] } {
					 set status "Pass"
					 set status_string [read [open $par_pass r]]
					 set logf $par_pass
		  } elseif { [file exists $par_fail] } {
					 set status "Fail"
					 set status_string [read [open $par_fail r]]
					 set logf $par_fail
		  } else {
					 set status "Abort" 
					 set status_string "Neither $task.pass and $task.fail files are present"
					 set logf $par_pass
		  }
		 
		  set status_string_arr($design_name) $status_string
		  set status_arr($design_name) $status
		  set logf_arr($design_name) $logf

		  if { $status_arr($design_name) == "Pass" } {
					 set design_final_status_flag 1
		  } else { 
					 set design_final_status_flag 0
		  }
		  set len_design [expr [string length $design_name] + 1]
		  set len ""
		  set sno 1
		  set fmt "%-*s%-*s%-*s"
		  if {[info exists ivar(enable_retiming)] && $ivar(enable_retiming) } {
					 if {[info exists ivar(retime_fubs)] && $ivar(retime_fubs) != ""} {	
								foreach fub $ivar(retime_fubs) {
										  set len_tmp [expr [string length $fub] + 1]
										  if { $len_tmp > $len }  { 
													 set len $len_tmp 
										  } elseif { $len_design > $len} { 
													 set len $len_design 
										  } else { }
								}	

								set len [expr $len + 10]
								puts $rpt_fh "[format $fmt 10 "S.NO." $len "DESIGN" 6 "STATUS"]"
								puts $rpt_fh "[string repeat = [string length $header]]"
								puts $rpt_fh "[format $fmt 10 1 $len $design_name 6 $status]"

								foreach fub $ivar(retime_fubs) {
										  incr sno
										  set fub_pass "$env(ward)/runs/${fub}.$env(block)/$env(tech)/fev_formality/fev_retime/logs/fev_retime.pass"
										  set fub_fail "$env(ward)/runs/${fub}.$env(block)/$env(tech)/fev_formality/fev_retime/logs/fev_retime.fail"
										  if { ([file exists $fub_pass] && [file exists $fub_fail]) } {
													 set status "Abort"
													 set status_string "Either $task.pass or $task.fail files are present"
													 set logf $fub_pass
										  } elseif { [file exists $fub_pass] } {
													 set status "Pass"
													 set status_string [read [open $fub_pass r]]
													 set logf $fub_pass
										  } elseif { [file exists $fub_fail] } {
													 set status "Fail"
													 set status_string [read [open $fub_fail r]]
													 set logf $fub_fail
										  } else {
													 set status "Abort" 
													 set status_string "Neither $task.pass and $task.fail files are present"
													 set logf $fub_pass
										  }
										   
										  puts $rpt_fh "[format $fmt 10 $sno $len $fub 6 $status]"

										  set status_arr($fub) $status
										  set status_string_arr($fub) $status_string
										  set logf_arr($fub) $logf

										  if { $status_arr($fub) == "Pass" } {
													 set fubs_final_status_flag 1
										  } else { 
													 set fubs_final_status_flag 0
										  }
										  set fubs_final_status_flag [expr $fubs_final_status_flag * $fubs_final_status_temp]
										  set fubs_final_status_temp $fubs_final_status_flag
								}
							
								set final_status [expr $fubs_final_status_flag * $design_final_status_flag]
								puts $rpt_fh "[string repeat = [string length $header]]"
							
								if {$final_status == 1 } {
										  puts $rpt_fh "RETIME RESULT SUMMARY: PASS"
								} else {
										  puts $rpt_fh "RETIME RESULT SUMMARY: FAIL"
								}
								puts $rpt_fh "[string repeat = [string length $header]]"
#								puts $rpt_fh "Time stamp : [clock format [clock seconds] -format "%d %b %Y, %H:%M"]"   

								foreach fub $ivar(retime_fubs) {
										  if { $status_arr($fub) == "Fail" } {
													 puts $rpt_fh "\nINFO: Retime fub $fub is failing with the following Error(s): \n$status_string_arr($fub)"
													 puts $rpt_fh "INFO: Please check the file: $logf_arr($fub)\n"
										  } elseif { $status_arr($fub) == "Abort" } {
													 set log_path [file dirname $logf_arr($fub)]
													 puts $rpt_fh "\nINFO: Retime fub $fub has either both $task.pass and $task.fail files or neither of them \nINFO: Check logs area: $log_path\n"
										  } else {
										  } 
								}
								if { $status_arr($design_name) == "Fail" } {
										  puts $rpt_fh "\nINFO: Design $design_name is failing with the following Error(s): \n$status_string_arr($design_name)"
										  puts $rpt_fh "INFO: Please check the file: $logf_arr($design_name)\n"
								} elseif { $status_arr($design_name) == "Abort" } {
										  set log_path [file dirname $logf_arr($design_name)]
										  puts $rpt_fh "\nINFO: Design $design_name has either both $task.pass and $task.fail files or neither of them \nINFO: Check logs area: $log_path\n"
								} else {
								}
					 }
		  }
		  close $rpt_fh

