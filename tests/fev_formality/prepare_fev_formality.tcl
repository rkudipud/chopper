#!/usr/intel/bin/tclsh8.6
####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


package require Tclx

puts "###################################################################"
puts "##############     PREPARING FEV RUNS AREA     ####################"
puts "###################################################################"


#initializing:
global env ivar design task

set genesis_opts ""
set template_path ""
set gold_template ""
set gold_path ""
set STPVER [exec $::env(CTH_SETUP_BIN)/cth_query ToolVersion stp]
set STPDIR "$env(CAD_ROOT)/stp/$STPVER"
set stp_run_cmd "$STPDIR/stp -r "
set stp_pack_cmd "$STPDIR/stp -p "
#puts "-----------------------------------------------------------------"
#puts "Getting the command line arguments "
#puts "-----------------------------------------------------------------\n"
set args $argv
set ii 0
array set options {-B "" -T "" -S "" -R "" -X "" -D "" -G "" -stp "" -O "" -help "" -no_generate_csh "" }
foreach { opt val } $args {
    if { ![info exists options($opt)] } {
        return -code error "unknown option \"$opt\""
    }
    set options($opt) $val
}

set use_orig_do 0
set dont_generate_csh 0
set use_stp_mode 0

while { $ii < [llength $args] } {
    set opt_name [lindex $args $ii]
    switch -glob -- $opt_name {
        "-B" {
            incr ii
            set block [lindex $args $ii]
            set env(block) $block
            #puts "$block"
        }
        "-T" {
            incr ii
            set task [lindex $args $ii]
            #puts "$task"
        }
        "-S" {
            incr ii
            set eco_step [lindex $args $ii]
            #puts "$eco_step"
        }
        "-R" {
            incr ii
            set run_dir [lindex $args $ii]
            #puts "$run_dir"
        }
        "-X" {
            incr ii
            set tech [lindex $args $ii]
            set env(tech) $tech
            #puts "$tech"
        }
        "-D" {
            incr ii
            set design [lindex $args $ii]
            set env(design) $design
            #puts "$tech"
        }
        "-G" {
            incr ii
            set tag [lindex $args $ii]
            set env(tag) $tag
            #puts "$tech"
        }
        "-O" {
            #	incr ii
            set use_orig_do "1"
        }
        "-stp" {
            #	incr ii
            set use_stp_mode "1"
        }
        "-no_generate_csh" {
            #	incr ii
            set dont_generate_csh "1"
        }

        default {
            if { $opt_name eq "-help" } {
                puts "Mandatory arguments :"
                puts "\t-B			Specify build name(M) "
                puts "\t-T			Specify task name(M)"
                puts "\t-S			Specify step name for ECO(M)"
                puts "Optional arguments :"
                puts "\t-R			Specify the fev run dir"
                puts "\t-X			Specify the tech node"
                puts "\t-G			Specify the release tag"
                puts "\t-D			Specify the design name if its different from build name"
                puts "\t-O			Overwrite the existing dofile in the run dir"
                puts "\t-stp			Specify if you want to run in stp mode"
                exit
            }
            puts "INTEL_ERROR  : Unsupported option $opt_name"
            exit -1
        }
    }
    incr ii
}


set flow "fev_formality"
set env(flow) $flow

if { [info exists env(ward)] && $env(ward) != "" } {
    set ward $env(ward)
} else {
    puts "INTEL_ERROR  : Environment variable ward not specified, cannot proceed"
    exit -1
}

if { ![info exists block] || $block == "" } {
    puts "INTEL_ERROR  : Mandatory input -B not specified"
    exit -1
}

if { ![info exists task] || $task == "" } {
    puts "INTEL_ERROR  : Mandatory input -T not specified"
    exit -1
}

if { ![info exists run_dir] || $run_dir == "" } {
    set run_dir $task
}

if { ![info exists tag] || $tag == "" } {
    set tag "latest"
    set env(tag) $tag
}


if { ![info exists tech] || $tech == "" } {
    if { [info exists env(tech)] && $env(tech) != "" } {
        set tech $env(tech)
        #puts "tech is $tech"
    } else {
        puts "INTEL_ERROR  : -X is not specified and ENV variable tech is also set"
        exit -1
    }
}

