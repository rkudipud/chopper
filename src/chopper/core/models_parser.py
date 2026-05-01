"""Parser-phase model records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

__all__ = ["ParseResult", "ParsedFile", "ProcEntry"]


@dataclass(frozen=True)
class ProcEntry:
    """One Tcl proc definition extracted by :func:`chopper.parser.parse_file`."""

    canonical_name: str
    short_name: str
    qualified_name: str
    source_file: Path
    start_line: int
    end_line: int
    body_start_line: int
    body_end_line: int
    namespace_path: str
    calls: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    dpa_start_line: int | None = None
    dpa_end_line: int | None = None
    comment_start_line: int | None = None
    comment_end_line: int | None = None

    def __post_init__(self) -> None:  # noqa: C901 — invariants live together
        for name in ("start_line", "end_line", "body_start_line", "body_end_line"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"ProcEntry.{name} must be a positive 1-indexed int, got {value!r}")
        if self.start_line > self.end_line:
            raise ValueError(f"ProcEntry.start_line ({self.start_line}) must be <= end_line ({self.end_line})")

        if not (self.start_line <= self.body_start_line <= self.end_line):
            raise ValueError(
                f"ProcEntry.body_start_line ({self.body_start_line}) must be in [{self.start_line}, {self.end_line}]"
            )
        if not (self.start_line <= self.body_end_line <= self.end_line):
            raise ValueError(
                f"ProcEntry.body_end_line ({self.body_end_line}) must be in [{self.start_line}, {self.end_line}]"
            )

        for first, last, label in (
            (self.dpa_start_line, self.dpa_end_line, "dpa"),
            (self.comment_start_line, self.comment_end_line, "comment"),
        ):
            if (first is None) != (last is None):
                raise ValueError(f"ProcEntry {label}_start_line and {label}_end_line must both be set or both None")
            if first is not None and last is not None:
                if first < 1 or last < 1:
                    raise ValueError(f"ProcEntry {label} span must be 1-indexed positive ints")
                if first > last:
                    raise ValueError(f"ProcEntry {label}_start_line ({first}) must be <= {label}_end_line ({last})")

        expected = f"{self.source_file.as_posix()}::{self.qualified_name}"
        if self.canonical_name != expected:
            raise ValueError(
                f"ProcEntry.canonical_name {self.canonical_name!r} does not match "
                f"'<source_file.as_posix()>::<qualified_name>' = {expected!r}"
            )

        if list(self.calls) != sorted(set(self.calls)):
            raise ValueError("ProcEntry.calls must be deduplicated and lexicographically sorted")


@dataclass(frozen=True)
class ParsedFile:
    """Per-file aggregate returned by ``ParserService`` for one Tcl file."""

    path: Path
    procs: tuple[ProcEntry, ...]
    encoding: Literal["utf-8", "latin-1"]

    def __post_init__(self) -> None:
        starts = [p.start_line for p in self.procs]
        if starts != sorted(starts):
            raise ValueError("ParsedFile.procs must be sorted by start_line")
        for proc in self.procs:
            if proc.source_file != self.path:
                raise ValueError(
                    f"ProcEntry.source_file ({proc.source_file!r}) does not match ParsedFile.path ({self.path!r})"
                )


@dataclass(frozen=True)
class ParseResult:
    """Domain-wide parser output with a full-domain canonical-name index."""

    files: dict[Path, ParsedFile] = field(default_factory=dict)
    index: dict[str, ProcEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from_files: dict[str, ProcEntry] = {}
        for parsed in self.files.values():
            for proc in parsed.procs:
                if proc.canonical_name in from_files:
                    raise ValueError(f"ParseResult: duplicate canonical_name across files: {proc.canonical_name!r}")
                from_files[proc.canonical_name] = proc
        missing = set(from_files) - set(self.index)
        if missing:
            raise ValueError(f"ParseResult.index is missing entries listed in ParseResult.files: {sorted(missing)!r}")
        for cn, proc in from_files.items():
            if self.index[cn] is not proc:
                raise ValueError(
                    f"ParseResult.index[{cn!r}] does not refer to the same ProcEntry instance as files view"
                )

        if list(self.index.keys()) != sorted(self.index.keys()):
            raise ValueError("ParseResult.index keys must be lexicographically sorted")
