# only_comment.tcl — single-file domain whose sole file has no procs.
# Validates that P2 returns an empty ProcEntry list without emitting
# PE-02 brace imbalance (there are no braces), and that downstream
# phases handle `procs_in = 0` without division-by-zero in trim_stats.
#
# This fixture drives scenario S-7 from HANDOFF_REVIEW_20260421.md.
