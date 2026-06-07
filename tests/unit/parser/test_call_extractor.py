"""Unit tests for :mod:`chopper.parser.call_extractor_body`.

These tests drive the extractor end-to-end through :func:`extract_procs`
(Stage 1d + Stage 1e) because call extraction's contract is defined on
:class:`~chopper.core.models_parser.ProcEntry` fields. Direct unit tests of
``extract_body_refs`` remain useful for suppression edge cases where
constructing a full proc around each pattern would be noisy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.parser.call_extractor_body import extract_body_refs
from chopper.parser.call_extractor_constants import EDA_FLOW_COMMANDS, LOG_PROC_NAMES, TCL_BUILTINS
from chopper.parser.proc_extractor import extract_procs
from chopper.parser.tokenizer import tokenize


def _calls(source: str) -> tuple[str, ...]:
    """Run extract_procs on a single-proc source and return the proc's calls."""
    r = extract_procs(Path("u.tcl"), source)
    assert len(r.procs) == 1, f"expected exactly 1 proc, got {len(r.procs)}"
    return r.procs[0].calls


def _source_refs(source: str) -> tuple[str, ...]:
    r = extract_procs(Path("u.tcl"), source)
    assert len(r.procs) == 1, f"expected exactly 1 proc, got {len(r.procs)}"
    return r.procs[0].source_refs


