"""Chopper core: shared dataclasses, protocols, errors, diagnostics, context.

This package is the only module that may be imported by every sibling
service. It never imports from any sibling (enforced by `import-linter`).
"""

from __future__ import annotations
