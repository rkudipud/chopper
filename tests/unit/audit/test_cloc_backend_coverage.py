"""Per-file coverage tests for src/chopper/audit/cloc_backend.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_cloc_backend_returns_none_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc returns None when cloc/perl is unavailable, per the
    module contract 'Returns None so the caller can fall back'."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: False)
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc foo {} {}\n")
    assert result is None


def test_cloc_backend_returns_zero_for_blank_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty/whitespace-only input must return 0 (not None), matching the
    pure-Python fallback contract for blank files."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "   \n\n   ")
    assert result == 0


def test_cloc_backend_returns_none_on_subprocess_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When subprocess.run raises OSError (perl missing from PATH at runtime),
    count_sloc_via_cloc must return None so the caller falls back gracefully."""

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=OSError("not found")))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_backend_returns_none_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero exit code from cloc -> return None (fallback).  cloc signals
    language-identification failure or internal errors via non-zero exit."""

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=1, stdout="", stderr="err")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_backend_returns_none_on_json_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unparseable JSON output -> return None.  This handles corrupted or
    truncated cloc output without crashing."""

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=0, stdout="NOT JSON", stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_backend_returns_none_when_no_sum_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON without a SUM key means cloc didn't recognise the language.
    The spec says return None so the caller falls back."""
    import subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=0, stdout=json.dumps({"header": {}}), stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_backend_returns_none_when_code_not_int(monkeypatch: pytest.MonkeyPatch) -> None:
    """SUM.code must be an int; string/null -> None (fallback)."""
    import subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=0, stdout=json.dumps({"SUM": {"code": "five"}}), stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_backend_returns_code_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy-path: cloc returns valid JSON with SUM.code -> return the int."""
    import subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=0, stdout=json.dumps({"SUM": {"code": 7}}), stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result == 7


def test_cloc_backend_returns_none_on_tmpfile_write_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError writing the temporary file -> return None; no subprocess fork."""
    import tempfile

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    class _FailTmpFile:
        def __init__(self, *a, **kw): ...
        def __enter__(self):
            raise OSError("no space")

        def __exit__(self, *a): ...

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", _FailTmpFile)
    result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc x {} {}\n")
    assert result is None


def test_cloc_batch_empty_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch([]) must return [] without forking."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    assert cloc_backend.count_sloc_via_cloc_batch([]) == []
    cloc_backend.is_available.cache_clear()


def test_cloc_batch_unavailable_returns_none_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """When cloc is unavailable, batch must return [None]*n so callers
    fall back to the pure-Python counter per-slot."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: False)
    items = [(Path("a.tcl"), "proc x {} {}\n"), (Path("b.tcl"), "proc y {} {}\n")]
    result = cloc_backend.count_sloc_via_cloc_batch(items)
    assert result == [None, None]


def test_cloc_batch_subprocess_failure_returns_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the batch subprocess fails (non-zero exit), the batch function
    returns the current result list (blanks pre-set to 0, rest None)."""

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=1, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    items = [(Path("a.tcl"), "proc x {} {}\n"), (Path("b.tcl"), "")]
    result = cloc_backend.count_sloc_via_cloc_batch(items)
    # b.tcl is blank -> pre-set to 0; a.tcl failed -> None.
    assert len(result) == 2
    assert result[1] == 0  # blank pre-set


def test_cloc_batch_json_error_returns_partial_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad JSON from batch subprocess -> return current result list."""

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    fake_result = subprocess.CompletedProcess([], returncode=0, stdout="BAD_JSON", stderr="")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=fake_result))
    items = [(Path("a.tcl"), "proc x {} {}\n")]
    result = cloc_backend.count_sloc_via_cloc_batch(items)
    assert result == [None]


