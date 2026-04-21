####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


#-- Last code rework - 2024.03


################################################################################
#proc	    : Abort										
#purpose    : To checks for aborts in verification
################################################################################
proc Abort {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(Abort)]
    set RULE_DESC "Verification Failed due to Abort Points in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Verification Failed, Abort points found"
    set FIX_ADVICE($proc_name) "Fix the Abort points"
    set RULE_OWNER($proc_name) "Ashley, Catherine"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set result 0

    # Aborts are reported in the aborted_points.rpt, could not find reference in the log file
    set abrt_rpt "$fev_run_dir/reports/${block}.aborted_points.rpt"
    if { (![file exists $abrt_rpt]) } {
        puts $filew "FATAL violation: $abrt_rpt File Not Found"
        set tmpmsg "$abrt_rpt rpt is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $abrt_rpt Found"
    }

    set verif [open $abrt_rpt r]
    set fatal 0
    set parse 0
    set abortpoints 0
    while { [gets $verif line] >= 0 } {
        if { [ regexp {No aborted compare points} $line] } {
            set result 0
        } elseif { [ regexp {(Hard|Loop)\s+:\s+Ref\s+(DFF|PO|DLAT|CUT|BBOX|Port)\s+r:(.*)} $line match hardloop golType golName] } {
            incr abortpoints
            set parse 1
            set result 1
        } elseif { $parse } {
            if { [ regexp {\s+Impl\s+(DFF|PO|DLAT|CUT|BBOX|Port)\s+i:(.*)} $line match revType revName] } {
                set tmpmsg "$golType $golName $revType $revName"
                lappend ERROR_LIST $tmpmsg
                set result 1
            }
            set parse 0
        } elseif { [ regexp {before (\S*)} $line] } {
            set fatal 1  
            set result 1
            set tmpmsg "$block ERROR: Run fail to complete"
            lappend ERROR_LIST $tmpmsg
        }
    }

    close $verif

    if { $fatal } {
        puts $filew "$prefix Run fail to complete"
    }
    if { $abortpoints } {
        puts $filew "$prefix Abort points exist: Check reports/*.aborted_points.rpt for details"
    }

    return $result
}


