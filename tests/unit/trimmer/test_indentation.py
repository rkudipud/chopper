"""Tests for P5c Tcl indentation normalization."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance
from chopper.core.models_trimmer import FileOutcome, GeneratedArtifact, TrimReport
from chopper.trimmer.indentation import TclIndentationService, format_tcl_indentation
from tests.unit.trimmer._helpers import DOMAIN, make_ctx


def _manifest(decisions: dict[str, FileTreatment]) -> CompiledManifest:
    file_decisions: dict[Path, FileTreatment] = {}
    provenance: dict[Path, FileProvenance] = {}
    for raw_path, treatment in sorted(decisions.items()):
        path = Path(raw_path)
        file_decisions[path] = treatment
        provenance[path] = FileProvenance(
            path=path,
            treatment=treatment,
            reason="fi-literal" if treatment is not FileTreatment.REMOVE else "default-exclude",
            input_sources=("base:files.include",) if treatment is not FileTreatment.REMOVE else (),
            proc_model="overlay" if treatment is FileTreatment.PROC_TRIM else None,
        )
    return CompiledManifest(file_decisions=file_decisions, proc_decisions={}, provenance=provenance)


def _outcome(path: str, treatment: FileTreatment, *, bytes_out: int) -> FileOutcome:
    return FileOutcome(
        path=Path(path),
        treatment=treatment,
        bytes_in=bytes_out,
        bytes_out=bytes_out,
        procs_kept=(),
        procs_removed=(),
    )


def _report(*outcomes: FileOutcome) -> TrimReport:
    ordered = tuple(sorted(outcomes, key=lambda outcome: outcome.path.as_posix()))
    return TrimReport(
        outcomes=ordered,
        files_copied=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for outcome in ordered if outcome.treatment is FileTreatment.REMOVE),
        procs_kept_total=0,
        procs_removed_total=0,
    )


def test_format_tcl_indentation_ports_legacy_brace_logic() -> None:
    text = "proc foo {} {\nputs ok\nif {$flag} {\nputs nested\n}\ntopology:\n}\n"

    assert format_tcl_indentation(text) == (
        "proc foo {} {\n    puts ok\n    if {$flag} {\n        puts nested\n    }\n  topology:\n}\n"
    )


def test_format_tcl_indentation_backslash_continuation() -> None:
    """Backslash-continuation lines get one extra indent level."""
    text = 'proc foo {} {\nputs body\n}\ndefine_proc_attributes foo \\\n-info "does something"\n'
    result = format_tcl_indentation(text)
    assert result == ('proc foo {} {\n    puts body\n}\ndefine_proc_attributes foo \\\n    -info "does something"\n')


def test_format_tcl_indentation_multi_continuation() -> None:
    """Multiple consecutive continuation lines all get one extra indent level."""
    text = "set long_cmd \\\n-opt1 val1 \\\n-opt2 val2 \\\n-opt3 val3\n"
    result = format_tcl_indentation(text)
    # All continuation lines at same indent (+1 level from opening line)
    assert result == ("set long_cmd \\\n    -opt1 val1 \\\n    -opt2 val2 \\\n    -opt3 val3\n")


def test_format_tcl_indentation_continuation_inside_proc() -> None:
    """Continuation inside a proc body gets proc indent + continuation indent."""
    text = "proc bar {} {\nsome_command \\\n-flag value\nputs done\n}\n"
    result = format_tcl_indentation(text)
    assert result == ("proc bar {} {\n    some_command \\\n        -flag value\n    puts done\n}\n")


def test_format_tcl_indentation_double_backslash_not_continuation() -> None:
    r"""Line ending with \\\\ (escaped backslash) is NOT a continuation."""
    text = 'set path "C:\\\\"\nputs next_line\n'
    result = format_tcl_indentation(text)
    # Both lines at indent 0 — no continuation
    assert result == ('set path "C:\\\\"\nputs next_line\n')


def test_format_tcl_indentation_blank_lines_no_trailing_whitespace() -> None:
    """Blank lines inside proc bodies are truly empty (no trailing whitespace)."""
    text = "proc foo {} {\n\n    puts body\n\t\n    puts more\n}\n"
    result = format_tcl_indentation(text)
    assert result == ("proc foo {} {\n\n    puts body\n\n    puts more\n}\n")


def test_service_formats_proc_trim_and_generated_but_not_full_copy_tcl() -> None:
    """P5c rewrites PROC_TRIM and GENERATED ``.tcl`` only.

    FULL_COPY ``.tcl`` outputs (and any non-Tcl outputs) must reach disk
    byte-for-byte identical to their source — see issue #22.
    """
    full_text = "proc copied {} {\nputs copied\n}\n"
    trim_text = "proc kept {} {\nputs kept\n}\n"
    generated_text = "# Chopper-generated stage: stage\nif {$ready} {\nputs ready\n}\n"
    note_text = "    not tcl\n"
    fs = InMemoryFS(
        {
            DOMAIN / "full.tcl": full_text,
            DOMAIN / "trim.tcl": trim_text,
            DOMAIN / "stage.tcl": generated_text,
            DOMAIN / "note.txt": note_text,
        }
    )
    ctx, sink = make_ctx(fs=fs)
    manifest = _manifest(
        {
            "full.tcl": FileTreatment.FULL_COPY,
            "note.txt": FileTreatment.FULL_COPY,
            "stage.tcl": FileTreatment.GENERATED,
            "trim.tcl": FileTreatment.PROC_TRIM,
        }
    )
    report = _report(
        _outcome("full.tcl", FileTreatment.FULL_COPY, bytes_out=len(full_text.encode("utf-8"))),
        _outcome("note.txt", FileTreatment.FULL_COPY, bytes_out=len(note_text.encode("utf-8"))),
        _outcome("trim.tcl", FileTreatment.PROC_TRIM, bytes_out=len(trim_text.encode("utf-8"))),
    )
    artifacts = (GeneratedArtifact(path=Path("stage.tcl"), kind="tcl", content=generated_text, source_stage="stage"),)

    updated_report, updated_artifacts, rewritten = TclIndentationService().run(ctx, manifest, report, artifacts)

    assert sink.codes() == []
    # FULL_COPY ``.tcl`` is not in the rewritten path tuple.
    assert rewritten == (DOMAIN / "stage.tcl", DOMAIN / "trim.tcl")
    # FULL_COPY contents on disk are unchanged.
    assert fs.read_text(DOMAIN / "full.tcl") == full_text
    assert fs.read_text(DOMAIN / "trim.tcl") == "proc kept {} {\n    puts kept\n}\n"
    assert fs.read_text(DOMAIN / "stage.tcl") == (
        "# Chopper-generated stage: stage\nif {$ready} {\n    puts ready\n}\n"
    )
    assert fs.read_text(DOMAIN / "note.txt") == note_text

    outcomes = {outcome.path.as_posix(): outcome for outcome in updated_report.outcomes}
    # FULL_COPY bytes_out unchanged from the pre-P5c value.
    assert outcomes["full.tcl"].bytes_out == len(full_text.encode("utf-8"))
    assert outcomes["trim.tcl"].bytes_out == len(fs.read_text(DOMAIN / "trim.tcl").encode("utf-8"))
    assert outcomes["note.txt"].bytes_out == len(note_text.encode("utf-8"))
    assert updated_artifacts[0].content == fs.read_text(DOMAIN / "stage.tcl")


# -- Fixture-based tests (real-world patterns) --

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "edge_cases"


def test_format_tcl_indentation_fixture_backslash_continuation() -> None:
    """Real-world fixture: indentation handles backslash continuations,
    trailing whitespace, and blank lines inside proc bodies correctly."""
    fixture = FIXTURES_DIR / "indent_backslash_continuation.tcl"
    text = fixture.read_text(encoding="utf-8")
    result = format_tcl_indentation(text)

    # Idempotency: re-formatting produces identical output.
    assert format_tcl_indentation(result) == result

    # No trailing whitespace on any line.
    for i, line in enumerate(result.splitlines(), 1):
        assert line == line.rstrip(), f"Line {i} has trailing whitespace: {repr(line)}"

    # Blank lines are truly empty (no whitespace-only lines).
    for i, line in enumerate(result.splitlines(), 1):
        if not line.strip():
            assert line == "", f"Line {i} is whitespace-only: {repr(line)}"

    # Specific structural checks:
    lines = result.splitlines()

    # define_proc_attributes continuation: -info line gets +1 indent from proc body
    for i, line in enumerate(lines):
        if "define_proc_attributes read_libs \\" in line:
            # Inside proc body (indent=1), continuation is (1+1)*4 = 8 spaces
            assert lines[i + 1].startswith("        -info"), f"Continuation line not indented: {repr(lines[i + 1])}"
            break

    # Multi-continuation: all continuation args at same level
    for i, line in enumerate(lines):
        if "set long_command [some_proc \\" in line:
            assert lines[i + 1].startswith("    -arg1"), repr(lines[i + 1])
            assert lines[i + 2].startswith("    -arg2"), repr(lines[i + 2])
            assert lines[i + 3].startswith("    -arg3"), repr(lines[i + 3])
            break

    # Double-backslash is NOT treated as continuation
    for i, line in enumerate(lines):
        if 'set path "C:\\\\Windows\\\\System32\\\\"' in line:
            # Next line should be at indent 0, not +1
            assert lines[i + 1] == "puts $path", repr(lines[i + 1])
            break


def test_format_tcl_indentation_fixture_comment_braces() -> None:
    """Comments with braces must not affect indentation or brace counting.

    Real-world patterns extracted from ``fev_formality/default_fm_procs.tcl``:
    template banner comments containing ``{}{`` / ``#}``, commented-out
    ``define_proc_attributes`` blocks with backslash continuations, and
    inline ``;#`` comments. None of these may shift the running indent of
    the following statement.
    """
    fixture = FIXTURES_DIR / "indent_comment_braces.tcl"
    text = fixture.read_text(encoding="utf-8")
    result = format_tcl_indentation(text)

    # Idempotency
    assert format_tcl_indentation(result) == result

    lines = result.splitlines()
    # All statements inside ``proc example`` must remain at proc body
    # indent (4 spaces) — neither the unmatched braces in the template
    # banner nor the trailing ``\`` on the commented-out
    # ``define_proc_attributes`` line may push them deeper.
    body_statements = (
        'puts "after template comment"',
        'puts "after backslash comment"',
        'puts "after inline comment"',
    )
    for stmt in body_statements:
        match = [line for line in lines if line.endswith(stmt)]
        assert match, f"missing statement {stmt!r} in:\n{result}"
        assert match[0] == f"    {stmt}", repr(match[0])

    # Closing brace of the proc lands back at column 0.
    assert lines[-1] == "}"


def test_format_tcl_indentation_fixture_quoted_braces() -> None:
    """Braces inside double-quoted strings must be ignored by the brace counter.

    Real-world patterns extracted from ``fev_formality`` flows: ``iproc_msg``
    diagnostics whose message strings embed ``{`` characters, and
    ``set_vclp_setup_commands`` arguments where a braced word contains a
    quoted string with nested braces. The if-block at the end must still
    indent its body correctly after these strings.
    """
    fixture = FIXTURES_DIR / "indent_quoted_braces.tcl"
    text = fixture.read_text(encoding="utf-8")
    result = format_tcl_indentation(text)

    # Idempotency
    assert format_tcl_indentation(result) == result

    lines = result.splitlines()
    # The if-block body must reach 8 spaces (proc body + if body).
    if_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("if {$flag}"))
    assert lines[if_idx] == "    if {$flag} {", repr(lines[if_idx])
    assert lines[if_idx + 1] == "        puts nested", repr(lines[if_idx + 1])
    assert lines[if_idx + 2] == "    }", repr(lines[if_idx + 2])

    # Last `puts "done"` is still inside the proc body (4 spaces).
    assert '    puts "done"' in lines
    assert lines[-1] == "}"


# -- Targeted regression tests for comment- and quote-awareness --


def test_format_tcl_indentation_comment_with_unmatched_open_brace() -> None:
    """A ``#`` comment containing ``{`` must not push following lines deeper."""
    text = "proc foo {} {\n# bogus open brace {\nputs ok\n}\n"
    result = format_tcl_indentation(text)
    assert result == ("proc foo {} {\n    # bogus open brace {\n    puts ok\n}\n")


def test_format_tcl_indentation_comment_with_unmatched_close_brace() -> None:
    """A ``#}`` comment line must not outdent following lines."""
    text = "proc foo {} {\n#}\nputs ok\n}\n"
    result = format_tcl_indentation(text)
    assert result == ("proc foo {} {\n    #}\n    puts ok\n}\n")


def test_format_tcl_indentation_comment_continuation_not_propagated() -> None:
    """A comment line ending with ``\\`` must not make the next line a continuation."""
    text = "proc foo {} {\n# define_proc_attributes foo \\\nputs ok\n}\n"
    result = format_tcl_indentation(text)
    # Expected: ``puts ok`` at proc body indent (4 spaces), NOT 8 spaces.
    assert result == ("proc foo {} {\n    # define_proc_attributes foo \\\n    puts ok\n}\n")


def test_format_tcl_indentation_quoted_unmatched_brace() -> None:
    """Unmatched ``{`` inside a ``"..."`` string must not shift indent."""
    text = 'proc foo {} {\niproc_msg -info "Setting: {opened brace}"\nputs ok\n}\n'
    result = format_tcl_indentation(text)
    assert result == ('proc foo {} {\n    iproc_msg -info "Setting: {opened brace}"\n    puts ok\n}\n')


def test_format_tcl_indentation_escaped_quote_does_not_toggle_string_state() -> None:
    """Backslash-escaped ``\\"`` inside a string must not toggle the in-string flag."""
    text = 'proc foo {} {\nputs "outer \\"inner\\" still outer {ignored}"\nputs ok\n}\n'
    result = format_tcl_indentation(text)
    # The whole string stays one quoted span; the ``{ignored}`` braces are
    # inside the string and must not shift indent.
    assert result == ('proc foo {} {\n    puts "outer \\"inner\\" still outer {ignored}"\n    puts ok\n}\n')
