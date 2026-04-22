"""Content hashing for audit artifacts.

Bible §5.5.11 requires every JSON artifact be serialised deterministically;
the sha256 hash produced here is the byte-stability check the audit bundle
records for each written file.
"""

from __future__ import annotations

import hashlib

__all__ = ["sha256_hex"]


def sha256_hex(content: str) -> str:
    """Return the SHA-256 hex digest of ``content`` encoded as UTF-8."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()