def test_count_sloc_via_cloc_batch_returns_nones_on_subprocess_failure() -> None:
    """count_sloc_via_cloc_batch returns a list of Nones when subprocess fails."""

    from chopper.audit.cloc_backend import count_sloc_via_cloc_batch

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""

    items = [(Path("a.tcl"), "proc foo {} {}"), (Path("b.tcl"), "proc bar {} {}")]

    with patch("chopper.audit.cloc_backend.is_available", return_value=True):
        with patch("chopper.audit.cloc_backend._perl_executable", return_value="/usr/bin/perl"):
            with patch("chopper.audit.cloc_backend.cloc_script_path", return_value=Path("/fake/cloc.pl")):
                with patch("subprocess.run", return_value=mock_proc):
                    result = count_sloc_via_cloc_batch(items)

    assert all(v is None for v in result)


def test_count_sloc_via_cloc_batch_returns_nones_on_json_decode_error() -> None:
    """count_sloc_via_cloc_batch returns Nones when subprocess output is bad JSON."""
    from chopper.audit.cloc_backend import count_sloc_via_cloc_batch

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "NOT JSON AT ALL"

    items = [(Path("x.tcl"), "proc x {} {}")]

    with patch("chopper.audit.cloc_backend.is_available", return_value=True):
        with patch("chopper.audit.cloc_backend._perl_executable", return_value="/usr/bin/perl"):
            with patch("chopper.audit.cloc_backend.cloc_script_path", return_value=Path("/fake/cloc.pl")):
                with patch("subprocess.run", return_value=mock_proc):
                    result = count_sloc_via_cloc_batch(items)

    assert all(v is None for v in result)


def test_cloc_script_path_returns_none_on_module_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """cloc_script_path returns None when resources.files raises ModuleNotFoundError (lines 71-72)."""
    import importlib.resources as _resources

    from chopper.audit import cloc_backend

    cloc_backend.cloc_script_path.cache_clear()
    monkeypatch.setattr(_resources, "files", lambda pkg: (_ for _ in ()).throw(ModuleNotFoundError("no pkg")))
    result = cloc_backend.cloc_script_path()
    cloc_backend.cloc_script_path.cache_clear()
    assert result is None


def test_cloc_script_path_returns_none_on_as_file_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """cloc_script_path returns None when resources.as_file raises OSError (lines 82-84)."""
    import importlib.resources as _resources
    from contextlib import contextmanager

    from chopper.audit import cloc_backend

    cloc_backend.cloc_script_path.cache_clear()

    mock_ref = MagicMock()

    @contextmanager
    def _bad_as_file(ref):  # type: ignore[misc]
        raise OSError("disk error")
        yield  # unreachable but makes it a generator

    monkeypatch.setattr(_resources, "files", lambda pkg: mock_ref)
    monkeypatch.setattr(_resources, "as_file", _bad_as_file)
    result = cloc_backend.cloc_script_path()
    cloc_backend.cloc_script_path.cache_clear()
    assert result is None


def test_cloc_count_sloc_oserror_on_unlink_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc handles OSError from tmp_path.unlink in finally (lines 166-167)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"SUM": {"code": 5}}'
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)

    # Patch Path.unlink to raise OSError -- should be caught silently
    original_unlink = Path.unlink

    def _bad_unlink(self, **kwargs):  # type: ignore[misc]
        raise OSError("unlink failed")

    monkeypatch.setattr(Path, "unlink", _bad_unlink)

    try:
        result = cloc_backend.count_sloc_via_cloc(Path("x.tcl"), "proc foo {} {}\n")
        # The function should complete without raising, returning the code value
        assert result == 5
    finally:
        monkeypatch.setattr(Path, "unlink", original_unlink)


