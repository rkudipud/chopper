# Edge case: brace data word of shape {" "} (quote, space, quote).
#
# P-01a extension. The second double-quote is preceded by a space (a
# word-boundary byte) yet must NOT open a quoted word, because the whole
# brace word `{" "}` is literal data (Tcl Endekas rule 6). Before the
# level-scoped literal-data-word fix this leaked a phantom quoted word
# that swallowed the closing `}` and raised a false PE-02 unbalanced-braces.
#
# Every proc body below is balanced; tokenizing this file must yield
# zero errors and final_brace_depth == 0. Patterns mirror real Synopsys
# Conformal/Formality idioms (regsub / string map space-collapse).

proc collapse_spaces {additional_libs} {
    # Real-world shape: collapse runs of whitespace to a single space.
    regsub -all { \s+} $additional_libs {" "} additional_libs
    return $additional_libs
}

proc strip_all_spaces {s} {
    # Multi-quote-pair sibling shape, still all-literal inside the brace.
    return [string map {" " ""} $s]
}

proc quote_with_close_brace_is_literal {} {
    # Regression guard: a lone `}` INSIDE a real quoted word stays literal
    # (the quote opens at a word boundary in script context and closes at
    # the matching `"`). This must NOT be mistaken for a structural close.
    puts "end of block: }"
}

proc quoted_semicolon_stays_literal {} {
    # TW-02 pin: `;` inside a quoted word is literal, not a command split.
    puts "a; b"
}
