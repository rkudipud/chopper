"""Per-file coverage tests for src/chopper/compiler/flow_resolver.py.

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


def test_flow_resolver_find_stage_index_raises_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage_index, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    with pytest.raises(ChopperError, match="missing stage"):
        _find_stage_index([s], "nope")


def test_flow_resolver_find_stage_raises_for_unknown() -> None:
    from chopper.compiler.flow_resolver import _find_stage, _MutableStage  # type: ignore[attr-defined]
    from chopper.core.errors import ChopperError
    from chopper.core.models_config import StageDefinition

    s = _MutableStage.from_definition(StageDefinition(name="a", load_from="base", steps=("step1",)))
    with pytest.raises(ChopperError, match="missing stage"):
        _find_stage([s], "nope")
