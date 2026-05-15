"""Per-file coverage tests for src/chopper/audit/service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from chopper.adapters.fs_memory import InMemoryFS
from chopper.core.context import ChopperContext
from chopper.core.context import RunConfig
import datetime


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_audit_service_emits_vw20_on_write_failure(tmp_path: Path) -> None:
    """Audit writers tolerate OSError by emitting VW-20 and continuing."""

    from datetime import UTC, datetime

    from chopper.adapters.fs_local import LocalFS
    from chopper.audit.service import AuditService
    from chopper.core.context import ChopperContext, RunConfig
    from chopper.core.models_audit import RunRecord

    domain = tmp_path / "d"
    domain.mkdir()
    audit = domain / ".chopper"

    class _WriteFail(LocalFS):
        def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:  # type: ignore[override]
            raise OSError("read-only")

    cfg = RunConfig(domain_root=domain, backup_root=tmp_path / "bk", audit_root=audit, strict=False, dry_run=False)
    ctx = ChopperContext(config=cfg, fs=_WriteFail(), diag=_Sink(), progress=_Progress())
    now = datetime.now(UTC)
    record = RunRecord(
        run_id="abc",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
    )
    AuditService().run(ctx, record)
    assert "VW-20" in _codes(ctx)


def test_audit_service_safe_read_returns_none_on_oserror(tmp_path: Path) -> None:
    """AuditService._safe_read must return None (not raise) when the file
    cannot be read so the audit bundle write can continue with partial data."""
    from chopper.adapters.fs_local import LocalFS
    from chopper.audit.service import AuditService
    from chopper.core.context import ChopperContext, RunConfig

    domain = tmp_path / "d"
    domain.mkdir()
    cfg = RunConfig(
        domain_root=domain,
        backup_root=tmp_path / "bk",
        audit_root=domain / ".chopper",
        strict=False,
        dry_run=False,
    )

    class _FailFS(LocalFS):
        def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:  # type: ignore[override]
            raise OSError("locked")

    ctx = ChopperContext(config=cfg, fs=_FailFS(), diag=_Sink(), progress=_Progress())
    result = AuditService()._safe_read(ctx, domain / "nonexistent.json")
    assert result is None


def test_collect_input_jsons_returns_empty_when_loaded_is_none() -> None:
    """AuditService._collect_input_jsons returns [] immediately when record.loaded is None."""
    from datetime import datetime, timezone

    from chopper.audit.service import AuditService
    from chopper.core.models_audit import RunRecord

    now = datetime.now(timezone.utc)
    record = RunRecord(
        run_id="r-none",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        loaded=None,
    )
    ctx = _ctx()
    result = AuditService()._copy_inputs(ctx, record)
    assert result == []


def test_copy_inputs_with_readable_base_and_unreadable_feature() -> None:
    """_copy_inputs: base read succeeds; unreadable feature is silently skipped (lines 138-144)."""
    from datetime import datetime, timezone

    from chopper.audit.service import AuditService
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig

    fs = InMemoryFS()
    base_path = DOMAIN / "base.json"
    feature_path = DOMAIN / "feat.json"
    fs.write_text(base_path, '{"domain": "d"}')
    # feat.json intentionally NOT written → _safe_read returns None → feature skipped

    base = BaseJson(source_path=base_path, domain="d")
    feature = FeatureJson(source_path=feature_path, name="feat")
    loaded = LoadedConfig(base=base, features=(feature,))

    now = datetime.now(timezone.utc)
    record = RunRecord(
        run_id="r-copy-test",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        loaded=loaded,
    )
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    result = AuditService()._copy_inputs(ctx2, record)
    assert any(name == "input_base.json" for name, _ in result)
    assert not any("feat" in name for name, _ in result)


def test_copy_inputs_feature_with_none_text_continues() -> None:
    """_copy_inputs: feature text=None path skips feature entry (lines 143-144)."""
    from datetime import datetime, timezone

    from chopper.audit.service import AuditService
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig

    fs = InMemoryFS()
    base_path = DOMAIN / "base.json"
    feature_path = DOMAIN / "missing_feat.json"
    fs.write_text(base_path, '{"domain": "d"}')
    # Do NOT write feature_path → _safe_read returns None → lines 143-144 hit

    base = BaseJson(source_path=base_path, domain="d")
    feature = FeatureJson(source_path=feature_path, name="missing_feat")
    loaded = LoadedConfig(base=base, features=(feature,))

    now = datetime.now(timezone.utc)
    record = RunRecord(
        run_id="r-feat-none",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        loaded=loaded,
    )
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    result = AuditService()._copy_inputs(ctx2, record)
    # Feature was unreadable → only base entry present
    names = [n for n, _ in result]
    assert "input_base.json" in names
    assert not any("missing_feat" in n for n in names)


def test_copy_inputs_readable_feature_written() -> None:
    """_copy_inputs: readable feature produces input_features/01_feat.json (lines 143-144)."""
    from datetime import datetime, timezone

    from chopper.audit.service import AuditService
    from chopper.core.models_audit import RunRecord
    from chopper.core.models_config import BaseJson, FeatureJson, LoadedConfig

    fs = InMemoryFS()
    base_path = DOMAIN / "base.json"
    feature_path = DOMAIN / "feat.json"
    fs.write_text(base_path, '{"domain": "d"}')
    fs.write_text(feature_path, '{"name": "feat"}')  # readable → lines 143-144 hit

    base = BaseJson(source_path=base_path, domain="d")
    feature = FeatureJson(source_path=feature_path, name="feat")
    loaded = LoadedConfig(base=base, features=(feature,))

    now = datetime.now(timezone.utc)
    record = RunRecord(
        run_id="r-feat-readable",
        command="validate",
        started_at=now,
        ended_at=now,
        exit_code=0,
        loaded=loaded,
    )
    cfg = RunConfig(domain_root=DOMAIN, backup_root=BACKUP, audit_root=AUDIT, strict=False, dry_run=False)
    ctx2 = ChopperContext(config=cfg, fs=fs, diag=_Sink(), progress=_Progress())

    result = AuditService()._copy_inputs(ctx2, record)
    names = [n for n, _ in result]
    assert "input_base.json" in names
    assert any("feat.json" in n for n in names)
