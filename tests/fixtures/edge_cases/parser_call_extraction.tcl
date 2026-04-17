proc caller {} {
    # Direct call
    direct_helper arg1 arg2

    # Bracketed call
    set result [bracketed_helper arg1]

    # Call after semicolon
    set x 1; semicolon_helper

    # Call inside if
    if {$cond} {
        control_flow_helper
    }

    # Source reference
    source lib/utils.tcl
    iproc_source -file lib/helpers.tcl -optional

    return $result
}

proc direct_helper {a b} {
    return "$a $b"
}

proc bracketed_helper {a} {
    return $a
}

proc semicolon_helper {} {
    return "semi"
}

proc control_flow_helper {} {
    return "flow"
}
