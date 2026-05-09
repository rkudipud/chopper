# Real-world idiom from Synopsys Formality default_fm_procs.tcl:
# `set q {"}` is a single-character data word containing the literal `"`.
# Tcl Endekas rule 6: contents of `{...}` are literal bytes.
# Earlier tokenizer versions opened a phantom quoted word here and
# silently swallowed the matching `}`, eventually emitting PE-02
# unbalanced-braces hundreds of lines later.
proc demo {} {
    set q {"}
    set x ""
    if { 1 } {
        # Mixed forms in one body: balanced quotes inside script context
        # must still tokenize as a quoted word (TW-02 contract).
        set msg "hello world"
        set re {".*"}
    }
}
