# Fixture: escaped-bracket-in-string (issue #25 -- P-46).
#
# Tests that \[ inside a double-quoted string is a *literal* character and must
# NOT be extracted as a proc call (false-positive TW-02).
#
# Covered cases:
#   1. ANSI escape sequence  "\x1b\[H\x1b\[2J" -- H and 2J are not proc names.
#   2. Escaped bracket in string literal  " \[flow_setup\]" -- flow_setup is not a proc call.
#   3. Unescaped bracket  [real_proc $arg] -- real_proc IS a proc call (regression guard).
#   4. Double-backslash bracket  "\\[real_call $arg]" -- \\[ is escaped-backslash +
#      real [ command substitution; real_call IS a proc call (even backslash count).

proc ansi_escape_string {} {
    # ANSI cursor-home + clear: \x1b\[H\x1b\[2J
    # \[ is escaped -- H and 2J are NOT proc calls.
    puts -nonewline "\x1b\[H\x1b\[2J"
}

proc literal_bracket_in_string {} {
    # Escaped brackets in a string literal.
    # \[flow_setup\] -- flow_setup is NOT a proc call.
    append status_str " \[flow_setup\]"
}

proc real_bracket_call_preserved {} {
    # Unescaped bracket -- real_proc IS a proc call.
    set x [real_proc $arg]
}

proc double_backslash_bracket {} {
    # \\[real_call $arg] -- \\ is an escaped backslash (even count),
    # so [real_call $arg] IS command substitution; real_call IS a proc call.
    puts "test \\[real_call $arg]"
}
