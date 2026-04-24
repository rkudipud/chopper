"""Unit tests for the MCP read-only tool handlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.mcp.tools import (
    DESTRUCTIVE_TOOL_NAMES,
    TOOL_NAMES,
    MCPProtocolError,
    build_tools,
    call_explain_diagnostic,
    call_read_audit,
)


class TestBuildTools:
    def test_advertises_exactly_three_tools(self) -> None:
        tools = build_tools()
        assert len(tools) == 3

    def test_advertised_names_match_tool_names_constant(self) -> None:
        tools = build_tools()
        assert tuple(t.name for t in tools) == TOOL_NAMES

    def test_destructive_tools_are_never_advertised(self) -> None:
        tools = build_tools()
        names = {t.name for t in tools}
        for destructive in DESTRUCTIVE_TOOL_NAMES:
            assert destructive not in names

    def test_every_tool_has_input_schema(self) -> None:
        for tool in build_tools():
            assert tool.inputSchema is not None
            assert tool.inputSchema.get("type") == "object"
            assert "properties" in tool.inputSchema

    def test_descriptions_mention_read_only_semantics(self) -> None:
        for tool in build_tools():
            assert tool.description is not None
            assert "read-only" in tool.description.lower() or "no mutation" in tool.description.lower()


class TestExplainDiagnostic:
    def test_known_code_returns_registry_payload(self) -> None:
        raw = call_explain_diagnostic({"code": "VE-06"})
        payload = json.loads(raw)
        assert payload["code"] == "VE-06"
        assert payload["slug"] == "file-not-in-domain"
        assert payload["severity"] == "error"
        assert payload["exit_code"] == 1
        assert payload["source"] == "validator"

    def test_pe_04_is_known_to_registry(self) -> None:
        raw = call_explain_diagnostic({"code": "PE-04"})
        payload = json.loads(raw)
        assert payload["slug"] == "mcp-protocol-error"
        assert payload["source"] == "mcp"
        assert payload["exit_code"] == 4

    def test_missing_code_parameter_raises_protocol_error(self) -> None:
        with pytest.raises(MCPProtocolError):
            call_explain_diagnostic({})

    def test_malformed_code_raises_protocol_error(self) -> None:
        with pytest.raises(MCPProtocolError):
            call_explain_diagnostic({"code": "not-a-code"})

    def test_unknown_but_well_formed_code_raises_protocol_error(self) -> None:
        with pytest.raises(MCPProtocolError):
            call_explain_diagnostic({"code": "VE-99"})

    def test_description_pulled_from_registry_doc(self) -> None:
        raw = call_explain_diagnostic({"code": "VE-06"})
        payload = json.loads(raw)
        # VE-06 description in DIAGNOSTIC_CODES.md mentions "domain".
        assert "domain" in payload["description"].lower()
        assert payload["recovery_hint"]


class TestReadAudit:
    def test_missing_bundle_path_raises_protocol_error(self) -> None:
        with pytest.raises(MCPProtocolError):
            call_read_audit({})

    def test_nonexistent_bundle_raises_protocol_error(self, tmp_path: Path) -> None:
        with pytest.raises(MCPProtocolError):
            call_read_audit({"bundle_path": str(tmp_path / "nope")})

    def test_returns_full_json_blobs(self, tmp_path: Path) -> None:
        bundle = tmp_path / ".chopper"
        bundle.mkdir()
        (bundle / "chopper_run.json").write_text(json.dumps({"exit_code": 0, "phases": ["P0", "P1"]}), encoding="utf-8")
        (bundle / "trim_report.txt").write_text("plain text report\n", encoding="utf-8")
        sub = bundle / "input_features"
        sub.mkdir()
        (sub / "01_dft.feature.json").write_text(json.dumps({"name": "dft"}), encoding="utf-8")

        raw = call_read_audit({"bundle_path": str(bundle)})
        payload = json.loads(raw)
        assert payload["bundle_path"] == bundle.as_posix()
        assert payload["files"]["chopper_run.json"] == {"exit_code": 0, "phases": ["P0", "P1"]}
        assert payload["files"]["trim_report.txt"] == "plain text report\n"
        assert payload["files"]["input_features/01_dft.feature.json"] == {"name": "dft"}

    def test_invalid_json_is_returned_as_raw(self, tmp_path: Path) -> None:
        bundle = tmp_path / ".chopper"
        bundle.mkdir()
        (bundle / "bogus.json").write_text("not json", encoding="utf-8")
        raw = call_read_audit({"bundle_path": str(bundle)})
        payload = json.loads(raw)
        assert payload["files"]["bogus.json"] == {"__invalid_json__": "not json"}


class TestServerGuard:
    def test_build_server_refuses_destructive_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mcp import types

        from chopper.mcp import server as server_module

        def _poisoned() -> list[types.Tool]:
            return [
                types.Tool(
                    name="chopper.trim",
                    description="should never be registered",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]

        monkeypatch.setattr(server_module, "build_tools", _poisoned)
        with pytest.raises(RuntimeError, match="destructive tools"):
            server_module.build_server()

    def test_build_server_returns_ok_with_canonical_toolset(self) -> None:
        from chopper.mcp import server as server_module

        # Does not raise; the canonical tool set is clean.
        server_module.build_server()
