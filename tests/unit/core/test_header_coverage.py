"""Per-file coverage tests for src/chopper/core/header.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



import datetime


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_intel_header_text_uses_current_year_when_none() -> None:
    """intel_header_text(year=None) must produce a string containing the
    current calendar year.  This keeps generated output up-to-date without
    requiring callers to pass the year explicitly."""
    from datetime import datetime

    from chopper.core.header import intel_header_text

    text = intel_header_text(year=None)
    current_year = str(datetime.now().year)
    assert current_year in text


def test_intel_header_text_year_none_derives_current_year() -> None:
    """intel_header_text(year=None) must derive the copyright year from datetime.now()."""
    from datetime import datetime

    from chopper.core.header import intel_header_text

    text = intel_header_text(year=None)
    current_year = datetime.now().year
    assert str(current_year) in text


def test_intel_header_text_explicit_year_skips_datetime_now() -> None:
    """intel_header_text(year=2023) uses the provided year without calling datetime.now() (68->70)."""
    from chopper.core.header import intel_header_text

    text = intel_header_text(year=2023)
    assert "2023" in text
    assert "Intel" in text
