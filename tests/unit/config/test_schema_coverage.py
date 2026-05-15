"""Per-file coverage tests for src/chopper/config/schema.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



import pytest
from _pytest.monkeypatch import MonkeyPatch


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_schema_dir_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from chopper.config import schema as schema_mod

    real = schema_mod.Path

    class _Fake(type(real("/"))):  # type: ignore[misc]
        pass

    # Directly patch is_dir to return False on the computed schemas path.
    monkeypatch.setattr(schema_mod.Path, "is_dir", lambda self: False)
    with pytest.raises(RuntimeError, match="schemas/ not found"):
        schema_mod._schema_dir()
