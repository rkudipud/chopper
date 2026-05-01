"""Atomic proc-drop algorithm.

:func:`drop_procs` rewrites a Tcl file's text with target procs removed.
Each drop range spans the proc body plus any associated
``define_proc_attributes`` block and comment banner (merged into the
minimum enclosing range). Ranges are applied **bottom-up** (descending
by start line) so remaining procs' 1-indexed line coordinates stay
valid during the rewrite.

Overlapping ranges are merged before deletion. A drop range that
escapes the ``[1, len(lines)]`` window indicates stale parser output
and raises :class:`ProcDropError`; the caller translates this to a
``VE-26`` diagnostic.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chopper.core.models_parser import ProcEntry

__all__ = ["ProcDropError", "drop_procs"]


class ProcDropError(ValueError):
    """Drop range is outside the file's line window. Trimmer emits ``VE-26``."""


@dataclass(frozen=True)
class _Range:
    start: int  # 1-indexed, inclusive
    end: int  # 1-indexed, inclusive


def _span_for(proc: ProcEntry) -> _Range:
    """Return the minimum enclosing drop range for ``proc``."""

    starts = [proc.start_line]
    ends = [proc.end_line]
    if proc.dpa_start_line is not None and proc.dpa_end_line is not None:
        starts.append(proc.dpa_start_line)
        ends.append(proc.dpa_end_line)
    if proc.comment_start_line is not None and proc.comment_end_line is not None:
        starts.append(proc.comment_start_line)
        ends.append(proc.comment_end_line)
    return _Range(start=min(starts), end=max(ends))


def _merge_overlaps(ranges: list[_Range]) -> list[_Range]:
    """Merge touching or overlapping ranges. Input may be unsorted."""

    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: (r.start, r.end))
    merged: list[_Range] = [sorted_ranges[0]]
    for current in sorted_ranges[1:]:
        last = merged[-1]
        # Adjacent (current.start == last.end + 1) counts as overlap so
        # consecutive proc drops do not leave a single-line gap behind.
        if current.start <= last.end + 1:
            merged[-1] = _Range(start=last.start, end=max(last.end, current.end))
        else:
            merged.append(current)
    return merged


def drop_procs(text: str, procs_to_drop: Iterable[ProcEntry]) -> str:
    """Return ``text`` with every proc in ``procs_to_drop`` deleted.

    Lines are split on the platform-neutral ``"\\n"`` delimiter and
    rejoined with the same character. A trailing newline on the input
    is preserved iff at least one line remains after deletion; an empty
    result (every line deleted) returns the empty string.

    Raises
    ------
    ProcDropError
        If any drop range falls outside ``[1, len(lines)]``.
    """

    procs = list(procs_to_drop)
    if not procs:
        return text

    # Split preserving the final-newline signal.
    had_trailing_newline = text.endswith("\n")
    # splitlines() drops the trailing empty element; we want explicit control.
    if text == "":
        lines: list[str] = []
    else:
        raw = text.split("\n")
        # If the text ends with "\n", split produces a trailing empty string we don't want.
        if had_trailing_newline:
            raw = raw[:-1]
        lines = raw

    ranges = [_span_for(p) for p in procs]
    ranges = _merge_overlaps(ranges)

    for rng in ranges:
        if rng.start < 1 or rng.end > len(lines):
            raise ProcDropError(f"Drop range [{rng.start}, {rng.end}] escapes file window [1, {len(lines)}]")

    # Apply descending-order deletion (bottom-up) to preserve line coords
    # of lower-numbered ranges while we iterate.
    for rng in sorted(ranges, key=lambda r: r.start, reverse=True):
        del lines[rng.start - 1 : rng.end]

    if not lines:
        return ""
    result = "\n".join(lines)
    if had_trailing_newline:
        result += "\n"
    return result
