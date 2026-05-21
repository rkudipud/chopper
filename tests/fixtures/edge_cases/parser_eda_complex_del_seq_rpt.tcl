########################################################################
#proc       : del_seq_rpt
#purpose    : proc called in fevlite to dump out del_seq.xml
#usage      : del_seq_rpt design
#Owner      : global various
#BU         : global
#CTH release: global
#HSD        : global
########################################################################
proc del_seq_rpt { design } {
    iproc_msg -info "del_seq_rpt procedure is invoked from file: [lindex [info frame 2] 5]"

    global env ivar
    set task $ivar(task)
    set toprint ""
    set seq_con_x_cnt 0
    array unset touniq

    set fileID [open reports/${design}.deleted_seq.f18.rpt r]

    # while + if + regexp{pattern}: all braces balanced; \( \) are escaped parens, not braces
    while { [gets $fileID line] >= 0 } {
        if { [regexp {\s+(DFF|DLAT)\s+(\S+)\s+\((ZERO|ONE)\):\s+sequential X to 0,? (.*)\(.*} $line full seqtype signal const notes] } {
            if { $notes eq "" } {
                set notes "Other"
            }
            # Multi-line lappend with backslash continuation: no { or } in the strings — brace depth unaffected
            lappend toprint "<fev type=\"seqconstx\" block=\"$design\" \
                violation=\"$signal\" violation_type=\"$seqtype\" \
                violation_reason=\"$notes\" \/>"
            set touniq($signal) constx
            incr seq_con_x_cnt
        } elseif { [regexp {\s+(DFF|DLAT)\s+(\S+)\s+\((ZERO|ONE)\):\s+(data|reset) evaluated to (\d)\s+\((.*)\)} $line full seqtype signal const notes val] } {
            if { ![info exists touniq($signal)] } {
                lappend toprint "<fev type=\"seqconst0\" block=\"$design\" \
                    violation=\"$signal\" violation_reason=\"$notes evaluated to $val\" \/>"
                set touniq($signal) const
            }
        }
    }
    close $fileID

    # foreach_in_collection: Synopsys EDA iterator; treated as CONTROL_FLOW (§7.14)
    set instances [find_cfm -instance -hierarchical -collection -golden]
    foreach_in_collection inst_t $instances {
        if { [info exists touniq($inst_t)] } {
            set loc [get_attribute $inst_t location]
            set inst_print [get_attribute $inst_t parent]
            lappend toprint "<fev_instance instance=\"$inst_print\" file=\"$loc\" \/>"
        }
    }

    set file [open "reports/fev_delseq.xml" w]
    foreach print_count $toprint {
        puts $file $print_count
    }
    puts $file "</fev_delseq>"
    close $file
}
define_proc_attributes del_seq_rpt \
    -info "proc called in fevlite to dump out del_seq.xml"
