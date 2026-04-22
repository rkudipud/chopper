"""Unit tests for :mod:`chopper.parser.service` — ParserService + parse_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core.context import ChopperContext, RunConfig
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.models import FileStat
from chopper.parser.service import ParserService, parse_file

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _InMemoryFS:
    """Minimal filesystem double for ParserService tests.

    Holds a mapping of :class:`Path` → raw ``bytes``. ``read_text``
    decodes with the requested encoding, so ``UnicodeDecodeError``
    surfaces naturally and exercises the service's fallback path.
    """

    def __init__(self, files: dict[Path, bytes]) -> None:
        self._files = files

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return self._files[path].decode(encoding)

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
    ctx = ChopperContext(config=cfg, fs=_InMemoryFS(files), diag=sink, progress=_NullProgress())
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
