# util.tcl -- base contributes the whole file; feature_a drops proc foo;
# feature_b (declared after feature_a) re-includes proc foo. Final keeps both.

proc foo {} {
    return "foo"
}

proc bar {} {
    return "bar"
}