if { ![info exists design] || $design == "" } {
    set design $block
    set env(design) $design
}

puts "INTEL_INFO   : Setting Up the run area"
set fev_run_dir "$env(ward)/runs/$block/$tech/$flow/$run_dir"
set logs_dir $fev_run_dir/logs
set reports_dir $fev_run_dir/reports
set scripts_dir $fev_run_dir/scripts
set out_dir $fev_run_dir/outputs

if { [file exists $fev_run_dir] } {
    puts "INTEL_INFO   : $fev_run_dir directory already exists"
} else {
    file mkdir $fev_run_dir
}

if { [file exists $logs_dir] } {
    puts "INTEL_INFO   : logs directory already exists"
} else {
    file mkdir $logs_dir
}

if { [file exists $scripts_dir] } {
    puts "INTEL_INFO   : scripts directory already exists"
} else {
    file mkdir $scripts_dir
}


if { [file exists $reports_dir] } {
    puts "INTEL_INFO   : reports directory already exists, taking back up"
    if { [file exists ${reports_dir}.bck] } {
        if { [catch {file delete -force ${reports_dir}.bck} errMsg] } {
            puts "INTEL_ERROR  : Error while deleting ${reports_dir}.bck : $errMsg"
            exit -1
        }
    }
    if { [catch {file rename -force $reports_dir ${reports_dir}.bck} errMsg] } {
        puts "INTEL_ERROR  : Error while moving $reports_dir : $errMsg"
        exit -1
    }
}

file mkdir $reports_dir

if { [file exists $out_dir] } {
    puts "INTEL_INFO   : outputs directory already exists"
} else {
    file mkdir $out_dir
}

puts "INTEL_INFO   : Deleteing previously generated result files"
if { [file exists $fev_run_dir/logs/$task.pass] } {
    file delete $fev_run_dir/logs/$task.pass
}
if { [file exists $fev_run_dir/logs/$task.fail] } {
    file delete $fev_run_dir/logs/$task.fail
}
if { [file exists $fev_run_dir/fev_results.log] } {
    file delete $fev_run_dir/fev_results.log
}

puts "INTEL_INFO   : Reading the $env(ward)/global/common/setup.tcl"
source $env(ward)/global/common/setup.tcl

set search $ivar(search_path)
iproc_msg -info "Search paths are $search"

if { [info exists eco_step] } {
    set task $eco_step
}

if { $task == "fev_retime" || $task == "fev_fm_rtl2logicopto" || $task == "fev_fm_rtl2apr" || $task == "fev_fm_full_febe" || $task == "fev_fm_quick_febe" || $task == "fev_fm_fcl" || $task == "fev_fm_rtl2syn" || $task == "eco_post_rtl_to_eco_net" || $task == "eco_pre_rtl_to_pre_net" } {
    set template_name "fev_fm_rtl2gate"
} elseif { $task == "fev_fm_rtl2rtl" || $task == "fev_fm_lite" || $task == "fev_fm_sim2syn" || $task == "fev_fm_hier2flat_upf" || $task == "fev_fm_ctechverif" || $task == "eco_pre_rtl_to_post_rtl"} {
    set template_name "fev_fm_rtl2rtl"
} elseif { $task == "fev_fm_syn2apr" } {
    set template_name "fev_fm_gate2gate"
} elseif { [info exists ivar($task,template_map)] && $ivar($task,template_map) != "" } {
    set template_name $ivar($task,template_map)
    iproc_msg -info "Template name is $template_name"
} elseif { $task == "eco_pre_synth" } {
    set template_name "fev_fm_eco_pre_synth"
} elseif { $task == "eco_post_synth" } {
    set template_name "fev_fm_eco_post_synth"
} elseif { $task == "eco_confirm_patch" } {
    set template_name "fev_fm_eco_confirm_patch"
} else {
    iproc_msg -error "Task name provided is not present in the default list, please provide the template mapping"
    set template_name ""
    exit -1
}

##Generating gen_dofile.csh
set ifile "$fev_run_dir/gen_script.csh"
if { [catch {set GFH [open $ifile "w+"]} errMsg] } {
    iproc_msg -error "Error while creating $ifile : $errMsg"
    exit -1
}

