"""Per-file coverage tests for src/chopper/parser/service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.adapters.fs_memory import InMemoryFS
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_parser_message_for_non_brace_body() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="non-brace-body", line_no=3, detail="myproc")
    assert "non-brace body" in _message_for(d)


def test_parser_message_for_dpa_name_mismatch() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="dpa-name-mismatch", line_no=10, detail="dpa says X but proc Y")
    assert _message_for(d) == "dpa says X but proc Y"


def test_parser_normalize_absolute_path_outside_domain_returned_as_is() -> None:
    from chopper.parser.service import ParserService

    ctx = _ctx()
    raw = Path("/elsewhere/outside.tcl")
    out = ParserService._normalize(ctx, raw)
    # Absolute path lying outside domain_root is returned unchanged.
    assert out == raw


def test_parser_enumerate_skips_chopper_dir_and_handles_list_oserror() -> None:
    from chopper.parser.service import ParserService

    class _BadList(InMemoryFS):
        def __init__(self, files: dict[Path, str], failing_dir: Path) -> None:
            super().__init__(files)
            self._fail = failing_dir

        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == self._fail:
                raise OSError("permission denied")
            return super().list(path, pattern=pattern)

    fs = _BadList(
        {
            DOMAIN / "ok.tcl": "proc a {} {}\n",
            DOMAIN / ".chopper" / "log": "x",
            DOMAIN / "bad" / "x.tcl": "proc b {} {}\n",
        },
        failing_dir=DOMAIN / "bad",
    )
    ctx = _ctx(fs=fs)
    out = ParserService()._enumerate_domain_tcl(ctx)
    rel = {p.as_posix() for p in out}
    assert "ok.tcl" in rel
    # bad/ failed to list, .chopper excluded.
    assert "bad/x.tcl" not in rel
    assert ".chopper/log" not in rel


def test_parser_enumerate_skips_files_with_bad_stat() -> None:
    from chopper.parser.service import ParserService

    class _StatFail(InMemoryFS):
        def __init__(self, files: dict[Path, str], failing_path: Path) -> None:
            super().__init__(files)
            self._fail = failing_path

        def stat(self, path: Path):  # type: ignore[override]
            if path == self._fail:
                raise OSError("denied")
            return super().stat(path)

    fs = _StatFail({DOMAIN / "ok.tcl": "x", DOMAIN / "bad.tcl": "y"}, failing_path=DOMAIN / "bad.tcl")
    ctx = _ctx(fs=fs)
    out = {p.as_posix() for p in ParserService()._enumerate_domain_tcl(ctx)}
    assert "ok.tcl" in out
    assert "bad.tcl" not in out


def test_parser_message_for_dpa_orphan() -> None:
    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    d = ExtractorDiagnostic(kind="dpa-orphan", line_no=8, detail="myattrs")
    assert "no preceding proc" in _message_for(d).lower()


def test_parser_normalize_windows_absolute_outside_domain_returned_as_is() -> None:
    from chopper.parser.service import ParserService

    ctx = _ctx()
    raw = Path("C:/elsewhere/x.tcl")
    out = ParserService._normalize(ctx, raw)
    # Absolute path outside domain_root → returned unchanged.
    assert out.as_posix() == raw.as_posix()


def test_parser_run_skips_files_that_vanish_during_full_domain_walk() -> None:
    from chopper.parser.service import ParserService

    class _DisappearingFS(InMemoryFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            if path.name == "ghost.tcl":
                raise OSError("file vanished")
            return super().read_text(path, encoding=encoding)

    fs = _DisappearingFS()
    fs.write_text(DOMAIN / "ok.tcl", "proc a {} {}\n")
    fs.write_text(DOMAIN / "ghost.tcl", "proc b {} {}\n")
    ctx = _ctx(fs=fs)
    # Surface set is just ok.tcl; ghost.tcl is enumerated as non-surface
    # full-domain harvest, where read_text() failures are swallowed.
    result = ParserService().run(ctx, [DOMAIN / "ok.tcl"])
    # ok.tcl parsed; ghost.tcl absent from index because read failed.
    assert any("ok.tcl" in cn for cn in result.index)
    assert not any("ghost.tcl" in cn for cn in result.index)


def test_parser_message_for_raises_assertion_on_unmapped_kind() -> None:
    """Building an ExtractorDiagnostic with an unrecognised ``kind``
    string bypasses the Literal hint at runtime and reaches the
    AssertionError safety net inside ``_message_for``."""
    from typing import cast

    from chopper.parser.proc_extractor import ExtractorDiagnostic
    from chopper.parser.service import _message_for

    bogus = ExtractorDiagnostic(kind=cast("object", "totally-bogus"), line_no=1, detail="x")  # type: ignore[arg-type]
    with pytest.raises(AssertionError, match="unmapped"):
        _message_for(bogus)


def test_parser_full_domain_walk_skips_paths_outside_source_root() -> None:
    """If FS.list yields a path that is not relative to source_root
    (an unusual injected value), ``relative_to`` raises ValueError and
    the BFS skips that entry instead of crashing."""
    from chopper.parser.service import ParserService

    class _LeakyFS(InMemoryFS):
        _leaked = False

        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            children = list(super().list(path, pattern=pattern))
            if not _LeakyFS._leaked and path == DOMAIN:
                _LeakyFS._leaked = True
                # Inject a path that is not under source_root → ValueError
                # in relative_to().
                children.append(Path("/elsewhere/leaked.tcl"))
            return tuple(children)

    fs = _LeakyFS()
    fs.write_text(DOMAIN / "ok.tcl", "proc a {} {}\n")
    ctx = _ctx(fs=fs)
    result = ParserService().run(ctx, [DOMAIN / "ok.tcl"])
    # ok.tcl indexed; leaked path silently skipped.
    assert any("ok.tcl" in cn for cn in result.index)


def test_parse_file_unbalanced_braces_no_diagnostic_callback() -> None:
    """parse_file returns [] with on_diagnostic=None when tokenizer has errors (branch 132->143)."""
    from chopper.parser.service import parse_file

    # Unbalanced braces → tokenizer error → branch 132->143 (no emit)
    result = parse_file(Path("bad.tcl"), "proc foo { {", on_diagnostic=None)
    assert result == []
