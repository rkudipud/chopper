# proc_inside_control_flow.tcl — Procs inside if/for/catch should NOT be indexed

if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}

for {set i 0} {$i < 10} {incr i} {
    proc loop_proc {} {
        return "loop"
    }
}

catch {
    proc error_proc {} {
        return "error"
    }
}

# This one SHOULD be indexed (at file root)
proc valid_proc {} {
    return "valid"
}
