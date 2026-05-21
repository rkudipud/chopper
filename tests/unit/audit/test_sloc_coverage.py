"""Per-file coverage tests for src/chopper/audit/sloc.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_sloc_csv_branch_counts_only_data_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from chopper.audit.sloc import count_sloc

    # Targets the pure-Python CSV branch; cloc's CSV profile counts the
    # ``,,`` row as code, so force the fallback for deterministic coverage.
    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    text = "a,b,c\n,,\n1,2,3\n"
    n = count_sloc(Path("data.csv"), text)
    assert n == 2  # header + one data row; the empty-comma row is skipped


def test_sloc_json_path_uses_count_raw() -> None:
    from chopper.audit.sloc import count_sloc

    text = '{\n  "a": 1\n}\n'
    n = count_sloc(Path("config.json"), text)
    assert n == 3


def test_sloc_unknown_extension_falls_back_to_count_raw() -> None:
    from chopper.audit.sloc import count_sloc

    n = count_sloc(Path("readme.md"), "# title\n\nbody\n")
    assert n == 2


def test_sloc_shell_shebang_counts_as_sloc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per ARCHITECTURE.md §5.10, a shebang line (``#!``) on line 1 of a
    shell/Python/Perl file counts as a logical source line because it is
    executable interpreter directive, not a comment."""
    from chopper.audit.sloc import count_sloc

    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    text = "#!/usr/bin/env tclsh\nproc foo {} {}\n# a comment\n"
    n = count_sloc(Path("run.sh"), text)
    # shebang + proc → 2 SLOC; comment skipped.
    assert n == 2


def test_sloc_shell_hash_not_shebang_is_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A regular ``#`` comment on line 1 of a shell file is NOT shebang
    and must not count as SLOC."""
    from chopper.audit.sloc import count_sloc

    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    text = "# just a comment on line 1\nproc foo {} {}\n"
    n = count_sloc(Path("run.sh"), text)
    assert n == 1  # only proc line


def test_sloc_csv_skips_comma_only_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per ARCHITECTURE.md §5.10, CSV rows that contain only commas/whitespace
    are blank equivalents and must not count as SLOC."""
    from chopper.audit.sloc import count_sloc

    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    text = "col1,col2,col3\n,,,\n1,2,3\n"
    n = count_sloc(Path("data.csv"), text)
    assert n == 2  # header + data row; empty-comma row excluded


def test_sloc_many_batch_path_uses_python_fallback_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When CHOPPER_SLOC_BACKEND=python, count_sloc_many must use the
    pure-Python fallback for every item, bypassing the cloc subprocess
    entirely (ARCHITECTURE.md §5.10 override mechanism)."""
    from chopper.audit.sloc import count_sloc_many

    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    items = [
        (Path("a.tcl"), "proc x {} {}\n# comment\n"),
        (Path("b.tcl"), "proc y {} {}\nproc z {} {}\n"),
    ]
    result = count_sloc_many(items)
    assert len(result) == 2
    assert result[0] == 1  # proc only
    assert result[1] == 2  # two procs


def test_sloc_many_empty_list_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_many([]) → [] always, regardless of backend."""
    from chopper.audit.sloc import count_sloc_many

    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    assert count_sloc_many([]) == []


def test_sloc_many_cloc_batch_falls_back_per_slot_when_cloc_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When cloc is unavailable, count_sloc_many must fall back per-slot
    to the pure-Python counter and return the same length as the input."""
    from chopper.audit import cloc_backend
    from chopper.audit import sloc as sloc_mod

    # Do not set CHOPPER_SLOC_BACKEND=python, so batch path is tried.
    monkeypatch.delenv("CHOPPER_SLOC_BACKEND", raising=False)
    cloc_backend.is_available.cache_clear()
    # Simulate cloc unavailable: batch returns [None, None]
    monkeypatch.setattr(cloc_backend, "count_sloc_via_cloc_batch", lambda items: [None] * len(items))
    items = [(Path("a.tcl"), "proc x {} {}\n"), (Path("b.tcl"), "# comment\nproc y {} {}\n")]
    result = sloc_mod.count_sloc_many(items)
    # Falls back to pure-Python per-slot.
    assert len(result) == 2
    assert result[0] == 1
    assert result[1] == 1
    cloc_backend.is_available.cache_clear()


def test_sloc_json_extension_counts_nonblank_lines() -> None:
    """JSON extension: every non-blank line counts (count_raw fallback path)."""
    from chopper.audit.sloc import count_sloc

    text = '{"key": "value"}\n\n{"other": 1}\n'
    result = count_sloc(Path("data.json"), text)
    assert result == 2  # 2 non-blank lines


def test_sloc_shell_shebang_on_line1_counts() -> None:
    """Shell shebang on line 1 must count as SLOC (is_shell branch in _count_hash_comment)."""
    from chopper.audit.sloc import count_sloc

    text = "#!/usr/bin/env tcsh\necho hello\n# a comment\n"
    result = count_sloc(Path("run.csh"), text)
    # shebang (#! on line 1 counts) + echo = 2; comment excluded
    assert result == 2


def test_sloc_python_backend_json_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """_count_sloc_python hits _NO_COMMENT_EXTENSIONS branch for .json (line 145)."""
    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    from chopper.audit import sloc as _sloc_mod

    result = _sloc_mod._count_sloc_python(Path("data.json"), '{"a":1}\n\n{"b":2}\n')
    assert result == 2  # 2 non-blank lines; blank line in middle doesn't count


def test_sloc_hash_comment_blank_line_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """_count_hash_comment: blank line triggers the `continue` branch (line 160)."""
    monkeypatch.setenv("CHOPPER_SLOC_BACKEND", "python")
    from chopper.audit import sloc as _sloc_mod

    # Tcl file with a blank line between two code lines
    result = _sloc_mod._count_hash_comment("proc foo {} {}\n\nproc bar {} {}\n", is_shell=False)
    assert result == 2  # blank line skipped; 2 code lines counted
