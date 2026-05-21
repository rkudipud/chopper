# Verbatim from sta_pt/generate_clock_arrival_reports.tcl line 32 + 168.
# Bug: PW-11/PI-04 — DPA-name extractor absorbs `\`-continued flag args
# into the proc-name string, producing a false PW-11 mismatch and a
# PI-04 with a trailing `\` in the message field.
#
# Expected after fix: zero PW-11 and zero PI-04 against this file —
# the DPA target name is exactly `gen_clock_arrival_report` and matches
# the preceding proc.

proc gen_clock_arrival_report {args} {
    return $args
}

define_proc_attributes gen_clock_arrival_report \
    -info "Generate the ptsim reports" \
    -define_args {\
     {-clock "Collection of clock(s)" "clk" list required}\
     {-startpoint "Collection of start point to generate report from" "startpoint" list optional}\
     {-endpoints "Collection of end point(s) to generate report from" "endpoints" list optional}\
     {-rptname "File name to write the report into" "rptname" string optional}\
     {-apply_annotation "Flag if annotation is to be applied" "" boolean optional}\
     {-annotation_file "File naming containing ptsim annotation commands" "annotfile" string optional}
 }
