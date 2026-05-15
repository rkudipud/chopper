"""Per-file coverage tests for src/chopper/core/models_audit.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



import pytest


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_internal_error_rejects_empty_kind() -> None:
    from chopper.core.models_audit import InternalError

    with pytest.raises(ValueError, match="non-empty"):
        InternalError(kind="", message="x")
