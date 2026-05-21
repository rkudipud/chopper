# Regression test for GitHub Issue #19: Multiple procs with sequential DPA blocks.
# When multiple procs are excluded, each with their own define_proc_attributes block,
# the trimmer must drop all DPA blocks atomically with their procs.
# If DPA detection fails for the second (or later) procs in a sequence, orphaned
# DPA blocks remain in the trimmed output, causing VE-16 brace imbalance errors.
#
# This fixture simulates the pc_eco domain structure from the real issue report.

proc pc_eco_set_dont_touch_annotated_delay {} {
    # Internal implementation
    set attr "dont_touch"
    return $attr
}
define_proc_attributes pc_eco_set_dont_touch_annotated_delay \
    -info "Sets dont_touch annotation on delay-related nets" \
    -define_args {
        {-net_name "Name of the net" "net" string optional}
        {-delay_value "Delay value to set" "0" string optional}
    }

proc pc_eco_set_size_cell_restrictions {} {
    # Internal implementation
    set size_limit 1000
    return $size_limit
}
define_proc_attributes pc_eco_set_size_cell_restrictions \
    -info "Applies size cell restrictions for eco flow" \
    -define_args {
        {-cell_type "Type of cell to restrict" "std_cell" string required}
        {-max_size "Maximum size limit" "1000" string optional}
    }

proc pc_eco_remove_attr_name_size_cell_restrictions {} {
    # Internal implementation
    set removed 0
    return $removed
}
define_proc_attributes pc_eco_remove_attr_name_size_cell_restrictions \
    -info "Removes attribute name restrictions from size cells" \
    -define_args {
        {-attribute_name "Name of attribute to remove" "attr" string required}
        {-all_sizes "Remove from all size variants" "1" boolean optional}
    }

# This proc should survive after excluding the three procs above
proc pc_eco_report_timing {} {
    # Report timing information
    return "timing_report"
}
define_proc_attributes pc_eco_report_timing \
    -info "Generates timing report for ECO" \
    -define_args {
        {-output_file "File to write report" "report.txt" string optional}
        {-verbose "Enable verbose output" "0" boolean optional}
    }
