# ns_calls.tcl — Namespace-qualified call resolution test

namespace eval flow {
    namespace eval setup {
        proc init {} {
            # Bare call — should try flow::setup::helper first, then global helper
            helper
            # Relative qualified — should try flow::setup::utils::clean, then utils::clean
            utils::clean
            # Absolute — should resolve to exactly signoff::check
            ::signoff::check
        }
    }
}

namespace eval flow {
    namespace eval setup {
        proc helper {} {
            return "local helper"
        }
    }
}

namespace eval utils {
    proc clean {} {
        return "clean"
    }
}

namespace eval signoff {
    proc check {} {
        return "signoff check"
    }
}

# Global helper — should NOT be chosen if flow::setup::helper exists
proc helper {} {
    return "global helper"
}
