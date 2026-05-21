# Verbatim from PE-02 bug report: a Python file ended up in
# `base.files.include` because a domain owner mixed `.py` companions
# alongside `.tcl`. Chopper's brace counter ran against this file and
# raised PE-02 "Unbalanced braces" against perfectly valid Python.
#
# Expected: ParserService skips non-`.tcl/.itcl/.sdc` files at the
# enumeration boundary. No PE-02 emitted. (Already fixed in 0.4.0;
# this file is the regression anchor.)
ivar_value = "{}"
ivar_value = ivar_value.replace("}", "}\n   ")
def helper():
    return {"x": 1}
