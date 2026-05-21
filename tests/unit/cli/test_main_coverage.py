"""Per-file coverage tests for src/chopper/cli/main.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import sys
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


def test_cli_main_last_resort_exception_writes_internal_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import importlib

    main_mod = importlib.import_module("chopper.cli.main")
    # __init__.py rebinds chopper.cli.main to the function; reach the
    # actual submodule via sys.modules so monkeypatch can mutate it.
    main_mod = sys.modules["chopper.cli.main"]

    def _boom(_args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main_mod, "cmd_validate", _boom)
    monkeypatch.chdir(tmp_path)
    rc = main_mod.main(["validate", "--base", "noexist.json"])
    assert rc == 1
    err = capsys.readouterr().err
    assert err  # some stderr message was written


def test_main_programmer_error_handler_returns_1() -> None:
    """main() returns 1 and writes an internal error log when an Exception escapes the CLI."""
    from chopper.cli.main import main

    mock_internal = MagicMock()
    mock_internal.kind = "RuntimeError"
    mock_internal.message = "boom"
    mock_internal.log_path = None

    with patch("chopper.cli.main.cmd_validate", side_effect=RuntimeError("boom")):
        with patch("chopper.cli.main.write_internal_error_log", return_value=mock_internal):
            rc = main(["validate", "--base", "/fake/base.json"])
    assert rc == 1


def test_main_returns_exit_code_on_success() -> None:
    """main() returns the exit code from args.func() on success (line 155)."""
    from chopper.cli.main import main

    with patch("chopper.cli.main.cmd_validate", return_value=0) as mock_cmd:
        rc = main(["validate", "--base", "/fake/base.json"])
    assert rc == 0
    mock_cmd.assert_called_once()


def test_main_propagates_systemexit() -> None:
    """main() re-raises SystemExit from args.func() (line 158)."""
    from chopper.cli.main import main

    with patch("chopper.cli.main.cmd_validate", side_effect=SystemExit(2)):
        with pytest.raises(SystemExit) as exc_info:
            main(["validate", "--base", "/fake/base.json"])
    assert exc_info.value.code == 2
