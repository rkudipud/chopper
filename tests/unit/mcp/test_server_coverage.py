"""Per-file coverage tests for src/chopper/mcp/server.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from unittest.mock import MagicMock
from unittest.mock import patch


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_cmd_mcp_serve_returns_exit_code_from_run_stdio_server() -> None:
    """cmd_mcp_serve returns whatever exit code run_stdio_server produces."""
    from chopper.cli.commands import cmd_mcp_serve

    with patch("chopper.mcp.run_stdio_server", return_value=0):
        assert cmd_mcp_serve(MagicMock()) == 0

    with patch("chopper.mcp.run_stdio_server", return_value=4):
        assert cmd_mcp_serve(MagicMock()) == 4


def test_serve_once_returns_4_on_fatal_mcp_protocol_error() -> None:
    """_serve_once returns exit code 4 when a fatal MCPProtocolError escapes server.run."""
    import asyncio
    from contextlib import asynccontextmanager

    from chopper.mcp.server import _serve_once
    from chopper.mcp.tools import MCPProtocolError

    @asynccontextmanager
    async def _failing_stdio():
        raise MCPProtocolError("fatal mcp protocol error during __aenter__")
        yield (MagicMock(), MagicMock())  # unreachable

    with patch("chopper.mcp.server.stdio_server", return_value=_failing_stdio()):
        result = asyncio.run(_serve_once())
    assert result == 4


def test_mcp_call_tool_routes_chopper_validate() -> None:
    """_call_tool dispatches chopper.validate to call_validate (line 101)."""
    import asyncio
    import mcp.types as t
    from chopper.mcp.server import build_server

    server = build_server()
    handler = server.request_handlers[t.CallToolRequest]
    req = t.CallToolRequest(
        method="tools/call",
        params=t.CallToolRequestParams(
            name="chopper.validate",
            arguments={"domain_root": "/tmp"},
        ),
    )
    with patch("chopper.mcp.server.call_validate", return_value='{"ok": true}'):
        result = asyncio.run(handler(req))
    assert result is not None


def test_serve_once_returns_0_on_clean_shutdown() -> None:
    """_serve_once returns 0 when server.run completes normally (lines 132-137)."""
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from chopper.mcp.server import _serve_once

    @asynccontextmanager
    async def _ok_stdio():
        yield MagicMock(), MagicMock()

    mock_server = MagicMock()
    mock_server.run = AsyncMock(return_value=None)
    mock_server.create_initialization_options = MagicMock(return_value=None)

    with patch("chopper.mcp.server.build_server", return_value=mock_server):
        with patch("chopper.mcp.server.stdio_server", side_effect=_ok_stdio):
            result = asyncio.run(_serve_once())

    assert result == 0
