# Verbatim quoted-string-with-semicolon snippets from the sta_pt domain.
# Bug: TW-02 — `;` inside `"..."` strings was treated as a Tcl command
# separator, so the next word in the string became a fake proc call.
#
# Tcl rule (Endekas/Dodekalogue): inside `"..."` and `{...}`, `;` is
# a literal character. It is a command terminator ONLY outside quoting.
#
# Expected after fix: zero TW-02 entries with callee in
# {`defined`, `retaining`, `Please`, `exceeding`, `Reduced`} for this file.

# From util_max_transition_constraint.tcl:470, :485 (proc body).
proc apply_max_transition_constraint {use clock_name max_trans_clock used_const_clock intel_info} {
    puts "$intel_info Applied max transition constraint '[format "%.3f" \
         $max_trans_clock($clock_name)]' ns on clock path for clock \
         '$clock_name' (based on $use($clock_name); defined by $used_const_clock)"
}

# From pt2spice_procs.tcl:830 / pt_restore_session_dmsa.tcl:171.
proc distribute_sim_jobs {sim_flow_name} {
    iproc_msg -info "NBPredict could not infer the max cores for \
                     $sim_flow_name spice farm; retaining the existing \
                     max cores value."
}

# From lib_post_processing.tcl:220 / ip_lib_post_processing.tcl:344.
proc lib_post_processing {intel_info} {
    puts "\n$intel_info ivar(sta,enable_lef_post_processing) is \
          $::ivar(sta,enable_lef_post_processing); Please set this to 1 \
          to enable area annotation from lef file."
}

# From modelval_procs.tcl:245.
proc gen_message_summary {msgid message_instances} {
    iproc_msg -warning "Message ID '$msgid' has [sizeof_collection \
                        $message_instances] instances; exceeding the 1000 \
                        instance limit. Only the first 1000 will be processed."
}

# From sta_pt_procs.tcl:2067.
proc xpv_path_reduction {paths xpv_saved_paths} {
    iproc_msg -info "XPV path reduction: Initial = \
                     [sizeof_collection $paths] ; Reduced = \
                     [sizeof_collection $xpv_saved_paths]"
}
