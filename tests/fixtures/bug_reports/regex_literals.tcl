# Verbatim regex/grep literal snippets from the sta_pt domain.
# Bug: TW-02 — proc-call extractor recursed into Tcl `{...}` brace-quoted
# regular expressions passed to regexp/regsub/exec grep|egrep, splitting
# on `|` and on individual letters in `[abc]` character classes, then
# warning each fragment as an unresolved proc.
#
# Tcl rule: `{...}` is a literal brace-quoted word; the contents are NOT
# parsed as Tcl source by the caller. For regex-consuming commands, the
# extractor must treat the entire braced word as opaque.
#
# Expected after fix: zero TW-02 entries with callees in
# {ERROR, FATAL, L, o, g, i, c, Warning, Error, Fatal, nom, v}.

# Pattern A: alternation `|` in `exec grep -P {...}` (sta_setup.tcl:2233).
proc retire_scenario {scenario_work_log_file} {
    if {[catch {exec grep -P {^-F-|^Fatal|^FATAL|^(INTEL_)?FATAL|^\[FATAL\]|^-E-|^Error|^ERROR|^(INTEL_)?ERROR|^\[ERROR\]} $scenario_work_log_file}]} {
        return 0
    }
    return 1
}

# Pattern B: char-class contents in `regexp {...}` (generate_twf.tcl:897).
proc process_nets {logical_net_name} {
    set tmp ""
    set num_return_string [regexp {([\*]+[L]+[o]+[g]+[i]+[c]+[0-1]+[\*]+)} $logical_net_name tmp]
    return $num_return_string
}

# Pattern C: alternation in `regexp {(?:...)}` (modelval_procs.tcl:335).
proc gen_message_summary_regex {line} {
    set match ""
    set count ""
    if {[regexp {(?:Warning|Error|Fatal):\s+.*?\s+([0-9]+)\s+.*} $line match count]} {
        return $count
    }
    return ""
}

# Pattern D: char-class in `exec egrep -i {...}` (lib_post_processing.tcl:56).
proc voltage_map_check {} {
    set lines [exec egrep -i {voltage_map\s*\(\s*\"*[nom\|v].*,\s*[0-9].[0-9]*\s*\)} stdin]
    return $lines
}
