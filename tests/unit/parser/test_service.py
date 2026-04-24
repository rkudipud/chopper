"""Unit tests for :mod:`chopper.parser.service` — ParserService + parse_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import (
    FileStat,
)
from chopper.parser.service import ParserService, parse_file

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _InMemoryFS:
    """Minimal filesystem double for ParserService tests.

    Holds a mapping of :class:`Path` → raw ``bytes``. ``read_text``
    decodes with the requested encoding, so ``UnicodeDecodeError``
    surfaces naturally and exercises the service's fallback path.

    Tests key files by domain-relative path; :meth:`read_text` accepts
    either relative or absolute (``domain_root`` prefixed) paths so it
    mirrors the production adapters' tolerance after the parser's
    I/O-boundary absolutization fix.
    """

    def __init__(self, files: dict[Path, bytes], *, domain_root: Path | None = None) -> None:
        self._files = files
        self._domain_root = domain_root

    def _lookup(self, path: Path) -> bytes:
        if path in self._files:
            return self._files[path]
        if self._domain_root is not None:
            try:
                rel = path.relative_to(self._domain_root)
            except ValueError:
                raise KeyError(path) from None
            if rel in self._files:
                return self._files[rel]
        raise KeyError(path)

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return self._lookup(path).decode(encoding)

    # Unused by ParserService but required for protocol satisfaction.
    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None: ...  # pragma: no cover
    def exists(self, path: Path) -> bool:  # pragma: no cover
        return path in self._files

    def list(self, path: Path, *, pattern: str | None = None):  # pragma: no cover
        return ()

    def stat(self, path: Path) -> FileStat:  # pragma: no cover
        return FileStat(size=len(self._files[path]), mtime=0.0, is_dir=False)

    def rename(self, src: Path, dst: Path) -> None: ...  # pragma: no cover
    def remove(self, path: Path, *, recursive: bool = False) -> None: ...  # pragma: no cover
    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...  # pragma: no cover
    def copy_tree(self, src: Path, dst: Path) -> None: ...  # pragma: no cover


class _CollectingSink:
    """Accumulates emitted diagnostics in insertion order."""

    def __init__(self) -> None:
        self.emissions: list[Diagnostic] = []

    def emit(self, diagnostic: Diagnostic) -> None:
        self.emissions.append(diagnostic)

    def snapshot(self):
        return tuple(self.emissions)

    def finalize(self) -> DiagnosticSummary:  # pragma: no cover - not used in these tests
        return DiagnosticSummary(errors=0, warnings=0, infos=0)


class _NullProgress:
    def phase_started(self, phase: Phase) -> None: ...  # pragma: no cover
    def phase_done(self, phase: Phase) -> None: ...  # pragma: no cover
    def step(self, message: str) -> None: ...  # pragma: no cover


def _make_ctx(files: dict[Path, bytes], domain_root: Path = Path("dom")) -> tuple[ChopperContext, _CollectingSink]:
    sink = _CollectingSink()
    cfg = RunConfig(
        domain_root=domain_root,
        backup_root=domain_root.parent / f"{domain_root.name}_backup",
        audit_root=domain_root / ".chopper",
        strict=False,
        dry_run=False,
    )
    ctx = ChopperContext(
        config=cfg,
        fs=_InMemoryFS(files, domain_root=domain_root),
        diag=sink,
        progress=_NullProgress(),
    )
    return ctx, sink


# ---------------------------------------------------------------------------
# parse_file — pure utility
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_clean_no_procs(self) -> None:
        result = parse_file(Path("a.tcl"), "set x 1\n")
        assert result == []

    def test_clean_one_proc(self) -> None:
        result = parse_file(Path("a.tcl"), "proc foo {} { return 1 }\n")
        assert len(result) == 1
        assert result[0].short_name == "foo"
        assert result[0].canonical_name == "a.tcl::foo"

    def test_forwards_extractor_diagnostics(self) -> None:
        emitted: list[Diagnostic] = []
        result = parse_file(
            Path("a.tcl"),
            "proc ${prefix}_foo {} {}\n",
            on_diagnostic=emitted.append,
        )
        assert result == []
        assert len(emitted) == 1
        assert emitted[0].code == "PW-01"
        assert emitted[0].path == Path("a.tcl")

    def test_translates_multiple_diagnostic_kinds(self) -> None:
        emitted: list[Diagnostic] = []
        # Duplicate proc → PE-01; DPA name mismatch → PW-11; the
        # unattached DPA line is then reported as an orphan → PI-04.
        src = 'proc dup {} {}\nproc dup {} {}\ndefine_proc_attributes nothing -info "x"\n'
        parse_file(Path("a.tcl"), src, on_diagnostic=emitted.append)
        codes = {d.code for d in emitted}
        assert codes == {"PE-01", "PW-11", "PI-04"}

    def test_tokenizer_error_emits_pe02_and_returns_empty(self) -> None:
        emitted: list[Diagnostic] = []
        # Unclosed brace — tokenizer reports unclosed_braces.
        result = parse_file(Path("a.tcl"), "proc foo {} {\n", on_diagnostic=emitted.append)
        assert result == []
        assert len(emitted) == 1
        assert emitted[0].code == "PE-02"
        assert emitted[0].severity.value == "error"

    def test_negative_depth_emits_pe02(self) -> None:
        emitted: list[Diagnostic] = []
        result = parse_file(Path("a.tcl"), "} extra\n", on_diagnostic=emitted.append)
        assert result == []
        assert emitted[0].code == "PE-02"

    def test_on_diagnostic_none_silent(self) -> None:
        # No callback → errors are silently discarded.
        result = parse_file(Path("a.tcl"), "proc ${x} {} {}\n")
        assert result == []

    def test_pe02_emits_at_first_error_line(self) -> None:
        emitted: list[Diagnostic] = []
        src = "set x 1\nproc foo {} {\nbody line\n"  # unclosed at EOF
        parse_file(Path("a.tcl"), src, on_diagnostic=emitted.append)
        # unclosed_braces is reported at the final line (EOF line).
        assert emitted[0].code == "PE-02"
        assert emitted[0].line_no is not None


# ---------------------------------------------------------------------------
# ParserService.run — I/O + orchestration
# ---------------------------------------------------------------------------


class TestParserServiceBasic:
    def test_single_file(self) -> None:
        path = Path("utils.tcl")
        ctx, sink = _make_ctx({path: b"proc helper {} { return 1 }\n"})
        result = ParserService().run(ctx, [path])
        assert path in result.files
        assert len(result.files[path].procs) == 1
        assert "utils.tcl::helper" in result.index
        assert sink.emissions == []

    def test_multiple_files(self) -> None:
        a, b = Path("a.tcl"), Path("b.tcl")
        ctx, _ = _make_ctx(
            {
                a: b"proc p_a {} {}\n",
                b: b"proc p_b {} {}\n",
            }
        )
        result = ParserService().run(ctx, [a, b])
        assert set(result.files.keys()) == {a, b}
        assert set(result.index.keys()) == {"a.tcl::p_a", "b.tcl::p_b"}

    def test_empty_file_list(self) -> None:
        ctx, _ = _make_ctx({})
        result = ParserService().run(ctx, [])
        assert result.files == {}
        assert result.index == {}

    def test_service_is_stateless(self) -> None:
        # Two independent runs do not bleed state.
        a = Path("a.tcl")
        ctx1, _ = _make_ctx({a: b"proc p1 {} {}\n"})
        ctx2, _ = _make_ctx({a: b"proc p2 {} {}\n"})
        svc = ParserService()
        r1 = svc.run(ctx1, [a])
        r2 = svc.run(ctx2, [a])
        assert "a.tcl::p1" in r1.index
        assert "a.tcl::p2" in r2.index
        assert "a.tcl::p1" not in r2.index


class TestDeterminism:
    def test_files_dict_is_lex_sorted(self) -> None:
        # Inputs in reverse order still produce a lex-sorted files dict.
        files = {Path(f"{n}.tcl"): b"" for n in ("c", "a", "b")}
        ctx, _ = _make_ctx(files)
        result = ParserService().run(ctx, [Path("c.tcl"), Path("a.tcl"), Path("b.tcl")])
        assert list(result.files.keys()) == [Path("a.tcl"), Path("b.tcl"), Path("c.tcl")]

    def test_index_keys_lex_sorted(self) -> None:
        files = {
            Path("z.tcl"): b"proc z_helper {} {}\n",
            Path("a.tcl"): b"proc a_helper {} {}\n",
        }
        ctx, _ = _make_ctx(files)
        result = ParserService().run(ctx, list(files.keys()))
        assert list(result.index.keys()) == sorted(result.index.keys())

    def test_duplicate_input_paths_deduplicated(self) -> None:
        # Same path appearing twice in the input list should not cause a
        # double-parse or a duplicate key collision.
        a = Path("a.tcl")
        ctx, _ = _make_ctx({a: b"proc foo {} {}\n"})
        result = ParserService().run(ctx, [a, a])
        assert len(result.files) == 1


class TestEncoding:
    def test_utf8_success(self) -> None:
        # UTF-8 BOM plus ASCII content decodes fine.
        a = Path("a.tcl")
        ctx, sink = _make_ctx({a: b"proc helper {} { return 1 }\n"})
        result = ParserService().run(ctx, [a])
        assert result.files[a].encoding == "utf-8"
        assert sink.emissions == []

    def test_latin1_fallback_emits_pw02(self) -> None:
        # Bytes that are NOT valid UTF-8 but ARE valid Latin-1.
        # 0xFF is an invalid UTF-8 start byte; Latin-1 reads it as ÿ.
        a = Path("a.tcl")
        content = b"proc helper {} { return \xff }\n"
        ctx, sink = _make_ctx({a: content})
        result = ParserService().run(ctx, [a])
        assert result.files[a].encoding == "latin-1"
        codes = [d.code for d in sink.emissions]
        assert "PW-02" in codes
        # The PW-02 diagnostic carries the file path.
        pw02 = next(d for d in sink.emissions if d.code == "PW-02")
        assert pw02.path == a

    def test_latin1_content_parsed(self) -> None:
        # Ensure we actually get a ProcEntry when falling back to Latin-1.
        a = Path("a.tcl")
        content = b"proc helper {} { set x \xff }\n"
        ctx, _ = _make_ctx({a: content})
        result = ParserService().run(ctx, [a])
        assert "a.tcl::helper" in result.index


class TestPathNormalization:
    def test_absolute_path_made_relative(self) -> None:
        # The service normalizes the absolute input to a domain-relative
        # path before reading through ``ctx.fs``; the fixture must key
        # the file under that same relative form.
        domain = Path("/tmp/dom").resolve()
        file_abs = domain / "sub" / "a.tcl"
        rel = Path("sub/a.tcl")
        ctx, _ = _make_ctx({rel: b"proc foo {} {}\n"}, domain_root=domain)
        result = ParserService().run(ctx, [file_abs])
        # The canonical name uses the domain-relative POSIX form.
        assert "sub/a.tcl::foo" in result.index

    def test_relative_path_preserved(self) -> None:
        a = Path("procs/core.tcl")
        ctx, _ = _make_ctx({a: b"proc setup {} {}\n"})
        result = ParserService().run(ctx, [a])
        assert "procs/core.tcl::setup" in result.index

    def test_absolute_outside_domain_kept_asis(self) -> None:
        # An absolute path outside domain_root is handed through unchanged;
        # the parser does not gate these (the compiler/config layer emits
        # VE-06 for this condition). We just verify no exception occurs.
        domain = Path("/tmp/dom").resolve()
        outside = Path("/elsewhere/a.tcl")
        ctx, _ = _make_ctx({outside: b"proc foo {} {}\n"}, domain_root=domain)
        result = ParserService().run(ctx, [outside])
        # ProcEntry built; canonical name uses the original absolute POSIX form.
        assert any(cn.endswith("::foo") for cn in result.index.keys())


# ---------------------------------------------------------------------------
# Non-Tcl companion files — regression guards for GitHub issue #2.
#
# The bible (OOS-01 in ``technical_docs/chopper_description.md`` §1.3)
# states that non-Tcl files (``.py`` / ``.pl`` / ``.csh`` / config)
# participate in F1 file-level treatment only and must never enter the
# Tcl tokenizer. Before the fix, a ``.py`` file containing a stray
# ``}`` inside a Python string literal (e.g. ``value.replace("}", …)``)
# was fed to the tokenizer, produced a ``negative_depth`` error, and
# the service translated that into a spurious
# ``PE-02 unbalanced-braces`` that aborted P2.
# ---------------------------------------------------------------------------


class TestNonTclSkip:
    # Bytes verbatim from tests/fixtures/edge_cases/non_tcl_python_stray_braces.py.
    # A ``}`` appears at brace_depth 0 inside a raw-string regex, which is
    # exactly what drives the Tcl tokenizer to negative_depth. Kept inline
    # so the assertion remains readable even without the fixture on disk.
    _PYTHON_CONTENT_THAT_EXPLODES_TCL_TOKENIZER = (
        b"import re\n"
        b'HIER_PATTERN = re.compile(r"hier\\{([^}]+)\\}")\n'
        b"def splice(value):\n"
        b'    return value.replace("}", "}\\n")\n'
    )

    def test_python_file_not_parsed(self) -> None:
        # The ``.py`` file contents would trigger PE-02 under the Tcl
        # tokenizer; the parser must skip it silently.
        py = Path("generate_summary_html.py")
        ctx, sink = _make_ctx({py: self._PYTHON_CONTENT_THAT_EXPLODES_TCL_TOKENIZER})
        result = ParserService().run(ctx, [py])
        assert py not in result.files
        assert result.index == {}
        codes = [d.code for d in sink.emissions]
        assert "PE-02" not in codes, codes
        assert sink.emissions == []

    def test_mixed_tcl_and_non_tcl(self) -> None:
        # A ``.tcl`` sibling is parsed normally; the ``.py`` is silently
        # skipped and the presence of the ``.py`` in the input list must
        # not affect the Tcl result or emit any diagnostic.
        tcl = Path("procs/core.tcl")
        py = Path("scripts/generate_summary_html.py")
        ctx, sink = _make_ctx(
            {
                tcl: b"proc run_setup {} { return 1 }\n",
                py: self._PYTHON_CONTENT_THAT_EXPLODES_TCL_TOKENIZER,
            }
        )
        result = ParserService().run(ctx, [tcl, py])
        assert set(result.files.keys()) == {tcl}
        assert "procs/core.tcl::run_setup" in result.index
        assert sink.emissions == []

    @pytest.mark.parametrize(
        "path",
        [
            Path("script.pl"),  # Perl
            Path("script.py"),  # Python
            Path("wrapper.csh"),  # C-shell
            Path("wrapper.sh"),  # Bourne shell
            Path("config.cfg"),  # Config file
            Path("data.txt"),  # Plain text
            Path("notes.md"),  # Markdown
            Path("sta_pt.stack"),  # Scheduler stack file
            Path("Makefile"),  # No suffix
        ],
    )
    def test_various_non_tcl_suffixes_skipped(self, path: Path) -> None:
        # Any non-.tcl suffix — including no suffix at all — is skipped
        # without attempting a read (the fixture deliberately contains
        # bytes that would be invalid as Tcl).
        ctx, sink = _make_ctx({path: b"} this would be negative_depth in tcl {\n"})
        result = ParserService().run(ctx, [path])
        assert path not in result.files
        assert sink.emissions == []

    def test_tcl_suffix_case_insensitive(self) -> None:
        # Authored variants like ``.TCL`` / ``.Tcl`` must still be
        # parsed; the suffix check is case-insensitive.
        upper = Path("Legacy.TCL")
        mixed = Path("Tool.Tcl")
        ctx, _ = _make_ctx(
            {
                upper: b"proc upper_proc {} {}\n",
                mixed: b"proc mixed_proc {} {}\n",
            }
        )
        result = ParserService().run(ctx, [upper, mixed])
        assert upper in result.files
        assert mixed in result.files
        assert {"Legacy.TCL::upper_proc", "Tool.Tcl::mixed_proc"} <= set(result.index)

    def test_non_tcl_file_is_never_read(self) -> None:
        # Even a pathological non-Tcl file whose *absence* from the
        # in-memory FS would raise ``KeyError`` on read must not cause
        # an error, because the filter skips it before the read.
        py = Path("missing.py")
        # Note: the file is NOT seeded into _InMemoryFS. A read attempt
        # would raise KeyError.
        ctx, sink = _make_ctx({})
        result = ParserService().run(ctx, [py])
        assert result.files == {}
        assert sink.emissions == []


# ---------------------------------------------------------------------------
# Real-world scenario tests — pathologies observed in production Synopsys
# Formality Tcl: CRLF line endings, ``define_proc_attributes`` blocks joined
# by backslash continuation, proc bodies opened at column 0, single-line
# banner comments.  Snippets are copied verbatim from real scripts.
# ---------------------------------------------------------------------------

# ``define_proc_attributes`` backslash-continuation block, CRLF line endings.
# Before the parser fixed its ``text.split('\\n')`` bug, ``\\r`` leaked into
# the continuation detector and the DPA block was misread as orphan + name
# mismatch (PI-04 + PW-11 fired spuriously).  This is the regression guard.
_REAL_DPA_CRLF = (
    b"proc match_nd_to_1d {args} {\r\n"
    b"  # body\r\n"
    b"}\r\n"
    b"\r\n"
    b"define_proc_attributes match_nd_to_1d \\\r\n"
    b' -info "Create user matches for reference ND ports/bbox_pins" \\\r\n'
    b" -define_args {\\\r\n"
    b'  {-type "Types to match" type list optional}\r\n'
    b" }\r\n"
)

# Column-0 proc body + banner comment, copied verbatim from the real
# ``dangle_dont_verify_par`` proc in the production flow.  The body is NOT
# indented — parser must still identify boundaries by brace balance alone.
_REAL_COLUMN_ZERO_BODY = (
    b"# Added for 3rd round of DMR 1p0\r\n"
    b"proc dangle_dont_verify_par {infile outfile} {\r\n"
    b"# Define the flexible pattern to search for\r\n"
    b"set pattern {# .*/([^/]+) is dangling feedthrough port\\.}\r\n"
    b"\r\n"
    b"# Open the input file for reading\r\n"
    b"set input_fileId [open $infile r]\r\n"
    b"\r\n"
    b"# Read the input file line by line\r\n"
    b"while {[gets $input_fileId line] != -1} {\r\n"
    b"    puts $output_fileId $line\r\n"
    b"}\r\n"
    b"\r\n"
    b"close $input_fileId\r\n"
    b"}\r\n"
)


class TestRealWorldScenarios:
    """Pathologies lifted verbatim from production Synopsys Formality Tcl."""

    def test_dpa_with_crlf_and_backslash_continuation(self) -> None:
        """CRLF + ``\\``-continued ``define_proc_attributes`` must attach silently.

        Regression guard: ``proc_extractor`` used to split on ``\\n`` without
        stripping trailing ``\\r`` on Windows line endings, so the
        continuation detector never recognised the block and spuriously
        emitted ``PI-04`` (orphan DPA) + ``PW-11`` (DPA name mismatch).
        """
        a = Path("procs.tcl")
        ctx, sink = _make_ctx({a: _REAL_DPA_CRLF})
        result = ParserService().run(ctx, [a])
        codes = sorted({d.code for d in sink.emissions})
        assert codes == [], f"CRLF + DPA continuation regressed: {codes}"
        proc = next(iter(result.index.values()))
        assert proc.short_name == "match_nd_to_1d"
        # DPA range must cover lines 5–8 of the CRLF source (1-indexed).
        assert proc.dpa_start_line == 5
        assert proc.dpa_end_line == 8

    def test_column_zero_proc_body_parses_as_single_proc(self) -> None:
        """Unindented proc body — brace balance alone must bound the proc.

        Real script ``dangle_dont_verify_par`` opens its body at column 0
        with blank lines sprinkled through.  Parser must still return
        exactly one proc with a well-ordered body span.
        """
        a = Path("dangle.tcl")
        ctx, sink = _make_ctx({a: _REAL_COLUMN_ZERO_BODY})
        result = ParserService().run(ctx, [a])
        assert [d.code for d in sink.emissions] == []
        procs = list(result.index.values())
        assert len(procs) == 1
        proc = procs[0]
        assert proc.short_name == "dangle_dont_verify_par"
        # Banner comment on the line immediately preceding ``proc``.
        assert proc.comment_start_line == 1
        assert proc.comment_end_line == 1
        # Well-ordered span invariant holds for column-0 bodies too.
        assert proc.start_line <= proc.body_start_line
        assert proc.body_start_line <= proc.body_end_line
        assert proc.body_end_line <= proc.end_line


# ``swap_to_current_instance`` — verbatim from the production Formality
# flow.  Pathological traits:
#   * body indented with leading tabs AND leading spaces (mixed whitespace);
#   * deeply nested if/elseif/else chain with inline ``regexp`` bodies that
#     themselves contain ``{ ... }`` groupings the tokenizer must treat as
#     literal brace pairs, not body terminators;
#   * trailing ``close $outputFile`` on the last line before the outer ``}``.
_REAL_SWAP_PROC = (
    "proc swap_to_current_instance {infile outfile} {\n"
    "\t# Open the input file for reading\n"
    "\tset inputFile [open $infile r]\n"
    "\tset fileData [read $inputFile]\n"
    "\tclose $inputFile\n"
    "\t\n"
    '\tset lines [split $fileData "\\n"]\n'
    "\tset modifiedLines {}\n"
    "\tset previousLineWasContainerR 0\n"
    "\tset previousLineWasDesignRef 0\n"
    "\t\n"
    "\tforeach line $lines {\n"
    "\t    if {$previousLineWasContainerR && $previousLineWasDesignRef && [regexp {\\sset\\s} $line]} {\n"
    '\t        lappend modifiedLines "current_instance \\$ref_instance_query"\n'
    "\t        lappend modifiedLines $line\n"
    "\t        set previousLineWasContainerR 0\n"
    "\t        set previousLineWasDesignRef 0\n"
    "\t    } elseif {$previousLineWasContainerR && [regexp {current_design \\$ref} $line]} {\n"
    "\t        set previousLineWasDesignRef 1\n"
    "\t    } elseif {[regexp {current_container r} $line]} {\n"
    "\t        set previousLineWasContainerR 1\n"
    "\t    } else {\n"
    "\t        lappend modifiedLines $line\n"
    "\t    }\n"
    "\t}\n"
    "\t\n"
    '\tset modifiedData [join $modifiedLines "\\n"]\n'
    "\tset outputFile [open $outfile w]\n"
    "\tputs $outputFile $modifiedData\n"
    "\tclose $outputFile\n"
    "}\n"
)


# ``handle_change_direction`` — verbatim from the production Formality
# flow.  Pathological traits:
#   * body opens at column 0 (no indentation at all);
#   * ``puts $outputFile "current_instance \\$impl..."`` lines contain
#     *string literals* that look like Tcl code — the parser must NOT
#     misread them as embedded procs or extra brace opens;
#   * embedded literal ``{`` inside a ``puts`` argument string.
_REAL_HANDLE_CHANGE_DIRECTION = (
    "proc handle_change_direction {infile outfile} {\n"
    "set inputFile [open $infile r]\n"
    "set outputFile [open $outfile w]\n"
    "\n"
    'set previousLine ""\n'
    "while {[gets $inputFile line] != -1} {\n"
    "    if {[regexp {set_direction (\\S+) in} $previousLine match1 port_name1]} {\n"
    "        if {[regexp {set_dont_verify_points (\\S+)} $line match2 port_name2] && $port_name1 eq $port_name2} {\n"
    '            puts $outputFile "current_instance \\$impl_instance_query"\n'
    '            puts $outputFile " set rp \\[get_ports -quiet $port_name1\\]"\n'
    '            puts $outputFile " if { \\[sizeof_collection \\$rp\\] ==0 } {"\n'
    '            puts $outputFile " set rp \\[get_pins -quiet $port_name1\\]"\n'
    '            puts $outputFile " }"\n'
    '            set previousLine ""\n'
    "            continue\n"
    "        }\n"
    "    }\n"
    '    if {$previousLine ne ""} {\n'
    "        puts $outputFile $previousLine\n"
    "    }\n"
    "    set previousLine $line\n"
    "}\n"
    "\n"
    "close $inputFile\n"
    "close $outputFile\n"
    "}\n"
)


class TestRealWorldMessyFormatting:
    """Pathological indentation + embedded-code-as-string from production procs."""

    def test_mixed_tab_space_indented_body_with_nested_regexp_braces(self) -> None:
        """``swap_to_current_instance``: tab-indented body with nested
        ``regexp { ... }`` literal brace groups must not confuse the
        body-brace counter.  One proc out, well-ordered span.
        """
        a = Path("swap.tcl")
        ctx, sink = _make_ctx({a: _REAL_SWAP_PROC.encode("utf-8")})
        result = ParserService().run(ctx, [a])
        assert [d.code for d in sink.emissions] == []
        procs = list(result.index.values())
        assert len(procs) == 1
        assert procs[0].short_name == "swap_to_current_instance"
        assert procs[0].start_line == 1
        # Closing ``}`` is the last line of the snippet.
        assert procs[0].end_line == _REAL_SWAP_PROC.count("\n")

    def test_column_zero_body_with_tcl_code_inside_puts_strings(self) -> None:
        """``handle_change_direction``: column-0 body where ``puts``
        emits *strings* containing literal ``current_instance``,
        ``set rp``, ``if { ... }``.  These are string payloads, not
        nested procs — parser must see exactly one proc.
        """
        a = Path("handle.tcl")
        ctx, sink = _make_ctx({a: _REAL_HANDLE_CHANGE_DIRECTION.encode("utf-8")})
        result = ParserService().run(ctx, [a])
        assert [d.code for d in sink.emissions] == []
        procs = list(result.index.values())
        assert len(procs) == 1, (
            f"puts-with-tcl-looking-string misread as multiple procs: {[p.short_name for p in procs]}"
        )
        assert procs[0].short_name == "handle_change_direction"

    def test_absolute_outside_domain_kept_asis(self) -> None:
        # An absolute path outside domain_root is handed through unchanged;
        # the parser does not gate these (the compiler/config layer emits
        # VE-06 for this condition). We just verify no exception occurs.
        domain = Path("/tmp/dom").resolve()
        outside = Path("/elsewhere/a.tcl")
        ctx, _ = _make_ctx({outside: b"proc foo {} {}\n"}, domain_root=domain)
        result = ParserService().run(ctx, [outside])
        # ProcEntry built; canonical name uses the original absolute POSIX form.
        assert any(cn.endswith("::foo") for cn in result.index.keys())


class TestDiagnosticForwarding:
    def test_pe01_forwarded(self) -> None:
        a = Path("a.tcl")
        ctx, sink = _make_ctx({a: b"proc dup {} {}\nproc dup {} {}\n"})
        ParserService().run(ctx, [a])
        codes = [d.code for d in sink.emissions]
        assert "PE-01" in codes

    def test_pw04_forwarded(self) -> None:
        a = Path("a.tcl")
        ctx, sink = _make_ctx({a: b"namespace eval $var {\n    proc foo {} {}\n}\n"})
        ParserService().run(ctx, [a])
        codes = [d.code for d in sink.emissions]
        assert "PW-04" in codes

    def test_pe02_on_unbalanced_braces(self) -> None:
        a = Path("a.tcl")
        ctx, sink = _make_ctx({a: b"proc foo {} { unclosed\n"})
        result = ParserService().run(ctx, [a])
        codes = [d.code for d in sink.emissions]
        assert "PE-02" in codes
        # File still appears in the result with zero procs.
        assert result.files[a].procs == ()

    def test_all_diagnostics_carry_file_path(self) -> None:
        a = Path("a.tcl")
        ctx, sink = _make_ctx({a: b'proc dup {} {}\nproc dup {} {}\ndefine_proc_attributes nothing -info "x"\n'})
        ParserService().run(ctx, [a])
        for d in sink.emissions:
            assert d.path == a


class TestPublicShape:
    def test_service_is_frozen_dataclass(self) -> None:
        # Frozen: trying to mutate raises.
        from dataclasses import FrozenInstanceError

        svc = ParserService()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            svc.some_field = 1  # type: ignore[attr-defined]

    def test_parse_file_exported(self) -> None:
        from chopper.parser.service import __all__

        assert "parse_file" in __all__
        assert "ParserService" in __all__
        assert "DiagnosticCollector" in __all__


# ------------------------------------------------------------------
# Extracted from test_final_coverage_push.py (module-aligned consolidation).
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Extracted from test_small_modules_torture.py (module-aligned consolidation).
# ------------------------------------------------------------------
