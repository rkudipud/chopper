"""Unit tests for Stage 1 parser data models (ProcEntry, ParsedFile, ParseResult)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.models import ParsedFile, ParseResult, ProcEntry


def _make_proc(
    *,
    short: str = "helper",
    qualified: str = "helper",
    file: str = "utils.tcl",
    start: int = 1,
    end: int = 3,
    body_start: int | None = None,
    body_end: int | None = None,
    namespace_path: str = "",
    calls: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    dpa: tuple[int, int] | None = None,
    comment: tuple[int, int] | None = None,
) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{qualified}",
        short_name=short,
        qualified_name=qualified,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=body_start if body_start is not None else start + 1,
        body_end_line=body_end if body_end is not None else end - 1,
        namespace_path=namespace_path,
        calls=calls,
        source_refs=source_refs,
        dpa_start_line=dpa[0] if dpa else None,
        dpa_end_line=dpa[1] if dpa else None,
        comment_start_line=comment[0] if comment else None,
        comment_end_line=comment[1] if comment else None,
    )


class TestProcEntryCanonicalName:
    """TCL_PARSER_SPEC §4.3.1 canonical-name test vectors."""

    @pytest.mark.parametrize(
        ("file_path", "qualified_name", "expected"),
        [
            ("utils.tcl", "helper", "utils.tcl::helper"),
            ("utils.tcl", "a::helper", "utils.tcl::a::helper"),
            ("utils.tcl", "a::b::helper", "utils.tcl::a::b::helper"),
            ("utils.tcl", "abs::x", "utils.tcl::abs::x"),
            ("common/helpers.tcl", "foo", "common/helpers.tcl::foo"),
            ("common/helpers.tcl", "ns::foo", "common/helpers.tcl::ns::foo"),
            ("sub/dir/f.tcl", "p::q::r", "sub/dir/f.tcl::p::q::r"),
        ],
    )
    def test_canonical_name_matches_spec_vector(self, file_path: str, qualified_name: str, expected: str) -> None:
        proc = ProcEntry(
            canonical_name=expected,
            short_name=qualified_name.rsplit("::", 1)[-1],
            qualified_name=qualified_name,
            source_file=Path(file_path),
            start_line=1,
            end_line=3,
            body_start_line=2,
            body_end_line=2,
            namespace_path="",
        )
        assert proc.canonical_name == expected

    def test_canonical_name_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="canonical_name"):
            ProcEntry(
                canonical_name="wrong::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=1,
                end_line=3,
                body_start_line=2,
                body_end_line=2,
                namespace_path="",
            )


class TestProcEntryLineInvariants:
    def test_valid_spans(self) -> None:
        proc = _make_proc(start=5, end=10, body_start=6, body_end=9)
        assert proc.start_line <= proc.body_start_line <= proc.body_end_line <= proc.end_line

    def test_one_line_proc(self) -> None:
        # §6.2 edge case: one-line proc ⇒ start==end==body_start==body_end.
        proc = _make_proc(start=5, end=5, body_start=5, body_end=5)
        assert proc.start_line == proc.end_line == 5

    def test_empty_multiline_body_allowed(self) -> None:
        # §6.2 edge case: body_start > body_end means empty body.
        proc = _make_proc(start=3, end=4, body_start=4, body_end=3)
        assert proc.body_start_line > proc.body_end_line

    def test_whitespace_body(self) -> None:
        # §6.2 edge case: blank lines inside body.
        proc = _make_proc(start=6, end=9, body_start=7, body_end=8)
        assert proc.body_end_line == 8

    def test_zero_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive 1-indexed"):
            _make_proc(start=0, end=3)

    def test_negative_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive 1-indexed"):
            _make_proc(start=1, end=3, body_start=-1)

    def test_start_after_end_rejected(self) -> None:
        with pytest.raises(ValueError, match="start_line"):
            _make_proc(start=10, end=5, body_start=5, body_end=5)

    def test_body_outside_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="body_start_line"):
            _make_proc(start=5, end=10, body_start=20, body_end=9)

    def test_body_end_outside_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="body_end_line"):
            _make_proc(start=5, end=10, body_start=6, body_end=20)


class TestProcEntryOptionalSpans:
    def test_dpa_both_set(self) -> None:
        proc = _make_proc(dpa=(11, 13))
        assert proc.dpa_start_line == 11
        assert proc.dpa_end_line == 13

    def test_dpa_only_start_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa_start_line and dpa_end_line"):
            ProcEntry(
                canonical_name="utils.tcl::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=1,
                end_line=3,
                body_start_line=2,
                body_end_line=2,
                namespace_path="",
                dpa_start_line=5,
                dpa_end_line=None,
            )

    def test_dpa_inverted_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa_start_line"):
            _make_proc(dpa=(13, 11))

    def test_dpa_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa span"):
            _make_proc(dpa=(0, 2))

    def test_comment_both_set(self) -> None:
        proc = _make_proc(comment=(1, 4), start=5, end=8)
        assert proc.comment_start_line == 1
        assert proc.comment_end_line == 4

    def test_comment_only_end_rejected(self) -> None:
        with pytest.raises(ValueError, match="comment_start_line and comment_end_line"):
            ProcEntry(
                canonical_name="utils.tcl::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=5,
                end_line=7,
                body_start_line=6,
                body_end_line=6,
                namespace_path="",
                comment_end_line=4,
            )


class TestProcEntryCallsContract:
    def test_empty_calls_allowed(self) -> None:
        proc = _make_proc(calls=())
        assert proc.calls == ()

    def test_sorted_unique_calls_accepted(self) -> None:
        proc = _make_proc(calls=("a", "b", "c"))
        assert proc.calls == ("a", "b", "c")

    def test_unsorted_calls_rejected(self) -> None:
        with pytest.raises(ValueError, match="calls must be"):
            _make_proc(calls=("b", "a"))

    def test_duplicate_calls_rejected(self) -> None:
        with pytest.raises(ValueError, match="calls must be"):
            _make_proc(calls=("a", "a", "b"))


class TestParsedFile:
    def test_single_proc(self) -> None:
        proc = _make_proc(file="x.tcl", start=1, end=3)
        pf = ParsedFile(path=Path("x.tcl"), procs=(proc,), encoding="utf-8")
        assert pf.procs == (proc,)

    def test_procs_sorted_by_start_line(self) -> None:
        p1 = _make_proc(short="a", qualified="a", file="x.tcl", start=1, end=3)
        p2 = _make_proc(short="b", qualified="b", file="x.tcl", start=5, end=7)
        pf = ParsedFile(path=Path("x.tcl"), procs=(p1, p2), encoding="utf-8")
        assert pf.procs[0].start_line == 1

    def test_procs_out_of_order_rejected(self) -> None:
        p1 = _make_proc(short="a", qualified="a", file="x.tcl", start=5, end=7)
        p2 = _make_proc(short="b", qualified="b", file="x.tcl", start=1, end=3)
        with pytest.raises(ValueError, match="sorted by start_line"):
            ParsedFile(path=Path("x.tcl"), procs=(p1, p2), encoding="utf-8")

    def test_proc_path_mismatch_rejected(self) -> None:
        proc = _make_proc(file="a.tcl")
        with pytest.raises(ValueError, match="source_file"):
            ParsedFile(path=Path("b.tcl"), procs=(proc,), encoding="utf-8")

    def test_latin1_encoding(self) -> None:
        pf = ParsedFile(path=Path("x.tcl"), procs=(), encoding="latin-1")
        assert pf.encoding == "latin-1"


class TestParseResult:
    def test_empty(self) -> None:
        pr = ParseResult()
        assert pr.files == {}
        assert pr.index == {}

    def test_single_file_single_proc(self) -> None:
        proc = _make_proc(file="a.tcl", short="helper", qualified="helper")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        pr = ParseResult(files={Path("a.tcl"): pf}, index={proc.canonical_name: proc})
        assert pr.index["a.tcl::helper"] is proc

    def test_index_missing_proc_rejected(self) -> None:
        proc = _make_proc(file="a.tcl")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        with pytest.raises(ValueError, match="index keys diverge"):
            ParseResult(files={Path("a.tcl"): pf}, index={})

    def test_index_extra_key_rejected(self) -> None:
        proc = _make_proc(file="a.tcl", short="helper", qualified="helper")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        # Fabricate a second ProcEntry that isn't in any ParsedFile.
        stray = _make_proc(file="b.tcl", short="stray", qualified="stray")
        with pytest.raises(ValueError, match="index keys diverge"):
            ParseResult(
                files={Path("a.tcl"): pf},
                index={proc.canonical_name: proc, stray.canonical_name: stray},
            )

    def test_duplicate_canonical_across_files_rejected(self) -> None:
        p1 = _make_proc(file="a.tcl", short="helper", qualified="helper")
        # Construct a collision by reusing the canonical string across a different file.
        p2 = ProcEntry(
            canonical_name=p1.canonical_name,
            short_name="helper",
            qualified_name="helper",
            source_file=Path("a.tcl"),  # deliberately same file-path to reach ParseResult check
            start_line=10,
            end_line=12,
            body_start_line=11,
            body_end_line=11,
            namespace_path="",
        )
        pf = ParsedFile(path=Path("a.tcl"), procs=(p1, p2), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate canonical_name"):
            ParseResult(files={Path("a.tcl"): pf}, index={p1.canonical_name: p1})

    def test_index_must_be_sorted(self) -> None:
        p_b = _make_proc(file="a.tcl", short="b", qualified="b")
        p_a = _make_proc(file="a.tcl", short="a", qualified="a", start=5, end=7)
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_b, p_a), encoding="utf-8")
        # Build an index in *non-sorted* insertion order.
        idx = {p_b.canonical_name: p_b, p_a.canonical_name: p_a}
        with pytest.raises(ValueError, match="lexicographically sorted"):
            ParseResult(files={Path("a.tcl"): pf}, index=idx)

    def test_sorted_index_accepted(self) -> None:
        p_a = _make_proc(file="a.tcl", short="a", qualified="a", start=5, end=7)
        p_b = _make_proc(file="a.tcl", short="b", qualified="b", start=1, end=3)
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_b, p_a), encoding="utf-8")
        idx = {p_a.canonical_name: p_a, p_b.canonical_name: p_b}
        pr = ParseResult(files={Path("a.tcl"): pf}, index=idx)
        assert list(pr.index.keys()) == sorted(pr.index.keys())

    def test_index_entry_refers_to_different_instance_rejected(self) -> None:
        # The same canonical_name but a distinct ProcEntry instance — a shape
        # the service layer must never produce.
        kwargs = {
            "canonical_name": "a.tcl::helper",
            "short_name": "helper",
            "qualified_name": "helper",
            "source_file": Path("a.tcl"),
            "start_line": 1,
            "end_line": 3,
            "body_start_line": 2,
            "body_end_line": 2,
            "namespace_path": "",
        }
        p_in_files = ProcEntry(**kwargs)
        p_in_index = ProcEntry(**kwargs)  # equal but not the same instance
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_in_files,), encoding="utf-8")
        with pytest.raises(ValueError, match="same ProcEntry instance"):
            ParseResult(files={Path("a.tcl"): pf}, index={p_in_index.canonical_name: p_in_index})