def _body_refs(body_source: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Drive ``extract_body_refs`` directly, wrapping ``body_source`` in a proc."""
    wrapped = f"proc harness {{}} {{\n{body_source}\n}}\n"
    tok_result = tokenize(wrapped)
    tokens = tok_result.tokens
    # Find body LBRACE/RBRACE indices: third and last brace respectively.
    from chopper.parser.tokenizer import TokenKind

    lbraces = [i for i, t in enumerate(tokens) if t.kind is TokenKind.LBRACE]
    rbraces = [i for i, t in enumerate(tokens) if t.kind is TokenKind.RBRACE]
    # lbrace[0] = args open, lbrace[1] = args close... no, args is `{}` so
    # lbrace[0]/rbrace[0] = args pair, lbrace[1]/rbrace[-1] = body pair.
    body_lbrace_idx = lbraces[1]
    body_rbrace_idx = rbraces[-1]
    return extract_body_refs(tokens, body_lbrace_idx, body_rbrace_idx)


# ---------------------------------------------------------------------------
# Basic call extraction
# ---------------------------------------------------------------------------


class TestBasicCalls:
    def test_single_user_call(self) -> None:
        src = "proc foo {} {\n    helper_proc arg1 arg2\n}\n"
        assert _calls(src) == ("helper_proc",)

    def test_multiple_user_calls_sorted_and_deduped(self) -> None:
        src = "proc foo {} {\n    helper_b arg\n    helper_a arg\n    helper_b arg\n}\n"
        assert _calls(src) == ("helper_a", "helper_b")

    def test_namespace_qualified_call(self) -> None:
        src = "proc foo {} {\n    ::ns::helper arg1\n}\n"
        # Leading `::` stripped per Sec.5.3 step 3b.
        assert _calls(src) == ("ns::helper",)

    def test_relative_qualified_call(self) -> None:
        src = "proc foo {} {\n    ns::helper arg1\n}\n"
        assert _calls(src) == ("ns::helper",)

    def test_call_after_semicolon(self) -> None:
        src = "proc foo {} {\n    set x 1; helper_proc\n}\n"
        assert _calls(src) == ("helper_proc",)

    def test_empty_body(self) -> None:
        src = "proc foo {} {}\n"
        assert _calls(src) == ()

    def test_whitespace_only_body(self) -> None:
        src = "proc foo {} {\n\n\n}\n"
        assert _calls(src) == ()


# ---------------------------------------------------------------------------
# Suppression (Sec.5.5)
# ---------------------------------------------------------------------------


class TestSuppression:
    def test_tcl_builtins_suppressed(self) -> None:
        # Sec.5.5 -- `set`, `if`, etc. must not surface as user procs.
        src = (
            "proc foo {} {\n"
            "    set x 1\n"
            "    if { $x == 1 } { return 0 }\n"
            "    foreach i $list {\n"
            "        incr i\n"
            "    }\n"
            "}\n"
        )
        assert _calls(src) == ()

    def test_dynamic_call_suppressed(self) -> None:
        # Sec.5.2: `$cmd arg` -- dynamic dispatch.
        src = "proc foo {} {\n    $cmd arg1\n}\n"
        assert _calls(src) == ()

    def test_log_proc_suppresses_first_word(self) -> None:
        # Sec.5.5 Level 3: log-proc names not extracted as calls.
        src = 'proc foo {} {\n    iproc_msg -info "read_libs invoked"\n}\n'
        assert _calls(src) == ()

    def test_log_proc_string_arg_not_a_call(self) -> None:
        # Sec.5.5 Level 3: proc name mentioned inside a log string is NOT a call.
        src = 'proc foo {} {\n    iproc_msg -info "read_libs will now run"\n}\n'
        calls = _calls(src)
        assert "read_libs" not in calls

    def test_log_proc_embedded_bracket_is_real(self) -> None:
        # Sec.5.5 Level 3 exception: [real_call] inside log string is a real call.
        src = 'proc foo {} {\n    iproc_msg -info "result: [compute_metric $x]"\n}\n'
        assert "compute_metric" in _calls(src)

    def test_set_proc_name_suppresses_entire_command(self) -> None:
        # Sec.5.5 Level 2f: `set PROC read_libs` -- the assigned value is NOT a call.
        src = "proc foo {} {\n    set PROC read_libs\n}\n"
        assert _calls(src) == ()

    def test_info_exists_suppressed(self) -> None:
        # Sec.5.5 Level 2g: `info exists <name>` -- <name> is not a call.
        src = "proc foo {} {\n    info exists read_libs\n}\n"
        assert _calls(src) == ()

    def test_dpa_second_word_not_extracted(self) -> None:
        # P-35 trap: `define_proc_attributes <name>` -- <name> is NOT a call.
        src = 'proc foo {} {\n    define_proc_attributes read_libs -info "x"\n}\n'
        assert _calls(src) == ()

    def test_set_app_var_suppressed(self) -> None:
        # Sec.5.5 Level 2d.
        src = 'proc foo {} {\n    set_app_var search_path "/lib"\n}\n'
        assert _calls(src) == ()


# ---------------------------------------------------------------------------
# Bracket sub-calls (Sec.5.3 step 4)
# ---------------------------------------------------------------------------


class TestBracketCalls:
    def test_embedded_bracket_call(self) -> None:
        # Sec.5.3 step 4: `[helper_proc $x]` as an argument is a real call.
        src = "proc foo {} {\n    set x [helper_proc $y]\n}\n"
        # `set` is suppressed; the bracket call is still extracted.
        assert _calls(src) == ("helper_proc",)

    def test_multiple_bracket_calls(self) -> None:
        src = "proc foo {} {\n    puts [a_call] [b_call] [c_call]\n}\n"
        # `puts` is a Tcl builtin; bracket calls extracted.
        assert _calls(src) == ("a_call", "b_call", "c_call")

    def test_bracket_call_builtin_suppressed(self) -> None:
        # `[set x 1]` -- bracket call's first word is a builtin, suppressed.
        src = "proc foo {} {\n    puts [set x 1]\n}\n"
        assert _calls(src) == ()

    def test_bracket_first_word_only(self) -> None:
        # Only the FIRST word inside `[...]` is a call candidate.
        src = "proc foo {} {\n    set x [helper first_arg_not_a_call]\n}\n"
        assert _calls(src) == ("helper",)


# ---------------------------------------------------------------------------
# source / iproc_source extraction (Sec.5.4)
# ---------------------------------------------------------------------------


class TestSourceRefs:
    def test_source_literal_path(self) -> None:
        src = "proc foo {} {\n    source common/helpers.tcl\n}\n"
        assert _source_refs(src) == ("common/helpers.tcl",)

    def test_iproc_source_file_flag(self) -> None:
        src = "proc foo {} {\n    iproc_source -file common/helpers.tcl\n}\n"
        assert _source_refs(src) == ("common/helpers.tcl",)

    def test_iproc_source_with_optional_flag(self) -> None:
        src = "proc foo {} {\n    iproc_source -file a.tcl -optional\n}\n"
        assert _source_refs(src) == ("a.tcl",)

    def test_iproc_source_with_use_hooks_flag(self) -> None:
        # Sec.5.4: hook-file discovery is a field concern -- path is captured plainly.
        src = "proc foo {} {\n    iproc_source -file a.tcl -use_hooks\n}\n"
        assert _source_refs(src) == ("a.tcl",)

    def test_source_with_echo_verbose_flags(self) -> None:
        # Sec.5.4: strip option flags first, then extract path.
        src = "proc foo {} {\n    source -echo -verbose common/helpers.tcl\n}\n"
        assert _source_refs(src) == ("common/helpers.tcl",)

    def test_source_dynamic_path_dropped(self) -> None:
        # Sec.5.4: `source $var` -- unresolvable, produces no source_ref.
        src = "proc foo {} {\n    source $path\n}\n"
        assert _source_refs(src) == ()

    def test_source_not_a_call_edge(self) -> None:
        # Sec.5.4: `source` never becomes a call in `calls` -- it is a file edge.
        src = "proc foo {} {\n    source a.tcl\n}\n"
        assert _calls(src) == ()

    def test_multiple_sources_preserve_order(self) -> None:
        # Sec.6.1 invariant 6: source_refs preserves source order, no dedup.
        src = "proc foo {} {\n    source a.tcl\n    source b.tcl\n    source a.tcl\n}\n"
        assert _source_refs(src) == ("a.tcl", "b.tcl", "a.tcl")


# ---------------------------------------------------------------------------
# EDA flow commands
# ---------------------------------------------------------------------------


class TestEDAFlowCommands:
    def test_eda_flow_commands_extracted_not_suppressed(self) -> None:
        # Sec.5.5: EDA flow commands are extracted (they will produce TW-02 at
        # trace time -- that is the expected behaviour).
        src = "proc foo {} {\n    current_design\n}\n"
        # `current_design` is in EDA_FLOW_COMMANDS but NOT in TCL_BUILTINS
        # and NOT in LOG_PROC_NAMES, so it surfaces as a candidate.
        assert "current_design" in _calls(src)

    def test_read_verilog_extracted(self) -> None:
        src = "proc foo {} {\n    read_verilog top.v\n}\n"
        assert "read_verilog" in _calls(src)


# ---------------------------------------------------------------------------
# Control-flow bodies are scanned (Sec.5.3 step 3d)
# ---------------------------------------------------------------------------


class TestControlFlowBodies:
    def test_calls_inside_if_body(self) -> None:
        src = "proc foo {} {\n    if { $x == 1 } {\n        helper_proc\n    }\n}\n"
        assert "helper_proc" in _calls(src)

    def test_calls_inside_foreach_body(self) -> None:
        src = "proc foo {} {\n    foreach item $list {\n        process_item $item\n    }\n}\n"
        assert "process_item" in _calls(src)

    def test_calls_inside_foreach_in_collection(self) -> None:
        # Sec.7.14: Synopsys iterator -- body is scanned for calls.
        src = "proc foo {} {\n    foreach_in_collection item [all_latches] {\n        process_cell $item\n    }\n}\n"
        assert "process_cell" in _calls(src)


# ---------------------------------------------------------------------------
# Real-world nested proc-call graph -- verbatim from production Synopsys
# Formality Tcl (``add_fm_td_constraints``).  This proc invokes four other
# user procs (``swap_to_current_instance``, ``handle_change_direction``,
# ``dangle_dont_verify``, ``dangle_dont_verify_par``) amid heavy builtin
# noise (``file exists``, ``foreach``, ``regexp``, ``get_attribute``,
# ``get_cells``, ``current_design``, ``puts``, ``source``).  The extractor
# must surface the four user-proc call sites and suppress the builtins.
# ---------------------------------------------------------------------------

_REAL_ADD_FM_TD_CONSTRAINTS = """proc add_fm_td_constraints { side variant design } {
    iproc_msg -info "add_fm_td_constraints procedure is invoked from file: [lindex [info frame 6] 5]"

    global ivar env ref impl ref_instance_query impl_instance_query RTL_SFP module_name
    set task $ivar(task)

    if { [info exists ivar($task,td_constraints)] && (!$ivar($task,td_constraints)) } {
        return
    }

    current_container i

    if { $side eq "REF" } {
        set ivar_side "golden"
    } else {
        set ivar_side "revised"
    }

    set path $ivar($task,fev_dot_tcl_path)

    if { [file exists "$path/${design}_fev_fm.tcl"] } {
        set bfile "$path/${design}_fev_fm.tcl"
    } else {
        set bfile ""
    }

    if { [file exists $bfile] } {
        set RTL_SFP 0
        set outfile "outputs/${design}_fev_fm.tcl"
        dangle_dont_verify_par $bfile $outfile
        source -echo -verbose $outfile
    }

    if { [info exists ivar($task,$design,black_box)] && $ivar($task,$design,black_box) != "" } {
        foreach module $ivar($task,$design,black_box) {
            set bfile "$path/../../collateral/td/$module/${module}_fev_fm.tcl"

            if { [file exists $bfile] } {
                set temp_file "outputs/${module}_fev_fm_temp.tcl"
                set temp_file1 "outputs/${module}_fev_fm_temp1.tcl"
                set outfile "outputs/${module}_fev_fm.tcl"

                swap_to_current_instance $bfile $temp_file
                handle_change_direction $temp_file $temp_file1
                dangle_dont_verify $temp_file1 $outfile

                current_design $ref
                set bbox_instances [get_attribute [get_cells -hier -filter "hdl_design_name==$module"] full_name]
                if {$bbox_instances ne ""} {
                    foreach ref_bbox $bbox_instances {
                        regexp {^[^/]+/[^/]+/[^/]+/(.*)} $ref_bbox -> front_trimmed_bbox_instance
                        source -echo -verbose $outfile
                    }
                }
            }
        }
    }
}
"""


class TestRealWorldNestedProcCalls:
    """Verbatim production proc that dispatches to four other user procs.

    This is the canonical fixture for the chopper call-graph: any regression
    where the extractor either drops a user-proc call or treats a builtin as
    a user proc fails here.
    """

    def test_add_fm_td_constraints_surfaces_four_user_proc_calls(self) -> None:
        calls = _calls(_REAL_ADD_FM_TD_CONSTRAINTS)
        # All four user-proc invocations must be captured.
        assert "dangle_dont_verify" in calls
        assert "dangle_dont_verify_par" in calls
        assert "swap_to_current_instance" in calls
        assert "handle_change_direction" in calls

    def test_add_fm_td_constraints_suppresses_tcl_builtins(self) -> None:
        calls = set(_calls(_REAL_ADD_FM_TD_CONSTRAINTS))
        # Builtins must not pollute the call set.
        for builtin in ("set", "if", "foreach", "return", "file", "regexp", "global"):
            assert builtin not in calls, f"builtin {builtin!r} leaked into calls"

    def test_calls_inside_catch_body(self) -> None:
        src = "proc foo {} {\n    catch {\n        risky_call\n    } err\n}\n"
        assert "risky_call" in _calls(src)


# ---------------------------------------------------------------------------
# Determinism + boundary
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize(
        "source",
        [
            "proc foo {} { a; b; c }\n",
            "proc foo {} {\n    helper_a\n    helper_b\n}\n",
            'proc foo {} {\n    iproc_msg -info "[real_call $x]"\n}\n',
        ],
    )
    def test_same_source_same_calls(self, source: str) -> None:
        assert _calls(source) == _calls(source)

    def test_calls_sorted_and_dedup(self) -> None:
        # Sec.6.1 invariant 5.
        src = "proc foo {} {\n    z_call; a_call; m_call; a_call\n}\n"
        assert _calls(src) == ("a_call", "m_call", "z_call")


# ---------------------------------------------------------------------------
# extract_body_refs -- direct unit tests
# ---------------------------------------------------------------------------


class TestDirectBodyExtractor:
    def test_empty_body_range(self) -> None:
        calls, refs = _body_refs("")
        assert calls == ()
        assert refs == ()

    def test_only_comments_no_calls(self) -> None:
        body = "# just a comment\n# another comment"
        calls, refs = _body_refs(body)
        assert calls == ()
        assert refs == ()

    def test_direct_classify_skips_dollar(self) -> None:
        body = "$dynamic_cmd arg1"
        calls, refs = _body_refs(body)
        assert calls == ()

    def test_direct_source_extraction(self) -> None:
        body = "source common/helpers.tcl"
        calls, refs = _body_refs(body)
        assert refs == ("common/helpers.tcl",)
        assert calls == ()


# ---------------------------------------------------------------------------
# Constant sanity
# ---------------------------------------------------------------------------


class TestConstants:
    def test_tcl_builtins_has_core(self) -> None:
        for kw in ("set", "if", "foreach", "return", "puts", "eval", "catch"):
            assert kw in TCL_BUILTINS

    def test_source_is_a_builtin(self) -> None:
        # `source` is handled via source_refs; it must be a builtin to
        # prevent it surfacing as a call edge.
        assert "source" in TCL_BUILTINS

    def test_log_proc_names_nonempty(self) -> None:
        assert "iproc_msg" in LOG_PROC_NAMES
        assert "puts" in LOG_PROC_NAMES

    def test_eda_flow_commands_nonempty(self) -> None:
        assert "current_design" in EDA_FLOW_COMMANDS
        assert "read_verilog" in EDA_FLOW_COMMANDS


# ---------------------------------------------------------------------------
# Escaped brackets in string literals (issue #25 -- Pitfall P-46)
# ---------------------------------------------------------------------------


class TestEscapedBracketCalls:
    r"""Verify that ``\[`` inside a quoted string is not extracted as a proc call.

    In Tcl, a backslash-escaped ``\[`` inside a ``"..."`` word is a literal
    ``[`` character, not the start of a command substitution.  The call
    extractor must not emit a candidate for the token that follows the
    escaped bracket.

    Regression guard: unescaped ``[`` must still be extracted normally, and
    ``\\[`` (even backslash count -> escaped backslash + real ``[``) must also
    be extracted.
    """

    def test_ansi_escape_sequence_not_a_call(self) -> None:
        # \x1b\[H\x1b\[2J -- ANSI cursor-home + clear.
        # \[ is escaped; H and 2J are NOT proc calls (false-positive from issue #25).
        src = 'proc foo {} {\n    puts -nonewline "\\x1b\\[H\\x1b\\[2J"\n}\n'
        assert _calls(src) == ()

    def test_escaped_bracket_string_literal_not_a_call(self) -> None:
        # \[flow_setup\] in a string -- flow_setup is NOT a proc call.
        src = 'proc foo {} {\n    append status_str " \\[flow_setup\\]"\n}\n'
        assert _calls(src) == ()

    def test_unescaped_bracket_still_extracted(self) -> None:
        # Regression guard: [real_proc $arg] is a real bracket call.
        src = "proc foo {} {\n    set x [real_proc $arg]\n}\n"
        assert _calls(src) == ("real_proc",)

    def test_double_backslash_bracket_extracted(self) -> None:
        # \\[real_call $arg] -- two backslashes (even count) cancel each other;
        # the [ is a real command-substitution opener; real_call IS a proc call.
        src = 'proc foo {} {\n    puts "test \\\\[real_call $arg]"\n}\n'
        assert _calls(src) == ("real_call",)

    def test_multiple_escaped_brackets_all_suppressed(self) -> None:
        # Multiple \[ in one word -- all suppressed, no false positives.
        src = 'proc foo {} {\n    set msg "\\[alpha\\] and \\[beta\\]"\n}\n'
        assert _calls(src) == ()

    def test_mixed_escaped_and_real_bracket(self) -> None:
        # \[fake_call] is escaped (not a call); [real_call] is real (is a call).
        src = 'proc foo {} {\n    puts "\\[fake_call] [real_call]"\n}\n'
        calls = set(_calls(src))
        assert "real_call" in calls
        assert "fake_call" not in calls


# ------------------------------------------------------------------
# Extracted from test_final_coverage_push.py (module-aligned consolidation).
# ------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Brace-delimited switch patterns (Pitfall P-47)
# ---------------------------------------------------------------------------


class TestSwitchBracePatterns:
    r"""Brace-delimited switch patterns with ``[...]`` must not yield false calls.

    ``switch { {[a-z]+} body }`` -- the ``{[a-z]+}`` is a literal pattern
    string, not command substitution.  Characters like ``a`` and ``z`` inside
    character-class brackets are NOT proc calls.  (P-47)
    """

    def test_brace_pattern_char_class_not_a_call(self) -> None:
        src = (
            "proc foo {ch} {\n"
            "    switch $ch {\n"
            "        {[a-z]} {\n"
            "            lower_handler $ch\n"
            "        }\n"
            "        default {\n"
            "            other_handler $ch\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        calls = set(_calls(src))
        # character-class fragments must NOT appear as calls
        assert "a" not in calls
        assert "z" not in calls
        # body code inside the arms MUST still be extracted
        assert "lower_handler" in calls
        assert "other_handler" in calls

    def test_multiple_brace_patterns_suppressed(self) -> None:
        src = (
            "proc foo {ch} {\n"
            "    switch $ch {\n"
            "        {[0-9]} {\n"
            "            numeric_handler $ch\n"
            "        }\n"
            "        {[A-Z]+} {\n"
            "            upper_handler $ch\n"
            "        }\n"
            "        default {\n"
            "            fallback_proc $ch\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        calls = set(_calls(src))
        for false_candidate in ("0", "9", "A", "Z"):
            assert false_candidate not in calls, f"{false_candidate!r} leaked as a call"
        assert "numeric_handler" in calls
        assert "upper_handler" in calls
        assert "fallback_proc" in calls

    def test_mixed_word_and_brace_patterns(self) -> None:
        src = (
            "proc foo {kind} {\n"
            "    switch $kind {\n"
            "        word_pat {\n"
            "            word_proc $kind\n"
            "        }\n"
            "        {[A-Z]+} {\n"
            "            upper_proc $kind\n"
            "        }\n"
            "        default {\n"
            "            default_proc $kind\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        calls = set(_calls(src))
        assert "word_proc" in calls
        assert "upper_proc" in calls
        assert "default_proc" in calls
        assert "A" not in calls
        assert "Z" not in calls
        assert "word_pat" not in calls

    def test_body_code_inside_switch_arm_still_extracted(self) -> None:
        # Regression guard: bodies after brace patterns must be walked normally.
        # Uses bracket substitution to ensure extraction regardless of at_cmd_pos.
        src = (
            "proc foo {ch} {\n"
            "    switch $ch {\n"
            "        {[a-z]} {\n"
            "            set result [transform_char $ch]\n"
            "            emit_result $result\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        calls = set(_calls(src))
        assert "transform_char" in calls
        assert "emit_result" in calls
        assert "a" not in calls

    def test_fixture_classify_char(self) -> None:
        """Fixture-based regression: classify_char must not extract a, z, 0, 9."""
        from pathlib import Path

        fixture = Path(__file__).parent.parent.parent / "fixtures" / "edge_cases" / "parser_switch_brace_pattern.tcl"
        from chopper.parser.proc_extractor import extract_procs

        r = extract_procs(fixture, fixture.read_text())
        calls_by_proc = {p.qualified_name: set(p.calls) for p in r.procs}
        char_calls = calls_by_proc.get("classify_char", set())
        for false_candidate in ("a", "z", "0", "9"):
            assert false_candidate not in char_calls, f"{false_candidate!r} leaked from classify_char"
        assert "real_handler" in char_calls
        assert "numeric_handler" in char_calls
        assert "other_handler" in char_calls


# ---------------------------------------------------------------------------
# Missing standard Tcl builtins (Pitfall P-48)
# ---------------------------------------------------------------------------


class TestMissingBuiltins:
    """Standard Tcl 8.5+/8.6+ builtins omitted from TCL_BUILTINS cause false TW-02.

    These commands appeared as first-word commands in proc bodies and were
    treated as unresolved user proc calls.  (P-48)
    """

    def test_lassign_not_extracted_as_call(self) -> None:
        src = "proc foo {line} {\n    lassign [split $line :] host port path\n    connect $host $port $path\n}\n"
        calls = set(_calls(src))
        assert "lassign" not in calls
        assert "connect" in calls

    def test_subst_not_extracted_as_call(self) -> None:
        src = "proc foo {tmpl} {\n    set result [subst $tmpl]\n    emit_result $result\n}\n"
        calls = set(_calls(src))
        assert "subst" not in calls
        assert "emit_result" in calls

    def test_apply_not_extracted_as_call(self) -> None:
        src = "proc foo {vals} {\n    set mapped [apply {{x} { transform $x }} $vals]\n    collect_results $mapped\n}\n"
        calls = set(_calls(src))
        assert "apply" not in calls
        assert "collect_results" in calls

    def test_throw_not_extracted_as_call(self) -> None:
        src = (
            "proc foo {val} {\n"
            '    if {$val < 0} { throw {RANGE NEGATIVE} "value must be >= 0" }\n'
            "    process_val $val\n"
            "}\n"
        )
        calls = set(_calls(src))
        assert "throw" not in calls
        assert "process_val" in calls

    def test_lmap_not_extracted_as_call(self) -> None:
        src = "proc foo {lst} {\n    set out [lmap x $lst { transform_item $x }]\n    finalize $out\n}\n"
        calls = set(_calls(src))
        assert "lmap" not in calls
        assert "finalize" in calls

    def test_builtins_in_tcl_builtins_constant(self) -> None:
        for name in ("lassign", "subst", "apply", "throw", "lmap", "lrepeat", "lreverse"):
            assert name in TCL_BUILTINS, f"{name!r} missing from TCL_BUILTINS"
