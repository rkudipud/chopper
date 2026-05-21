# computed_ns.tcl — Computed namespace name should trigger warning

namespace eval ${dynamic_name} {
    proc should_not_be_indexed {} {
        return "dynamic ns"
    }
}

namespace eval static_ns {
    proc should_be_indexed {} {
        return "static ns"
    }
}
