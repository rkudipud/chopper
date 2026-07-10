"""Optional pre-P5 P4 checkout-before-edit integration (opt-in via ``--p4``).

Three small subprocess wrappers used by :class:`~chopper.trimmer.service.TrimmerService`
when ``RunConfig.p4_checkout`` is True and the run is not a dry-run. Every
function here is a thin, mockable wrapper -- none of them raise on
``p4`` failures; failures are returned as data so the caller decides
abort/rollback policy (never invoked, and never abort/crash Chopper
itself on an environment issue).

Chopper never runs ``p4 add``, ``p4 delete``, or ``p4 submit`` -- only
``p4 edit`` (checkout) and, on rollback, ``p4 revert``. Submission
remains a human's job.

See ``technical_docs/ARCHITECTURE.md`` FR-53.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

__all__ = ["check_p4_available", "checkout_files", "revert_files"]

_TIMEOUT_SECONDS = 30


def check_p4_available(domain_root: Path) -> tuple[bool, str | None]:
    """Return ``(available, reason_if_not)``.

    Two gates, deliberately simple (no per-file ``p4 where`` probe):

    1. The ``p4`` binary must be resolvable on ``PATH``.
    2. ``p4 info`` must succeed (exit 0) when run with ``cwd=domain_root``
       -- the simplest reliable signal that this directory is inside a
       reachable, working p4 client workspace.

    Never raises: subprocess/OS errors are captured and returned as the
    ``reason_if_not`` string.
    """
    if shutil.which("p4") is None:
        return False, "the 'p4' executable was not found on PATH"
    try:
        proc = subprocess.run(
            ["p4", "info"],
            cwd=domain_root,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"'p4 info' could not be run: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "non-zero exit with no stderr output"
        return False, f"'p4 info' failed (exit {proc.returncode}): {stderr}"
    return True, None


def checkout_files(domain_root: Path, paths: Sequence[Path]) -> tuple[tuple[Path, ...], Path | None, str | None]:
    """Run ``p4 edit -t text+x <path>`` for each path in order, stopping at
    the first failure.

    Returns ``(succeeded, failed_path_or_None, failure_message_or_None)``.
    ``paths`` are domain-relative POSIX paths; commands run with
    ``cwd=domain_root``. Never raises.

    Paths are passed as absolute values to ``p4 edit`` to avoid CWD-based
    resolution failures (some P4 server/client combinations return exit 0
    with "file(s) not on client" in stderr when given a relative path from
    a Python subprocess, even though the same relative path works fine from
    an interactive shell).

    Failure detection covers two cases:

    * ``returncode != 0`` -- explicit P4 error.
    * ``returncode == 0`` but ``stdout`` is empty -- P4's silent-failure
      pattern (e.g. ``"file(s) not on client"`` in stderr with exit 0).
      A genuine successful ``p4 edit`` always emits at least one
      ``- opened for edit`` line on stdout.
    """
    succeeded: list[Path] = []
    for rel in paths:
        abs_path = (domain_root / rel).as_posix()
        try:
            proc = subprocess.run(
                ["p4", "edit", "-t", "text+x", abs_path],
                cwd=domain_root,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return tuple(succeeded), rel, f"{type(exc).__name__}: {exc}"
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "non-zero exit with no stderr output"
            return tuple(succeeded), rel, stderr
        if not proc.stdout.strip():
            # Exit 0 with no stdout: P4 silent failure (e.g. "file(s) not
            # on client" in stderr, or workspace mapping mismatch).
            diag = proc.stderr.strip() or "p4 edit exit 0 with no stdout confirmation"
            return tuple(succeeded), rel, diag
        succeeded.append(rel)
    return tuple(succeeded), None, None


def revert_files(domain_root: Path, paths: Sequence[Path]) -> None:
    """Best-effort ``p4 revert <path>`` for each path.

    Swallows all errors: this runs during failure-path rollback, where
    raising would mask the original error and could leave the domain in
    a worse, half-reverted state with no diagnostic at all.
    """
    for rel in paths:
        abs_path = (domain_root / rel).as_posix()
        try:
            subprocess.run(
                ["p4", "revert", abs_path],
                cwd=domain_root,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
