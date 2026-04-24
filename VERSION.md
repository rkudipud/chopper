# Chopper Version

This file is the canonical location for product release naming and release-number communication.

## Current Release

| Field | Value |
| --- | --- |
| Product name | Chopper |
| Release channel | Stable |
| Release version | 0.3.0 |
| Release date | 2026-04-24 |

## Version-Carrying Files

The current release number is intentionally repeated only where the tool or packaging metadata requires it:

- `VERSION.txt` (machine-readable release-number file at repo root; first line is the bare version string)
- `pyproject.toml`
- `src/chopper/__init__.py`
- `src/chopper/audit/writers.py`
- generated packaging metadata such as `src/chopper.egg-info/PKG-INFO`

## Versioning Rules

- Narrative docs refer to the product as **Chopper**.
- Concrete release numbers do not appear in narrative docs.
- Schema identifiers such as `chopper/base/v1` remain unchanged because they are configuration contract strings, not product branding.
