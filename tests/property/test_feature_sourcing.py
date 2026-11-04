"""Property checks for v2 feature-vars expansion and emission."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from hypothesis import given, settings
from hypothesis import strategies as st

from chopper.config.service import expand_vars_entry
from chopper.generators.vars_emitter import emit_feature_vars

_SEGMENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_PATH = st.lists(_SEGMENT, min_size=1, max_size=4).map(lambda parts: "/".join(parts) + ".tcl")


@settings(max_examples=500)
@given(entry=_PATH)
def test_pointer_expansion_preserves_parent_and_prefixes_only_basename(entry: str) -> None:
    expanded = expand_vars_entry(entry)
    original = PurePosixPath(entry)
    assert expanded[0] == entry
    assert [PurePosixPath(path).parent for path in expanded] == [original.parent] * 3
    assert [PurePosixPath(path).name for path in expanded] == [
        original.name,
        f"tech_{original.name}",
        f"project_{original.name}",
    ]


@settings(max_examples=500)
@given(flow=_SEGMENT, entries=st.lists(_PATH, max_size=5, unique=True))
def test_emitter_keeps_block_order_and_emits_exactly_three_optional_lines(flow: str, entries: list[str]) -> None:
    blocks = tuple(expand_vars_entry(entry) for entry in entries)
    artifact = emit_feature_vars(flow, blocks)
    assert artifact.path == Path(f"{flow}_feature_vars.tcl")
    assert f"# Feature vars.tcl sourcing file for {flow}\n" in artifact.content
    assert [line for line in artifact.content.splitlines() if line.startswith("iproc_source ")] == [
        f"iproc_source -file {entry} -optional" for block in blocks for entry in block
    ]
    assert emit_feature_vars(flow, blocks) == artifact
