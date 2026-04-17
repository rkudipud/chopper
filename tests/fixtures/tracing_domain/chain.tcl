# chain.tcl — Linear call chain: entry -> step1 -> step2 -> step3

proc entry_point {} {
    step1
}

proc step1 {} {
    step2
}

proc step2 {} {
    step3
}

proc step3 {} {
    return "end"
}
