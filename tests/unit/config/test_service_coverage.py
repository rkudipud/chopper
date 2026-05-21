"""Per-file coverage tests for src/chopper/config/service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext, RunConfig
from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_config_source_root_returns_backup_when_state_says_backup_exists() -> None:
    from chopper.config.service import _config_source_root
    from chopper.core.models_common import DomainState

    ctx = _ctx()
    state_with_backup = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
    assert _config_source_root(ctx, state_with_backup) == BACKUP

    state_no_backup = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
    assert _config_source_root(ctx, state_no_backup) == DOMAIN
    assert _config_source_root(ctx, None) == DOMAIN


def test_config_enumerate_handles_list_oserror() -> None:
    from chopper.config.service import _enumerate_domain_files

    class _BadList(InMemoryFS):
        def list(self, path: Path, *, pattern: str | None = None) -> tuple[Path, ...]:  # type: ignore[override]
            if path == DOMAIN / "bad":
                raise OSError("denied")
            return super().list(path, pattern=pattern)

    fs = _BadList()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.mkdir(DOMAIN / "bad", parents=True, exist_ok=True)
    ctx = _ctx(fs=fs)
    out = _enumerate_domain_files(ctx)
    posix = {p.as_posix() for p, _ in out}
    assert "ok.tcl" in posix


def test_config_enumerate_handles_stat_oserror() -> None:
    from chopper.config.service import _enumerate_domain_files

    class _StatFail(InMemoryFS):
        def stat(self, path: Path):  # type: ignore[override]
            if path == DOMAIN / "bad.tcl":
                raise OSError("denied")
            return super().stat(path)

    fs = _StatFail()
    fs.write_text(DOMAIN / "ok.tcl", "x")
    fs.write_text(DOMAIN / "bad.tcl", "y")
    ctx = _ctx(fs=fs)
    out = {p.as_posix() for p, _ in _enumerate_domain_files(ctx)}
    assert "ok.tcl" in out
    assert "bad.tcl" not in out


def test_is_glob_pattern_returns_true_for_metachar() -> None:
    """_is_glob_pattern must return True when the string contains *, ?, or [."""
    from chopper.config.service import _is_glob_pattern

    assert _is_glob_pattern("*.tcl") is True
    assert _is_glob_pattern("file[0-9].tcl") is True
    assert _is_glob_pattern("file?.tcl") is True
    assert _is_glob_pattern("plain.tcl") is False


def test_match_glob_against_exact_literal_match() -> None:
    """_match_glob_against returns the matching Path for an exact literal pattern."""
    from chopper.config.service import _match_glob_against

    domain_files = [
        (Path("sub/file.tcl"), "sub/file.tcl"),
        (Path("other.tcl"), "other.tcl"),
    ]
    # Exact literal match (no globs): exercises the fnmatchcase fallback path.
    result = _match_glob_against("other.tcl", domain_files)
    assert Path("other.tcl") in result


def test_load_and_hydrate_feature_raw_none_returns_none() -> None:
    """_load_and_hydrate_feature returns None when _load_raw returns None (line 211)."""
    from chopper.config.service import ConfigService

    ctx = _ctx()
    svc = ConfigService()
    # Use a path that doesn't exist in the InMemoryFS → _load_raw → None → line 211
    result = svc._load_and_hydrate_feature(ctx, DOMAIN / "nonexistent.json")
    assert result is None


def test_enumerate_domain_files_skips_child_outside_domain() -> None:
    """_enumerate_domain_files skips children where relative_to raises ValueError (lines 285-286)."""
    from chopper.config.service import _enumerate_domain_files

    mock_fs = MagicMock()
    alien = Path("/alien/file.tcl")
    alien_stat = MagicMock()
    alien_stat.is_dir = False

    def fake_list(p: Path) -> list[Path]:
        if p == DOMAIN:
            return [alien]
        return []

    mock_fs.exists.return_value = True
    mock_fs.list.side_effect = fake_list
    mock_fs.stat.return_value = alien_stat

    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=mock_fs, diag=_Sink(), progress=_Progress())

    result = _enumerate_domain_files(ctx2)
    assert result == []
