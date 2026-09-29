"""Per-file coverage tests for src/chopper/core/header.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

import pytest

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
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


# ---------------------------------------------------------------------------
# needs_header -- header-injection test vectors (ARCHITECTURE.md Sec.6.6.1, issue #30)
# ---------------------------------------------------------------------------

_INTEL_HEADED_BODY = (
    "####################################################################################################",
    "#Intel Legal compliant copyright header",
    "####################################################################################################",
    "#-- INTEL CONFIDENTIAL",
    "#-- Copyright (c) 2025 Intel Corporation",
    "####################################################################################################",
    "source setup.tcl",
)


@pytest.mark.parametrize(
    ("filename", "body", "expected"),
    [
        # Plain bodies in '#'-comment output types get the header.
        ("stage.tcl", ("source setup.tcl", "load_design"), True),
        ("stage.stack", ("N eco", "J -tool x", "D"), True),
        ("stage.TCL", ("puts hi",), True),
        ("stage.py", ("print('hi')",), True),
        ("stage.csh", ("echo hi",), True),
        # Line-1 shebang: the body owns its header (issue #30).
        ("stage.tcl", ("#!/bin/sh", "# restart under tclsh \\", 'exec tclsh "$0" "$@"'), False),
        ("stage.tcl", ("#!/usr/bin/env tclsh", "puts hi"), False),
        ("stage.stack", ("#!/bin/csh -f", "echo hi"), False),
        # Only line 1 is a shebang position.
        ("stage.tcl", ("", "#!/bin/sh", "puts hi"), True),
        ("stage.tcl", (" #!/bin/sh", "puts hi"), True),
        # Copyright notice in the leading comment block: no second header.
        ("stage.tcl", _INTEL_HEADED_BODY, False),
        ("stage.tcl", ("# Copyright 2019-2024 Synopsys, Inc.", "puts hi"), False),
        ("stage.tcl", ("", "# (C) Copyright IBM Corp.", "puts hi"), False),
        ("stage.stack", ("# COPYRIGHT (c) Intel", "N eco", "D"), False),
        # Not a notice: the word alone, a derived word, or a notice after code.
        ("stage.tcl", ("# scan sources for copyright headers", "run_scan"), True),
        ("stage.tcl", ("# Intel copyrighted materials, 2025", "puts hi"), True),
        ("stage.tcl", ("source setup.tcl", "# Copyright (c) 2025 Intel Corporation"), True),
        ("stage.tcl", ("#", "# notes only", "#"), True),
        # Output types without '#' comments are never corrupted with one.
        ("stage.json", ("puts hi",), False),
        ("notes.txt", ("hello",), False),
    ],
)
def test_needs_header_vectors(filename: str, body: tuple[str, ...], expected: bool) -> None:
    from pathlib import Path

    from chopper.core.header import needs_header

    assert needs_header(Path(filename), body) is expected


def test_needs_header_is_false_for_chopper_generated_output() -> None:
    """Regenerating a stage from a file Chopper already stamped must not stack a second header."""
    from pathlib import Path

    from chopper.core.header import intel_header_lines, needs_header

    body = (*intel_header_lines(), "# Chopper-generated stage: setup", "source setup.tcl")
    assert needs_header(Path("setup.tcl"), body) is False
