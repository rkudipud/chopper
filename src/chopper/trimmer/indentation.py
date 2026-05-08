"""P5c Tcl indentation normalization.

This module ports the legacy Perl brace-driven formatter into Python and
applies it to emitted ``.tcl`` outputs that Chopper itself rewrote
(``PROC_TRIM``) or synthesized (``GENERATED``) after P5a trim and P5b
generation have written files into the rebuilt domain.

``FULL_COPY`` ``.tcl`` files are intentionally **not** normalized: a
full-copy output is contractually a byte-for-byte copy of the source file
(see issue #22 / `technical_docs/IMPLEMENTATION.md` Pitfall P-44 / P-45).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_trimmer import FileOutcome, GeneratedArtifact, TrimReport

__all__ = ["TclIndentationService", "format_tcl_indentation"]


_TCL_SUFFIX = ".tcl"
_MARKER_LINE = re.compile(r"^\s*((topology|interface|constraint|action):|end|pattern\s+\S+)\s*$")
# FULL_COPY is intentionally excluded: full-copy outputs are byte-for-byte
# copies of the source file (issue #22). Only files that Chopper itself
# rewrote (PROC_TRIM) or synthesized (GENERATED) are normalized.
_NORMALIZED_TREATMENTS = frozenset({FileTreatment.PROC_TRIM, FileTreatment.GENERATED})


@dataclass(frozen=True)
class TclIndentationService:
    """Normalize indentation for final Tcl outputs before P6 validation."""

    tab_space: int = 4

    def run(
        self,
        ctx: ChopperContext,
        manifest: CompiledManifest,
        trim_report: TrimReport,
        artifacts: tuple[GeneratedArtifact, ...],
    ) -> tuple[TrimReport, tuple[GeneratedArtifact, ...], tuple[Path, ...]]:
        """Format final ``.tcl`` outputs and return updated P6 inputs.

        The returned ``TrimReport`` carries final post-format byte counts
        for non-generated Tcl outcomes. Generated Tcl artifacts are updated
        in memory so callers see the same content that was written to disk.
        The path tuple is absolute and is intended for ``validate_post``'s
        ``rewritten`` argument.
        """

        normalized: dict[Path, str] = {}
        rewritten: list[Path] = []
        current_report = trim_report
        current_artifacts = artifacts

        # NOTE: ``_tcl_output_paths`` only yields PROC_TRIM and GENERATED
        # ``.tcl`` paths. FULL_COPY ``.tcl`` outputs are deliberately
        # excluded (issue #22): a full-copy file must reach disk byte-for-byte
        # identical to its source, so the indentation pass must not touch it.
        for rel_path in _tcl_output_paths(manifest):
            target = ctx.config.domain_root / rel_path
            try:
                text = ctx.fs.read_text(target)
                formatted = format_tcl_indentation(text, tab_space=self.tab_space)
                if formatted != text:
                    ctx.fs.write_text(target, formatted)
            except (OSError, UnicodeDecodeError) as exc:
                _emit_ve25(ctx, rel_path, f"Tcl indentation normalization failed: {exc}")
                return _mark_interrupted(current_report), current_artifacts, tuple(rewritten)

            normalized[rel_path] = formatted
            rewritten.append(target)
            current_report = _with_updated_bytes(current_report, normalized)
            current_artifacts = _with_updated_artifacts(current_artifacts, normalized)

        return current_report, current_artifacts, tuple(rewritten)


def format_tcl_indentation(text: str, *, tab_space: int = 4) -> str:
    """Return ``text`` with legacy Perl-style leading whitespace.

    The formatter strips leading whitespace from each line, tracks a
    running indentation level from unescaped Tcl braces, outdents lines
    that begin with a closing brace, and half-outdents selected domain
    marker lines. It always emits LF line endings and terminates non-empty
    files with a final newline, matching the Perl script's print loop.
    """

    if text == "":
        return ""

    indent = 0
    output: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.lstrip()
        flag = 0
        original_indent = indent
        previous = ""
        char = ""
        previous_previous = ""

        for current in line:
            previous_previous = previous
            previous = char
            char = current
            if char == "{" and previous != "\\":
                indent += 1
                if flag == 0:
                    flag -= 1
            elif char == "}" and (previous != "\\" or (previous == "\\" and previous_previous == "\\")):
                indent -= 1
                if flag == 0:
                    flag += 1

        if flag == 1:
            spaces = tab_space * (original_indent - 1)
        elif _MARKER_LINE.match(line):
            spaces = (tab_space * original_indent) - (tab_space // 2)
        else:
            spaces = tab_space * original_indent
        output.append(f"{' ' * max(spaces, 0)}{line}")

    return "\n".join(output) + "\n"


def _tcl_output_paths(manifest: CompiledManifest) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path, treatment in manifest.file_decisions.items()
                if treatment in _NORMALIZED_TREATMENTS and path.suffix.lower() == _TCL_SUFFIX
            ),
            key=lambda path: path.as_posix(),
        )
    )


def _with_updated_bytes(report: TrimReport, normalized: dict[Path, str]) -> TrimReport:
    outcomes: list[FileOutcome] = []
    changed = False
    for outcome in report.outcomes:
        text = normalized.get(outcome.path)
        # Only PROC_TRIM bytes can shift here. FULL_COPY is never normalized
        # (issue #22) and GENERATED bytes flow through ``GeneratedArtifact``,
        # not ``TrimReport.outcomes``.
        if text is None or outcome.treatment is not FileTreatment.PROC_TRIM:
            outcomes.append(outcome)
            continue
        bytes_out = len(text.encode("utf-8"))
        changed = changed or bytes_out != outcome.bytes_out
        outcomes.append(
            FileOutcome(
                path=outcome.path,
                treatment=outcome.treatment,
                bytes_in=outcome.bytes_in,
                bytes_out=bytes_out,
                procs_kept=outcome.procs_kept,
                procs_removed=outcome.procs_removed,
            )
        )
    if not changed:
        return report
    return _build_report(tuple(outcomes), rebuild_interrupted=report.rebuild_interrupted)


def _with_updated_artifacts(
    artifacts: tuple[GeneratedArtifact, ...],
    normalized: dict[Path, str],
) -> tuple[GeneratedArtifact, ...]:
    updated: list[GeneratedArtifact] = []
    changed = False
    for artifact in artifacts:
        text = normalized.get(artifact.path)
        if text is None:
            updated.append(artifact)
            continue
        changed = changed or text != artifact.content
        updated.append(
            GeneratedArtifact(
                path=artifact.path,
                kind=artifact.kind,
                content=text,
                source_stage=artifact.source_stage,
            )
        )
    return tuple(updated) if changed else artifacts


def _mark_interrupted(report: TrimReport) -> TrimReport:
    if report.rebuild_interrupted:
        return report
    return _build_report(report.outcomes, rebuild_interrupted=True)


def _build_report(outcomes: tuple[FileOutcome, ...], *, rebuild_interrupted: bool) -> TrimReport:
    return TrimReport(
        outcomes=outcomes,
        files_copied=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.REMOVE),
        procs_kept_total=sum(len(outcome.procs_kept) for outcome in outcomes),
        procs_removed_total=sum(len(outcome.procs_removed) for outcome in outcomes),
        rebuild_interrupted=rebuild_interrupted,
    )


def _emit_ve25(ctx: ChopperContext, rel_path: Path, detail: str) -> None:
    ctx.diag.emit(
        Diagnostic.build(
            "VE-25",
            phase=Phase.P5_TRIM,
            message=f"Failed to write {rel_path.as_posix()!r} into rebuilt domain: {detail}",
            hint="Inspect the rebuilt Tcl file; partial domain will rebuild from backup on re-run",
        )
    )
