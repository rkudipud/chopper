# sequential_ns.tcl — Sequential namespace eval blocks for the same and different namespaces

namespace eval utils {
    proc helper_a {} {
        return "a"
    }
}

namespace eval utils {
    proc helper_b {} {
        return "b"
    }
}

namespace eval tools {
    proc tool_x {} {
        return "x"
    }
}

proc global_proc {} {
    return "global"
}
