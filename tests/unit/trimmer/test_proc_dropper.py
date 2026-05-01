"""Tests for :func:`chopper.trimmer.proc_dropper.drop_procs`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.models_parser import ProcEntry
from chopper.trimmer.proc_dropper import ProcDropError, drop_procs


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
    assert drop_procs(text, []) == text


def test_drops_single_proc_from_middle() -> None:
    text = "line1\nproc foo {} {\n  body\n}\nline5\n"
    proc = _mk("foo", start=2, end=4)
    assert drop_procs(text, [proc]) == "line1\nline5\n"


def test_drop_preserves_trailing_newline_absence() -> None:
    text = "a\nb\nc"
    proc = _mk("f", start=2, end=2)
    assert drop_procs(text, [proc]) == "a\nc"


def test_drop_all_lines_returns_empty_string() -> None:
    text = "only\n"
    proc = _mk("f", start=1, end=1)
    assert drop_procs(text, [proc]) == ""


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
    result = drop_procs(text, [proc])
    assert result == "proc kept {} {}\n"


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
    assert drop_procs(text, [proc]) == "proc kept {} {}\n"


def test_descending_order_preserves_coords_with_multiple_drops() -> None:
    """Drop two procs in any manifest order — output must be identical."""
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
    result_ac = drop_procs(text, [p_a, p_c])
    result_ca = drop_procs(text, [p_c, p_a])
    assert result_ac == result_ca == "proc KEEP {} {}\n"


def test_overlapping_ranges_merge() -> None:
    """Adjacent ranges (gap of 0) must merge cleanly."""
    # 1=proc a, 2=proc b (back-to-back)
    lines = ["proc a {} {}", "proc b {} {}", "proc c {} {}"]
    text = "\n".join(lines) + "\n"
    p_a = _mk("a", start=1, end=1)
    p_b = _mk("b", start=2, end=2)
    assert drop_procs(text, [p_a, p_b]) == "proc c {} {}\n"


def test_out_of_range_raises_proc_drop_error() -> None:
    text = "line1\nline2\n"
    bogus = _mk("x", start=5, end=7)
    with pytest.raises(ProcDropError):
        drop_procs(text, [bogus])


def test_text_without_trailing_newline_round_trip() -> None:
    text = "keep\nproc f {} {}\nkeep2"
    proc = _mk("f", start=2, end=2)
    assert drop_procs(text, [proc]) == "keep\nkeep2"


def test_empty_text_with_bogus_span_errors() -> None:
    proc = _mk("f", start=1, end=1)
    with pytest.raises(ProcDropError):
        drop_procs("", [proc])


def test_drop_last_proc_leaves_no_trailing_blank() -> None:
    text = "proc kept {} {}\nproc last {} {\n  body\n}\n"
    proc = _mk("last", start=2, end=4)
    assert drop_procs(text, [proc]) == "proc kept {} {}\n"


# ---------------------------------------------------------------------------
# Real-world structural-fidelity tests
#
# The guarantee under test: when Chopper drops some procs from a file, every
# surviving proc (including its banner comment and any associated DPA block)
# must appear in the output byte-identical to the input — same indentation
# (column-0 bodies, tab-indented bodies), same blank lines, same comments.
# Snippets below are copied verbatim from production Synopsys Formality Tcl.
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
    byte-identical in the surviving text.
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

    result = drop_procs(_REAL_TWO_PROCS, [drop])
    assert expected_block in result, "kept proc block was altered by the dropper; expected verbatim preservation"
    # And the dropped proc must be fully gone (neither banner nor body).
    assert "proc dangle_dont_verify {" not in result
    assert "# Define the flexible pattern to search for" not in result


def test_real_world_drop_removes_banner_of_dropped_proc() -> None:
    """The banner comment belonging to the dropped proc must go with it."""
    procs = parse_file(Path("dangle.tcl"), _REAL_TWO_PROCS)
    drop = next(p for p in procs if p.short_name == "dangle_dont_verify_par")
    assert drop.comment_start_line is not None
    result = drop_procs(_REAL_TWO_PROCS, [drop])
    # The surviving ``dangle_dont_verify`` keeps its own banner, but the
    # second banner (above ``_par``) is gone.
    assert result.count("# Added for 3rd round of DMR 1p0") == 1
    assert "proc dangle_dont_verify_par" not in result
    assert "Column-0 body" not in result
    # The first proc's tab-indented body must still be present verbatim.
    assert "\t\tif {[regexp $pattern $line match extracted]} {\n" in result
