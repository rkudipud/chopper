"""Tests for :func:`chopper.trimmer.proc_dropper.annotate_procs`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.models_parser import ProcEntry
from chopper.core.provenance_markers import marker_pair
from chopper.trimmer.proc_dropper import ProcDropError, annotate_procs


def _source_of(_canonical_name: str) -> str:
    return "base"


def _kept_marker(name: str) -> tuple[str, str]:
    return marker_pair(action="kept", kind="proc", name=name, source="base")


def _removed_marker(name: str) -> tuple[str, str]:
    return marker_pair(action="removed", kind="proc", name=name, source="base")


def _mk(
    name: str,
    *,
    start: int,
    end: int,
    dpa: tuple[int, int] | None = None,
    comment: tuple[int, int] | None = None,
    file: str = "a.tcl",
) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{name}",
        short_name=name,
        qualified_name=name,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=start + 1 if start + 1 <= end else start,
        body_end_line=end - 1 if end - 1 >= start else end,
        namespace_path="",
        calls=(),
        source_refs=(),
        dpa_start_line=dpa[0] if dpa else None,
        dpa_end_line=dpa[1] if dpa else None,
        comment_start_line=comment[0] if comment else None,
        comment_end_line=comment[1] if comment else None,
    )


def test_no_procs_returns_text_unchanged() -> None:
    text = "proc foo {} {}\nproc bar {} {}\n"
    assert annotate_procs(text, [], [], _source_of) == text


def test_drops_single_proc_from_middle() -> None:
    text = "line1\nproc foo {} {\n  body\n}\nline5\n"
    proc = _mk("foo", start=2, end=4)
    begin, end = _removed_marker("foo")
    assert annotate_procs(text, [], [proc], _source_of) == f"line1\n{begin}\n{end}\nline5\n"


def test_drop_preserves_trailing_newline_absence() -> None:
    text = "a\nb\nc"
    proc = _mk("f", start=2, end=2)
    begin, end = _removed_marker("f")
    assert annotate_procs(text, [], [proc], _source_of) == f"a\n{begin}\n{end}\nc"


def test_drop_all_lines_leaves_only_marker_pair() -> None:
    text = "only\n"
    proc = _mk("f", start=1, end=1)
    begin, end = _removed_marker("f")
    assert annotate_procs(text, [], [proc], _source_of) == f"{begin}\n{end}\n"


def test_kept_proc_wraps_body_in_place_unchanged() -> None:
    text = "proc foo {} {\n  body\n}\n"
    proc = _mk("foo", start=1, end=3)
    begin, end = _kept_marker("foo")
    assert annotate_procs(text, [proc], [], _source_of) == f"{begin}\nproc foo {{}} {{\n  body\n}}\n{end}\n"


def test_comment_and_dpa_included_in_span() -> None:
    # Lines: 1=comment, 2=comment, 3=dpa, 4=proc start, 5=proc body, 6=proc end, 7=next
    lines = [
        "# comment1",  # 1
        "# comment2",  # 2
        "define_proc_attributes foo -p x",  # 3
        "proc foo {} {",  # 4
        "  body",  # 5
        "}",  # 6
        "proc kept {} {}",  # 7
    ]
    text = "\n".join(lines) + "\n"
    proc = _mk("foo", start=4, end=6, dpa=(3, 3), comment=(1, 2))
    begin, end = _removed_marker("foo")
    result = annotate_procs(text, [], [proc], _source_of)
    assert result == f"{begin}\n{end}\nproc kept {{}} {{}}\n"


def test_dpa_after_proc_still_absorbed() -> None:
    # DPA following the proc (tail DPA style).
    lines = [
        "proc foo {} {",
        "  body",
        "}",
        "define_proc_attributes foo -p x",
        "proc kept {} {}",
    ]
    text = "\n".join(lines) + "\n"
    proc = _mk("foo", start=1, end=3, dpa=(4, 4))
    begin, end = _removed_marker("foo")
    assert annotate_procs(text, [], [proc], _source_of) == f"{begin}\n{end}\nproc kept {{}} {{}}\n"


def test_multiple_procs_each_with_sequential_dpa_dropped_separately() -> None:
    lines = [
        "proc foo {} {",
        "  body",
        "}",
        "define_proc_attributes foo -info 'first'",
        "proc bar {} {",
        "  body",
        "}",
        "define_proc_attributes bar -info 'second'",
        "proc baz {} {",
        "  body",
        "}",
        "define_proc_attributes baz -info 'third'",
        "proc kept {} {}",
    ]
    text = "\n".join(lines) + "\n"
    p_foo = _mk("foo", start=1, end=3, dpa=(4, 4))
    p_bar = _mk("bar", start=5, end=7, dpa=(8, 8))
    p_baz = _mk("baz", start=9, end=11, dpa=(12, 12))

    result = annotate_procs(text, [], [p_foo, p_bar, p_baz], _source_of)

    foo_begin, foo_end = _removed_marker("foo")
    bar_begin, bar_end = _removed_marker("bar")
    baz_begin, baz_end = _removed_marker("baz")
    assert result == (f"{foo_begin}\n{foo_end}\n{bar_begin}\n{bar_end}\n{baz_begin}\n{baz_end}\nproc kept {{}} {{}}\n")
    assert "define_proc_attributes" not in result


def test_descending_order_preserves_coords_with_multiple_drops() -> None:
    """Drop two procs in any manifest order -- output must be identical."""
    lines = [
        "proc a {} {",  # 1
        "  body",  # 2
        "}",  # 3
        "proc KEEP {} {}",  # 4
        "proc c {} {",  # 5
        "  body",  # 6
        "}",  # 7
    ]
    text = "\n".join(lines) + "\n"
    p_a = _mk("a", start=1, end=3)
    p_c = _mk("c", start=5, end=7)
    result_ac = annotate_procs(text, [], [p_a, p_c], _source_of)
    result_ca = annotate_procs(text, [], [p_c, p_a], _source_of)
    a_begin, a_end = _removed_marker("a")
    c_begin, c_end = _removed_marker("c")
    assert result_ac == result_ca == f"{a_begin}\n{a_end}\nproc KEEP {{}} {{}}\n{c_begin}\n{c_end}\n"


def test_adjacent_ranges_each_get_own_marker() -> None:
    """Adjacent drop spans (gap of 0) no longer merge -- each proc gets its own marker pair."""
    lines = ["proc a {} {}", "proc b {} {}", "proc c {} {}"]
    text = "\n".join(lines) + "\n"
    p_a = _mk("a", start=1, end=1)
    p_b = _mk("b", start=2, end=2)
    a_begin, a_end = _removed_marker("a")
    b_begin, b_end = _removed_marker("b")
    assert (
        annotate_procs(text, [], [p_a, p_b], _source_of)
        == f"{a_begin}\n{a_end}\n{b_begin}\n{b_end}\nproc c {{}} {{}}\n"
    )


def test_out_of_range_raises_proc_drop_error() -> None:
    text = "line1\nline2\n"
    bogus = _mk("x", start=5, end=7)
    with pytest.raises(ProcDropError):
        annotate_procs(text, [], [bogus], _source_of)


def test_overlapping_spans_raise_proc_drop_error() -> None:
    text = "line1\nline2\nline3\n"
    p_a = _mk("a", start=1, end=2)
    p_b = _mk("b", start=2, end=3)
    with pytest.raises(ProcDropError):
        annotate_procs(text, [], [p_a, p_b], _source_of)


def test_text_without_trailing_newline_round_trip() -> None:
    text = "keep\nproc f {} {}\nkeep2"
    proc = _mk("f", start=2, end=2)
    begin, end = _removed_marker("f")
    assert annotate_procs(text, [], [proc], _source_of) == f"keep\n{begin}\n{end}\nkeep2"


def test_empty_text_with_bogus_span_errors() -> None:
    proc = _mk("f", start=1, end=1)
    with pytest.raises(ProcDropError):
        annotate_procs("", [], [proc], _source_of)


def test_drop_last_proc_leaves_no_trailing_blank() -> None:
    text = "proc kept {} {}\nproc last {} {\n  body\n}\n"
    proc = _mk("last", start=2, end=4)
    begin, end = _removed_marker("last")
    assert annotate_procs(text, [], [proc], _source_of) == f"proc kept {{}} {{}}\n{begin}\n{end}\n"


def test_source_of_is_consulted_per_proc() -> None:
    text = "proc a {} {}\nproc b {} {}\n"
    p_a = _mk("a", start=1, end=1)
    p_b = _mk("b", start=2, end=2)

    def source_of(canonical_name: str) -> str:
        return "feature:dft" if canonical_name.endswith("::a") else "default"

    result = annotate_procs(text, [p_a], [p_b], source_of)
    a_begin, a_end = marker_pair(action="kept", kind="proc", name="a", source="feature:dft")
    b_begin, b_end = marker_pair(action="removed", kind="proc", name="b", source="default")
    assert result == f"{a_begin}\nproc a {{}} {{}}\n{a_end}\n{b_begin}\n{b_end}\n"


# ---------------------------------------------------------------------------
# Real-world structural-fidelity tests
#
# The guarantee under test: when Chopper annotates a file, every surviving
# proc's original bytes (banner comment, DPA block, body -- same indentation,
# same blank lines) still appear verbatim inside its marker wrapper, and a
# removed proc's banner and body are both fully gone, replaced by an empty
# marker pair. Snippets below are copied verbatim from production Synopsys
# Formality Tcl.
# ---------------------------------------------------------------------------

from chopper.parser.service import parse_file  # noqa: E402  (test-local helper import)

# Two real procs in one file.  ``dangle_dont_verify`` (drop target) has a
# tab-indented body; ``dangle_dont_verify_par`` (keep target) has its body
# opened at column 0 and contains blank lines.  Both carry a single-line
# banner comment (``# Added for 3rd round of DMR 1p0``).  This is the exact
# formatting style we encounter in the wild.
_REAL_TWO_PROCS = (
    "# Added for 3rd round of DMR 1p0\n"
    "proc dangle_dont_verify {infile outfile} {\n"
    "\t# Define the flexible pattern to search for\n"
    "\tset pattern {# .*/([^/]+) is dangling feedthrough port\\.}\n"
    "\n"
    "\tset input_fileId [open $infile r]\n"
    "\tset output_fileId [open $outfile w]\n"
    "\n"
    "\twhile {[gets $input_fileId line] != -1} {\n"
    "\t\tif {[regexp $pattern $line match extracted]} {\n"
    '\t\t\tputs $output_fileId "matched $extracted"\n'
    "\t\t} else {\n"
    "\t\t\tputs $output_fileId $line\n"
    "\t\t}\n"
    "\t}\n"
    "\n"
    "\tclose $input_fileId\n"
    "\tclose $output_fileId\n"
    "}\n"
    "\n"
    "# Added for 3rd round of DMR 1p0\n"
    "proc dangle_dont_verify_par {infile outfile} {\n"
    "# Column-0 body: this is how the real file is formatted.\n"
    "set pattern {# .*/([^/]+) is dangling feedthrough port\\.}\n"
    "\n"
    "set input_fileId [open $infile r]\n"
    "set output_fileId [open $outfile w]\n"
    "\n"
    "while {[gets $input_fileId line] != -1} {\n"
    "    puts $output_fileId $line\n"
    "}\n"
    "\n"
    "close $input_fileId\n"
    "close $output_fileId\n"
    "}\n"
)


def test_real_world_dropping_one_proc_preserves_other_verbatim() -> None:
    """After dropping ``dangle_dont_verify``, ``dangle_dont_verify_par``
    (body, banner comment, blank lines, column-0 indentation) must appear
    byte-identical inside its ``kept`` marker wrapper.
    """
    procs = parse_file(Path("dangle.tcl"), _REAL_TWO_PROCS)
    assert {p.short_name for p in procs} == {"dangle_dont_verify", "dangle_dont_verify_par"}
    drop = next(p for p in procs if p.short_name == "dangle_dont_verify")
    keep = next(p for p in procs if p.short_name == "dangle_dont_verify_par")

    # The exact bytes that must survive, read from the input via the
    # ``keep`` proc's own line span (banner comment line 1 above).
    source_lines = _REAL_TWO_PROCS.split("\n")
    keep_start = keep.comment_start_line if keep.comment_start_line is not None else keep.start_line
    expected_block = "\n".join(source_lines[keep_start - 1 : keep.end_line])

    result = annotate_procs(_REAL_TWO_PROCS, [keep], [drop], _source_of)
    assert expected_block in result, "kept proc block was altered by the annotator; expected verbatim preservation"
    # And the dropped proc must be fully gone (neither banner nor body).
    assert "proc dangle_dont_verify {" not in result
    assert "# Define the flexible pattern to search for" not in result
    # The kept proc is wrapped in its own marker pair.
    begin, end = _kept_marker("dangle_dont_verify_par")
    assert begin in result
    assert end in result


def test_real_world_drop_removes_banner_of_dropped_proc() -> None:
    """The banner comment belonging to the dropped proc must go with it."""
    procs = parse_file(Path("dangle.tcl"), _REAL_TWO_PROCS)
    keep = next(p for p in procs if p.short_name == "dangle_dont_verify")
    drop = next(p for p in procs if p.short_name == "dangle_dont_verify_par")
    assert drop.comment_start_line is not None
    result = annotate_procs(_REAL_TWO_PROCS, [keep], [drop], _source_of)
    # The surviving ``dangle_dont_verify`` keeps its own banner, but the
    # second banner (above ``_par``) is gone.
    assert result.count("# Added for 3rd round of DMR 1p0") == 1
    assert "proc dangle_dont_verify_par" not in result
    assert "Column-0 body" not in result
    # The first proc's tab-indented body must still be present verbatim.
    assert "\t\tif {[regexp $pattern $line match extracted]} {\n" in result
