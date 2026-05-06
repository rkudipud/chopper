"""Unit tests for :mod:`chopper.mcp.server`."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mcp import types

from chopper.mcp import server as server_module
from chopper.mcp.tools import MCPProtocolError


def _call_tool(name: str, arguments: dict[str, Any] | None = None) -> types.ServerResult:
    server = server_module.build_server()
    handler = server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(params=types.CallToolRequestParams(name=name, arguments=arguments))
    return asyncio.run(handler(request))


def test_build_pe04_uses_protocol_diagnostic_shape() -> None:
    diag = server_module._build_pe04(MCPProtocolError("bad request"))

    assert diag.code == "PE-04"
    assert diag.slug == "mcp-protocol-error"
    assert diag.message == "bad request"


def test_build_server_refuses_tool_set_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_module, "build_tools", lambda: [])

    with pytest.raises(RuntimeError, match="tool set drift"):
        server_module.build_server()


def test_call_tool_unknown_name_returns_pe04_text() -> None:
    result = _call_tool("chopper.unknown", {})

    assert result.root.content[0].text.startswith("PE-04 mcp-protocol-error")


def test_call_tool_dispatches_explain_diagnostic() -> None:
    result = _call_tool("chopper.explain_diagnostic", {"code": "PE-04"})
    payload = result.root.content[0].text

    assert '"code": "PE-04"' in payload


def test_call_tool_dispatches_read_audit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = tmp_path / ".chopper"
    bundle.mkdir()
    (bundle / "trim_report.txt").write_text("ok\n", encoding="utf-8")

    result = _call_tool("chopper.read_audit", {"bundle_path": str(bundle)})
    payload = result.root.content[0].text

    assert "trim_report.txt" in payload


class _ProtocolErrorContext:
    async def __aenter__(self) -> tuple[object, object]:
        raise MCPProtocolError("frame broke")

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def test_serve_once_protocol_error_returns_exit_4(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(server_module, "stdio_server", lambda: _ProtocolErrorContext())

    exit_code = asyncio.run(server_module._serve_once())

    captured = capsys.readouterr()
    assert exit_code == 4
    assert "PE-04 mcp-protocol-error" in captured.err


def test_run_stdio_server_treats_keyboard_interrupt_as_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_keyboard_interrupt(coro: object) -> int:
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        raise KeyboardInterrupt

    monkeypatch.setattr(server_module.asyncio, "run", _raise_keyboard_interrupt)

    assert server_module.run_stdio_server() == 0
