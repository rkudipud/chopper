"""Unit tests for the MCP read-only tool handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chopper.core.diagnostics import DiagnosticSummary
from chopper.core.models_audit import RunResult
from chopper.mcp.tools import (
    DESTRUCTIVE_TOOL_NAMES,
    TOOL_NAMES,
    MCPProtocolError,
    build_tools,
    call_explain_diagnostic,
    call_read_audit,
    call_validate,
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

    def test_missing_registry_doc_returns_empty_prose(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from chopper.mcp import tools as tools_module

        monkeypatch.setattr(tools_module, "_REGISTRY_DOC", tmp_path / "missing.md")
        monkeypatch.setattr(tools_module, "_prose_cache", None)

        raw = call_explain_diagnostic({"code": "VE-06"})
        payload = json.loads(raw)

        assert payload["description"] == ""
        assert payload["recovery_hint"] == ""

    def test_registry_parser_ignores_non_rows_and_short_rows(self, tmp_path: Path) -> None:
        from chopper.mcp import tools as tools_module

        registry = tmp_path / "DIAGNOSTIC_CODES.md"
        registry.write_text(
            "not a table row\n| VE-06 | too-short |\n| VE-07 | P1 | validator | 1 | real description | real hint |\n",
            encoding="utf-8",
        )

        parsed = tools_module._parse_registry(registry)

        assert parsed["VE-07"].description == "real description"
        assert parsed["VE-07"].recovery_hint == "real hint"


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

    def test_binary_file_is_reported_as_skipped(self, tmp_path: Path) -> None:
        bundle = tmp_path / ".chopper"
        bundle.mkdir()
        (bundle / "opaque.bin").write_bytes(b"\xff\xfe\x00")

        raw = call_read_audit({"bundle_path": str(bundle)})
        payload = json.loads(raw)

        assert payload["files"]["opaque.bin"] == {"__skipped__": "binary content"}


class TestValidate:
    def test_missing_domain_root_raises_protocol_error(self) -> None:
        with pytest.raises(MCPProtocolError):
            call_validate({"base": "base.json"})

    def test_project_is_mutually_exclusive_with_base(self) -> None:
        with pytest.raises(MCPProtocolError, match="mutually exclusive"):
            call_validate({"domain_root": "/domain", "project": "project.json", "base": "base.json"})

    def test_base_or_project_is_required(self) -> None:
        with pytest.raises(MCPProtocolError, match="one of"):
            call_validate({"domain_root": "/domain"})

    def test_features_must_be_string_array(self) -> None:
        with pytest.raises(MCPProtocolError, match="features"):
            call_validate({"domain_root": "/domain", "base": "base.json", "features": ["ok.json", 7]})

    def test_successful_validate_returns_serialized_run_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import chopper.orchestrator as orchestrator_module
        from chopper.cli import commands as commands_module

        captured: dict[str, Any] = {}

        def _fake_make_context(ns: Any, *, dry_run: bool) -> tuple[object, object]:
            captured["namespace"] = ns
            captured["dry_run"] = dry_run
            return object(), object()

        class _Runner:
            def run(self, ctx: object, *, command: str) -> RunResult:
                captured["ctx"] = ctx
                captured["command"] = command
                return RunResult(exit_code=0, summary=DiagnosticSummary(errors=0, warnings=0, infos=0))

        monkeypatch.setattr(commands_module, "_make_context", _fake_make_context)
        monkeypatch.setattr(orchestrator_module, "ChopperRunner", _Runner)

        raw = call_validate(
            {
                "domain_root": "/domain",
                "base": "base.json",
                "features": ["feature_b.json", "feature_a.json"],
                "strict": True,
            }
        )
        payload = json.loads(raw)

        assert payload["exit_code"] == 0
        assert captured["dry_run"] is True
        assert captured["command"] == "validate"
        ns = captured["namespace"]
        assert ns.command == "validate"
        assert ns.domain == "/domain"
        assert ns.features == "feature_b.json,feature_a.json"
        assert ns.strict is True


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
