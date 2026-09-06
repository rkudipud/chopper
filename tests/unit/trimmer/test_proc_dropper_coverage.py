"""Per-file coverage tests for src/chopper/trimmer/proc_dropper.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_proc_dropper_includes_leading_comment_in_drop_range() -> None:
    from chopper.core.models_parser import ProcEntry
    from chopper.trimmer.proc_dropper import annotate_procs

    text = "# leading comment\nproc gone {} { return 1 }\nproc keep {} { return 2 }\n"
    pe = ProcEntry(
        canonical_name="x.tcl::gone",
        short_name="gone",
        qualified_name="gone",
        source_file=Path("x.tcl"),
        start_line=2,
        end_line=2,
        body_start_line=2,
        body_end_line=2,
        namespace_path="",
        comment_start_line=1,
        comment_end_line=1,
    )
    out = annotate_procs(text, [], [pe], lambda _cn: "base")
    assert "return 1" not in out
    assert "keep" in out


def test_proc_dropper_span_for_absorbs_dpa_and_comment() -> None:
    from chopper.core.models_parser import ProcEntry
    from chopper.trimmer.proc_dropper import _span_for

    pe = ProcEntry(
        canonical_name="x.tcl::foo",
        short_name="foo",
        qualified_name="foo",
        source_file=Path("x.tcl"),
        start_line=4,
        end_line=6,
        body_start_line=5,
        body_end_line=5,
        namespace_path="",
        dpa_start_line=3,
        dpa_end_line=3,
        comment_start_line=1,
        comment_end_line=2,
    )
    assert _span_for(pe).start == 1
    assert _span_for(pe).end == 6
