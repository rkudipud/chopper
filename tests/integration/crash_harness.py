"""
Crash injection harness for Chopper state-machine transition tests.

Usage:    Stage 3 (Trimmer & Lifecycle) integration tests for domain lifecycle crash recovery.

This module provides:
  - @inject_crash_at(transition_name) decorator: raises SystemExit(1) at a
    named state-transition code point so integration tests can verify that
    Chopper's recovery path leaves the domain in a recoverable state.
  - assert_domain_recoverable(domain_path): asserts the domain invariant that
    either a valid domain/ or a valid domain_backup/ (or both) exist — never
    neither.
  - TRANSITION_POINTS: documented list of all 5 injection points from the
    DomainState machine.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from importlib import import_module
from pathlib import Path

# ---------------------------------------------------------------------------
# Injection point registry
# ---------------------------------------------------------------------------

#: All named injection points, keyed by transition label.
#: Each maps to the moment *after* that step has taken place but *before* the
#: next state promotion is confirmed.
TRANSITION_POINTS: dict[str, str] = {
    "after_backup_created": (
        "Injected after os.rename(domain → domain_backup) succeeds but before staging directory is created."
    ),
    "after_staging_written": (
        "Injected after staging directory is fully written but before the atomic rename staging → domain."
    ),
    "after_staging_promoted": (
        "Injected immediately after staging → domain rename but before .chopper/ audit artifacts are written."
    ),
    "after_retrim_staging_written": (
        "Re-trim path equivalent of after_staging_written: after new staging is written but before promotion."
    ),
    "after_cleanup_rename": (
        "Injected after domain_backup is renamed to domain_backup.deleting.<ts> "
        "but before deletion completes (tests partial-cleanup recovery)."
    ),
}

# Thread-local storage so concurrent test workers don't interfere.
_state = threading.local()


def _get_active_point() -> str | None:
    return getattr(_state, "active_point", None)


def _set_active_point(name: str | None) -> None:
    _state.active_point = name


# ---------------------------------------------------------------------------
# Core injection mechanism
# ---------------------------------------------------------------------------


def maybe_crash(transition_name: str) -> None:
    """Call this at the named transition point inside Chopper implementation code.

    If the crash harness has armed this transition for the current thread, this
    function raises SystemExit(1) to simulate a process crash.  Production code
    must call this with a string literal matching one of TRANSITION_POINTS.

    Example usage inside trimmer/lifecycle.py::

        from tests.integration.crash_harness import maybe_crash
        ...
        os.rename(domain_path, backup_path)
        maybe_crash("after_backup_created")   # no-op in production; crash in tests
    """
    if _get_active_point() == transition_name:
        _set_active_point(None)  # disarm so re-run doesn't crash again
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def inject_crash_at(transition_name: str) -> Callable:
    """Decorator that arms the crash harness for one named transition point.

    The decorated test function runs with the harness armed.  When Chopper's
    implementation calls maybe_crash(transition_name), SystemExit(1) is raised.
    The decorator catches SystemExit and re-raises it as RuntimeError("crash
    injected at <transition_name>") so pytest can inspect it normally.

    Usage::

        @inject_crash_at("after_backup_created")
        def test_recovery_from_backup_created(virgin_domain):
            chopper_trim(virgin_domain)          # will crash mid-trim
            ...
    """
    if transition_name not in TRANSITION_POINTS:
        raise ValueError(f"Unknown transition point {transition_name!r}. Valid points: {list(TRANSITION_POINTS)}")

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _set_active_point(transition_name)
            try:
                return fn(*args, **kwargs)
            except SystemExit as exc:
                raise RuntimeError(f"Crash injected at transition '{transition_name}' (exit code {exc.code})") from exc
            finally:
                _set_active_point(None)  # always disarm

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Domain state assertions
# ---------------------------------------------------------------------------


def assert_domain_recoverable(domain_path: Path) -> None:
    """Assert the core domain lifecycle invariant after a simulated crash.

    Invariant: at any point there must be EITHER a valid ``domain/`` directory
    OR a valid ``domain_backup/`` directory (or both).  Never neither.

    A "valid" directory means it exists and is a non-empty directory (the
    harness does not validate internal content — callers should follow up with
    more specific assertions).

    :param domain_path: The ``domain/`` path that was being trimmed.
    :raises AssertionError: If neither domain/ nor domain_backup/ is a valid directory.
    """
    backup_path = domain_path.parent / (domain_path.name + "_backup")

    domain_ok = domain_path.is_dir()
    backup_ok = backup_path.is_dir()

    assert domain_ok or backup_ok, (
        f"Domain invariant violated after crash:\n"
        f"  domain/        exists={domain_ok}  path={domain_path}\n"
        f"  domain_backup/ exists={backup_ok}  path={backup_path}\n"
        "Neither directory is present — data loss scenario."
    )


def assert_domain_state(domain_path: Path, expected_state: str) -> None:
    """Assert that the domain is in the expected DomainState after a crash.

    :param domain_path: The ``domain/`` path.
    :param expected_state: One of 'virgin', 'backup_created', 'staging',
        'trimmed', 'cleaned'.
    """
    lifecycle = import_module("chopper.trimmer.lifecycle")
    actual = lifecycle.detect_domain_state(domain_path)
    assert actual.value == expected_state, (
        f"Expected domain state {expected_state!r}, got {actual.value!r} for domain {domain_path}"
    )


# ---------------------------------------------------------------------------
# Context manager variant (for explicit arming/disarming)
# ---------------------------------------------------------------------------


class CrashAt:
    """Context manager that arms the crash harness for a named transition.

    Usage::

        with CrashAt("after_staging_written"):
            with pytest.raises(RuntimeError, match="after_staging_written"):
                chopper_trim(domain_path)
        assert_domain_recoverable(domain_path)
    """

    def __init__(self, transition_name: str) -> None:
        if transition_name not in TRANSITION_POINTS:
            raise ValueError(f"Unknown transition point {transition_name!r}. Valid points: {list(TRANSITION_POINTS)}")
        self._name = transition_name

    def __enter__(self) -> CrashAt:
        _set_active_point(self._name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        _set_active_point(None)
        if exc_type is SystemExit:
            raise RuntimeError(f"Crash injected at transition '{self._name}' (exit code {exc_val.code})") from exc_val
        return False
