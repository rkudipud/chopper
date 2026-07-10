"""Unit tests for :mod:`chopper.trimmer.p4_checkout` (subprocess wrappers).

All ``subprocess.run`` and ``shutil.which`` calls are mocked -- no real ``p4``
binary is invoked. See ``technical_docs/ARCHITECTURE.md`` FR-53.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from chopper.trimmer.p4_checkout import check_p4_available, checkout_files, revert_files

DOMAIN_ROOT = Path("/work/my_domain")


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# check_p4_available
# ---------------------------------------------------------------------------


class TestCheckP4Available:
    def test_p4_missing_from_path(self) -> None:
        with patch("chopper.trimmer.p4_checkout.shutil.which", return_value=None) as mock_which:
            available, reason = check_p4_available(DOMAIN_ROOT)
        mock_which.assert_called_once_with("p4")
        assert available is False
        assert reason is not None
        assert "PATH" in reason

    def test_p4_info_raises_file_not_found(self) -> None:
        with (
            patch("chopper.trimmer.p4_checkout.shutil.which", return_value="/usr/bin/p4"),
            patch(
                "chopper.trimmer.p4_checkout.subprocess.run",
                side_effect=FileNotFoundError("no such file"),
            ) as mock_run,
        ):
            available, reason = check_p4_available(DOMAIN_ROOT)
        assert available is False
        assert reason is not None
        assert "FileNotFoundError" in reason
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == DOMAIN_ROOT

    def test_p4_info_times_out(self) -> None:
        with (
            patch("chopper.trimmer.p4_checkout.shutil.which", return_value="/usr/bin/p4"),
            patch(
                "chopper.trimmer.p4_checkout.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["p4", "info"], timeout=30),
            ),
        ):
            available, reason = check_p4_available(DOMAIN_ROOT)
        assert available is False
        assert reason is not None
        assert "TimeoutExpired" in reason

    def test_p4_info_nonzero_exit_with_stderr(self) -> None:
        with (
            patch("chopper.trimmer.p4_checkout.shutil.which", return_value="/usr/bin/p4"),
            patch(
                "chopper.trimmer.p4_checkout.subprocess.run",
                return_value=_completed(returncode=1, stderr="not a client workspace"),
            ),
        ):
            available, reason = check_p4_available(DOMAIN_ROOT)
        assert available is False
        assert reason is not None
        assert "not a client workspace" in reason

    def test_p4_info_nonzero_exit_empty_stderr(self) -> None:
        with (
            patch("chopper.trimmer.p4_checkout.shutil.which", return_value="/usr/bin/p4"),
            patch(
                "chopper.trimmer.p4_checkout.subprocess.run",
                return_value=_completed(returncode=1, stderr=""),
            ),
        ):
            available, reason = check_p4_available(DOMAIN_ROOT)
        assert available is False
        assert reason is not None
        assert reason != ""

    def test_success(self) -> None:
        with (
            patch("chopper.trimmer.p4_checkout.shutil.which", return_value="/usr/bin/p4") as mock_which,
            patch(
                "chopper.trimmer.p4_checkout.subprocess.run",
                return_value=_completed(returncode=0),
            ) as mock_run,
        ):
            available, reason = check_p4_available(DOMAIN_ROOT)
        mock_which.assert_called_once_with("p4")
        args, kwargs = mock_run.call_args
        assert args[0] == ["p4", "info"]
        assert kwargs["cwd"] == DOMAIN_ROOT
        assert available is True
        assert reason is None


# ---------------------------------------------------------------------------
# checkout_files
# ---------------------------------------------------------------------------


class TestCheckoutFiles:
    def test_empty_path_list(self) -> None:
        with patch("chopper.trimmer.p4_checkout.subprocess.run") as mock_run:
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, [])
        mock_run.assert_not_called()
        assert succeeded == ()
        assert failed_path is None
        assert failure_message is None

    def test_all_succeed_in_order(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl"), Path("c.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            return_value=_completed(returncode=0),
        ) as mock_run:
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, paths)
        assert succeeded == tuple(paths)
        assert failed_path is None
        assert failure_message is None
        assert mock_run.call_count == 3
        for call, path in zip(mock_run.call_args_list, paths, strict=True):
            args, kwargs = call
            assert args[0] == ["p4", "edit", "-t", "text+x", path.as_posix()]
            assert kwargs["cwd"] == DOMAIN_ROOT

    def test_failure_on_nth_path(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl"), Path("c.tcl")]
        responses = [
            _completed(returncode=0),
            _completed(returncode=1, stderr="no such file"),
        ]
        with patch("chopper.trimmer.p4_checkout.subprocess.run", side_effect=responses) as mock_run:
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, paths)
        assert succeeded == (Path("a.tcl"),)
        assert failed_path == Path("b.tcl")
        assert failure_message == "no such file"
        assert mock_run.call_count == 2

    def test_failure_nonzero_exit_empty_stderr(self) -> None:
        paths = [Path("a.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            return_value=_completed(returncode=1, stderr=""),
        ):
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, paths)
        assert succeeded == ()
        assert failed_path == Path("a.tcl")
        assert failure_message is not None
        assert failure_message != ""

    def test_exception_mid_batch(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            side_effect=[_completed(returncode=0), OSError("boom")],
        ):
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, paths)
        assert succeeded == (Path("a.tcl"),)
        assert failed_path == Path("b.tcl")
        assert failure_message is not None
        assert "OSError" in failure_message

    def test_exception_timeout_mid_batch(self) -> None:
        paths = [Path("a.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["p4", "edit"], timeout=30),
        ):
            succeeded, failed_path, failure_message = checkout_files(DOMAIN_ROOT, paths)
        assert succeeded == ()
        assert failed_path == Path("a.tcl")
        assert failure_message is not None
        assert "TimeoutExpired" in failure_message


# ---------------------------------------------------------------------------
# revert_files
# ---------------------------------------------------------------------------


class TestRevertFiles:
    def test_normal_case_calls_revert_per_path(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            return_value=_completed(returncode=0),
        ) as mock_run:
            revert_files(DOMAIN_ROOT, paths)
        assert mock_run.call_count == 2
        for call, path in zip(mock_run.call_args_list, paths, strict=True):
            args, kwargs = call
            assert args[0] == ["p4", "revert", path.as_posix()]
            assert kwargs["cwd"] == DOMAIN_ROOT

    def test_oserror_does_not_raise_and_continues(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            side_effect=[OSError("boom"), _completed(returncode=0)],
        ) as mock_run:
            revert_files(DOMAIN_ROOT, paths)  # must not raise
        assert mock_run.call_count == 2

    def test_timeout_does_not_raise_and_continues(self) -> None:
        paths = [Path("a.tcl"), Path("b.tcl")]
        with patch(
            "chopper.trimmer.p4_checkout.subprocess.run",
            side_effect=[
                subprocess.TimeoutExpired(cmd=["p4", "revert"], timeout=30),
                _completed(returncode=0),
            ],
        ) as mock_run:
            revert_files(DOMAIN_ROOT, paths)  # must not raise
        assert mock_run.call_count == 2
