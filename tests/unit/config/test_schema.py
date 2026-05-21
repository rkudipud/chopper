"""Unit tests for :mod:`chopper.config.schema` — JSON schema validation."""

from __future__ import annotations

from pathlib import Path

from chopper.config.schema import validate_json
from chopper.core.diagnostics import Diagnostic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect(raw: dict, path: Path = Path("test.json")) -> list[Diagnostic]:
    emitted: list[Diagnostic] = []
    validate_json(raw, path, emitted.append)
    return emitted


def _valid(raw: dict, path: Path = Path("test.json")) -> bool:
    return validate_json(raw, path, lambda _: None)


# ---------------------------------------------------------------------------
# Base JSON schema
# ---------------------------------------------------------------------------


class TestBaseSchema:
    def test_minimal_valid_files(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "my_domain",
            "files": {"include": ["setup.tcl"]},
        }
        assert _valid(doc)

    def test_minimal_valid_procedures(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "my_domain",
            "procedures": {"include": [{"file": "a.tcl", "procs": ["foo"]}]},
        }
        assert _valid(doc)

    def test_minimal_valid_stages(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "my_domain",
            "stages": [{"name": "setup", "load_from": "", "steps": ["source setup.tcl"]}],
        }
        assert _valid(doc)

    def test_missing_domain(self) -> None:
        doc = {
            "$schema": "base-v1",
            "files": {"include": ["setup.tcl"]},
        }
        diags = _collect(doc)
        assert len(diags) == 1
        assert diags[0].code == "VE-02"

    def test_no_capability_block(self) -> None:
        # anyOf fails: at least one of files/procedures/stages required
        doc = {"$schema": "base-v1", "domain": "d"}
        diags = _collect(doc)
        assert len(diags) == 1
        assert diags[0].code == "VE-02"

    def test_additional_property_rejected(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["a.tcl"]},
            "unexpected_field": True,
        }
        diags = _collect(doc)
        assert len(diags) == 1
        assert diags[0].code == "VE-02"

    def test_empty_files_include_rejected(self) -> None:
        # minItems: 1 on files.include
        doc = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": []},
        }
        diags = _collect(doc)
        assert len(diags) == 1
        assert diags[0].code == "VE-02"

    def test_path_traversal_rejected(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["../etc/passwd"]},
        }
        diags = _collect(doc)
        assert diags[0].code == "VE-02"

    def test_absolute_path_rejected(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "d",
            "files": {"include": ["/abs/path.tcl"]},
        }
        diags = _collect(doc)
        assert diags[0].code == "VE-02"

    def test_full_base_valid(self) -> None:
        doc = {
            "$schema": "base-v1",
            "domain": "my_domain",
            "owner": "team",
            "vendor": "synopsys",
            "tool": "pt",
            "description": "desc",
            "options": {"cross_validate": False},
            "files": {"include": ["setup.tcl"], "exclude": ["legacy.tcl"]},
            "procedures": {
                "include": [{"file": "a.tcl", "procs": ["foo"]}],
                "exclude": [{"file": "b.tcl", "procs": ["bar"]}],
            },
            "stages": [{"name": "s1", "load_from": "", "steps": ["step1"]}],
        }
        assert _valid(doc)

    def test_only_one_diagnostic_emitted_per_file(self) -> None:
        # Multiple schema errors — only the first should be forwarded.
        doc = {"$schema": "base-v1"}  # missing domain AND no capability block
        diags = _collect(doc)
        assert len(diags) == 1


# ---------------------------------------------------------------------------
# Feature JSON schema
# ---------------------------------------------------------------------------


class TestFeatureSchema:
    def test_minimal_valid(self) -> None:
        doc = {"$schema": "feature-v1", "name": "dft"}
        assert _valid(doc)

    def test_missing_name(self) -> None:
        doc = {"$schema": "feature-v1"}
        diags = _collect(doc)
        assert diags[0].code == "VE-02"

    def test_full_feature_valid(self) -> None:
        doc = {
            "$schema": "feature-v1",
            "name": "dft",
            "domain": "my_domain",
            "description": "DFT feature",
            "depends_on": ["base_feature"],
            "metadata": {
                "owner": "team",
                "tags": ["dft"],
                "wiki": "https://wiki.example.com",
            },
            "files": {"include": ["procs/dft.tcl"]},
            "procedures": {
                "include": [{"file": "procs/dft.tcl", "procs": ["setup_scan"]}],
            },
            "flow_actions": [
                {
                    "action": "add_stage_after",
                    "name": "dft_check",
                    "reference": "main",
                    "load_from": "main",
                    "steps": ["setup_scan"],
                }
            ],
        }
        assert _valid(doc)

    def test_invalid_flow_action(self) -> None:
        doc = {
            "$schema": "feature-v1",
            "name": "x",
            "flow_actions": [{"action": "teleport", "stage": "s", "reference": "r", "items": ["i"]}],
        }
        diags = _collect(doc)
        assert diags[0].code == "VE-02"


# ---------------------------------------------------------------------------
# Project JSON schema
# ---------------------------------------------------------------------------


class TestProjectSchema:
    def test_minimal_valid(self) -> None:
        doc = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "base": "jsons/base.json",
        }
        assert _valid(doc)

    def test_missing_base(self) -> None:
        doc = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
        }
        diags = _collect(doc)
        assert diags[0].code == "VE-12"

    def test_base_path_traversal_rejected(self) -> None:
        doc = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "base": "../outside/base.json",
        }
        diags = _collect(doc)
        assert diags[0].code == "VE-12"

    def test_full_project_valid(self) -> None:
        doc = {
            "$schema": "project-v1",
            "project": "P",
            "domain": "d",
            "owner": "team",
            "base": "jsons/base.json",
            "features": ["jsons/features/dft.json"],
            "notes": ["DFT after main"],
        }
        assert _valid(doc)


# ---------------------------------------------------------------------------
# Missing / unknown $schema
# ---------------------------------------------------------------------------


class TestUnknownSchema:
    def test_missing_schema_field(self) -> None:
        doc = {"domain": "d", "files": {"include": ["a.tcl"]}}
        diags = _collect(doc)
        assert diags[0].code == "VE-01"

    def test_unknown_schema_id(self) -> None:
        doc = {"$schema": "chopper/base/v999", "domain": "d"}
        diags = _collect(doc)
        assert diags[0].code == "VE-01"

    def test_non_dict_input(self) -> None:
        diags = _collect([1, 2, 3])  # type: ignore[arg-type]
        assert diags[0].code == "VE-01"

    def test_diagnostic_carries_source_path(self) -> None:
        path = Path("jsons/base.json")
        diags = _collect({"$schema": "base-v1"}, path=path)
        assert diags[0].path == path
