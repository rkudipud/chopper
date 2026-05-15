"""Per-file coverage tests for src/chopper/core/models_compiler.py.

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


def test_shadow_event_rejects_empty_layer() -> None:
    """ShadowEvent.layer must be non-empty per the frozen-dataclass contract."""
    from chopper.core.models_compiler import ShadowEvent

    with pytest.raises(ValueError, match="non-empty"):
        ShadowEvent(layer="", prior_layer="base", action="remove")


def test_shadow_event_rejects_empty_prior_layer() -> None:
    """ShadowEvent.prior_layer must be non-empty; otherwise audit trail is opaque."""
    from chopper.core.models_compiler import ShadowEvent

    with pytest.raises(ValueError, match="non-empty"):
        ShadowEvent(layer="feat", prior_layer="", action="remove")
