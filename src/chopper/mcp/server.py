"""Stdio MCP server entry point for Chopper.

The server is constructed when :func:`run_stdio_server` is called (from
the ``chopper mcp-serve`` CLI handler) so that simply importing
:mod:`chopper.mcp` does not have any side effects.

Transport is stdio only: JSON-RPC frames on stdin, responses on stdout,
logging on stderr. There is no TCP, HTTP, or WebSocket transport and no
daemon mode. See ``technical_docs/chopper_description.md`` §3.9.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from chopper.mcp.tools import (
    DESTRUCTIVE_TOOL_NAMES,
    TOOL_NAMES,
    MCPProtocolError,
    build_tools,
    call_explain_diagnostic,
    call_read_audit,
    call_validate,
)

__all__ = ["build_server", "run_stdio_server"]


def _assert_no_destructive_tools(tools: list[types.Tool]) -> None:
    """Fail-closed guard: destructive tools must NEVER be registered.

    Asserted at server-construction time so a programmer error cannot
    reach a running client. Also asserted again by
    ``tests/integration/test_mcp_stdio_e2e.py`` against the advertised
    ``tools/list`` response.
    """

    names = {tool.name for tool in tools}
    if not names.isdisjoint(DESTRUCTIVE_TOOL_NAMES):
        overlap = sorted(names & set(DESTRUCTIVE_TOOL_NAMES))
        raise RuntimeError(
            f"programmer error: destructive tools registered over MCP: {overlap}. "
            "See technical_docs/chopper_description.md §3.9."
        )
    if set(names) != set(TOOL_NAMES):
        raise RuntimeError(
            f"programmer error: MCP tool set drift. Expected {sorted(TOOL_NAMES)!r}, got {sorted(names)!r}."
        )


def build_server() -> Server:
    """Construct and return the MCP ``Server`` with handlers wired.

    Exposed as a helper so tests can introspect the configured server
    without spinning up a stdio pipe.
    """

    server: Server = Server("chopper")
    tools = build_tools()
    _assert_no_destructive_tools(tools)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        args = arguments or {}
        try:
            if name == "chopper.validate":
                payload = call_validate(args)
            elif name == "chopper.explain_diagnostic":
                payload = call_explain_diagnostic(args)
            elif name == "chopper.read_audit":
                payload = call_read_audit(args)
            else:
                raise MCPProtocolError(f"unknown tool {name!r}")
        except MCPProtocolError as exc:
            # Surface as a tool-error TextContent so the client sees the
            # message. The server stays alive; only the single call fails.
            return [types.TextContent(type="text", text=f"PE-04 mcp-protocol-error: {exc}")]
        return [types.TextContent(type="text", text=payload)]

    return server


async def _serve_once() -> int:
    """Run the stdio server until the client disconnects.

    Returns the process exit code: ``0`` on clean shutdown, ``4`` on a
    fatal protocol error that escapes the per-call ``try``.
    """

    server = build_server()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
        return 0
    except MCPProtocolError as exc:
        print(f"PE-04 mcp-protocol-error: {exc}", file=sys.stderr)
        return 4


def run_stdio_server() -> int:
    """Synchronous entry point. Returns a process exit code."""

    try:
        return asyncio.run(_serve_once())
    except KeyboardInterrupt:
        # Clean SIGINT on stdio → exit 0. The MCP spec treats client
        # disconnect and SIGINT as equivalent shutdown signals.
        return 0
