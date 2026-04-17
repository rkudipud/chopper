# cross_file.tcl — Calls procs in other files (chain.tcl, diamond.tcl)

proc orchestrator {} {
    entry_point
    top
    source chain.tcl
    iproc_source -file diamond.tcl
}
