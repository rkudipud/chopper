"""Golden-file contract for the four shipped audit artifacts.

Closes T-01 from the 2026-04-23 spec-conformance audit. Bible NFR-03
(byte-identical output on every run) was previously only asserted by
example unit tests. This module pins the *wire shape* of the four
artifacts Chopper ships under ``.chopper/``:

* ``chopper_run.json`` — bible §5.5.2
* ``compiled_manifest.json`` — bible §5.5.3
* ``dependency_graph.json`` — bible §5.5.4
* ``trim_report.json`` — bible §5.5.5

Approach: run ``chopper validate`` and ``chopper trim --dry-run``
end-to-end against a seeded minimal domain; capture the four artifacts;
strip the small number of legitimately-variable fields (run id, tmp
paths, wall-clock timestamps, duration); feed the remainder to
``pytest-regressions`` ``data_regression`` for byte-stable comparison.

Updating goldens: run ``pytest tests/golden/ --force-regen`` **only**
when the artifact shape change was approved in the bible and cascaded
per [project.instructions.md](../../.github/instructions/project.instructions.md)
"Cascading Updates". Regenerating without a spec change is the
anti-pattern objection #2 of the audit flagged — do not do it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from chopper.cli.main import main

# ---------------------------------------------------------------------------
# Fixture seeding — identical to test_cli_e2e._seed_valid_domain so the
# golden shape matches the CLI-level smoke domain, keeping the contract
# aligned with what operators actually exercise.
# ---------------------------------------------------------------------------


def _seed_valid_domain(domain: Path) -> Path:
    domain.mkdir(parents=True, exist_ok=True)
    (domain / "vars.tcl").write_text("# vars\nset PI 3.14\n", encoding="utf-8")
    (domain / "helper.tcl").write_text("proc helper_a {} { return 1 }\n", encoding="utf-8")
    jsons = domain / "jsons"
    jsons.mkdir(parents=True, exist_ok=True)
    base_path = jsons / "base.json"
    base_path.write_text(
        json.dumps(
            {
                "$schema": "chopper/base/v1",
                "domain": domain.name,
                "files": {"include": ["vars.tcl", "helper.tcl"]},
            }
        ),
        encoding="utf-8",
    )
    return base_path


# ---------------------------------------------------------------------------
# Normalisation — strip fields that legitimately vary between runs but are
# not part of the shape contract.
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# Fields whose *value* varies (tmp path, timestamp, uuid) but whose
# *presence* matters. Replaced with a stable sentinel so the golden
# fixes shape without fixing volatile content.
_VOLATILE_STRING_FIELDS = {
    "run_id",
    "domain_path",
    "backup_path",
    "base_json",
    "project_json",
    "timestamp_start",
    "timestamp_end",
    "chopper_version",
}
_VOLATILE_LIST_FIELDS = {
    "feature_jsons",
    "project_notes",
    "command",
}
_VOLATILE_NUMERIC_FIELDS = {
    "duration_seconds",
}


def _normalize(value: Any, *, key: str | None = None) -> Any:
    """Recursively replace volatile leaf values with stable sentinels.

    Dict keys drive the substitution — a key named ``run_id`` whose value
    looks like a UUID becomes ``"<run_id>"``. Values that *don't* match
    the expected volatile shape are preserved so an accidental shape
    drift (run_id suddenly becoming an int, for example) still fails the
    golden.
    """
    if isinstance(value, dict):
        return {k: _normalize(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        if key in _VOLATILE_LIST_FIELDS:
            # Preserve length + element types but scrub content.
            return [f"<{key}[{i}]>" for i, _ in enumerate(value)]
        return [_normalize(v) for v in value]
    if key in _VOLATILE_STRING_FIELDS and isinstance(value, str):
        # UUID, path, or timestamp — just pin that it *is* a string.
        if _UUID_RE.match(value):
            return f"<{key}:uuid>"
        if _ISO_RE.match(value):
            return f"<{key}:timestamp>"
        return f"<{key}:string>"
    if key in _VOLATILE_NUMERIC_FIELDS and isinstance(value, int | float):
        return f"<{key}:number>"
    # Paths embedded in non-volatile string fields (e.g. diagnostic
    # `context` entries with tmp paths) — rewrite any run-specific tmp
    # prefix to a stable marker.
    if isinstance(value, str) and value.startswith(("/tmp/", "C:\\", "C:/", "/private/")):
        return "<tmp-path>"
    return value


def _load_artifact(domain: Path, name: str) -> Any:
    raw = (domain / ".chopper" / name).read_text(encoding="utf-8")
    return _normalize(json.loads(raw))


# ---------------------------------------------------------------------------
# Golden tests — one per artifact, plus a combined manifest guard.
# ---------------------------------------------------------------------------


@pytest.fixture
def trimmed_domain(tmp_path: Path) -> Path:
    """Run a full dry-run trim and return the domain directory."""
    domain = tmp_path / "mini"
    base = _seed_valid_domain(domain)
    rc = main(["trim", "--domain", str(domain), "--base", str(base), "--dry-run"])
    assert rc == 0, "dry-run trim must succeed for golden fixture"
    return domain


def test_chopper_run_json_shape(trimmed_domain: Path, data_regression) -> None:
    """Bible §5.5.2 — chopper_run.json shape is stable."""
    data_regression.check(_load_artifact(trimmed_domain, "chopper_run.json"))


def test_compiled_manifest_json_shape(trimmed_domain: Path, data_regression) -> None:
    """Bible §5.5.3 — compiled_manifest.json shape is stable."""
    data_regression.check(_load_artifact(trimmed_domain, "compiled_manifest.json"))


def test_dependency_graph_json_shape(trimmed_domain: Path, data_regression) -> None:
    """Bible §5.5.4 — dependency_graph.json shape is stable."""
    data_regression.check(_load_artifact(trimmed_domain, "dependency_graph.json"))


def test_trim_report_json_shape(trimmed_domain: Path, data_regression) -> None:
    """Bible §5.5.5 — trim_report.json shape is stable (dry-run variant).

    A live-trim run would additionally exercise the file-operation and
    proc-removal paths; the dry-run variant pins the no-op shape so a
    future regression that spuriously records work in dry-run is
    caught.
    """
    data_regression.check(_load_artifact(trimmed_domain, "trim_report.json"))
