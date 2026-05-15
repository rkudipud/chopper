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
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_proc_dropper_includes_leading_comment_in_drop_range() -> None:
    from chopper.core.models_parser import ProcEntry
    from chopper.trimmer.proc_dropper import drop_procs

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
    out = drop_procs(text, [pe])
    assert "gone" not in out
    assert "keep" in out


def test_proc_dropper_merge_overlaps_empty() -> None:
    from chopper.trimmer.proc_dropper import _merge_overlaps

    assert _merge_overlaps([]) == []
