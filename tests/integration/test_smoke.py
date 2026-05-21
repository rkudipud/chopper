"""Baseline smoke checks that keep the documented integration target live."""

from __future__ import annotations

import chopper
from tests.integration.crash_harness import TRANSITION_POINTS


def test_crash_harness_declares_expected_transition_points() -> None:
    assert chopper.__version__
    assert len(TRANSITION_POINTS) == 5
    assert "after_backup_created" in TRANSITION_POINTS
