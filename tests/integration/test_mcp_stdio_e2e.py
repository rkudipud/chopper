"""End-to-end stdio test for ``chopper mcp-serve``.

Spawns the MCP server as a subprocess, initializes the protocol, lists
the advertised tools, and invokes ``chopper.explain_diagnostic``. The
destructive-tool guard is asserted against the ``tools/list`` response.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

pytest.importorskip("mcp")


def _frame(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload) + "\n").encode("utf-8")


async def _read_response(proc: asyncio.subprocess.Process, timeout: float = 15.0) -> dict[str, object]:
    assert proc.stdout is not None
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
    if not line:
        stderr = b""
        if proc.stderr is not None:
            try:
                stderr = await asyncio.wait_for(proc.stderr.read(4096), timeout=1.0)
            except TimeoutError:
                stderr = b""
        raise AssertionError(f"MCP server produced no output on stdout; stderr={stderr!r}")
    return json.loads(line.decode("utf-8"))


async def _send(proc: asyncio.subprocess.Process, payload: dict[str, object]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(_frame(payload))
    await proc.stdin.drain()


@asynccontextmanager
async def _spawn_server() -> AsyncIterator[asyncio.subprocess.Process]:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "chopper.cli.main",
        "mcp-serve",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield proc
    finally:
        if proc.returncode is None:
            if proc.stdin is not None:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()


async def _initialize(proc: asyncio.subprocess.Process) -> dict[str, object]:
    await _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "chopper-tests", "version": "0.4.0"},
            },
        },
    )
    response = await _read_response(proc)
    await _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return response


async def _scenario_list_tools() -> list[str]:
    async with _spawn_server() as proc:
        init_response = await _initialize(proc)
        assert init_response.get("id") == 1
        assert "result" in init_response

        await _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        response = await _read_response(proc)
        assert response.get("id") == 2
        result = response["result"]
        assert isinstance(result, dict)
        tools = result.get("tools")
        assert isinstance(tools, list)
        return [tool["name"] for tool in tools]


async def _scenario_explain() -> dict[str, object]:
    async with _spawn_server() as proc:
        await _initialize(proc)
        await _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "chopper.explain_diagnostic",
                    "arguments": {"code": "VE-06"},
                },
            },
        )
        response = await _read_response(proc)
        assert response.get("id") == 3
        result = response["result"]
        content = result["content"]
        assert isinstance(content, list) and content
        return json.loads(content[0]["text"])


async def _scenario_unknown_tool() -> dict[str, object]:
    async with _spawn_server() as proc:
        await _initialize(proc)
        await _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "chopper.trim", "arguments": {}},
            },
        )
        return await _read_response(proc)


def test_mcp_serve_lists_only_read_only_tools() -> None:
    names = asyncio.run(_scenario_list_tools())
    assert sorted(names) == sorted(["chopper.validate", "chopper.explain_diagnostic", "chopper.read_audit"])
    for forbidden in ("chopper.trim", "chopper.cleanup"):
        assert forbidden not in names


def test_mcp_explain_diagnostic_round_trip() -> None:
    payload = asyncio.run(_scenario_explain())
    assert payload["code"] == "VE-06"
    assert payload["slug"] == "file-not-in-domain"
    assert payload["exit_code"] == 1


def test_mcp_unknown_tool_surfaces_as_protocol_error() -> None:
    response = asyncio.run(_scenario_unknown_tool())
    if "error" in response:
        assert response.get("id") == 4
        return
    result = response["result"]
    content = result["content"]
    assert any("PE-04" in item.get("text", "") for item in content)