################################################################################
#proc	    : CheckBadRenamingRules										
#purpose    : To checks for Bad renaming rules in verification
################################################################################
proc CheckBadRenamingRules {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER ERRGEN_RULE_VAR
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckBadRenamingRules)]
    #set RULE_DESC "Found renaming/Compare rules that can be applied on interface ports. Please Specify -type option to set_compare_rules so that it won't be applied to a PORT but only be on flops and latches for the integrity of the FEV run"
    set RULE_DESC "Found renaming rules to be applied on interface ports."
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Bad renaming rule errors."
    set FIX_ADVICE($proc_name) "Review the renaming rules on PI/PO/BBOX pin in $block.renaming_rules.rpt"
    set RULE_OWNER($proc_name) "Eyoel, Armede"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"
    
    set comp_rule_ref_rpt "$fev_run_dir/reports/$block.compare_rules_ref.rpt"
    set comp_rule_impl_rpt "$fev_run_dir/reports/$block.compare_rules_impl.rpt"
    
    
    if {![file exists $comp_rule_ref_rpt]  || ![file exists $comp_rule_impl_rpt]} {
        puts $filew "FATAL violation: File - $comp_rule_ref_rpt or $comp_rule_impl_rpt not found"
        set tmpmsg "$comp_rule_ref_rpt or $comp_rule_impl_rpt files are not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required Files - $comp_rule_ref_rpt and $comp_rule_impl_rpt  found"
    }
    
    set module $block
    set report_badrenrule 0
    
    set file_list {}
    lappend file_list $comp_rule_ref_rpt
    lappend file_list $comp_rule_impl_rpt

    foreach comp_file $file_list {
        #puts "file-name----$comp_file--"
        set LOGFH [open $comp_file]
        set RRside "ref"
        if {[regexp {impl.rpt$} $comp_file]} {
           set RRside "impl"
        }
        while { [gets $LOGFH line] >= 0 } { 
            if { [regexp {^\s*$} $line] } { continue } ; #ignoring blank lines
            if { [regexp {^\s*//.*$} $line] } { continue } ; #ignoring comment lines
            if { [regexp {^\s*#.*$} $line] } { continue } ; #ignoring comment lines
            if { [regexp {^\s*\'(\S+)\'\s+\-\>\s+\'(\S+)\'} $line  match RRname RRrename ] } {
                #puts "--$RRname---$RRrename--"  
                set msg "$RRname $RRside $RRrename"
                set found_issue 0
                if { [regexp {.*\-type\s+(\S+)} $line match2 type] } {
                   if { $type eq "PORT" } {
                       set found_issue 1                      
                   } 
                } else {
                   set found_issue 1
                }
    
                if { $ERRGEN_SVRTY(CheckBadRenamingRules) eq "ERROR"  && $found_issue } {
                   set tmpmsg "$msg"
                   lappend ERROR_LIST $tmpmsg
                   set report_badrenrule 1
                }
            }
        }
        close $LOGFH
    }

    if { $report_badrenrule } {
        puts $filew "$prefix Bad renaming/compare rule errors found in the design: Check reports/*.compare_rules_ref/impl.rpt for details.Please provide a -type option in your set_compare_rules command so that it is not applied to a PORT by mistake"
    }
    
    return $report_badrenrule
}


################################################################################
#proc	    : CheckforGeneralError										
#purpose    : To checks for Genral errors in the run
################################################################################
proc CheckforGeneralError {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER

    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckforGeneralError)]
    set proc_name [lindex [info level 0] 0]
    set RULE_DESC " Errors found in the FEV run"
    set DESC($proc_name) "Errors found in the fev run"
    set FIX_ADVICE($proc_name) "Please check the Error msgs in the fm.log"
    set RULE_OWNER($proc_name) "Suresh Babu, Malliga"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0
    set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "$log_file file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }

    set LOGFH [open $log_file]
    while { [gets $LOGFH line] >= 0 } {
        if { [ regexp -nocase {^(//)?\s*errors\s*:?\s*$} $line] } { continue }
        if { (([ regexp -nocase {^(//)?\s*(error|fatal|intel_error)\s*:?\s*(.+)$} $line match - - errormsg]) || ([ regexp {^// (Warning: Error exit from dofile)} $line match errormsg])) } {
            # exclude the error messages that are captured from VCLP Tree Summary
            if { [regexp {^\s+error\s+(\S+)\s+(\S+)\s+(\d+)$} $line] } { continue }
            set violation 1
            regsub -all {\[\S+ \d+ \d+:\d+:\d+\]} $errormsg "" errormsg 
            regsub -all {\[\w+ \w+ +\d+ \d+:\d+:\d+ \d+\]} $errormsg "" errormsg 
            if { $ERRGEN_SVRTY(CheckforGeneralError) == "ERROR" } {
                set tmpmsg "$errormsg"
                lappend ERROR_LIST $tmpmsg
            }
        }
    }
    close $LOGFH

    if { $violation } {
        puts $filew "$prefix Errors found in the log during the fev run"
    }
    return $violation
}


################################################################################
#proc	    : CheckFevDotTcl										
#purpose    : To checks for fot Tcl in fev RUN
################################################################################
proc CheckFevDotTcl {} {
	puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER 
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckFevDotTcl)]
    set RULE_DESC "Reports missing ports in the design that are referred to in fev_fm.tcl commands"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Reports missing ports in the design that are referred to in fev_fm.tcl commands"
    set RULE_OWNER($proc_name) "Miklesh Naicker"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"
    
    set violation 0

    set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "$log_file file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }

    set LOGFH [open $log_file]
    set in_fev_dot_tcl 0
    while { [gets $LOGFH line] >= 0 } {
        if { ![regexp "Applying TD constraints for $task" $line] && !$in_fev_dot_tcl } { continue }
        set in_fev_dot_tcl 1
        if { [regexp {Done running: add_fm_td_constraints} $line] } { break }
        if { [regexp {Warning:\s+set_feedthrough_points:\s+(.*)} $line - errormsg] } {
            set violation 1
            lappend ERROR_LIST $errormsg
        }
    }
    close $LOGFH
	if { $violation } {
        puts $filew "$prefix Missing ports found in the design that are referred to in fev_fm.tcl: Check logs/fm.log for details"
    }
    return $violation
}


################################################################################
#proc	    : CheckIllegalDefines										
#purpose    : To checks for Illegal defines in desing elab
################################################################################
proc CheckIllegalDefines {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block ILLEGAL_DEFINES_LIST ERRGEN_RULE_VAR fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckIllegalDefines)]
    set proc_name [lindex [info level 0] 0]
    set RULE_DESC "Illegal defines found during read sverilog"
    set DESC($proc_name) "Illegal defines found during read_sverilog command"
    set FIX_ADVICE($proc_name) "Please remove illegal defines from read_sverilog command"
    set RULE_OWNER($proc_name) "Suresh Babu, Malliga"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

    set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "$log_file file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }


    # iterating through log
    set log_fp [open $log_file r]
    while { [gets $log_fp line] >= 0 } {
        if { [regexp "(Command:|;##)\\s*(read_sverilog|read_vhdl)\\s+(.*)" $line ] } {
            set found 0
            set unitname $block

            ## case 1 anything after -define { } //content inside braces
            if { [regexp {\-define\s+\{([^\}]*)\}} $line -> match] } {
                regsub -all {[\{|\}]} $match "" match
                set found 1

            ## case 2 anything after -define  till next opening brace //content inside braces
            } elseif { [regexp {\-define\s+([^\{]*)} $line -> match] } {
                regsub -all {[\{|\}]} $match "" match
                set found 1
            }

            if { $found == 1 } {
                foreach illdef $ERRGEN_RULE_VAR(CheckIllegalDefines,ILLEGAL_DEFINES_LIST) {
                    if { [lsearch $match $illdef] != -1 } {
                        set violation 1
                        ## to get unit name
                        if { [ regexp {\-libname\s+(\S+)} $line -> unit] } {
                            set unitname $unit
                        }
                        ## Entry into violations
                        if { $ERRGEN_SVRTY(CheckIllegalDefines) == "ERROR" } {
                            set tmpmsg "Golden $unitname: Illegal define $illdef found while reading design"
                            if { [ lsearch $ERROR_LIST $tmpmsg] < 0 } {
                                #puts $filew "$prefix $tmpmsg"
                                lappend ERROR_LIST $tmpmsg
                            }
                        }
                    }
                }
                set found 0
            }
        }
    }

    close $log_fp
	if { $violation } {
        puts $filew "$prefix Illegal defines found during read_sverilog command"
    }

    return $violation
}


################################################################################
#proc	    : CheckLPViolations
#purpose    : To checks for violation in low power verification
################################################################################
proc CheckLPViolations {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER

    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckLPViolations)]
    set proc_name [lindex [info level 0] 0]
    set RULE_DESC "Run has LP violations that need to be fixed"
    set DESC($proc_name) "Run has LP violations"
    set FIX_ADVICE($proc_name) "Fix the LP violations in $block.lp_violations.rpt"
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0
    set lp_rpt "$fev_run_dir/reports/${block}.lp_violations.rpt"


    # dicts for tracking the error and warning items
    set error_list [dict create]
    set error_string [dict create]

    # unique strig vars
    set ele_list {}

    # global vars to control
    set tag ""
    set uniq_str ""
    set difftype ""

    #ignore key_tags
    set ignore_keys [ list "Tag" "Description" "Violation" "LineNumber" "FileName" "FmId" "Element" "Goal" "ParentInstance" "Containment" "ClonedBlock" ]

    # record is for "tree summary reading"
    set record 0
    set skip 0
    set eof_stop 0


    if { ![file exists $lp_rpt] } {
        puts $filew "FATAL violation: $lp_rpt File Not Found"
        set tmpmsg "$lp_rpt rpt is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $lp_rpt Found"
    }

    set report_file [open $lp_rpt r]

    while { ([gets $report_file line] >= 0) || ([eof $report_file] && ($eof_stop == 0)) } {
        incr line_num
        # allows for one last iteration
        if { [eof $report_file] } {
            set eof_stop 1
        }

        # starts capturing the "Management Summary" section
        if { [regexp {^\s+Total\s+(\d+)\s+(\d+)\s+(\d+)} $line -> error_cnt warn_cnt info_cnt] } {
            if { $error_cnt == 0 && $warn_cnt == 0 } {
                break
            }
        }

        # starts capturin the "Tree Summary"
        if { [regexp {^\s+Severity\s+Stage\s+Tag\s+Count} $line match] } {
            set record 1
        }

        # captures the "Tree Summary" lines
        if { [regexp {^\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)} $line -> severity stage tag_name count] } {
            if { $record == 1 && $count != 0 } {
                if { $severity == "error" } {
                    dict set error_list $tag_name $count
                }
                continue
            }
        }

        # stops capturing "Tree Summary"
        if { [regexp {^\s+Total\s+\d+} $line] } {
            set record 0
            continue
        }

        # starts processing Table info
        if { [regexp {^\s+Tag\s+:\s+(\S+)} $line -> tag] } {
            set record 0
            set tag $tag
            set uniq_str "$tag"
            continue
        }

        ## empty lines are considered as the end of a violation - SPACE line
        if { ($tag ne "") && ( [regexp {^\s*$}  $line]  || [eof $report_file] ) } {
            set skip 0
            set difftype ""

            # porcess the captured string and push into viol array
            if { $tag ne "" && [string length $uniq_str] > 0 } {
                #this assumes space is after an tag (diff_bullet)
                set ele_item [lindex $ele_list 0]
                if { $ele_item ne "" } {
                    # Replace [ with _ and ] with _ in uniq_str
                    set ele_item [string map {"[" "_" "]" "_"} $ele_item]
                    append uniq_str ";$ele_item"
                }
                # Check if the tag exists in the error_list
                if { [dict exists $error_list $tag] } {
                    set violation 1
                    # Use the error_string dictionary
                    if { [dict exists $error_string $tag] } {
                        set str_array [dict get $error_string $tag]
                        if { $uniq_str ni $str_array } {
                            lappend str_array $uniq_str
                        } else {
                            # throw a fatal, as this uniq string already exists here
                            lappend str_array $uniq_str
                            puts $filew "FATAL violation: $uniq_str already exists in the error_string "
                            set tmpmsg "current $uniq_str already exists in the error_string "
                            lappend FATAL_LIST $tmpmsg
                        }
                    } else {
                        # Create a new list with the uniq_str
                        set str_array [list $uniq_str]
                    }
                    dict set error_string $tag $str_array
                }
                # reset everything
                set uniq_str ""
                set difftype ""
                set tag ""
                set ele_list {}
            }
            continue
        }

        # determines what to capture next
        if { $difftype eq "ImplementationOnly" } {
            if { [regexp {^\s+ReferenceUPF} $line] } {
                set skip 1
            }
            # makes sure only the Implemantation block is captured
            if { [regexp {^\s+ImplementationUPF} $line] } {
                set skip 0
            }
        } elseif { $difftype eq "ReferenceOnly" } {
            if { [regexp {^\s+ImplementationUPF} $line] } {
                set skip 1
            }
            # makes sure only the ReferenceUPF block is captured
            if { [regexp {^\s+ReferenceUPF} $line] } {
                set skip 0
            }
        } elseif { $difftype eq "Mismatch" } {
            if { [regexp {^\s+UPFCommand} $line] } {
                # set skip to 1 - stop capture upfcommand elements
                set skip 1
            }
            if { [regexp {^\s+(ImplementationUPF|ReferenceUPF)} $line] } {
                # sets skip back to 0 - capture rest of the elements
                set skip 0
            }
        }

        #Capture the element list
        if { [regexp {^\s+(\S+)\s+:\s+(\S+)} $line -> key_tag value_tag] } {
            # generic key value catch and process into string
            if { ($key_tag ni $ignore_keys) && ($skip eq 0) } {
                append uniq_str ";$value_tag"
            }

            # if key is element, append to the ele_list
            if { $key_tag eq "Element" } {
                lappend ele_list $value_tag
            }

            # sets the difftype top var
            if { $key_tag eq "DiffType" } {
                set difftype $value_tag
        	}
            continue
    	}
    }

    close $report_file

    dict for {key value} $error_string {
        if { $ERRGEN_SVRTY(CheckLPViolations) == "ERROR" } {
            foreach item $value {
                lappend ERROR_LIST $item
            }
        }
    }
    
    if { $violation } {
        puts $filew "$prefix LP Violations found: Check reports/*.lp_violations.rpt for details"
    }

    return $violation
}


################################################################################
#proc	: CheckParameterizedBBoxes 											
#purpose: To check for parameterized blackboxes in design
#################################################################################
proc CheckParameterizedBBoxes {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER fev_type ERRGEN_RULE_VAR
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckParameterizedBBoxes)]
    set RULE_DESC "Black box with parameterization are not allowed"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Black box with parameterization are not analyzed and may cause fatal issue when implementing multi instance in netlist."
    set FIX_ADVICE($proc_name) "Remove black boxing from modules with parameterization"
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"
    
    set violation 0

    set report_file "$fev_run_dir/reports/${block}.bboxes_parametrization_info.rpt"
    if { (![file exists $report_file]) } {
        puts $filew "FATAL violation: $report_file File Not Found"
        set tmpmsg "$report_file file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $report_file Found"
    }

    set fp [open $report_file]
    array unset viol_arr
    while { [gets $fp line] >= 0 } {
        if { [regexp {^\s*#|^\s*$} $line] } { continue }
        lassign [split $line ","] container module instance param value
        # ignoring/waivier
        if {$ERRGEN_RULE_VAR(CheckParameterizedBBoxes,EXEMPT_BBOX_MODULES) ne "" && [lsearch -exact $ERRGEN_RULE_VAR(CheckParameterizedBBoxes,EXEMPT_BBOX_MODULES) $module] > -1 } { 
            puts $filew "INFO: Exempting $module in Parameterized BBox rules"
            continue
        }
        if { $ERRGEN_RULE_VAR(CheckParameterizedBBoxes,EXEMPT_BBOX_MODULES_REGEXP) ne "" && [regexp $ERRGEN_RULE_VAR(CheckParameterizedBBoxes,EXEMPT_BBOX_MODULES_REGEXP) $module] } {
            puts $filew "INFO: Exempting $module in Parameterized BBox rules"
            continue	
        }
        if { $fev_type == "r2r" } { 
            set viol_arr($module,$container) "$param,$value"
        } elseif { $container == "r" } { # in r2g runs, (r)eference in RTL.
            set viol_arr($module,$container) "$param,$value"
        }
    }
    close $fp
    
    foreach module [array names viol_arr] {
        set violation 1
        if { $ERRGEN_SVRTY(CheckParameterizedBBoxes) eq "ERROR" } {
            lassign [split $module ","] module_name container 
            set tmpmsg "Module on container $container has parameters and has been black boxed: $module_name"
            lappend ERROR_LIST $tmpmsg
        }
    }
   	if { $violation } {
		puts $filew "$prefix Black box with parameterization are found: Check reports/*.bboxes_parametrization_info.rpt for details"
    }
    return $violation
}


################################################################################
#proc	    : CheckSeqConstX										
#purpose    : To checks for Seq ConstX in desing
################################################################################
proc CheckSeqConstX {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckSeqConstX)]
    set RULE_DESC "Checks for Sequential Constant X flops in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Checks for Sequential Constant X flops in the design"
    set RULE_OWNER($proc_name) "Miklesh, Naicker"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

	if { $task eq "fev_fm_lite" } {
		set FIX_ADVICE($proc_name) "Please check why Sequential Constant X flops exist in the RTL"
		set seq_const_x_rpt "$fev_run_dir/reports/$block.RTL_seq_constx.rpt"
	} else {
		set FIX_ADVICE($proc_name) "Please check why Sequential Constant X flops exist in the netlist"
		set seq_const_x_rpt "$fev_run_dir/reports/$block.seq_constx.rpt"
	}
	
    if { (![file exists $seq_const_x_rpt]) } {
        puts $filew "FATAL violation: $seq_const_x_rpt File Not Found"
        set tmpmsg "$seq_const_x_rpt report not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $seq_const_x_rpt Found"
    }

    set seq_const_x_rpt_FH [open $seq_const_x_rpt]
    while { [gets $seq_const_x_rpt_FH line] >= 0 } {
        if { [regexp {^\s+(\w+)\s+((i:|r:)\S+)} $line -> reason message side] } {
            set violation 1
            if { $ERRGEN_SVRTY(CheckSeqConstX) == "ERROR" } {
                set tmpmsg "Seq Const X flop: $message found in the design, reason: $reason"
                lappend ERROR_LIST $tmpmsg
            }
        }
    }

    close $seq_const_x_rpt_FH
	if { $violation } {
		puts $filew "$prefix Sequential Constant X flops in the design, Please check reports/*.seq_constx.rpt | reports/*.RTL_seq_constx.rpt for details"
    }
    return $violation
}


################################################################################
#proc	    : CheckSigTable										
#purpose    : To checks if Sigtable is generated or not
################################################################################
proc CheckSigTable {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER 
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckSigTable)]
    set RULE_DESC "Check if Sigtable is generated" 
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Check if Sigtable is generated" 
    set FIX_ADVICE($proc_name) "Please re-run FEV with sigtable generation enabled" 
    set RULE_OWNER($proc_name) "Renduchintala, Harika"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"
    
    set report_file "$fev_run_dir/reports/$block.sigtable.xml"
    
    if { [file exists $report_file] } {
        puts $filew "Sigtable file found"
        return 0
    } else {
        puts $filew "$prefix Sigtable was not generated in this run"
        if { $ERRGEN_SVRTY(CheckSigTable) eq "ERROR" } {
            set tmpmsg "Sigtable was not generated in this run"
            lappend ERROR_LIST $tmpmsg
        }
        return 1
    }	
}


################################################################################
#proc	    : CheckVLOGSixtyFour										
#purpose    : To check if there are duplicate module definitions
################################################################################
proc CheckVLOGSixtyFour {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER fev_type
    set prefix [get_severity_prefix $ERRGEN_SVRTY(CheckVLOGSixtyFour)]
    set RULE_DESC "Duplicate module definitions found. Simulation could have used a different definition from synthesis"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Duplicate module definitions found. Simulation could have used a different definition from synthesis"
    set FIX_ADVICE($proc_name) "Duplicate module definitions found. Simulation could have used a different definition from synthesis, Please fix the FMR_VLOG-064 violations."
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"
    
	set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "Log file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }
    
	set violation 0

    set LOG [open $log_file r]
	set inrange_i false
    while {[gets $LOG line] != -1} {
		if {$inrange_i} {
			if { [regexp {Setting top design to 'i:} $line] } {
				set inrange_i false
			} else {	
				if { [regexp {Warning: Overwriting existing module\s*(.*)} $line match implmod] } {
					puts $filew "INFO: Duplicate module definition found for $implmod in the IMPL side"
					if { ! [regexp {ctech_lib_} $implmod] } {
						set violation 1
						if { $ERRGEN_SVRTY(CheckVLOGSixtyFour) == "ERROR" } {
							set tmpmsg "Implementation $implmod"
							lappend ERROR_LIST $tmpmsg
						}
					}
				}
			}
		} else {
			if { [regexp {INTEL_INFO   : Reading IMPL side \(\:\:read_gate\) } $line] } {
				set inrange_i true
			}
		}
	}
	close $LOG 

	if {$fev_type eq "g2g"} {
    	set LOG [open $log_file r]
		set inrange false
		while {[gets $LOG line] != -1} {
			if {$inrange} {
				if { [regexp {Setting top design to 'r:} $line] } {
					set inrange false
				} else {
					if { [regexp {Warning: Overwriting existing module\s*(.*)} $line match module] } {
						puts $filew "INFO: Duplicate module definition found for $module in the REF side"
						if { ! [regexp {ctech_lib_} $module] } {
							set violation 1
							if { $ERRGEN_SVRTY(CheckVLOGSixtyFour) == "ERROR" } {
								set tmpmsg "Reference $module"
								lappend ERROR_LIST $tmpmsg
							}
						}
					}
				}
			} else {
				if { [regexp {INTEL_INFO   : Reading REF side \(\:\:read_gate\) } $line] } {
					set inrange true
				}
			}
		}
        close $LOG
	}
	if { $violation } {
		puts $filew "$prefix Duplicate module definitions found. Simulation could have used a different definition from synthesis, Please fix the FMR_VLOG-064 violations"
    }
	return $violation
}


################################################################################
#proc	    : DofileStaleness										
#purpose    : To checks if do file is tampered/changed
################################################################################
proc DofileStaleness {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER fev_type IF_ROOT out_dir
    set prefix [get_severity_prefix $ERRGEN_SVRTY(DofileStaleness)]
    set RULE_DESC "Check if the dofile is not tampered with after the generation"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Check if the dofile is not tampered/modified after the generation"
    set FIX_ADVICE($proc_name) "Please review the difference between the user area dofile and IF area dofile"
    set RULE_OWNER($proc_name) "Madhurima Yadav"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0
    set gen_do "$fev_run_dir/gen_script.csh"
    if { ![file exists $gen_do] } {
        puts $filew "$gen_do not found, Something went wrong creating $gen_do"
        set tmpmsg "$gen_do file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File - $gen_do found"
        set gen_dofile [open $gen_do r]
        set dis [gets $gen_dofile]
        close $gen_dofile
        if { [catch { exec cp -f $dis $IF_ROOT/$task.tcl } msg] } {
            set tmpmsg "Failed to copy $gen_do: $msg"
            puts $filew "$tmpmsg"
            lappend FATAL_LIST $tmpmsg
            return 1
        }
        if { [catch { exec cp -f $fev_run_dir/gen_script.csh $IF_ROOT/$task.csh } msg] } {
            set tmpmsg "Failed to copy $fev_run_dir/gen_script.csh: $msg"
            puts $filew "$tmpmsg"
            lappend FATAL_LIST $tmpmsg
            return 1
        } else {
            exec sed -i 1d $IF_ROOT/$task.csh
            exec chmod 755 $IF_ROOT/$task.csh
            exec chmod 755 $IF_ROOT/$task.tcl

            set file1 "$IF_ROOT/$task.csh"
            set file2 "$fev_run_dir/${task}.csh"
            set file3 "$IF_ROOT/$task.tcl"
            set file4 "$fev_run_dir/${task}.tcl"

            if { ![file exists $file2] } {
                puts $filew "ERROR: Required file $file2 not found"
                set tmpmsg "ERROR: Required file $file2 not found"
                lappend FATAL_LIST $tmpmsg
                return 1
            }
                
            if { ![file exists $file4] } {
                puts $filew "ERROR: Required file $file4 not found"
                set tmpmsg "ERROR: Required file $file4 not found"
                lappend FATAL_LIST $tmpmsg
                return 1
            }


            set fh1 [open $file1 r]
            set fh2 [open $file2 r]
            set fh3 [open $file3 r]
            set fh4 [open $file4 r]

            set csh_flag 0
            set tcl_flag 0
            if { [string compare [ read $fh1] [ read $fh2] ] != 0 } {
                set csh_flag 1
                set violation 1
                puts $filew "CSH file generated using command in gen_script.csh $file1 and users area  $fev_run_dir/$task.csh are different"
            } else {
                puts $filew "CSH file generated using command in gen_script.csh $file1 and users area  $fev_run_dir/$task.csh are same"
            }
            if { [string compare [ read $fh3] [ read $fh4] ] != 0 } {
                set tcl_flag 1
                set violation 1
                puts $filew "DOFILE generated using command in gen_script.csh ie. $file3 and users area $fev_run_dir/$task.tcl are different"
            } else {
                puts $filew "DOFILE file generated using command in gen_script.csh i.e $file3 and users area $fev_run_dir/$task.tcl are same"
            }
        }
    }
    if { [ regexp {.*fev_formality/(\S+)} $file1 match f1_name] } {
        set csh_path "$f1_name"
    }
    if { [ regexp {.*fev_formality/(\S+)} $file3 match f3_name] } {
        set tcl_path "$f3_name"
    }
    if { [ regexp {.*fev_formality/(\S+)} $fev_run_dir match fev_name] } {
        set fev_path "$fev_name"
    }

    if { $ERRGEN_SVRTY(DofileStaleness) == "ERROR" } {
        if { $csh_flag == 1 } {
            set tmpmsg "Generated CSH file $csh_path and users csh file $fev_path/$task.csh is different"
            lappend ERROR_LIST $tmpmsg
        }
        if { $tcl_flag == 1 } {
            set tmpmsg "Generated Dofile $tcl_path and user's dofile $fev_path/$task.tcl is different"
            lappend ERROR_LIST $tmpmsg
        }
    }
	if { $violation } {
        puts $filew "$prefix Difference found between default dofile|csh template and user's dofile|csh "
    }
    return $violation
}


################################################################################
#proc	    : MetaflopErrgen										
#purpose    : To checks for errors in metaflop verification
################################################################################
proc MetaflopErrgen {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(MetaflopErrgen)]
    set RULE_DESC "Checks for Metaflop merges and duplications"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Checks for Metaflop merges and duplications"
    set FIX_ADVICE($proc_name) "Please resolve Metaflop verification failures listed in $block.metaflop_verif.rpt"
    set RULE_OWNER($proc_name) "Miklesh Naicker"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

    set metarpt "$fev_run_dir/reports/$block.metaflop_verif.rpt"
    if { (![file exists $metarpt]) } {
        puts $filew "FATAL violation: $metarpt File Not Found"
        set tmpmsg "$metarpt report file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $metarpt Found"
    }

    set metaFH [open $metarpt]
    while { [gets $metaFH line] >= 0 } {
        if { [ regexp {(INTEL_ERROR|ERROR)\s*:\s*(.*)} $line match - msg ] } {
            set violation 1
            if { $ERRGEN_SVRTY(MetaflopErrgen) == "ERROR" } {
                set tmpmsg "$line"
                lappend ERROR_LIST $tmpmsg
            }
        }
    }

    close $metaFH
	if { $violation } {
        puts $filew "$prefix Metaflop violations exist in the design"
    }
    return $violation

}


################################################################################
#proc	    : NonEquivalent										
#purpose    : To checks for Non Eqs in design
################################################################################
proc NonEquivalent {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(NonEquivalent)]
    set RULE_DESC "Verification Failed due to NonEquivalent Points in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Verification Failed, NonEquivalent points found"
    set FIX_ADVICE($proc_name) "Fix the Non Equivalent Points"
    set RULE_OWNER($proc_name) "Ashley, Catherine"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set result 0

    # NonEq Points are in the failing_points.rpt
    set fail_rpt "$fev_run_dir/reports/${block}.failing_points.rpt"
    if { (![file exists $fail_rpt]) } {
        puts $filew "FATAL violation: $fail_rpt File Not Found"
        set tmpmsg "$fail_rpt report is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $fail_rpt Found"
    }

    set verif [open $fail_rpt r]
    set fatal 0
    set parse 0
    set failingpoints 0
    set fCount 0

    while { [gets $verif line] >= 0 } {
        if { [ regexp {No failing compare points} $line] } {
            set fCount 0
        } elseif { [ regexp {\s*(\S+)\s+Failing compare points} $line match fNum ] } {
            set fCount fNum
            set result 1
        } elseif { [ regexp {Ref\s+(None|BBNet|BBPin|Cut|DFF|DFF0|DFF1|DFFX|DFF0X|DFF1X|LAT|LAT0|LAT1|LATX|LAT0X|LAT1X|LATCG|TLA|TLA0X|TLA1X|Loop|Port|Und|Unk|PDCut|PGPin)(\s*r:(.*))?} $line match golType dummy golName] } {
            incr failingpoints
            set parse 1
            set result 1
            if { $golType eq "None" } {
                set golName "UNMATCHED"
            }
        } elseif { $parse } {
            if { [ regexp {Impl\s+(None|BBNet|BBPin|Cut|DFF|DFF0|DFF1|DFFX|DFF0X|DFF1X|LAT|LAT0|LAT1|LATX|LAT0X|LAT1X|LATCG|TLA|TLA0X|TLA1X|Loop|Port|Und|Unk|PDCut|PGPin)(\s+i:(.*))?} $line match revType dummy revName] } {
                #in Conformal, we had a Module name.  There is no Module for Formality.  So just use the Block name in place of Module
                if { $revType eq "None" } {
                    set revName "UNMATCHED"
                }
                set result 1
                set tmpmsg "$block $golType $golName $revType $revName"
                lappend ERROR_LIST $tmpmsg
            }
            set parse 0
        } elseif { [ regexp {before (\S*)} $line] } {
            set fatal 1
            set result 1
            set tmpmsg "$block ERROR: Run fail to complete"
            lappend ERROR_LIST $tmpmsg
        }
    }
    close $verif

    if { $fatal } {
        puts $filew "$prefix Run fail to complete"
    }
    if { $failingpoints } {
        puts $filew "$prefix NonEquivalent points exist: see reports/*.failing_points.rpt for details"
    }

    return $result
}



################################################################################
#proc	: NonMatchingBBoxes 											
#purpose: To check non matched and balanced BBoxes bw R and G
#################################################################################
proc NonMatchingBBoxes {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER ERRGEN_RULE_VAR EXEMPT_CELLS
    set prefix [get_severity_prefix $ERRGEN_SVRTY(NonMatchingBBoxes)]
    set RULE_DESC "NonMatchingBBoxes found in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "NonMatchingBBoxes(Unmapped) found in the design"
    set FIX_ADVICE($proc_name) "All the blackboxes should match for both Golden and Revised. Check your design for the list of blackboxes."
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"
    
    set bbreport "$fev_run_dir/reports/${block}.black_boxes_unmatched.rpt"
    if { (![file exists $bbreport]) } {
        puts $filew "FATAL violation: $bbreport File Not Found"
        set tmpmsg "$bbreport report file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $bbreport Found"
    }
    
    set violation 0
    set side ""
    set list_ref [list]
    set list_impl [list]

    set BBF [open $bbreport]
    # this creates list of items from report file
    while { [gets $BBF line] >= 0 } {
        if { [regexp {^\s*$} $line] } { continue } ; #ignoring blank lines
        if { [regexp {^Container:\s+(\w+)$} $line -> side] } {# here side is either "ref" or "impl"
            set side $side
        }
        if { $side ne "" && [regexp {^\s+(\w+)$} $line -> module] } {
            #puts "module: $module"
            lappend list_${side} $module
        }
    }
    close $BBF

    if { [llength $list_ref] > 0 || [llength $list_impl] > 0 } {
        # for processing Reference side
        foreach a $list_ref {
            set exempt 0
            if { $ERRGEN_RULE_VAR(NonMatchingBBoxes,EXEMPT_CELLS_GOLDEN) ne "" } {
                foreach cell $ERRGEN_RULE_VAR(NonMatchingBBoxes,EXEMPT_CELLS_GOLDEN) {
                    if { [string match $cell $a] } {
                        set exempt 1
                        break
                    }
                }
            }
            if { $exempt == 1 } {
                continue
            } else {
                set violation 1
                if { $ERRGEN_SVRTY(NonMatchingBBoxes) eq "ERROR" } {
                    set tmpmsg "Reference: $a"
                    lappend ERROR_LIST $tmpmsg
                }
            }
        }

        # for processing Implementation side
        foreach b $list_impl {
            set exempt 0
            if { $ERRGEN_RULE_VAR(NonMatchingBBoxes,EXEMPT_CELLS_REVISED) ne "" } {
                foreach cell $ERRGEN_RULE_VAR(NonMatchingBBoxes,EXEMPT_CELLS_REVISED) {
                    if { [string match $cell $b] } {
                        set exempt 1
                        break
                    }
                }
            }
            if { $exempt == 1 } {
                continue
            } else {
                set violation 1
                if { $ERRGEN_SVRTY(NonMatchingBBoxes) eq "ERROR" } {
                    set tmpmsg "Implementation: $b"
                    lappend ERROR_LIST $tmpmsg
                }
            }
        }
    }
    if { $violation } {
        puts $filew "$prefix NonMatchingBBoxes found in the design: Check reports/*.black_boxes_unmatched.rpt for details"
    }
    
    return $violation
}


################################################################################
#proc	    : ReportUserIvarsOverride										
#purpose    : To checks if any ivar is overridden by user
################################################################################
proc ReportUserIvarsOverride  {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST block RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER fev_type IF_ROOT out_dir task ivar
    set prefix [get_severity_prefix $ERRGEN_SVRTY(ReportUserIvarsOverride)]
    set RULE_DESC "Report the ivars which got overriden" 
    set proc_name [lindex [info level 0] 0]	
    set DESC($proc_name) "Report the ivars which got overriden"
    set FIX_ADVICE($proc_name) "Please review the ivars overriden by flow/project/user"
    set RULE_OWNER($proc_name) "Rajesh, Kudipudi"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"

    set violation 0

    set ivar_hist "$fev_run_dir/reports/${block}.ivar_history.rpt"
    if { (![file exists $ivar_hist]) } {
        puts $filew "FATAL violation: $ivar_hist File Not Found"
        set tmpmsg "$ivar_hist rpt is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $ivar_hist Found"
    }

    set waivedIvarsDict {}
    if { [info exists ivar(fev,waived_ivars)] && ($ivar(fev,waived_ivars) ne "") } {
        foreach var $ivar(fev,waived_ivars) {
			dict set waivedIvarsDict $var 1
		}
    }

    set arr_bscr ""
    set arr_fscr ""
    set ward $env(ward)


    #-- To look for fscript_dir/bscript_Dir and pushing to diff arrays 
    set ivar_hist_file [open $ivar_hist r]
    while { [gets $ivar_hist_file line] >= 0 } {
        if { [ regexp {^set\s+ivar\(fscript_dir\)\s+(\S+)\s+;\s+#\s*(.+)} $line match fscript] } { set arr_fscr "$fscript" }
        if { [ regexp {^set\s+ivar\(bscript_dir\)\s+(\S+)\s+;\s+#\s*(.+)} $line match bscript] } { set arr_bscr "$bscript" }
    }
    close $ivar_hist_file
    
    #-- To get all files from $all_dirs
    set fevsrc_dir "${fev_run_dir}/scripts"
    set all_dirs [ list $arr_fscr/$task $arr_fscr $arr_bscr/$task $arr_bscr $fevsrc_dir ]
    set uniq_fp [lsort -unique -increasing $all_dirs]

    set ivar_hist_file [open $ivar_hist r]
    while { [gets $ivar_hist_file line] >= 0 } {
        if { [regexp {^set\s+ivar\(([^,]+),([^\)]+)\)\s+([^;]+)\s+;\s*#\s*(.+)} $line match ivar_key1 ivar_key2 ivar_value ivar_path] } {
            if { $ivar_key1 == $task || $ivar_key1 =="fev" } {
                set found 0
                foreach element $ivar_path {
                    if { $found == 1 || [string first "::" $element] >= 0 } {
                        continue
                    }
                    #puts "element: $element"
                    foreach probable_path $uniq_fp {
                        #puts "[string first $probable_path $element]"
                        if { [string first $probable_path $element] >= 0 } {
                            #puts "found"
                            set found 1
                            break
                        }
                    }
                    if { $found == 1 } {
                        break
                    }
                }
                 if { $found == 1 && ![dict exists $waivedIvarsDict $ivar_key2] } {
                    # these two lines are in place to remove the absolute paths in info
                    set each [ regsub  "$ward/" $element "" ]
                    set ivar_value [ regsub  "$ward/" $ivar_value "" ]
                    set ivar_value [ regsub -all {[\{|\}]} $ivar_value "" ]
                    set tmpmsg "ivar($ivar_key1,$ivar_key2): $ivar_value from $each"
#                    puts $filew "ivar($ivar_key1,$ivar_key2): $ivar_value from $each"
                    lappend ERROR_LIST $tmpmsg
                    set violation 1
                }
            }
        }
    }

    close $ivar_hist_file
	if { $violation } {
		puts $filew "$prefix Ivars are overridden by user, Please review the overridden ivars"
    }
		    
    return $violation
}


################################################################################
#proc	    : RTLUndrivenNets										
#purpose    : To checks if any RTL undriven nets in design
################################################################################
proc RTLUndrivenNets {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(RTLUndrivenNets)]
    set RULE_DESC "Undriven nets on RTL side"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Undriven nets on RTL side"
    set FIX_ADVICE($proc_name) "Review Undriven Nets in reports/$block.RTL_undrivens.rpt"
    set RULE_OWNER($proc_name) "Miklesh Naicker"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set report_undrivens 0

    set undrivenreport "$fev_run_dir/reports/${block}.RTL_undrivens.rpt"
    if { (![file exists $undrivenreport]) } {
        puts $filew "FATAL violation: $undrivenreport File Not Found"
        set tmpmsg "$undrivenreport rpt file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $undrivenreport Found"
    }

    set Undriven [open $undrivenreport r]
    while { [gets $Undriven line] >= 0 } {
        if { [regexp {^\s+Ref\s+Und\s+(.*)} $line match instance] } {
            set report_undrivens 1
            if { $ERRGEN_SVRTY(RTLUndrivenNets) == "ERROR" } {
                set tmpmsg "RTL undriven $instance"
                lappend ERROR_LIST $tmpmsg
            }
        }
    }
    close $Undriven

    if { $report_undrivens } {
        puts $filew "$prefix Undrivens found in the design: Check Reference Undriven in reports/*.RTL_undrivens.rpt for details"
    }

    return $report_undrivens
}

################################################################################
#proc	    : SupplyCheckNonEq										
#purpose    : To checks for Supply Check Non Eqs in design
################################################################################
proc SupplyCheckNonEq {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(SupplyCheckNonEq)]
    set RULE_DESC "Verification Failed due to Supply Check NonEquivalent Points in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Supply Check NonEquivalent points found"
    set FIX_ADVICE($proc_name) "Fix the Non Equivalent Points"
    set RULE_OWNER($proc_name) "Malliga,Suresh Babu "
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set result 0

    # NonEq Points are in the failing_points.rpt
    set fail_rpt "$fev_run_dir/reports/${block}.report_supply_connection_checks_failed.rpt"
    if { (![file exists $fail_rpt]) } {
        puts $filew "FATAL violation: $fail_rpt File Not Found"
        set tmpmsg "$fail_rpt report is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $fail_rpt Found"
    }

    set verif [open $fail_rpt r]
    set fatal 0
    set parse 0
    set failingpoints 0
    set fCount 0

    while { [gets $verif line] >= 0 } {
        if { [ regexp {Ref\s+(Reg|Macro)(\s*r:(.*))?\s*\((primary.power: )?(.*)\)} $line match golType dummy golName dummy2 golPower] } {
            incr failingpoints
            set parse 1
            set result 1
        } elseif { $parse } {
            if { [ regexp {Impl\s+(Reg|Macro)(\s+\(Failed\)\s*i:(.*))?\s*\((primary.power: )?(.*)\)} $line match revType dummy revName dummy2 revPower] } {
                set result 1
                set tmpmsg "$block $golType $golName $golPower $revType $revName $revPower"
                lappend ERROR_LIST $tmpmsg
            }
            set parse 0
        } elseif { [ regexp {before (\S*)} $line] } {
            set fatal 1
            set result 1
            set tmpmsg "$block ERROR: Run fail to complete"
            lappend ERROR_LIST $tmpmsg
        }
    }
    close $verif

    if { $fatal } {
        puts $filew "$prefix Run fail to complete"
    }
    if { $failingpoints } {
        puts $filew "$prefix Supply Check NonEquivalent points exist: see reports/*.report_supply_connection_checks_failed.rpt for details"
    }

    return $result
}

################################################################################
#proc	    : SupplyCheckUnmatched										
#purpose    : To checks for Supply Check Unmatched points in design
################################################################################
proc SupplyCheckUnmatched {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(SupplyCheckUnmatched)]
    set RULE_DESC "Verification Failed due to Supply Check Unmatched Points in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Supply Check Unmatched points found"
    set FIX_ADVICE($proc_name) "Fix the Unmatched Points"
    set RULE_OWNER($proc_name) "Malliga,Suresh Babu "
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

        # Unmatched Points are in the report_supply_connection_checks_unmatched.rpt
    set unmatch_rpt "$fev_run_dir/reports/${block}.report_supply_connection_checks_unmatched.rpt"
    
    if { (![file exists $unmatch_rpt]) } {
        puts $filew "FATAL violation: $unmatch_rpt File Not Found"
        set tmpmsg "$unmatch_rpt report is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $unmatch_rpt Found"
    }

    set verif [open $unmatch_rpt r]
    set fatal 0
    set unmatchedpoints 0
    set uCount 0
    set result 0

    while { [gets $verif line] >= 0 } {
        if { [ regexp {Ref\s+(Reg|Macro)(\s+\(Unmatched\)\s*(r:.*))?\s*} $line match golType dummy golName] } {
            incr unmatchedpoints
            set result 1
            set tmpmsg "$block $golType $golName"
            lappend ERROR_LIST $tmpmsg
        } elseif { [ regexp {Impl\s+(Reg|Macro)(\s+\(Unmatched\)\s*(i:.*))?\s*} $line match revType dummy revName] } {
            incr unmatchedpoints
	        set result 1
            set tmpmsg "$block $revType $revName"
            lappend ERROR_LIST $tmpmsg
        } elseif { [ regexp {before (\S*)} $line] } {
            set fatal 1
            set result 1
            set tmpmsg "$block ERROR: Run fail to complete"
            lappend ERROR_LIST $tmpmsg
        }
    }
    close $verif

    if { $fatal } {
        puts $filew "$prefix Run fail to complete"
    }
    if { $unmatchedpoints } {
        puts $filew "$prefix Supply Check Unmatched points exist: see reports/*.report_supply_connection_checks_unmatched.rpt for details"
    }

    return $result
}


################################################################################
#proc	    : UnmappedPins										
#purpose    : To checks for unmapped pins in design
################################################################################
proc UnmappedPins {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(UnmappedPins)]
    set RULE_DESC "Unmapped Pins found in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Unmapped Pins found in the design"
    set FIX_ADVICE($proc_name) "Please review the Unmapped Pins in $block.unverified_feedthrough.rpt"
    set RULE_OWNER($proc_name) "Miklesh Naicker"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

    set unmaprpt "$fev_run_dir/reports/$block.unverified_feedthrough.rpt"
    if { (![file exists $unmaprpt]) } {
        puts $filew "FATAL violation: $unmaprpt File Not Found"
        set tmpmsg "$unmaprpt report file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $unmaprpt Found"
    }

    set UNF [open $unmaprpt]
    while { [gets $UNF line] >= 0 } {

        if { [regexp {^\s+(.*)\sPort\s+(.*)} $line match side instance] } {
            #puts $line
            set violation 1
            if { $ERRGEN_SVRTY(UnmappedPins) == "ERROR" } {
                set tmpmsg "Port $instance not verified in $side"
                lappend ERROR_LIST $tmpmsg
            }
        }
    }
    close $UNF
	if { $violation } {
        puts $filew "$prefix Unmapped Pins found in the design: Check reports/*.unverified_feedthrough.rpt for details"
    }
    return $violation
}


################################################################################
#proc	    : Unverified										
#purpose    : To checks for Unverified points in verification
################################################################################
proc Unverified {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(Unverified)]
    set RULE_DESC "Verification Inconclusive due to Unverified Points in the design"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Verification Inconclusive, Unverified points found"
    set FIX_ADVICE($proc_name) "Fix the Unverified Points"
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

    # Unverified Points are in the unverified_points.rpt
    set unverif_rpt "$fev_run_dir/reports/${block}.unverified_points.rpt"
    if { (![file exists $unverif_rpt]) } {
        puts $filew "FATAL violation: $unverif_rpt File Not Found"
        set tmpmsg "$unverif_rpt report is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $unverif_rpt Found"
    }

    set rpt [open $unverif_rpt r]

    set fatal 0
    set parse 0
    set unverified 0
    set uCount 0

    while { [gets $rpt line] >= 0 } {
        if { [ regexp {No unverified compare points} $line] } {
            set uCount 0
        } elseif { [ regexp {\s*(\S+)\s+nverified compare points} $line match uNum ] } {
            set uCount uNum
            set violation 1
        } elseif { [ regexp {Ref\s+(None|BBNet|BBPin|Cut|DFF|DFF0|DFF1|DFFX|DFF0X|DFF1X|LAT|LAT0|LAT1|LATX|LAT0X|LAT1X|LATCG|TLA|TLA0X|TLA1X|Loop|Port|Und|Unk|PDCut|PGPin)(\s*r:(.*))?} $line match golType dummy golName] } {
            incr unverified
            set parse 1
            set violation 1
            if { $golType eq "None" } {
                set golName "UNMATCHED"
            }
        } elseif { $parse } {
            if { [ regexp {Impl\s+(None|BBNet|BBPin|Cut|DFF|DFF0|DFF1|DFFX|DFF0X|DFF1X|LAT|LAT0|LAT1|LATX|LAT0X|LAT1X|LATCG|TLA|TLA0X|TLA1X|Loop|Port|Und|Unk|PDCut|PGPin)(\s+i:(.*))?} $line match revType dummy revName] } {
                #in Conformal, we had a Module name.  There is no Module for Formality.  So just use the Block name in place of Module
                if { $revType eq "None" } {
                    set revName "UNMATCHED"
                }
                set violation 1
                set tmpmsg "$block $golType $golName $revType $revName"
                lappend ERROR_LIST $tmpmsg
            }
            set parse 0
        } elseif { [ regexp {before (\S*)} $line] } {
            set fatal 1
            set violation 1
            set tmpmsg "$block ERROR: Run fail to complete"
            lappend ERROR_LIST $tmpmsg
        }
    }
    close $rpt

    if { $fatal } {
        puts $filew "$prefix Run fail to complete"
    }
    if { $violation } {
        puts $filew "$prefix Unverified points exist: see reports/*.unverified_points.rpt for details"
    }

    return $violation
}


################################################################################
#proc	    : UserInterfaceMapping										
#purpose    : To checks if used manually added any interface mapping
################################################################################
proc UserInterfaceMapping {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(UserInterfaceMapping)]
    set RULE_DESC "Primary interface mapping done by user. Primary interface should be automatically mapped by Formality. Any manual mapping would need to be reviewed to avoid wrong mapping"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Primary interface should be automatically mapped by Formality. Any manual mapping would need to be reviewed to avoid wrong mapping"
    set FIX_ADVICE($proc_name) "Please review the mapping added by user under .user_matched_points.rpt"
    set RULE_OWNER($proc_name) "Kudipudi, Rajesh"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set usermap 0

    set usermappingreport  "$fev_run_dir/reports/$block.user_matched_points.rpt"
    set tmpmsg ""

     if { ![file exists $usermappingreport] } {
        puts $filew "FATAL violation: $usermappingreport not found"
        set tmpmsg "$usermappingreport report is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input $usermappingreport found"
    }

    set eof_stop 0
    set mName ""
    set mType ""
    set viol_list {}
   
    set LOGFH [open $usermappingreport]
    while { ([gets $LOGFH line] >= 0)  || ([eof $LOGFH] && ($eof_stop == 0)) } { 
        # allows for one last iteration
        if { [eof $LOGFH] } {
            set eof_stop 1
        }
        # ignore stuff
        if { [regexp {^\s*//.*$} $line] } { continue } ; #ignoring comment lines
        if { [regexp {^\s*#.*$} $line] } { continue } ; #ignoring comment lines
        # capture info for processing
        if { [regexp {^\s*\((\w+)\)\s+(\(\S+\))?\s+((r|i)\:\S+)} $line -> type direc name side ] } {
            if { $type in "Port BBPin" } {
                # when first element is discovered
                if { ($mName eq "") && ($mType eq "") } {
                    set usermap 1
                    set mName $name
                    set mType $type
                    # when rest of the elements are discovered
                } else {
                    set viol_str "$mType $mName $type $name"
                    lappend viol_list $viol_str
                }
            }
        }
        # process the empty line, or the end of file - refresh info
        if { ( [regexp {^\s*$} $line] || [eof $LOGFH] ) } {
            set mName ""
            set mType ""
        }
    }
	close $LOGFH

    # Can add logic here to exclude lines from err_str (optional)
    # if you want to exclude a string, add it to the list
    #set exclude_list {  "a" "b" "c" }
    #foreach err_str $exclude_list {
    #    set viol_list [ lsearch -all -inline -not -glob $viol_list $err_str ]
    #}


    # we have viols list lets push into ERROR_LIST
    if { ($ERRGEN_SVRTY(UserInterfaceMapping) eq "ERROR") && ($viol_list ne "") } {
        foreach viol $viol_list {
            set tmpmsg "$viol"
            lappend ERROR_LIST $tmpmsg
        }
    }

	if { $usermap } {
		puts $filew "$prefix Primary interface mapping done by user, Please review the manual mapping: Check reports/*.user_matched_points.rpt"
    }
    return $usermap

}


################################################################################
#proc	    : UserProcOverride										
#purpose    : To checks if any default proc is overridden by the user
################################################################################
proc UserProcOverride {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER ERRGEN_RULE_VAR ivar
    set prefix [get_severity_prefix $ERRGEN_SVRTY(UserProcOverride)]
    set RULE_DESC "User hook files or user_fm_procs.tcl is/are found"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "User hook files are found"
    set FIX_ADVICE($proc_name) "Please review user_fm_procs.tcl or inceptions files reported"
    set RULE_OWNER($proc_name) "Sharanya Khamithkar"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set violation 0

    set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "$log_file file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }

    set ward ""
    set flag_lines ""
    set lf_lines_search ""
    set inception_files ""
    set arr_bscr ""
    set arr_fscr ""
    set fevsrc_dir "${fev_run_dir}/scripts"
    set userproc ""

    set audit_fev_files "$ivar($task,hook_files) $ivar($task,audit_files)"
    set log [open $log_file r]
    while { [gets $log line] >= 0 } {
        if { [ regexp {\s*ivar\(fscript_dir\)\s+=\s+'(\S+)'.*} $line match fscr ] } { set arr_fscr "$fscr" }
        if { [ regexp {\s*ivar\(bscript_dir\)\s+=\s+'(\S+)'.*} $line match bscr ] } { set arr_bscr "$bscr" }
        #-- To get ward, to truncate from ivar value
        if { [ regexp {^INTEL_INFO\s*:\s*Initializing\s+::ward\s+=\s+'(\S+)'.*} $line match w ] } { set ward "$w" }
        if { [ regexp {^INTEL_INFO\s*:\s*SCRIPT_START\s*:.*} $line match ] } { lappend lf_lines_search $line }
    }

    close $log
    set pattern2 "INTEL_INFO\\s*:\\s*SCRIPT_START\\s*:\\s*(($fev_run_dir|$arr_fscr|$arr_fscr\/$task|$arr_bscr|$arr_bscr\/$task|$fevsrc_dir)\/user_fm_procs.tcl)"
    foreach line $lf_lines_search {
        foreach hook $audit_fev_files {
            set pattern1 "INTEL_INFO\\s*:\\s*SCRIPT_START\\s*:\\s*(($fev_run_dir|$arr_fscr|$arr_fscr\/$task|$arr_bscr|$arr_bscr\/$task|$fevsrc_dir)\/$hook)"
            if { [ regexp $pattern1 $line match path dir ] }  {
                lappend inception_files $path
            }
            if { [ regexp $pattern2 $line match path dir ] }  {
                set userproc $path
            }
        }
    }
    set all_files "$inception_files $userproc"
    array set viol_arr {}
    foreach file $all_files {
        if { [file exists $file] } {
            puts $filew "INFO: User override/hook file found - $file"
            #-- as all inception points or user_fm_procs.tcl are not mandatory files
            set fh [open $file r]
            while { [gets $fh line] >= 0 } {
                set proc_name ""
                regsub -all {\t} $line { } line
                regsub {^\s*} $line {} line
                regsub {\s*$} $line {} line
                if { [ regexp {^\s*$|^\s*\#} $line ] } {continue}
                if { [ regexp {^\s*puts} $line ] } {continue}

                if { [ regexp {^\s*proc\s+(\S+)\s+\{.*\}} $line tmp proc_name] } {

                    if { [info exists viol_arr($file,$proc_name,$line)] } {
                        incr viol_arr($file,$proc_name,$line)
                    } else {
                        set viol_arr($file,$proc_name,$line) 1
                    }

                    set brace_count 1
                    while { $brace_count >= 1 } {
                        if { [gets $fh line] < 0 } {
                            #we are at the end of the file
                            break
                        }
                        regsub -all {\t} $line { } line
                        regsub {^\s*} $line {} line
                        regsub {\s*$} $line {} line
                        if { [ regexp {^\s*$|^\s*\#} $line] } {continue}
                        set open_brace  [ llength [ regexp -all -inline {[^\\]\{} $line] ]
                        set close_brace [ llength [ regexp -all -inline {[^\\]\}|^\s*\}} $line] ]
                        set brace_count [ expr $brace_count - ($close_brace - $open_brace) ]


                        if { [info exists viol_arr($file,$proc_name,$line)] } {
                            incr viol_arr($file,$proc_name,$line)
                        } else {
                            set viol_arr($file,$proc_name,$line) 1
                        }
                    }
                } else {
                    if { [info exists viol_arr($file,$proc_name,$line)] } {
                        incr viol_arr($file,$proc_name,$line)
                    } else {
                        set viol_arr($file,$proc_name,$line) 1
                    }
                }
            }
            close $fh
        }
    }
    foreach key [ lsort [array names viol_arr] ] {
        lassign [split $key ","] file proc_name line

        if { [ regexp {^\s*$|^\s*\#} $line] } { continue }
        if {$ERRGEN_RULE_VAR(UserProcOverride,EXEMPT_REGEXP) != "" && [ regexp $ERRGEN_RULE_VAR(UserProcOverride,EXEMPT_REGEXP) $line] } { continue }

        if { [ regexp "($ward\/(.*))" $file match ignore f_name] } {
            set tmpmsg "Line is present in $f_name"
            if { $proc_name != "" } {
                append tmpmsg " under $proc_name"
            }
            append tmpmsg " with $viol_arr($key) occurrence(s) - $line"
            lappend ERROR_LIST $tmpmsg
            set violation 1
        }
    }

    #puts "$ERRGEN_RULE_VAR(UserProcOverride,EXEMPT_REGEXP)"
	if { $violation } {
		puts $filew "$prefix User hook files are found , Please review ."
    }

    return $violation
}


################################################################################
#proc	    : VerificationFailed										
#purpose    : To checks to flag if the verification has failed or not
################################################################################
proc VerificationFailed {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"

    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER
    set prefix [get_severity_prefix $ERRGEN_SVRTY(VerificationFailed)]
    set RULE_DESC "Verification Failed due to Non-Equivalent|Abort|In-conclusive points found"
    set proc_name [lindex [info level 0] 0]
    set DESC($proc_name) "Verification Failed, Non-Equivalent, Abort points or In-conclusive pins found"
    set FIX_ADVICE($proc_name) "Fix the Non-Equivalent|Abort|In-conclusive points"
    set RULE_OWNER($proc_name) "Khamithkar, Sharanya"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
    puts $filew "[date]"

    set result 0

    set log_file "$fev_run_dir/logs/${task}_fm.log"
    if { (![file exists $log_file]) } {
        puts $filew "FATAL violation: $log_file File Not Found"
        set tmpmsg "Log file is not found"
        lappend FATAL_LIST $tmpmsg
        return 1
    } else {
        puts $filew "INFO: Required input File $log_file Found"
    }
    
    set verif [open $log_file r]
    while { [gets $verif line] >= 0 } {
        if { [ regexp {^\s*Verification SUCCEEDED.*} $line ] } {
            set result 1
        }
    }
    close $verif


    if { $result } {
        puts $filew "INFO: Verification Succeeded"
        return 0
    } else {
        puts $filew "$prefix Verification Failed"
        if { $ERRGEN_SVRTY(VerificationFailed) == "ERROR" } {
            set tmpmsg "Verification Failed"
            lappend ERROR_LIST $tmpmsg
        }
        return 1
    }

}

################################################################################
#proc	    : VtoKErrgen										
#purpose    : To checks to flag if there are mismatches in v2k config
################################################################################

proc VtoKErrgen {} {
    puts "Started: [lindex [info level 0] 0] at [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    
    global ERRGEN_SVRTY ERROR_LIST RULE_DESC block fev_run_dir env filew FATAL_LIST task DESC FIX_ADVICE RULE_OWNER METHODOLOGY_OWNER IF_tool IF_global ivar ERRGEN_RULE_VAR
    set prefix [get_severity_prefix $ERRGEN_SVRTY(VtoKErrgen)]
    set proc_name [lindex [info level 0] 0]

    set RULE_DESC "Checks if the instances used in FEV run are coming from the same library as the cfg file provided in the collaterals"
    set DESC($proc_name) "Flags instances coming from different libraries between FEV run and the collateral provided in cfg file"
    set FIX_ADVICE($proc_name) "Please review the v2k_check.rpt file to see the mismatched instances"
    set RULE_OWNER($proc_name) "Suresh Babu, Malliga"
    set METHODOLOGY_OWNER($proc_name) "InspectFEV TASKFORCE"
	puts $filew "[date]"
    
    set cmd "$IF_tool/v2k_check.py"
	set json_path "$fev_run_dir/$block.v2k_binding.r.json" 
	set v2k_report_path "$fev_run_dir/reports/v2k_report.rpt"

    set cfg_file ""

    if {[info exists ivar($task,cfg_file)] && ($ivar($task,cfg_file) ne "")} {
        set cfg_file $ivar($task,cfg_file);
    }
   
    if {![file exists $cfg_file]} {

        set error_msg "$cfg_file doesn't exist."
        if { $ERRGEN_SVRTY(VtoKErrgen) eq "ERROR" } {
                lappend ERROR_LIST $error_msg
        }
        set violation 1
    } elseif {![file exists $json_path]} {

        set error_msg "$json_path doesn't exist."
        if { $ERRGEN_SVRTY(VtoKErrgen) eq "ERROR" } {
                lappend ERROR_LIST $error_msg
        }
        set violation 1

    } else {
        set violation 0
        set modified_json_path "$fev_run_dir/reports/$block.v2k_binding.modif.r.json"
		if { [catch { exec cp -f $json_path $modified_json_path } msg] } {
			puts $filew "FATAL violation: Failed to copy file $json_path to $modified_json_path"
			set tmpmsg "$modified_json_path not created"
            lappend FATAL_LIST $tmpmsg
            return 1

		}
		exec sed -i {s/\\/\\\\/g} $modified_json_path
        puts $filew "$cmd $modified_json_path $cfg_file $v2k_report_path"
        if { [catch {exec /usr/intel/bin/python3.13.2 $cmd $modified_json_path $cfg_file $v2k_report_path} ErrMsg] } {
            puts $filew "$ErrMsg ERROR: Failed v2k_check.py script. Please contact your DA!"
        }
    
        if { ![file exists $v2k_report_path] } {
            puts $filew "FATAL violation: File - $v2k_report_path not found"
            set tmpmsg "$v2k_report_path report is not found"
            lappend FATAL_LIST $tmpmsg
            return 1
        } else {
            puts $filew "INFO: Required input File - $v2k_report_path found"
        }
    
        set CheckV2k [open $v2k_report_path r]
        while { [gets $CheckV2k line] != -1 } {
            if { [regexp {\-ERROR\-} $line] } {
                set violation 1
                if { $ERRGEN_SVRTY(VtoKErrgen) eq "ERROR" } {
                    lappend ERROR_LIST $line
                }
            }
        }
        close $CheckV2k
    
    }
    if { $violation } {
        puts $filew "$prefix V2k violations exist in the design. Please see ./reports/v2k_check.rpt in your run area for details"
    }
    return $violation
}