def test_cloc_batch_returns_early_on_tmpdir_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch returns [None] on TemporaryDirectory OSError (lines 211-212)."""
    import tempfile

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    monkeypatch.setattr(tempfile, "TemporaryDirectory", MagicMock(side_effect=OSError("no tmp")))

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]


def test_cloc_batch_returns_early_when_no_valid_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch returns early when all writes fail (line 230)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    # Patch Path.write_text to raise OSError -> no files written -> valid == []
    original_write = Path.write_text

    def _bad_write(self, *a, **kw):  # type: ignore[misc]
        raise OSError("write failed")

    monkeypatch.setattr(Path, "write_text", _bad_write)

    try:
        result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
        assert result == [None]
    finally:
        monkeypatch.setattr(Path, "write_text", original_write)


def test_cloc_batch_returns_result_on_subprocess_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch catches subprocess OSError (lines 242-243)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=OSError("spawn failed")))

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]


def test_cloc_batch_returns_result_on_nonzero_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch returns [None] when subprocess returncode != 0 (line 251)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]


def test_cloc_batch_returns_result_on_json_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch returns [None] on JSONDecodeError (lines 262->259)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "NOT VALID JSON!!!"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]


def test_cloc_batch_returns_result_on_non_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch returns [None] when payload is not a dict (line 268)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "[1, 2, 3]"  # valid JSON but not a dict
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]


def test_cloc_batch_skips_header_and_sum_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch skips 'header' and 'SUM' keys (lines 271-272)."""
    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    # Payload has only header+SUM but no per-file entry -> result stays None
    import json as _json

    payload = {"header": {"cloc_version": "1.92"}, "SUM": {"code": 10, "blank": 2, "comment": 0}}
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = _json.dumps(payload)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [None]  # no match found, so stays None


def test_cloc_script_path_returns_none_on_resources_as_file_oserror2(monkeypatch: pytest.MonkeyPatch) -> None:
    """cloc_script_path returns None when resources.as_file raises OSError (line 84).

    Must patch `chopper.audit.cloc_backend.resources` because the module imports
    `from importlib import resources` and uses `resources.as_file` at call time.
    """
    from contextlib import contextmanager

    from chopper.audit import cloc_backend

    cloc_backend.cloc_script_path.cache_clear()

    # Create a fake ref object that looks like a valid resource
    fake_ref = MagicMock()

    # Fake resources module with files() returning fake_ref and as_file() raising
    @contextmanager
    def _bad_as_file(ref):  # type: ignore[misc]
        raise OSError("as_file disk error")
        yield  # makes it a generator

    fake_resources = MagicMock()
    fake_resources.files.return_value = fake_ref
    fake_resources.as_file = _bad_as_file

    monkeypatch.setattr(cloc_backend, "resources", fake_resources)
    result = cloc_backend.cloc_script_path()
    cloc_backend.cloc_script_path.cache_clear()
    assert result is None


def test_cloc_batch_skips_entry_without_code_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch skips per-file entries with missing/invalid code (branch 262->259)."""
    import json as _json
    import subprocess as _subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    # Payload has a file key but val has no "code" key (or code is not int)
    payload_dict = {
        "header": {"cloc_version": "1.92"},
        "/tmp/f000000.tcl": {"blank": 0, "comment": 0},  # no "code" key -> branch 262->259
        "SUM": {"code": 5},
    }
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = _json.dumps(payload_dict)
    monkeypatch.setattr(_subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    # No match found since the code entry was invalid
    assert result == [None]


def test_cloc_batch_handles_mixed_write_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch: one file writes, one fails write -> tp_opt None path (line 268)."""
    import json as _json
    import subprocess as _subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    write_call_count = [0]
    original_write = Path.write_text

    def _partial_write(self, *a, **kw):  # type: ignore[misc]
        write_call_count[0] += 1
        if write_call_count[0] == 1:
            raise OSError("first write fails")
        return original_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", _partial_write)

    # 2 items: first will fail write (tp_opt=None), second succeeds
    # subprocess returns valid but empty per-file mapping
    payload_dict: dict = {"header": {}, "SUM": {"code": 5}}
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = _json.dumps(payload_dict)
    monkeypatch.setattr(_subprocess, "run", lambda *a, **kw: mock_proc)

    result = cloc_backend.count_sloc_via_cloc_batch(
        [
            (Path("x.tcl"), "proc foo {} {}\n"),  # write fails -> tp_opt=None
            (Path("y.tcl"), "proc bar {} {}\n"),  # write succeeds
        ]
    )
    # First slot: write failed -> tp_opt is None -> continue -> stays None
    assert result[0] is None
    # Second slot: write succeeded but no code match -> stays None
    assert result[1] is None


