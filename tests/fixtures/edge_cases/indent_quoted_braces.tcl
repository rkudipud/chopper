proc quoted_braces {} {
iproc_msg -info "Setting: {opened brace} kept inside string"
set_vclp_setup_commands {-net "DIFF_MACRO_SUPPLY {VCC VSS}" -override}
iproc_msg -warn "Unmatched open brace { inside this message only"
if {$flag} {
puts nested
}
puts "done"
}
