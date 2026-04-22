"""Chopper core: shared dataclasses, protocols, errors, diagnostics, context.

Per bible §5.12.1 and ARCHITECTURE_PLAN.md §9, this package is the only module
that may be imported by every sibling service. It never imports from any
sibling (enforced by `import-linter`).
"""

from __future__ import annotations
