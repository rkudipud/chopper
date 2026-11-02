"""Tests for :func:`chopper.core.layout.source_root` (the single source-root rule)."""

from __future__ import annotations

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.layout import source_root
from tests.unit._coverage_helpers import BACKUP, DOMAIN, _ctx


def test_source_root_is_domain_without_backup() -> None:
    fs = InMemoryFS({DOMAIN / "a.tcl": "proc a {} {}\n"})
    assert source_root(_ctx(fs)) == DOMAIN


def test_source_root_prefers_backup_once_it_exists_on_disk() -> None:
    fs = InMemoryFS({DOMAIN / "a.tcl": "", BACKUP / "a.tcl": "proc a {} {}\n"})
    assert source_root(_ctx(fs)) == BACKUP


def test_source_root_tracks_a_backup_created_mid_run() -> None:
    # P5 creates the backup on a first live trim; P6/P7 must see it.
    fs = InMemoryFS({DOMAIN / "a.tcl": ""})
    ctx = _ctx(fs)
    assert source_root(ctx) == DOMAIN
    fs.mkdir(BACKUP, parents=True)
    assert source_root(ctx) == BACKUP
