"""Shared constants for Tcl body call extraction."""

from __future__ import annotations

__all__ = ["EDA_FLOW_COMMANDS", "LOG_PROC_NAMES", "TCL_BUILTINS"]


LOG_PROC_NAMES: frozenset[str] = frozenset(
    {
        "iproc_msg",
        "puts",
        "echo",
        "print_info",
        "print_warning",
        "print_error",
        "print_fatal",
        "rdt_print_info",
        "rdt_print_warn",
        "rdt_print_error",
        "log_message",
        "printvar",
        "time_stamp",
    }
)


EDA_FLOW_COMMANDS: frozenset[str] = frozenset(
    {
        "vpx",
        "vpxmode",
        "tclmode",
        "redirect",
        "tcl_set_command_name_echo",
        "annotate_trace",
        "current_design",
        "current_container",
        "set_top",
        "read_verilog",
        "read_sverilog",
        "read_db",
        "set_app_var",
        "get_app_var",
    }
)


TCL_BUILTINS: frozenset[str] = frozenset(
    {
        "if",
        "elseif",
        "else",
        "for",
        "foreach",
        "foreach_in_collection",
        "while",
        "switch",
        "catch",
        "try",
        "eval",
        "return",
        "break",
        "continue",
        "error",
        "set",
        "unset",
        "incr",
        "append",
        "lappend",
        "lset",
        "lindex",
        "llength",
        "lrange",
        "lreplace",
        "lsearch",
        "lsort",
        "list",
        "dict",
        "array",
        "string",
        "format",
        "scan",
        "regexp",
        "regsub",
        "split",
        "join",
        "expr",
        "concat",
        "proc",
        "namespace",
        "variable",
        "global",
        "upvar",
        "uplevel",
        "info",
        "rename",
        "interp",
        "open",
        "close",
        "read",
        "gets",
        "puts",
        "file",
        "glob",
        "pwd",
        "cd",
        "exec",
        "source",
        "iproc_source",
        "define_proc_attributes",
        "define_proc_arguments",
        "package",
        "clock",
        "after",
        "trace",
    }
)
