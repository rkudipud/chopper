"""Per-file coverage tests for src/chopper/config/loaders.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from pathlib import Path


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_load_procedures_section_exclude_with_procs_appends() -> None:
    """_load_procedures_section appends a non-empty exclude entry (line 108)."""
    from chopper.config.loaders import _load_procedures_section

    diags: list = []
    raw = {
        "include": [],
        "exclude": [{"file": "lib.tcl", "procs": ["foo", "bar"]}],
    }
    result = _load_procedures_section(raw, Path("base.json"), diags.append)
    assert len(result.exclude) == 1
    assert result.exclude[0].file == Path("lib.tcl")
    assert "foo" in result.exclude[0].procs
