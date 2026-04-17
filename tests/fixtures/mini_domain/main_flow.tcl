# main_flow.tcl — Mini domain primary flow file
# 3 procs: setup_flow, run_main, cleanup_flow

proc setup_flow {} {
    read_libs
    set x 1
    return $x
}

proc run_main {args} {
    setup_flow
    set result [process_data $args]
    return $result
}

proc cleanup_flow {} {
    set status "done"
    return $status
}
