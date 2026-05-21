# helper_procs.tcl — Mini domain helper procedures
# 3 procs: read_libs, process_data, debug_dump

proc read_libs {} {
    process_data "init"
    return 1
}

proc process_data {input} {
    set output [string toupper $input]
    return $output
}

proc debug_dump {data} {
    puts "DEBUG: $data"
    return 0
}
