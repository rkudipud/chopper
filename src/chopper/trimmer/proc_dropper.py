"""Atomic proc-annotate-and-drop algorithm.

:func:`annotate_procs` rewrites a Tcl file's text so every proc known to
the file -- surviving or removed -- carries a Sec.3.11 provenance
comment-marker pair (``## CHOPPER: BEGIN/END ...``). A surviving proc's
span (body plus any associated ``define_proc_attributes`` block and
comment banner, merged into the minimum enclosing range) is wrapped in
place; a removed proc's span is replaced with an empty marker pair (the
body is still fully deleted -- only the two-line marker remains).

Ranges are applied **bottom-up** (descending by start line) so
not-yet-processed procs' 1-indexed line coordinates stay valid during
the rewrite. Proc spans must not overlap; an overlapping or
out-of-window span indicates stale parser output and raises
:class:`ProcDropError`, which the caller translates to a ``VE-26``
diagnostic.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from chopper.core.models_parser import ProcEntry
from chopper.core.provenance_markers import marker_pair

__all__ = ["ProcDropError", "annotate_procs"]


class ProcDropError(ValueError):
    """Proc span is outside the file's line window, or overlaps another span. Trimmer emits ``VE-26``."""


@dataclass(frozen=True)
class _Range:
    start: int  # 1-indexed, inclusive
    end: int  # 1-indexed, inclusive


def _span_for(proc: ProcEntry) -> _Range:
    """Return the minimum enclosing span for ``proc``."""

    starts = [proc.start_line]
    ends = [proc.end_line]
    if proc.dpa_start_line is not None and proc.dpa_end_line is not None:
        starts.append(proc.dpa_start_line)
        ends.append(proc.dpa_end_line)
    if proc.comment_start_line is not None and proc.comment_end_line is not None:
        starts.append(proc.comment_start_line)
        ends.append(proc.comment_end_line)
    return _Range(start=min(starts), end=max(ends))


def annotate_procs(
    text: str,
    kept: Iterable[ProcEntry],
    dropped: Iterable[ProcEntry],
    source_of: Callable[[str], str],
) -> str:
    """Return ``text`` with every proc in ``kept`` and ``dropped`` wrapped in a provenance marker.

    ``source_of(canonical_name)`` returns the marker's ``source=`` value
    (``"base"``, ``"feature:<name>"``, or ``"default"``) for that proc.

    Lines are split on the platform-neutral ``"\\n"`` delimiter and
    rejoined with the same character. A trailing newline on the input
    is preserved iff at least one line remains after the rewrite; an
    empty result (every line deleted) returns the empty string.

    Raises
    ------
    ProcDropError
        If any span falls outside ``[1, len(lines)]``, or two spans overlap.
    """

    kept_list = list(kept)
    dropped_list = list(dropped)
    if not kept_list and not dropped_list:
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

    units: list[tuple[_Range, Literal["kept", "removed"], ProcEntry]] = [
        *((_span_for(proc), "kept", proc) for proc in kept_list),
        *((_span_for(proc), "removed", proc) for proc in dropped_list),
    ]

    for rng, _kind, _proc in units:
        if rng.start < 1 or rng.end > len(lines):
            raise ProcDropError(f"Proc span [{rng.start}, {rng.end}] escapes file window [1, {len(lines)}]")

    units.sort(key=lambda u: u[0].start)
    for prev_unit, cur_unit in zip(units, units[1:], strict=False):
        if cur_unit[0].start <= prev_unit[0].end:
            raise ProcDropError(
                f"Overlapping proc spans: [{prev_unit[0].start}, {prev_unit[0].end}] and "
                f"[{cur_unit[0].start}, {cur_unit[0].end}]"
            )

    # Apply descending-order rewrite (bottom-up) to preserve line coords
    # of not-yet-processed spans while we iterate.
    for rng, kind, proc in sorted(units, key=lambda u: u[0].start, reverse=True):
        begin, end = marker_pair(action=kind, kind="proc", name=proc.short_name, source=source_of(proc.canonical_name))
        replacement = [begin, end] if kind == "removed" else [begin, *lines[rng.start - 1 : rng.end], end]
        lines[rng.start - 1 : rng.end] = replacement

    # Every unit contributes at least a two-line marker pair, so ``lines``
    # is never empty here (unlike the old pure-deletion drop_procs, which
    # could delete every line and legitimately return "").
    result = "\n".join(lines)
    if had_trailing_newline:
        result += "\n"
    return result
