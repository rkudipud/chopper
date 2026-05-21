# diamond.tcl — Diamond dependency: top -> left + right -> bottom

proc top {} {
    left
    right
}

proc left {} {
    bottom
}

proc right {} {
    bottom
}

proc bottom {} {
    return "done"
}
