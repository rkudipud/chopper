# Fixture for Pitfall P-47: brace-delimited switch patterns with [...]
# content must not generate false proc-call candidates.
#
# In Tcl ``switch { {[a-z]} body {[0-9]} body }`` uses brace-quoted
# literals as patterns.  The characters inside those braces (``a``, ``z``,
# ``0``, ``9``, ``A``, ``Z``) are NOT command substitutions and must never
# be extracted as proc calls.
#
# Expected after fix:
#   classify_char: calls == {real_handler, numeric_handler, other_handler}
#   mixed_patterns: calls == {word_body_proc, upper_proc, default_proc}
#   None of: a, z, 0, 9, A, Z appear in any call set.

proc classify_char {ch} {
    switch $ch {
        {[a-z]} {
            real_handler $ch
        }
        {[0-9]} {
            numeric_handler $ch
        }
        default {
            other_handler $ch
        }
    }
}

proc mixed_patterns {kind} {
    switch $kind {
        word_pattern {
            word_body_proc $kind
        }
        {[A-Z]+} {
            upper_proc $kind
        }
        default {
            default_proc $kind
        }
    }
}
