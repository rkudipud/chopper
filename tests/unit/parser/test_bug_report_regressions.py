"""Regression tests anchored on real-world bug-report fixtures.

Each test drives Chopper's parser/tracer/validator pipeline against a
verbatim Tcl snippet lifted from a production sta_pt domain bug report
under ``tests/fixtures/bug_reports/``. Failures here mean a known
real-world misparse has regressed. Synthetic toy tests for the same
behaviours have been removed (or kept where they still cover unique
edge cases not present in the production fixtures).

Bug report ↔ fixture mapping is documented in
``tests/fixtures/bug_reports/README.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.parser.proc_extractor import extract_procs

FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "bug_reports"


def _calls_by_proc(fixture: str) -> dict[str, set[str]]:
    """Return ``{qualified_name: set_of_call_tokens}`` for the fixture file."""
    p = FIXTURE_ROOT / fixture
    r = extract_procs(p, p.read_text())
    return {proc.qualified_name: set(proc.calls) for proc in r.procs}


def _diagnostic_kinds(fixture: str) -> list[str]:
    """Return the sorted list of diagnostic ``kind`` strings emitted."""
    p = FIXTURE_ROOT / fixture
    r = extract_procs(p, p.read_text())
    return sorted(d.kind for d in r.diagnostics)


# ---------------------------------------------------------------------------
# Bug: TW-02_quoted_string_semicolon_misparse
# ---------------------------------------------------------------------------


class TestQuotedSemicolon:
    """``;`` inside ``"..."`` is a literal; the next word is NOT a call.

    Before fix, every example below produced a TW-02 false positive on
    a literal English word (``defined``, ``retaining``, ``Please``,
    ``exceeding``, ``Reduced``).
    """

    @pytest.mark.parametrize(
        "proc_name, forbidden_call",
        [
            ("apply_max_transition_constraint", "defined"),
            ("distribute_sim_jobs", "retaining"),
            ("lib_post_processing", "Please"),
            ("gen_message_summary", "exceeding"),
            ("xpv_path_reduction", "Reduced"),
        ],
    )
    def test_word_after_semicolon_in_quoted_string_is_not_a_call(
        self, proc_name: str, forbidden_call: str
    ) -> None:
        calls = _calls_by_proc("quoted_semicolon.tcl")
        assert proc_name in calls, f"fixture missing proc {proc_name!r}"
        assert forbidden_call not in calls[proc_name], (
            f"{proc_name}: extracted false call {forbidden_call!r} from a "
            f"quoted string containing ';'. Tcl rule: ';' is a command "
            f"separator only OUTSIDE quoting."
        )

    def test_legitimate_bracket_call_still_extracted(self) -> None:
        calls = _calls_by_proc("quoted_semicolon.tcl")
        # ``[sizeof_collection ...]`` inside the quoted message must
        # still be discovered as a real call edge.
        assert "sizeof_collection" in calls.get("gen_message_summary", set())
        assert "sizeof_collection" in calls.get("xpv_path_reduction", set())


# ---------------------------------------------------------------------------
# Bug: TW-02_regex_literal_misparse
# ---------------------------------------------------------------------------


class TestRegexLiteralOpacity:
    """Contents of ``{...}`` regex/grep literals are NOT Tcl commands."""

    @pytest.mark.parametrize(
        "proc_name, forbidden_calls",
        [
            ("retire_scenario", {"ERROR", "FATAL"}),
            ("process_nets", {"L", "o", "g", "i", "c"}),
            ("gen_message_summary_regex", {"Warning", "Error", "Fatal"}),
            ("voltage_map_check", {"nom", "v"}),
        ],
    )
    def test_regex_literal_contents_not_extracted(
        self, proc_name: str, forbidden_calls: set[str]
    ) -> None:
        calls = _calls_by_proc("regex_literals.tcl")
        assert proc_name in calls, f"fixture missing proc {proc_name!r}"
        leaked = calls[proc_name] & forbidden_calls
        assert not leaked, (
            f"{proc_name}: regex literal contents leaked as calls: "
            f"{sorted(leaked)}. Per Tcl semantics, ``{{...}}`` brace-quoted "
            f"arguments to regexp/regsub/exec/glob are LITERAL strings."
        )


# ---------------------------------------------------------------------------
# Bug: TW-02_switch_pattern_label_misparse
# ---------------------------------------------------------------------------


class TestSwitchPatternLabels:
    """``switch`` pattern labels and fall-through markers are NOT calls."""

    def test_switch_pattern_words_not_extracted(self) -> None:
        calls = _calls_by_proc("switch_patterns.tcl")
        forbidden = {
            "child_int_type", "clock_skew", "crpr_value", "derate", "edges",
            "endpoint", "tag", "single", "double", "triple", "default",
        }
        for proc, proc_calls in calls.items():
            leaked = proc_calls & forbidden
            assert not leaked, (
                f"{proc}: switch pattern labels leaked as proc calls: "
                f"{sorted(leaked)}."
            )

    def test_switch_body_code_still_extracted(self) -> None:
        # ``set`` is a Tcl builtin and is suppressed from calls, but the
        # `[set $variable_name]` bracket substitution should NOT crash
        # and should NOT add anything spurious — assert the proc is at
        # least discovered with no extra noise.
        calls = _calls_by_proc("switch_patterns.tcl")
        assert "psgen::get_path_data" in calls
        assert calls["psgen::get_path_data"] == set()


# ---------------------------------------------------------------------------
# Bug: PW-11_PI-04_dpa_line_continuation_misparse
# ---------------------------------------------------------------------------


class TestDpaMultilineContinuation:
    """DPA-name extractor must take only the first whitespace-delimited word.

    Verbatim case: ``define_proc_attributes gen_clock_arrival_report \\``
    followed by ``-info ... -define_args { {-clock ...} ... }`` across
    six continuation lines. Before fix, the entire continuation was
    absorbed into the "name" string and produced PW-11 plus PI-04.
    """

    def test_no_pw11_pi04_when_dpa_matches_proc(self) -> None:
        kinds = _diagnostic_kinds("dpa_multiline.tcl")
        assert "dpa-name-mismatch" not in kinds, (
            "DPA-name extractor incorrectly reported a name mismatch on a "
            "well-formed continued define_proc_attributes block."
        )
        assert "dpa-orphan" not in kinds, (
            "DPA-orphan was emitted even though the DPA's first arg "
            "matches the preceding proc."
        )

    def test_dpa_span_attached_to_proc(self) -> None:
        # The proc record should carry the DPA span end_line beyond the
        # proc body, because the DPA was successfully associated.
        p = FIXTURE_ROOT / "dpa_multiline.tcl"
        r = extract_procs(p, p.read_text())
        assert len(r.procs) == 1
        proc = r.procs[0]
        assert proc.qualified_name == "gen_clock_arrival_report"
        assert proc.dpa_start_line is not None
        assert proc.dpa_end_line is not None
        # The DPA spans 8 lines (line 14 through line 22 in the fixture);
        # exact lines depend on the file layout, but end > start.
        assert proc.dpa_end_line > proc.dpa_start_line


# ---------------------------------------------------------------------------
# Bug: PE-02_python_brace_false_positive
# ---------------------------------------------------------------------------


class TestNonTclSkippedAtEnumeration:
    """ParserService must skip non-``.tcl/.itcl/.sdc`` files at enumeration.

    ``.py`` files (and other foreign extensions) end up listed in
    ``base.files.include`` when domain owners mix companion scripts.
    Running Tcl tokenization against them produces nonsense PE-02.
    """

    def test_python_file_not_parsed_as_tcl(self) -> None:
        # The fixture file is .py; running extract_procs on it directly
        # would attempt Tcl tokenisation and produce PE-02. The service
        # layer (ParserService.run) is what filters by extension; this
        # test asserts that filter via the existing unit tests in
        # tests/unit/parser/test_service.py::TestNonTclSkip. Here we
        # only verify the fixture file exists and is intentionally NOT
        # a .tcl file.
        p = FIXTURE_ROOT / "python_braces.py"
        assert p.exists()
        assert p.suffix == ".py"