iproc_msg -info "Searching for template"
foreach sp $search {
    if { [file exists $sp/$template_name.tcl] } {
        iproc_msg -info "Template is $sp/$template_name.tcl"
        set gold_template "$sp/$template_name.tcl"
        set gold_path "$sp"
        break
    }
}

puts $GFH "$gold_template"

if { [file exists $fev_run_dir/$task.tcl] && ($use_orig_do == 0) } {
    iproc_msg -info "$task.tcl already exists in the run area, using the same"
} elseif { [file exists $ivar(bscript_dir)/$task/$task.tcl] } {
    iproc_msg -info "Copying the template script from block ivar(bscript_dir) archival area"
    file copy -force $ivar(bscript_dir)/$task/${task}.tcl $fev_run_dir
} else {
    if { $template_name != "" } {
        iproc_msg -info "Copying the template dofile from $gold_template area"
        file copy -force $gold_path/$template_name.tcl $fev_run_dir/$task.tcl
    }
}

#Creating the $task.csh file
if { [info exists dont_generate_csh] && $dont_generate_csh } {
    iproc_msg -warning "$fev_run_dir/${task}.csh already exists, not generating it again"
} else	{
    set sfile "$fev_run_dir/${task}.csh"
    if { [catch {set SFH [open $sfile "w+"]} errMsg] } {
        iproc_msg -error "Error while creating $sfile : $errMsg"
        exit -1
    }
}

#Creating the interactive.csh file
set ifile "$fev_run_dir/${task}_interactive.csh"
if { [catch {set IFH [open $ifile "w+"]} errMsg] } {
    iproc_msg -error "Error while creating $ifile : $errMsg"
    exit -1
}

#Creating the debug.csh file
set dfile "$fev_run_dir/${task}_debug.csh"
if { [catch {set DFH [open $dfile "w+"]} errMsg] } {
    iproc_msg -error "Error while creating $dfile : $errMsg"
    exit -1
}


## SFH file write begins here

if { [info exists dont_generate_csh] && !$dont_generate_csh } {
    puts $SFH "#!/bin/csh -f"
    puts $SFH "#-- Copyright (c) Intel Corporation"
    puts $SFH "#-- Intel Proprietary and Confidential Information"
    puts $SFH "setenv task $task"

    puts $SFH "set timestamp = `date +%m_%d_%H_%M`"
    puts $SFH "set LOGFILE = \"\$PWD/logs/${task}_fm.log.\${timestamp}\""
    puts $SFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/${task}_fm.log"
    if { [info exists eco_step] } {
        puts $SFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm_eco.log"
    } else {
        puts $SFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm.log"
    }
    puts $SFH "set LOGFILE = \"\$LOGFILE\""
    puts $SFH "set UPF_ALL_STATE_VERIFY = \"0\" "
    if { [info exists ivar($task,vclp_path)] && $ivar($task,vclp_path) != "" } {
        puts $SFH "setenv VC_STATIC_HOME $ivar($task,vclp_path)"
    }
	if { [info exists ivar($task,FM_ML_HOME)] && $ivar($task,FM_ML_HOME) != "" } {
        puts $SFH "setenv FM_ML_HOME $ivar($task,FM_ML_HOME)"
    }

    if { [info exists eco_step] } {
        # deals with ECO based runs
        if { [info exists ivar(fm_eco,fm_path)] && $ivar(fm_eco,fm_path) != "" } {
            # is FM version is overridden
            if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
                # stp mode
                puts $SFH "#-- remove old testcase pack or files"
                puts $SFH "rm -rf \$PWD/mytestcase"
                puts $SFH "/bin/echo \"$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
                puts $SFH "$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
            } else {
                # General vanilla run
                puts $SFH "/bin/echo \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
                puts $SFH "[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
            }
        } else {
            # General run
            if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
                # stp mode
                puts $SFH "#-- remove old testcase pack or files"
                puts $SFH "rm -rf \$PWD/mytestcase"
                puts $SFH "/bin/echo \"$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
                puts $SFH "$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
            } else {
                # General vanilla run
                puts $SFH "/bin/echo \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
                puts $SFH "fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
            }
        }
    } else {
        # deals with General FEV runs
        if { [info exists ivar($task,fm_path)] && $ivar($task,fm_path) != "" } {
            # is FM version is overridden
            if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
                # stp mode
                puts $SFH "#-- remove old testcase pack or files"
                puts $SFH "rm -rf \$PWD/mytestcase"
                puts $SFH "/bin/echo \"$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
                puts $SFH "$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
            } else {
                # General vanilla run
                puts $SFH "/bin/echo \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
                puts $SFH "$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
            }
        } else {
            # General run
            if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
                # stp mode
                puts $SFH "#-- remove old testcase pack or files"
                puts $SFH "rm -rf \$PWD/mytestcase"
                puts $SFH "/bin/echo \"$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
                puts $SFH "$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
            } else {
                # General vanilla run
                puts $SFH "/bin/echo \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
                puts $SFH "fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
            }
        }
    }

    puts $SFH "set exit_status = \$status "
    if { [info exists use_stp_mode] && $use_stp_mode == 1 } {
        puts $SFH "if ( -e \"\$PWD/mytestcase\" ) then "
        puts $SFH "\tset stp_pre = `ls \$PWD/mytestcase`"
        puts $SFH "\t/bin/echo \"INTEL_INFO   : stp pre pack is available at \$PWD/mytestcase/\$stp_pre \""
        puts $SFH "\t/bin/echo \"INTEL_INFO   : Starting stp packing ... \""
        puts $SFH "\t$stp_pack_cmd \$PWD/mytestcase/\$stp_pre"
        puts $SFH "else"
        puts $SFH "\t/bin/echo \"INTEL_ERROR  : stp pack not present \""
        puts $SFH "endif"
    }
    if { [info exists eco_step] } {
        puts $SFH "rm -rf reports_$task"
        puts $SFH "mv reports reports_$task"
    }
    puts $SFH "if ( \$exit_status ) then"
    puts $SFH "\t/bin/echo \"INTEL_ERROR  : Formality shell exited with error\" "
    puts $SFH "\texit 1 "
    puts $SFH "else "
    puts $SFH "\t/bin/echo \"INTEL_INFO   : Formality run completed, exited with status 0\" "
    puts $SFH "\texit 0 "
    puts $SFH "endif"
}


