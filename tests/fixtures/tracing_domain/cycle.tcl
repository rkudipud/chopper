# cycle.tcl — Mutual recursion cycle: ping -> pong -> ping

proc ping {} {
    pong
}

proc pong {} {
    ping
}

proc standalone {} {
    return "no cycle"
}
