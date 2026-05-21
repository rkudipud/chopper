"""Per-file coverage tests for src/chopper/mcp/tools.py.

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
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_require_string_raises_for_empty_value() -> None:
    """_require_string must raise MCPProtocolError when the parameter is
    an empty string, not just when it is missing."""
    from chopper.mcp.server import MCPProtocolError  # type: ignore[attr-defined]
    from chopper.mcp.tools import _require_string  # type: ignore[attr-defined]

    with pytest.raises(MCPProtocolError, match="non-empty string"):
        _require_string({"key": ""}, "key")


def test_require_string_raises_for_non_string_value() -> None:
    """_require_string must raise MCPProtocolError when the value is not a string."""
    from chopper.mcp.server import MCPProtocolError  # type: ignore[attr-defined]
    from chopper.mcp.tools import _require_string  # type: ignore[attr-defined]

    with pytest.raises(MCPProtocolError, match="non-empty string"):
        _require_string({"key": 42}, "key")
