# dynamic.tcl — Dynamic dispatch patterns (should warn, not trace)

proc caller_proc {} {
    # Direct call — should be traced
    static_helper

    # Bracketed call — should be traced
    set result [bracketed_helper arg1]

    # Dynamic dispatch — should warn TW-03 dynamic-call-form
    $cmd arg1 arg2

    # Eval-based — should warn TW-03 dynamic-call-form
    eval "dynamic_proc arg1"

    # Uplevel — should warn TW-03 dynamic-call-form
    uplevel 1 some_proc

    return $result
}

proc static_helper {} {
    return "static"
}

proc bracketed_helper {arg} {
    return $arg
}

proc dynamic_proc {arg} {
    return "should not be traced from eval"
}
