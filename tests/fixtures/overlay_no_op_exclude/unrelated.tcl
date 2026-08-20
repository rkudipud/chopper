# unrelated.tcl -- present on disk so VE-06 does not fire on the exclude path,
# but never included by any layer. The exclude is therefore a no-op (VE-27).

proc unrelated_proc {} {
    return "unrelated"
}
