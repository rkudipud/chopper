"""Tests for :class:`chopper.orchestrator.domain_state.DomainStateService`."""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.orchestrator import DomainStateService
from tests.unit.trimmer._helpers import BACKUP, DOMAIN, make_ctx


def test_case_1_domain_only() -> None:
    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}"})
    ctx, sink = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    assert state.case == 1
    assert state.domain_exists is True
    assert state.backup_exists is False
    assert sink.codes() == []


def test_case_2_both_present() -> None:
    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc foo {} {}",
            BACKUP / "a.tcl": "proc foo {} {}",
        }
    )
    ctx, sink = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    assert state.case == 2
    assert state.domain_exists is True
    assert state.backup_exists is True
    assert sink.codes() == []


def test_case_3_backup_only() -> None:
    fs = InMemoryFS({BACKUP / "a.tcl": "proc foo {} {}"})
    ctx, sink = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    assert state.case == 3
    assert state.domain_exists is False
    assert state.backup_exists is True
    assert sink.codes() == []


def test_case_4_emits_ve21_and_returns_state() -> None:
    fs = InMemoryFS()
    ctx, sink = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    assert state.case == 4
    assert state.domain_exists is False
    assert state.backup_exists is False
    assert sink.codes() == ["VE-21"]
    # Message mentions both roots.
    msg = sink.snapshot()[0].message
    assert DOMAIN.as_posix() in msg
    assert BACKUP.as_posix() in msg


def test_dry_run_does_not_affect_classification() -> None:
    fs = InMemoryFS({DOMAIN / "a": "x"})
    ctx, _ = make_ctx(fs=fs, dry_run=True)
    state = DomainStateService().run(ctx)
    assert state.case == 1


def test_nested_audit_dir_does_not_leak_into_classification() -> None:
    """A stale .chopper/ under domain/ must not flip case detection."""
    fs = InMemoryFS(
        {
            DOMAIN / ".chopper" / "prev.json": "{}",
            BACKUP / "a.tcl": "",
        }
    )
    ctx, sink = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    # Both exist — classical Case 2.
    assert state.case == 2
    assert sink.codes() == []


def test_hand_edited_flag_is_always_false() -> None:
    """Architecture Doc §2.8 Case 2: hand-edit detection is CLI-pre-flight only, not diagnostic."""
    fs = InMemoryFS({DOMAIN / "x": "", BACKUP / "x": ""})
    ctx, _ = make_ctx(fs=fs)
    state = DomainStateService().run(ctx)
    assert state.hand_edited is False


def test_custom_roots_are_honoured() -> None:
    alt_domain = Path("/other/proj")
    alt_backup = Path("/other/proj_backup")
    fs = InMemoryFS({alt_backup / "x": ""})
    ctx, _ = make_ctx(fs=fs, domain_root=alt_domain, backup_root=alt_backup)
    state = DomainStateService().run(ctx)
    assert state.case == 3
