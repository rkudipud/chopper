# nested_ns.tcl — Deeply nested namespace eval blocks

namespace eval a {
    namespace eval b {
        namespace eval c {
            proc deep_proc {} {
                return "deep"
            }
        }
        proc mid_proc {} {
            return "mid"
        }
    }
    proc top_proc {} {
        return "top"
    }
}
