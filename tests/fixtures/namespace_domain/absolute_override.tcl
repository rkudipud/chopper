# absolute_override.tcl — Absolute proc names override namespace context

namespace eval local {
    proc local_proc {} {
        return "in local"
    }

    proc ::global_override {} {
        return "forced global"
    }

    proc ::other::ns_proc {} {
        return "in other namespace"
    }
}
