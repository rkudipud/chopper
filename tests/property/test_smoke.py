"""Baseline Hypothesis smoke checks for the property-test target."""

from __future__ import annotations

from pathlib import PurePosixPath

from hypothesis import given
from hypothesis import strategies as st

import chopper

SEGMENT = st.from_regex(r"[a-z0-9_]+", fullmatch=True)


@given(st.lists(SEGMENT, min_size=1, max_size=4))
def test_generated_repo_paths_remain_posix(segments: list[str]) -> None:
    assert chopper.__version__
    assert "\\" not in PurePosixPath(*segments).as_posix()