def test_cloc_batch_success_path_with_matching_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch success: subprocess returns per-file code, result updated (lines 263-264, 273)."""
    import json as _json
    import subprocess as _subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    def _mock_run(*args, **kwargs):  # type: ignore[misc]
        # Extract the temp file paths from argv and include them in the payload
        argv = args[0]
        tmp_paths_in_argv = [p for p in argv if p.startswith("/tmp") or "/chopper_sloc" in p]
        payload: dict[str, object] = {"header": {"cloc_version": "1.92"}}
        for tp in tmp_paths_in_argv:
            payload[tp] = {"code": 7, "blank": 0, "comment": 0, "language": "Tcl"}
        payload["SUM"] = {"code": 7 * len(tmp_paths_in_argv), "blank": 0, "comment": 0}
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _json.dumps(payload)
        return mock_proc

    monkeypatch.setattr(_subprocess, "run", _mock_run)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    assert result == [7]  # success: per-file code matched and result updated


def test_cloc_batch_code_found_by_basename_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """count_sloc_via_cloc_batch: str(tp_opt) misses but tp_opt.name hits (line 270->272)."""
    import json as _json
    import subprocess as _subprocess

    from chopper.audit import cloc_backend

    cloc_backend.is_available.cache_clear()
    monkeypatch.setattr(cloc_backend, "is_available", lambda: True)
    monkeypatch.setattr(cloc_backend, "_perl_executable", lambda: "/usr/bin/perl")
    monkeypatch.setattr(cloc_backend, "cloc_script_path", lambda: Path("/cloc.pl"))

    def _mock_run_by_name(*args, **kwargs):  # type: ignore[misc]
        # Extract the temp file names (basename only) to trigger the fallback
        argv = args[0]
        tmp_paths_in_argv = [p for p in argv if "/chopper_sloc" in p or p.endswith(".tcl")]
        payload: dict[str, object] = {"header": {}}
        for tp in tmp_paths_in_argv:
            # Use only basename as key (not full path) -> triggers code=None -> fallback
            basename = Path(tp).name
            payload[basename] = {"code": 5, "blank": 0, "comment": 0}
        payload["SUM"] = {"code": 5}
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _json.dumps(payload)
        return mock_proc

    monkeypatch.setattr(_subprocess, "run", _mock_run_by_name)

    result = cloc_backend.count_sloc_via_cloc_batch([(Path("x.tcl"), "proc foo {} {}\n")])
    # Basename match means code=None from str(tp_opt) but code=5 from tp_opt.name
    assert result == [5]


def test_cloc_script_path_returns_none_when_resource_not_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``cloc_script_path`` (line 84): when ``importlib.resources.as_file``
    yields a path whose ``is_file()`` is False (e.g. resource resolves to
    a directory or a stale symlink), the function must fall through to
    the final ``return None`` without raising.
    """
    import importlib.resources as _resources
    from contextlib import contextmanager

    from chopper.audit import cloc_backend

    cloc_backend.cloc_script_path.cache_clear()

    # A directory exists on disk but is not a file -> ``is_file()`` is False.
    fake_dir = tmp_path / "not_a_cloc_file"
    fake_dir.mkdir()

    @contextmanager
    def _fake_as_file(_ref):
        yield fake_dir

    monkeypatch.setattr(_resources, "as_file", _fake_as_file)

    assert cloc_backend.cloc_script_path() is None

    cloc_backend.cloc_script_path.cache_clear()
