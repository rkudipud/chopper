########################################################################
#proc       : get_hier_summary
#purpose    : For generating hierarchical summary results
#usage      : get_hier_summary design
#Owner      : global various
#BU         : global
#CTH release: global
#HSD        : global
########################################################################
proc get_hier_summary { design } {
    iproc_msg -info "get_hier_summary procedure is invoked from file: [lindex [info frame 2] 5]"

    global env ivar
    set task $ivar(task)

    # EDA-specific: tcl_set_command_name_echo is a Synopsys/Cadence command, not a user proc
    tcl_set_command_name_echo off

    set HANDLE_FT $ivar($task,td_constraints)
    set fpt [get_compare_points -nonequivalent -count]

    # redirect -variable: Synopsys EDA command; the string arg content is NOT extracted as a call
    if { [info exists HANDLE_FT] && $HANDLE_FT == 1 } {
        set uoutr "-9999"
        redirect -variable po_rev_extra "report_unmapped_points -extra -type PO -ignore_verified_po_unmap -revised"
        foreach line [split $po_rev_extra "\n"] {
            if { [regexp {(\d+)\s+unmapped\s+points\s+reported} $line match uoutr] } {
                break
            } elseif { [regexp {There\s+is\s+no\s+unmapped\s+point} $line match] } {
                set uoutr 0
                break
            }
        }
    } else {
        set uoutr [get_unmap_points -PO -extra -unreachable -notmapped -revised -count]
    }

    # vpx / vpxmode / tclmode: Cadence LEC EDA commands — not user procs (§5.5)
    vpxmode
    vpx report hier_compare result -NONEQ
    vpx report hier_compare result -NONEQ >> fev_results.log
    tclmode

    set header "----HIER EC Results for job: $design ----"

    # puts/echo with complex format strings: all suppressed by §5.5 Level 3/4
    puts "[string repeat - [string length $header]]"
    puts $header
    puts "[string repeat = [string length $header]]"
    puts "[format %-7s%-5s%-5s DESIGN STAT TOOL]"

    # echo with Synopsys EDA redirect operator >>: inert for brace tracking
    echo "[string repeat = [string length $header]]" >> fev_results.log
    echo $header >> fev_results.log
    echo "[format %-7s%-5s DESIGN STAT]" >> fev_results.log

    tcl_set_command_name_echo on
}
define_proc_attributes get_hier_summary \
    -info "Generates summary in hier runs and adds to log"
