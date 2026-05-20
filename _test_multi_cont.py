#!/usr/bin/env python3
"""Quick test of multi-continuation behavior."""
from chopper.trimmer.indentation import format_tcl_indentation

# Multi-continuation case
text = "set long_cmd \\\n-opt1 val1 \\\n-opt2 val2 \\\n-opt3 val3\n"
result = format_tcl_indentation(text)
print("Input:")
for i, line in enumerate(text.splitlines(), 1):
    print(f"  {i}: {repr(line)}")
print("\nOutput:")
for i, line in enumerate(result.splitlines(), 1):
    print(f"  {i}: {repr(line)}")
