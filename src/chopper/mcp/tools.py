"""MCP tool definitions and handlers for Chopper.

Exactly three read-only tools are registered — no others. Any attempt to
register a destructive tool (``chopper.trim``, ``chopper.cleanup``) is a
programmer error and is asserted against in
``tests/integration/test_mcp_stdio_e2e.py``.

See ``technical_docs/chopper_description.md`` §3.9 for the authoritative
contract and the JSON parameter schemas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import types

from chopper.core.errors import ChopperError

__all__ = [
    "TOOL_NAMES",
    "DESTRUCTIVE_TOOL_NAMES",
    "build_tools",
    "call_validate",
    "call_explain_diagnostic",
    "call_read_audit",
    "MCPProtocolError",
]


TOOL_NAMES: tuple[str, ...] = (
    "chopper.validate",
    "chopper.explain_diagnostic",
    "chopper.read_audit",
)

# Destructive tools that are NEVER exposed over MCP. Kept as a named
# constant so tests can assert the guard.
DESTRUCTIVE_TOOL_NAMES: tuple[str, ...] = (
    "chopper.trim",
    "chopper.cleanup",
)


class MCPProtocolError(ChopperError):
    """Raised on malformed tool input. Surfaced as ``PE-04`` by the server."""


def build_tools() -> list[types.Tool]:
    """Return the list of tools advertised to MCP clients.

    The returned list is exactly three entries long, in the order defined
    by :data:`TOOL_NAMES`. Destructive tools are never included.
    """

    return [
        types.Tool(
            name="chopper.validate",
            description=(
                "Run `chopper validate` against a domain. Returns the typed RunResult as JSON "
                "(exit code, diagnostics, artifact paths). Read-only: does not mutate the "
                "filesystem. Accepts either a project JSON or a base + optional features combo."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain_root": {
                        "type": "string",
                        "description": "Absolute path to the domain root directory.",
                    },
                    "base": {
                        "type": "string",
                        "description": "Path to base JSON (mutually exclusive with `project`).",
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of feature JSON paths (mutually exclusive with `project`).",
                    },
                    "project": {
                        "type": "string",
                        "description": "Path to project JSON (mutually exclusive with `base`/`features`).",
                    },
                    "strict": {
                        "type": "boolean",
                        "description": "Exit non-zero on any warning.",
                        "default": False,
                    },
                },
                "required": ["domain_root"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="chopper.explain_diagnostic",
            description=(
                "Look up a diagnostic code (e.g. `VE-06`, `PW-11`) in the Chopper diagnostic "
                "registry and return its slug, severity, phase, source, exit code, description, "
                "and recovery hint. Read-only; no filesystem access."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Diagnostic code, e.g. 'VE-06' or 'PW-11'.",
                        "pattern": r"^[VTP][EWI]-\d{2}$",
                    },
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="chopper.read_audit",
            description=(
                "Read the contents of a Chopper `.chopper/` audit bundle. Returns the full JSON "
                "contents of every `.json` file under the bundle, keyed by path relative to the "
                "bundle root. Non-JSON files (e.g. `trim_report.txt`) are returned as raw strings. "
                "Read-only; no mutation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bundle_path": {
                        "type": "string",
                        "description": "Absolute path to a `.chopper/` audit bundle directory.",
                    },
                },
                "required": ["bundle_path"],
                "additionalProperties": False,
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _require_string(arguments: dict[str, Any], key: str) -> str:
    if key not in arguments:
        raise MCPProtocolError(f"missing required parameter {key!r}")
    value = arguments[key]
    if not isinstance(value, str) or not value:
        raise MCPProtocolError(f"parameter {key!r} must be a non-empty string")
    return value


def call_validate(arguments: dict[str, Any]) -> str:
    """Handle a `chopper.validate` MCP tool call.

    Constructs an argparse-like namespace and invokes the existing
    :func:`chopper.cli.commands.cmd_validate` code path. Returns the
    serialized :class:`RunResult` as a JSON string.
    """

    # Import lazily so importing the MCP package does not pull the full
    # pipeline into every MCP client's cold-start path.
    import argparse

    from chopper.cli.commands import _make_context  # type: ignore[attr-defined]
    from chopper.core.serialization import dump_model
    from chopper.orchestrator import ChopperRunner

    domain_root = _require_string(arguments, "domain_root")
    project = arguments.get("project")
    base = arguments.get("base")
    features = arguments.get("features")
    strict = bool(arguments.get("strict", False))

    # Validate mutual exclusivity up front so the error surfaces as PE-04
    # rather than a RunResult exit=2. Matches the CLI check in main.py.
    if project and (base or features):
        raise MCPProtocolError("`project` is mutually exclusive with `base` / `features`")
    if not project and not base:
        raise MCPProtocolError("one of `base` or `project` is required")

    if features is not None and not (isinstance(features, list) and all(isinstance(p, str) for p in features)):
        raise MCPProtocolError("`features` must be an array of strings")

    ns = argparse.Namespace(
        command="validate",
        domain=domain_root,
        base=base,
        features=",".join(features) if features else None,
        project=project,
        strict=strict,
        quiet=True,
        plain=True,
        verbose=0,
        dry_run=True,
    )
    ctx, _sink = _make_context(ns, dry_run=True)
    result = ChopperRunner().run(ctx, command="validate")
    return dump_model(result)


_CODE_RE = re.compile(r"^[VTP][EWI]-\d{2}$")


def call_explain_diagnostic(arguments: dict[str, Any]) -> str:
    """Handle a `chopper.explain_diagnostic` MCP tool call.

    Returns a JSON object: ``{code, slug, severity, phase, source,
    exit_code, description, recovery_hint}``. The description and
    recovery hint are looked up from
    ``technical_docs/DIAGNOSTIC_CODES.md`` (the single source of
    truth); slug / severity / source / exit_code come from the in-code
    registry which is kept in sync with the doc by
    ``schemas/scripts/check_diagnostic_registry.py``.
    """

    from chopper.core._diagnostic_registry import lookup

    code = _require_string(arguments, "code").strip()
    if not _CODE_RE.match(code):
        raise MCPProtocolError(f"code {code!r} is not well-formed; expected family+severity+NN, e.g. 'VE-06'")
    try:
        entry = lookup(code)
    except Exception as exc:  # noqa: BLE001 — normalize to protocol error
        raise MCPProtocolError(f"unknown diagnostic code {code!r}: {exc}") from exc

    description, recovery_hint = _read_registry_prose(code)
    payload = {
        "code": code,
        "slug": entry.slug,
        "severity": entry.severity.value,
        "phase": int(entry.phase),
        "source": entry.source,
        "exit_code": entry.exit_code,
        "description": description,
        "recovery_hint": recovery_hint,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def call_read_audit(arguments: dict[str, Any]) -> str:
    """Handle a `chopper.read_audit` MCP tool call.

    Returns a JSON object keyed by bundle-relative path. JSON files are
    parsed and returned as structured data; non-JSON files are returned
    as raw strings. Returns the **full** contents, not a curated summary.
    """

    bundle_path = _require_string(arguments, "bundle_path")
    root = Path(bundle_path).expanduser().resolve()
    if not root.is_dir():
        raise MCPProtocolError(f"bundle_path {bundle_path!r} is not an existing directory")

    contents: dict[str, Any] = {}
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(root).as_posix()
        try:
            raw = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary file: skip; the audit bundle spec is text/JSON only,
            # but tolerate the oddball so the whole call does not fail.
            contents[rel] = {"__skipped__": "binary content"}
            continue
        if file_path.suffix == ".json":
            try:
                contents[rel] = json.loads(raw)
            except json.JSONDecodeError:
                contents[rel] = {"__invalid_json__": raw}
        else:
            contents[rel] = raw
    return json.dumps({"bundle_path": root.as_posix(), "files": contents}, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Registry prose lookup
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RegistryProse:
    description: str
    recovery_hint: str


_REGISTRY_DOC = Path(__file__).resolve().parents[3] / "technical_docs" / "DIAGNOSTIC_CODES.md"

# Cache for the parsed registry prose so repeated tool calls do not re-read
# the file. Populated on first access.
_prose_cache: dict[str, _RegistryProse] | None = None


def _read_registry_prose(code: str) -> tuple[str, str]:
    """Return ``(description, recovery_hint)`` from DIAGNOSTIC_CODES.md.

    Falls back to empty strings if the doc cannot be read or the code is
    not found in the doc (the in-code registry is the authoritative
    existence check; the doc just supplies prose).
    """

    global _prose_cache
    if _prose_cache is None:
        _prose_cache = _parse_registry(_REGISTRY_DOC)
    entry = _prose_cache.get(code)
    if entry is None:
        return ("", "")
    return (entry.description, entry.recovery_hint)


def _parse_registry(path: Path) -> dict[str, _RegistryProse]:
    if not path.is_file():
        return {}
    result: dict[str, _RegistryProse] = {}
    row_re = re.compile(r"^\|\s*([VTP][EWI]-\d{2})\s*\|")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not row_re.match(raw_line):
            continue
        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        # The VE / VW / VI / TW / PE / PW / PI tables share a common shape
        # but differ in column count. Description is the second-to-last
        # field; recovery hint is the last field; that's stable across all
        # code tables in DIAGNOSTIC_CODES.md.
        if len(cells) < 3:
            continue
        code = cells[0]
        description = cells[-2]
        recovery_hint = cells[-1]
        result[code] = _RegistryProse(description=description, recovery_hint=recovery_hint)
    return result
