"""JSON-schema validation adapters for Chopper's three JSON schemas.

This module provides :func:`validate_json` — a single entry point that
accepts a raw parsed dict and determines which Chopper schema to validate
it against, then emits diagnostics via the supplied callback.

Schemas are read from ``schemas/`` relative to the *repo root*
(the directory four levels above this source file). The authoritative
schema files are:

* ``schemas/base-v1.schema.json``     → ``$schema: base-v1``
* ``schemas/feature-v1.schema.json``  → ``$schema: feature-v1``
* ``schemas/project-v1.schema.json``  → ``$schema: project-v1``

Diagnostic mapping:

* ``$schema`` field missing or unknown  → ``VE-01 missing-schema``
* Required field missing (jsonschema)   → ``VE-02 missing-required-fields``
* Project JSON schema failure           → ``VE-12 project-schema-invalid``
* Any other jsonschema validation error → ``VE-02`` (base/feature) or
  ``VE-12`` (project) depending on schema kind.

Only the *first* validation error per file is forwarded to the caller —
further errors on a malformed document are usually cascades of the same root
cause, and overwhelming the user with them is unhelpful.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import jsonschema.validators

from chopper.core.diagnostics import Diagnostic, Phase

__all__ = ["validate_json"]

# ---------------------------------------------------------------------------
# Known schema $id values.
# ---------------------------------------------------------------------------

_SCHEMA_ID_BASE = "base-v1"
_SCHEMA_ID_FEATURE = "feature-v1"
_SCHEMA_ID_PROJECT = "project-v1"

_KNOWN_SCHEMAS: frozenset[str] = frozenset([_SCHEMA_ID_BASE, _SCHEMA_ID_FEATURE, _SCHEMA_ID_PROJECT])

# Maps $schema value → the filename under schemas/.
_SCHEMA_FILE: dict[str, str] = {
    _SCHEMA_ID_BASE: "base-v1.schema.json",
    _SCHEMA_ID_FEATURE: "feature-v1.schema.json",
    _SCHEMA_ID_PROJECT: "project-v1.schema.json",
}


# ---------------------------------------------------------------------------
# Schema file resolution.
# ---------------------------------------------------------------------------


def _schema_dir() -> Path:
    """Return the absolute path to ``schemas/`` at the repo root.

    Resolved relative to *this file* (``src/chopper/config/schema.py``):
    go up 4 levels (config → chopper → src → repo-root) then into
    ``schemas/``.  The path is validated at first call; a missing
    ``schemas/`` directory is a packaging error and raises immediately.
    """
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent.parent  # src/chopper/config/schema.py → repo root
    schemas = repo_root / "schemas"
    if not schemas.is_dir():
        raise RuntimeError(f"schemas/ not found at {schemas}; check the repo layout (schemas/ must sit alongside src/)")
    return schemas


def _load_schema(schema_id: str) -> dict[str, Any]:
    """Load and return the jsonschema dict for the given ``$schema`` id."""
    fname = _SCHEMA_FILE[schema_id]
    schema_path = _schema_dir() / fname
    raw: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    return raw


# Cache compiled validators for the session to avoid re-parsing schema JSON on
# every file.  Each entry is a (schema_dict, Validator) pair.
_VALIDATOR_CACHE: dict[str, Any] = {}


def _get_validator(schema_id: str) -> Any:
    if schema_id not in _VALIDATOR_CACHE:
        raw = _load_schema(schema_id)
        cls = jsonschema.validators.validator_for(raw)
        cls.check_schema(raw)
        _VALIDATOR_CACHE[schema_id] = cls(raw)
    return _VALIDATOR_CACHE[schema_id]


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

DiagnosticEmitter = Callable[[Diagnostic], None]


def validate_json(
    raw: dict[str, Any],
    source_path: Path,
    on_diagnostic: DiagnosticEmitter,
) -> bool:
    """Validate a parsed JSON dict against the inferred Chopper schema.

    :param raw: The already-parsed JSON object (as returned by
        ``json.loads``).
    :param source_path: Domain-relative path of the source file — used
        for diagnostic provenance only.
    :param on_diagnostic: Callback receiving exactly **one**
        :class:`~chopper.core.diagnostics.Diagnostic` on the first
        validation failure.  Never called when the document is valid.
    :returns: ``True`` if the document is valid; ``False`` if a
        diagnostic was emitted (caller must not hydrate the dict).
    """
    schema_id: str | None = raw.get("$schema") if isinstance(raw, dict) else None

    if schema_id not in _KNOWN_SCHEMAS:
        on_diagnostic(
            Diagnostic.build(
                "VE-01",
                phase=Phase.P1_CONFIG,
                message=(f"Unknown or missing $schema: {schema_id!r}. Expected one of: {sorted(_KNOWN_SCHEMAS)}"),
                path=source_path,
                hint='Add "$schema": "base-v1" (or feature-v1 / project-v1 variant)',
            )
        )
        return False

    validator = _get_validator(schema_id)
    errors = sorted(validator.iter_errors(raw), key=lambda e: e.path)  # type: ignore[arg-type]

    if not errors:
        return True

    first = errors[0]
    code = "VE-12" if schema_id == _SCHEMA_ID_PROJECT else "VE-02"

    # Build a concise human-readable message from the jsonschema error.
    path_str = " → ".join(str(p) for p in first.absolute_path) if first.absolute_path else "(root)"
    on_diagnostic(
        Diagnostic.build(
            code,
            phase=Phase.P1_CONFIG,
            message=f"Schema validation failed at {path_str!r}: {first.message}",
            path=source_path,
            hint="Check the JSON authoring guide at technical_docs/JSON_AUTHORING_GUIDE.md",
        )
    )
    return False
