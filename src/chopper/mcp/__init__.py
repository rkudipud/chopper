"""MCP (Model Context Protocol) stdio server for Chopper.

This package implements the narrow, read-only MCP surface introduced in
release 0.4.0 and specified in ``technical_docs/chopper_description.md``
§3.9.

Transport is **stdio only** (JSON-RPC frames on stdin/stdout, logging on
stderr). There is no TCP/HTTP/WebSocket transport and no daemon mode.

Exactly three read-only tools are registered:

* ``chopper.validate`` — thin wrapper around :func:`chopper.cli.commands.cmd_validate`.
* ``chopper.explain_diagnostic`` — registry lookup against
  ``technical_docs/DIAGNOSTIC_CODES.md``.
* ``chopper.read_audit`` — return the **full** JSON contents of every file
  under a ``.chopper/`` bundle, keyed by relative path.

The destructive subcommands (``chopper.trim``, ``chopper.cleanup``) are
never registered. A test in ``tests/integration/`` asserts they are absent
from the advertised tool list.

Protocol-level failures emit :data:`chopper.core.diagnostics.PE_04` with
exit code 4.
"""

from __future__ import annotations

from chopper.mcp.server import run_stdio_server
from chopper.mcp.tools import TOOL_NAMES, build_tools

__all__ = ["TOOL_NAMES", "build_tools", "run_stdio_server"]
