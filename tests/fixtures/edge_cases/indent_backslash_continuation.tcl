# Real-world fixture: Tcl indentation edge cases from fev_formality domain.
# Tests backslash-continuation lines, trailing whitespace, and blank lines
# inside proc bodies. Extracted from default_fm_procs.tcl.

proc read_libs {} {
	define_proc_attributes read_libs \
   -info "To read Synopsys .db designs or technology libraries for LP and Non-LP runs"

	if { [info exists ::env(FM_SYN_LIBS)] } {
		set lib_list $::env(FM_SYN_LIBS)
	}

	foreach lib $lib_list {
		read_db $lib -technology_library
	}
}

proc read_rtl_define { container ip_name } {
		# Adding defines for units
		if { [info exists ::env(VERILOG_DEFINE)] } {

			set def_list [join $::env(VERILOG_DEFINE)]
		}
		if { [llength $def_list] > 0 } {
			read_sverilog -$container -libname ${ip_name} -define "$def_list" \{$VERILOG_CTECH_FILES\}
		} else {
			read_sverilog -$container -libname ${ip_name} \{$VERILOG_CTECH_FILES\}
		}
}

# Multi-continuation case
set long_command [some_proc \
    -arg1 value1 \
    -arg2 value2 \
    -arg3 value3]

# Double-backslash is NOT continuation
set path "C:\\Windows\\System32\\"
puts $path
