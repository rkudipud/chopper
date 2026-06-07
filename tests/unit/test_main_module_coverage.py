"""Per-file coverage tests for src/chopper/__main__.py.

Redistributed from the omnibus ``tests/unit/test_coverage_99.py``;
``__main__.py`` is the only top-level module in ``src/chopper/`` so it
gets its own fleet file in ``tests/unit/`` rather than in any
sub-package directory.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_main_module_entry_point_invokes_main_and_exits() -> None:
    """__main__.py calls main() and wraps the result in SystemExit.

    Per ARCHITECTURE.md Sec.5.1 the chopper CLI must be runnable as
    ``python -m chopper``.  The module-level ``raise SystemExit(main())``
    pattern is the standard Python idiom for this.
    """
    sys.modules.pop("chopper.__main__", None)
    with patch("chopper.cli.main.main", return_value=0) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            import chopper.__main__  # noqa: F401
        assert exc_info.value.code == 0
        mock_main.assert_called_once()
    sys.modules.pop("chopper.__main__", None)
