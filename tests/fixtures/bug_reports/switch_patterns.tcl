# Verbatim switch-pattern-label snippet from sta_pt/psgen.tcl:1956.
# Bug: TW-02 — switch pattern fall-through labels (e.g. `child_int_type -`
# `clock_skew -` ... `tag {body}`) were treated as proc calls.
#
# Tcl rule: `switch <expr> { pattern body ?pattern body ...? }` —
# pattern words are LITERAL strings to compare against the expr.
# A body of `-` means "use the next pair's body" (fall-through).
# Pattern words are NOT command invocations and must not be extracted
# as proc calls.
#
# Expected after fix: zero TW-02 entries with callees in
# {child_int_type, clock_skew, crpr_value, ..., tag} for this file.
# (The full list per the bug report is 32 fall-through labels.)

namespace eval ::psgen {}

proc ::psgen::get_path_data {attr_name} {
    switch $attr_name {
        child_int_type -
        clock_skew -
        crpr_value -
        derate -
        edges -
        endpoint -
        endpoint_clock -
        endpoint_clock_close_edge -
        endpoint_clock_is_inverted -
        endpoint_clock_is_propagated -
        endpoint_clock_latency -
        endpoint_clock_open_edge -
        endpoint_clock_open_edge_value -
        endpoint_clock_pin -
        endpoint_external_delay -
        endpoint_is_check_pin -
        endpoint_pin -
        endpoint_setup_delta -
        full_clock_skew -
        ideal_clock_skew -
        is_inferred_clock_skew -
        launch_clock -
        launch_clock_is_propagated -
        path_group -
        path_type -
        required -
        slack -
        startpoint -
        startpoint_clock -
        startpoint_clock_pin -
        startpoint_external_delay -
        startpoint_is_check_pin -
        tag {
            set variable_name "::psgen::_path_attr_$attr_name"
            return [set $variable_name]
        }
        default {
            return ""
        }
    }
}

# Also exercise: switch -regexp / switch -exact / switch with single-line
# bracelist body, to make sure the fix is not over-fitted to one shape.
proc ::psgen::classify {kind} {
    switch -exact -- $kind {
        single { return s }
        double - triple { return m }
        default { return ? }
    }
}