## IFH file write begins here

puts $IFH "#!/bin/csh -f"
puts $IFH "#-- Copyright (c) Intel Corporation"
puts $IFH "#-- Intel Proprietary and Confidential Information"
puts $IFH "setenv block $block"
puts $IFH "setenv design $design"
puts $IFH "cd $fev_run_dir"
puts $IFH "setenv flow $flow"
puts $IFH "setenv task $task"
puts $IFH "setenv tag $tag"
puts $IFH "setenv vendor \"snps\""
puts $IFH "unsetenv EXITSHELL"
puts $IFH "if ( -e $fev_run_dir/reports.bck ) then"
puts $IFH "\trm -rf $fev_run_dir/reports.bck"
puts $IFH "\tset ex_st = \$status"
puts $IFH "\tif (\$ex_st) then"
puts $IFH "\t\t/bin/echo \"INTEL_ERROR  : Error deleting $fev_run_dir/reports.bck dir\" "
puts $IFH "\t\texit -1"
puts $IFH "\tendif"
puts $IFH "endif"
puts $IFH "if ( -e $fev_run_dir/reports ) then"
puts $IFH "\tmv $fev_run_dir/reports $fev_run_dir/reports.bck"
puts $IFH "\tset ex_stat = \$status"
puts $IFH "\tif (\$ex_stat) then"
puts $IFH "\t\t/bin/echo \"INTEL_ERROR  : Error moving $fev_run_dir/reports dir\" "
puts $IFH "\t\texit -1"
puts $IFH "\tendif"
puts $IFH "endif"
puts $IFH "mkdir $fev_run_dir/reports"
puts $IFH "set timestamp = `date +%m_%d_%H_%M`"
puts $IFH "set LOGFILE = \"\$PWD/logs/${task}_fm.log.\${timestamp}\""
puts $IFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/${task}_fm.log"
if { [info exists eco_step] } {
    puts $IFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm_eco.log"
} else {
    puts $IFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm.log"
}
puts $IFH "set LOGFILE = \"\$LOGFILE\""
puts $IFH "set UPF_ALL_STATE_VERIFY = \"0\" "
if { [info exists ivar($task,vclp_path)] && $ivar($task,vclp_path) != "" } {
    puts $IFH "setenv VC_STATIC_HOME $ivar($task,vclp_path)"
}
if { [info exists ivar($task,FM_ML_HOME)] && $ivar($task,FM_ML_HOME) != "" } {
    puts $IFH "setenv FM_ML_HOME $ivar($task,FM_ML_HOME)"
}
if { [info exists eco_step] } {
    # deals with ECO based runs
    if { [info exists ivar(fm_eco,fm_path)] && $ivar(fm_eco,fm_path) != "" } {
        # is FM version is overridden
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $IFH "#-- remove old testcase pack or files"
            puts $IFH "rm -rf \$PWD/mytestcase"
            puts $IFH "/bin/echo \"$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $IFH "$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $IFH "/bin/echo \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $IFH "[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    } else {
        # General run
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $IFH "#-- remove old testcase pack or files"
            puts $IFH "rm -rf \$PWD/mytestcase"
            puts $IFH "/bin/echo \"$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $IFH "$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $IFH "/bin/echo \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $IFH "fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    }
} else {
    # deals with General FEV runs
    if { [info exists ivar($task,fm_path)] && $ivar($task,fm_path) != "" } {
        # is FM version is overridden
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $IFH "#-- remove old testcase pack or files"
            puts $IFH "rm -rf \$PWD/mytestcase"
            puts $IFH "/bin/echo \"$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $IFH "$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $IFH "/bin/echo \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $IFH "$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    } else {
        # General run
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $IFH "#-- remove old testcase pack or files"
            puts $IFH "rm -rf \$PWD/mytestcase"
            puts $IFH "/bin/echo \"$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $IFH "$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $IFH "/bin/echo \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $IFH "fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    }
}
puts $IFH "set exit_status = \$status "
if { [info exists use_stp_mode] && $use_stp_mode == 1 } {
    puts $IFH "if ( -e \"\$PWD/mytestcase\" ) then "
    puts $IFH "\tset stp_pre = `ls \$PWD/mytestcase`"
    puts $IFH "\t/bin/echo \"INTEL_INFO   : stp pre pack is available at \$PWD/mytestcase/\$stp_pre \""
    puts $IFH "\t/bin/echo \"INTEL_INFO   : Starting stp packing ... \""
    puts $IFH "\t$stp_pack_cmd \$PWD/mytestcase/\$stp_pre"
    puts $IFH "else"
    puts $IFH "\t/bin/echo \"INTEL_ERROR  : stp pack not present \""
    puts $IFH "endif"
}
if { [info exists eco_step] } {
    puts $IFH "rm -rf reports_$task"
    puts $IFH "mv reports reports_$task"
}
puts $IFH "if ( \$exit_status ) then"
puts $IFH "\t/bin/echo \"INTEL_ERROR  : Formality shell exited with error\" "
puts $IFH "\texit 1 "
puts $IFH "else "
puts $IFH "\t/bin/echo \"INTEL_INFO   : Formality run completed, exited with status 0\" "
puts $IFH "\texit 0 "
puts $IFH "endif"




## GFH file write begins here
puts $GFH "#!/bin/csh -f"
puts $GFH "#-- Copyright (c) Intel Corporation"
puts $GFH "#-- Intel Proprietary and Confidential Information"
puts $GFH "setenv task $task"
puts $GFH "set timestamp = `date +%m_%d_%H_%M`"
puts $GFH "set LOGFILE = \"\$PWD/logs/${task}_fm.log.\${timestamp}\""
if { [info exists eco_step] } {
    puts $GFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm_eco.log"
} else {
    puts $GFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/${task}_fm.log"
}
puts $GFH "ln -sf ${task}_fm.log.\${timestamp} \$PWD/logs/fm.log"
puts $GFH "set LOGFILE = \"\$LOGFILE\""
puts $GFH "set UPF_ALL_STATE_VERIFY = \"0\" "
if { [info exists ivar($task,vclp_path)] && $ivar($task,vclp_path) != "" } {
    puts $GFH "setenv VC_STATIC_HOME $ivar($task,vclp_path)"
}
if { [info exists ivar($task,FM_ML_HOME)] && $ivar($task,FM_ML_HOME) != "" } {
    puts $GFH "setenv FM_ML_HOME $ivar($task,FM_ML_HOME)"
}
if { [info exists eco_step] } {
    # deals with ECO based runs
    if { [info exists ivar(fm_eco,fm_path)] && $ivar(fm_eco,fm_path) != "" } {
        # is FM version is overridden
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $GFH "#-- remove old testcase pack or files"
            puts $GFH "rm -rf \$PWD/mytestcase"
            puts $GFH "/bin/echo \"$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $GFH "$stp_run_cmd \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $GFH "/bin/echo \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $GFH "[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    } else {
        # General run
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $GFH "#-- remove old testcase pack or files"
            puts $GFH "rm -rf \$PWD/mytestcase"
            puts $GFH "/bin/echo \"$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $GFH "$stp_run_cmd \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $GFH "/bin/echo \"fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $GFH "fmeco_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    }
} else {
    # deals with General FEV runs
    if { [info exists ivar($task,fm_path)] && $ivar($task,fm_path) != "" } {
        # is FM version is overridden
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $GFH "#-- remove old testcase pack or files"
            puts $GFH "rm -rf \$PWD/mytestcase"
            puts $GFH "/bin/echo \"$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $GFH "$stp_run_cmd \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $GFH "/bin/echo \"$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $GFH "$ivar($task,fm_path) -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    } else {
        # General run
        if { [info exists use_stp_mode] && $use_stp_mode == 1 }  {
            # stp mode
            puts $GFH "#-- remove old testcase pack or files"
            puts $GFH "rm -rf \$PWD/mytestcase"
            puts $GFH "/bin/echo \"$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE \""
            puts $GFH "$stp_run_cmd \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl\" ./mytestcase | tee \$LOGFILE "
        } else {
            # General vanilla run
            puts $GFH "/bin/echo \"fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE \""
            puts $GFH "fm_shell -work_path \$PWD -name_suffix current -overwrite -file \$PWD/$task.tcl | tee \$LOGFILE "
        }
    }
}
puts $GFH "set exit_status = \$status "
if { [info exists use_stp_mode] && $use_stp_mode == 1 } {
    puts $GFH "if ( -e \"\$PWD/mytestcase\" ) then "
    puts $GFH "\tset stp_pre = `ls \$PWD/mytestcase`"
    puts $GFH "\t/bin/echo \"INTEL_INFO   : stp pre pack is available at \$PWD/mytestcase/\$stp_pre \""
    puts $GFH "\t/bin/echo \"INTEL_INFO   : Starting stp packing ... \""
    puts $GFH "\t$stp_pack_cmd \$PWD/mytestcase/\$stp_pre"
    puts $GFH "else"
    puts $GFH "\t/bin/echo \"INTEL_ERROR  : stp pack not present \""
    puts $GFH "endif"
}
if { [info exists eco_step] } {
    puts $GFH "rm -rf reports_$task"
    puts $GFH "mv reports reports_$task"
}
puts $GFH "if ( \$exit_status ) then"
puts $GFH "\t/bin/echo \"INTEL_ERROR  : Formality shell exited with error\" "
puts $GFH "\texit 1 "
puts $GFH "else "
puts $GFH "\t/bin/echo \"INTEL_INFO   : Formality run completed, exited with status 0\" "
puts $GFH "\texit 0 "
puts $GFH "endif"

## DFH file write begins here

# to set save session name for a particular task
if { $task == "eco_pre_synth" } {
    set ss_name "pre_synth"
} elseif { $task == "eco_post_synth" } {
    set ss_name "post_synth"
} elseif { $task == "eco_confirm_patch" } {
    set ss_name "confirm_patch"
} else {
    set ss_name "verify"
}


if { [info exists dont_generate_csh] && !$dont_generate_csh } {
    puts $DFH "#!/bin/csh -f"
    puts $DFH "#-- Copyright (c) Intel Corporation"
    puts $DFH "#-- Intel Proprietary and Confidential Information"
    puts $DFH "setenv task $task"
    puts $DFH "setenv design $design"
    puts $DFH "set UPF_ALL_STATE_VERIFY = \"0\" "
    if { [info exists ivar($task,vclp_path)] && $ivar($task,vclp_path) != "" } {
        puts $DFH "setenv VC_STATIC_HOME $ivar($task,vclp_path)"
    }
	if { [info exists ivar($task,FM_ML_HOME)] && $ivar($task,FM_ML_HOME) != "" } {
        puts $DFH "setenv FM_ML_HOME $ivar($task,FM_ML_HOME)"
    }
    puts $DFH "\nsetenv ss_name ${design}.${ss_name}.fss"

    puts $DFH "if ( -e \"$fev_run_dir/\$ss_name\" ) then"
        if { [info exists eco_step] } {
        # deals with ECO based runs
        if { [info exists ivar(fm_eco,fm_path)] && $ivar(fm_eco,fm_path) != "" } {
            # is FM version is overridden
            # General vanilla run
            puts $DFH "\t/bin/echo \"[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -session \$ss_name -gui \""
            puts $DFH "\t[regsub {fm_shell} $ivar(fm_eco,fm_path) {fmeco_shell}] -work_path \$PWD -session \$ss_name -gui"
        } else {
            # General run
            # General vanilla run
            puts $DFH "\t/bin/echo \"fmeco_shell -work_path \$PWD -session \$ss_name -gui \""
            puts $DFH "\tfmeco_shell -work_path \$PWD -session \$ss_name -gui "
        }
    } else {
        # deals with General FEV runs
        if { [info exists ivar($task,fm_path)] && $ivar($task,fm_path) != "" } {
            # is FM version is overridden
            # General vanilla run
            puts $DFH "\t/bin/echo \"$ivar($task,fm_path) -work_path \$PWD -session \$ss_name -gui \""
            puts $DFH "\t$ivar($task,fm_path) -work_path \$PWD -session \$ss_name -gui "
        } else {
            # General run
            # General vanilla run
            puts $DFH "\t/bin/echo \"fm_shell -work_path \$PWD -session \$ss_name -gui \""
            puts $DFH "\tfm_shell -work_path \$PWD -session \$ss_name -gui "
        }
    }
    puts $DFH "\tset exit_status = \$status "
    puts $DFH "\tif ( \$exit_status ) then"
    puts $DFH "\t\t/bin/echo \"INTEL_ERROR  : Formality shell exited with error\" "
    puts $DFH "\t\texit 1 "
    puts $DFH "\telse "
    puts $DFH "\t\t/bin/echo \"INTEL_INFO   : Formality run completed, exited with status 0\" "
    puts $DFH "\t\texit 0 "
    puts $DFH "\tendif"

    puts $DFH "else"
    puts $DFH "\t/bin/echo \"INTEL_ERROR  : Cannot find \$ss_name checkpoint, please check your fev run area for save sessiom\""
    puts $DFH "\texit 1"
    puts $DFH "endif"

}

#closing files
if { [info exists dont_generate_csh] && !$dont_generate_csh } {
    close $SFH
}
close $IFH
close $GFH
close $DFH


#creating the fev_ivar dump
iproc_msg -info "Creating fev static interface file"
iproc_msg -info "design and task are $design and $task"
iproc_source -file $env(ward)/global/snps/fev_formality/vars.tcl -optional

if { [info exists ivar(fev,required_ivars)] } {

    set sif $fev_run_dir/outputs/fev_ivar_si.tcl
    if { [catch {set FH [open $sif "w+"]} errMsg] } {
        iproc_msg -error "Error while creating $sif: $errMsg"
        exit
    }
    set fmt1 "%-40s \"%s\""

    foreach reqd_ivar [lsort -dictionary $ivar(fev,required_ivars)] {
        #if the ivar has a *, get all variables
        set found_ivar 0
        foreach key [array names ivar -glob "$reqd_ivar"] {
            puts $FH [format $fmt1  "set ivar($key)" $ivar($key) ]
            set found_ivar 1
        }
        if {!$found_ivar} {
            puts $FH [format $fmt1  "#set ivar($reqd_ivar)" "NA" ]
        }
    }
    close $FH
} else {
    iproc_msg -warning "No static interface was created due to missing list of fev vars ivar(fev,required_ivars)"
}
puts "###################################################################"
iproc_msg -info "FEV run area is ready for use $fev_run_dir"
puts "###################################################################"

