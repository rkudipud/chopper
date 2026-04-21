#!/usr/intel/bin/tclsh8.6
####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


if { [lsearch $::auto_path $::env(ward)/global/common/packages] == -1 } {
    lappend ::auto_path $::env(ward)/global/common/packages
}
package require parseOpt

#Define script arguments
::parseOpt::cmdSpec promote.tcl {
    -help "Promote outputs to release area"
    -no_auto_dash_in_options 1
    -opt {
        {-optname -B,--build_dir                -type string                        -required 1     -help "Specify block/build name"}
        {-optname -D,--design                   -type string    -default ""         -required 0     -help "Design name defines ivar(design_name)"}
        {-optname -R,--run_dir                  -type string                        -required 0     -help "Specify block run directory"}
        {-optname -X,--tech                     -type string                        -required 0     -help "Specify block run directory"}
        {-optname -G,--tag                      -type string    -default latest     -required 0     -help "Specify required tag name"}
        {-optname -T,--task                     -type string                        -required 1     -help "Specify required task name"}
        {-optname -force,--force                -type bool      -default 0	        -required 0     -help "Force"}
        {-optname -N,--no_promote               -type bool      -default 0	        -required 0     -help "Metric upload only"}
    }
}

#Parse script arguments and exit upon a returned 0 or thrown error.
if { [catch { if {![::parseOpt::parseOpts promote.tcl opt $argv] } { exit 0 }}] } { exit 1 }

set env(flow) "fev_formality"
set ::env(vendor) "snps"

set block $opt(-B)
set design $opt(-B)
if { $opt(-X) != "" } {
    set tech $opt(-X)
} else {
    set tech $env(tech)
}

set task $opt(-T)
set ivar(task) $task

if { $opt(-D) != "" } {
    set env(design)  $opt(-D)
}

set fev_build_dir "$env(ward)/runs/$block/$tech"
set tag "latest"
if { $opt(-G) != "" } {
    set tag $opt(-G)
}
set run_dir $opt(-T)
if { $opt(-R) != "" } {
    set run_dir $opt(-R)
}
set force $opt(-force)

set no_promote $opt(-N)


if { ![file exists $fev_build_dir] } {
    puts "INTEL_ERROR  : Invalid build directory : $fev_build_dir"
    exit
}

if { ![file exists $fev_build_dir/$env(flow)/$run_dir] } {
    puts "INTEL_ERROR  : Invalid run directory : $fev_build_dir/$env(flow)/$run_dir"
    exit
}
set env(tag) $tag
set env(view_mode) 1
set env(block) $block
if { [catch {source $env(ward)/global/common/setup.tcl } msg] } {
    puts "INTEL_ERROR  : Sourcing $env(ward)/global/common/setup.tcl:   $msg"
}

if { $no_promote != "1" } {
    ## check for folders and link the cuirrent fev to release area
    set release_dir $fev_build_dir/release/$tag
    if { ![file exists $release_dir] } {
        file mkdir $release_dir
    }


    if { [file exists $release_dir/$run_dir] } {
        if { $force } {
            file delete -force $release_dir/$run_dir
        } else {
            iproc_msg -warning "Directory $release_dir/$run_dir exist. Use -force to overwrite"
            exit
        }
    }

    set stop_promote 0
    set fail_file "$fev_build_dir/$env(flow)/$run_dir/logs/$task.fail"
    if { [file exists $fail_file] } {
        iproc_msg -info "fail file present at $fail_file"
        set readfail [open $fail_file r]
        set readfail_l [read $readfail]
        close $readfail

        set lines [split $readfail_l "\n"]
        foreach line $lines {
            if { [regexp {^\s*Conformal\s+shell\s+exited with\s+status\s+255} $line match name] } {
                #iproc_msg -info "Line found $name"
                set stop_promote 1
            }
        }
    }

    if { $stop_promote == 0 } {
        exec ln -fs $fev_build_dir/$env(flow)/$run_dir $release_dir/$run_dir
        iproc_msg -info "Run dir is linked to $release_dir area"
    } else {
        iproc_msg -info "Can't perform promote as the Formality run has crashed"
    }

}

if { [ info exists ivar(cth_metric_upload) ] } {

    if { ($ivar(cth_metric_upload)) } {
        iproc_msg -info "Cheetah metric upload is enabled. uploading"
        iproc_msg -info "Calling cth_metric_upload"
        ##prepare indicator
        file mkdir $fev_build_dir/Indicators
        set report_file [open "$fev_build_dir/Indicators/gen_FEVMatrix.out" w]
        set cmd "$env(ward)/global/common/Indicators/parser/gen_FEVMatrix.tcl"
        if { [catch { eval exec [list $cmd --build_dir $block --flow fev_formality --report_file $fev_build_dir/Indicators/gen_FEVMatrix.out --run_dir $task --design $design --tech $tech --config_list [list $design $fev_build_dir]]} errmsg] } {
            iproc_msg -info "Refer $errmsg for details"
        }
        set csv_file "$fev_build_dir/Indicators/fev_formality.csv"
        #Block chain

        
        if { [file exists $csv_file] } {
            if { [catch {cth_metric_upload -input_csv $csv_file} upload_err] } {
                iproc_msg -error "Encountered problem while uploading Indicator data: $upload_err"
            } else {
                iproc_msg -info "Successfully uploaded: $csv_file"
            }
        } else {
            iproc_msg -info "Missing file: $csv_file. Cannot upload this Indicator data."
        }
    } else {
        iproc_msg -warning "Cheetah metric upload is disabled."
    }
} else {
    iproc_msg -error "cth_metric_upload ivar is undefined"
}

if { $no_promote != "1" } {
    iproc_msg -info "Calling DBI proc run_cth_dbi"
    run_cth_dbi -design_name $ivar(design_name) -block $block -bundle $task -ward_tag $env(tag)
}
