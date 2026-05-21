"""Quick repro of all five parser/tracer/validator fixes against the
bug-report fixtures. Run via:

    PYTHONPATH=src ./.venv/bin/python tests/fixtures/bug_reports/_repro_check.py

Prints calls and diagnostics per fixture; exits non-zero if any of the
known false positives still appear.
"""
from __future__ import annotations

import sys
from pathlib import Path

from chopper.parser.proc_extractor import extract_procs

ROOT = Path(__file__).parent
FALSE_POSITIVES = {
    "quoted_semicolon.tcl": {"defined", "retaining", "Please", "exceeding", "Reduced"},
    "regex_literals.tcl": {"ERROR", "FATAL", "L", "o", "g", "i", "c", "Warning", "Error", "Fatal", "nom", "v"},
    "switch_patterns.tcl": {
        "child_int_type", "clock_skew", "crpr_value", "derate", "edges",
        "endpoint", "tag", "single", "double", "triple",
    },
}

failures: list[str] = []
for name in sorted(FALSE_POSITIVES):
    p = ROOT / name
    text = p.read_text()
    er = extract_procs(p, text)
    seen_calls: set[str] = set()
    for proc in er.procs:
        seen_calls.update(proc.calls)
    leaked = seen_calls & FALSE_POSITIVES[name]
    print(f"=== {name} ===")
    for proc in er.procs:
        print(f"  proc {proc.qualified_name}  calls={list(proc.calls)}")
    if leaked:
        print(f"  LEAKED FALSE POSITIVES: {sorted(leaked)}")
        failures.append(f"{name}: {sorted(leaked)}")
    else:
        print("  OK (no false positives)")

# DPA fixture: must produce zero PW-11/PI-04 diagnostics.
dpa_path = ROOT / "dpa_multiline.tcl"
dpa_er = extract_procs(dpa_path, dpa_path.read_text())
print("=== dpa_multiline.tcl ===")
bad_diags = [d for d in dpa_er.diagnostics if d.kind in {"dpa-name-mismatch", "dpa-orphan"}]
for d in dpa_er.diagnostics:
    print(f"  DIAG {d.kind} line={d.line_no} :: {d.detail[:120]}")
if bad_diags:
    failures.append(f"dpa_multiline.tcl: {[d.kind for d in bad_diags]}")
else:
    print("  OK (no PW-11/PI-04)")

if failures:
    print("\nFAILURES:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("\nALL CLEAR")
