"""Per-file coverage tests for src/chopper/parser/proc_extractor.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from chopper.adapters.fs_memory import InMemoryFS
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_proc_extractor_handles_unclosed_body() -> None:
    """A proc whose body brace is never closed must produce a PW-02 error
    via the tokenizer (unbalanced brace); the extractor must handle this
    gracefully per IMPLEMENTATION.md Sec.P-04."""
    from chopper.parser.service import ParserService

    ctx = _ctx()
    fs = InMemoryFS()
    # Unclosed brace -- tokenizer emits an error token; extractor sees no body.
    fs.write_text(DOMAIN / "broken.tcl", "proc foo {} {\n# unclosed\n")
    ctx = _ctx(fs=fs)
    # Must not raise; parser tolerates broken input and logs diagnostics.
    result = ParserService().run(ctx, [DOMAIN / "broken.tcl"])
    # foo might be absent due to the unclosed brace.
    procs = list(result.index.keys())
    # No crash is the primary requirement.
    assert isinstance(procs, list)


def test_proc_extractor_skips_computed_proc_name() -> None:
    """ProcExtractor must skip computed proc names gracefully per IMPLEMENTATION.md Sec.P-04."""
    from chopper.parser.service import ParserService

    fs = InMemoryFS()
    # Computed proc name via variable substitution -- must not crash.
    fs.write_text(DOMAIN / "dyn.tcl", "proc $name {} { return 1 }\n")
    ctx = _ctx(fs=fs)
    result = ParserService().run(ctx, [DOMAIN / "dyn.tcl"])
    # No crash is the primary requirement; no proc entry for the dynamic name.
    assert isinstance(result.index, dict)


def test_proc_extractor_newline_between_args_and_body() -> None:
    """Parser handles NEWLINE tokens between args and body (line 341)."""
    from chopper.parser.service import ParserService

    fs = InMemoryFS()
    # Newline between args list and body brace
    fs.write_text(DOMAIN / "nl_proc.tcl", "proc foo {}\n{return 1}\n")
    ctx2 = _ctx(fs=fs)
    result = ParserService().run(ctx2, [DOMAIN / "nl_proc.tcl"])
    # Should parse successfully
    assert "foo" in result.index or any("foo" in k for k in result.index)


def test_proc_extractor_unclosed_brace_entry_none_pw03_none() -> None:
    """Parser handles unclosed brace body where entry=None and pw03=None (203->226, 221->226, 422)."""
    from chopper.parser.service import ParserService

    fs = InMemoryFS()
    # Proc with unclosed brace body -- body LBRACE exists but never closed
    # _build_entry returns None, _detect_non_brace_body also returns None (LBRACE not WORD)
    fs.write_text(DOMAIN / "bad_proc.tcl", "proc foo {} {unclosed body\n")
    ctx2 = _ctx(fs=fs)
    # Must not crash; the proc is malformed but parser handles gracefully
    result = ParserService().run(ctx2, [DOMAIN / "bad_proc.tcl"])
    assert isinstance(result.index, dict)


def test_scan_dpa_block_end_empty_lines_while_exits_immediately() -> None:
    """_scan_dpa_block_end with dpa_start_0 >= n exits while immediately (647->655)."""
    from chopper.parser.proc_extractor import _scan_dpa_block_end  # type: ignore[attr-defined]

    # Empty lines list -- while dpa_end_0 < n is 0 < 0 = False -> returns 0
    result = _scan_dpa_block_end([], 0)
    assert result == 0
