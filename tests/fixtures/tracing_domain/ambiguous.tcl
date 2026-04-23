# ambiguous.tcl — Ambiguous short-name resolution.
#
# Fixture target: the tracer must emit `TW-01 ambiguous-proc-match` when a
# bare call token matches two distinct canonical procs in the selected
# domain. See `technical_docs/chopper_description.md` §5.4 and technical_docs/DIAGNOSTIC_CODES.md.
#
# Shape:
#   - Two files (this file plus ambiguous_other.tcl) each define
#     `::<ns>::helper` in different namespaces (`util_ns`, `other_ns`).
#   - A third proc (`caller`) calls the bare token `helper`. Under the
#     deterministic namespace lookup contract, neither qualified candidate
#     matches the caller's own namespace, so the tracer falls back to the
#     global search, finds two procs named `helper` (via their unqualified
#     form) and reports ambiguity.
#
# Expected P4 outcome:
#   - `TW-01` emitted at the `helper` call site in `caller`
#   - Neither `util_ns::helper` nor `other_ns::helper` is auto-included
#     (trace is reporting-only; resolution requires explicit JSON entry)

namespace eval util_ns {
    proc helper {} { return "util-helper" }
}

namespace eval other_ns {
    proc helper {} { return "other-helper" }
}

proc caller {} {
    helper
}
