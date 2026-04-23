# bracketed_call.tcl — Tcl command substitution via `[...]`.
#
# Fixture target: call extraction (§5 of technical_docs/TCL_PARSER_SPEC.md) must
# identify the first word of a bracketed sub-expression as a call
# candidate — and only the first word. This is the canonical positive
# case for `[cmd arg ...]` substitution.
#
# Shape:
#   - `consumer` sets a variable to the result of `[formatter arg1]`.
#   - `consumer` also calls `[report status]` inside a puts argument to
#     verify that bracketed extraction survives being nested inside a
#     quoted string (the outer puts argument is data; the inner `[...]`
#     is command substitution).
#
# Expected extraction:
#   - candidate calls for `consumer`: {formatter, report}
#   - NOT extracted: `status`, `arg1`, `puts` arguments other than the
#     bracketed command name.

proc formatter {value} {
    return "formatted: $value"
}

proc report {label} {
    return "report:$label"
}

proc status {} {
    return "ok"
}

proc consumer {} {
    set result [formatter arg1]
    puts "debug: [report status]"
    return $result
}
