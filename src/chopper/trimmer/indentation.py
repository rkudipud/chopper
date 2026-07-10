"""P5c Tcl indentation normalization.

Applies a brace-driven indentation pass to emitted ``.tcl`` outputs
that Chopper itself rewrote (``PROC_TRIM``) or synthesized
(``GENERATED``) after P5a trim and P5b generation have written files
into the rebuilt domain.

``FULL_COPY`` ``.tcl`` files are intentionally **not** normalized: a
full-copy output is contractually a byte-for-byte copy of the source
file (see issue #22 / `technical_docs/IMPLEMENTATION.md` Pitfall P-44
/ P-45).
"""

from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from pathlib import Path

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest
from chopper.core.models_trimmer import FileOutcome, GeneratedArtifact, P4CheckoutResult, TrimReport

__all__ = ["TclIndentationService", "format_tcl_indentation", "tcl_output_paths"]


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
        *,
        enabled: bool = True,
    ) -> tuple[TrimReport, tuple[GeneratedArtifact, ...], tuple[Path, ...]]:
        """Format final ``.tcl`` outputs and return updated P6 inputs.

        The returned ``TrimReport`` carries final post-format byte counts
        for non-generated Tcl outcomes. Generated Tcl artifacts are updated
        in memory so callers see the same content that was written to disk.
        The path tuple is absolute and is intended for ``validate_post``'s
        ``rewritten`` argument.

        When ``enabled`` is ``False`` (the default for ``base.options.indent``
        is ``false``), the formatter is skipped entirely: ``trim_report`` and
        ``artifacts`` pass through unchanged, but the rewritten-path tuple is
        still computed so P6's brace-balance check runs over every PROC_TRIM
        and GENERATED ``.tcl`` output that P5a/P5b wrote.
        """

        if not enabled:
            rewritten_paths = tuple(ctx.config.domain_root / rel_path for rel_path in tcl_output_paths(manifest))
            return trim_report, artifacts, rewritten_paths

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
                    _write_text_preserving_mode(ctx, target, formatted)
            except (OSError, UnicodeDecodeError) as exc:
                _emit_ve25(ctx, rel_path, f"Tcl indentation normalization failed: {exc}")
                return _mark_interrupted(current_report), current_artifacts, tuple(rewritten)

            normalized[rel_path] = formatted
            rewritten.append(target)
            current_report = _with_updated_bytes(current_report, normalized)
            current_artifacts = _with_updated_artifacts(current_artifacts, normalized)

        return current_report, current_artifacts, tuple(rewritten)


def format_tcl_indentation(text: str, *, tab_space: int = 4) -> str:
    """Return ``text`` with brace-driven leading whitespace.

    The formatter strips leading whitespace from each line, tracks a
    running indentation level from unescaped Tcl braces, outdents lines
    that begin with a closing brace, half-outdents selected domain
    marker lines, and indents backslash-continuation lines one extra
    level beyond the opening line. It always emits LF line endings and
    terminates non-empty files with a final newline.

    Comment and quote awareness:

    * A ``#`` token at the start of a line (after optional whitespace)
      starts a comment that runs to end-of-line; braces inside the
      comment never affect the running indent level, and a comment
      line that ends with ``\\`` never propagates a continuation to
      the next line.
    * Braces inside an unescaped ``"..."`` double-quoted string are
      ignored by the indent counter.

    Known limitations: braces inside command substitution ``[...]``,
    braces inside nested braced words ``{...}``, and ``;#`` inline
    comments after a statement-terminating semicolon are not tracked.
    """

    if text == "":
        return ""

    indent = 0
    is_continuation = False
    output: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Preserve blank lines as truly empty (no trailing whitespace).
        if not line:
            output.append("")
            is_continuation = False
            continue

        flag = 0
        original_indent = indent
        previous = ""
        char = ""
        previous_previous = ""
        in_double_quote = False

        for current in line:
            previous_previous = previous
            previous = char
            char = current
            # Toggle double-quote state (ignore escaped quotes)
            if char == '"' and previous != "\\":
                in_double_quote = not in_double_quote

            # Tcl comments: a '#' that begins a token (start of line or after whitespace)
            # starts a comment that runs to end-of-line. When we see such a comment
            # marker outside of a double-quoted string, stop scanning further chars
            # so braces inside comments do not affect indentation counting.
            if char == "#" and not in_double_quote and previous in ("", " ", "\t"):
                break

            # While inside a double-quoted string ignore brace characters
            if in_double_quote:
                continue

            if char == "{" and previous != "\\":
                indent += 1
                if flag == 0:
                    flag -= 1
            elif char == "}" and (previous != "\\" or (previous == "\\" and previous_previous == "\\")):
                indent -= 1
                if flag == 0:
                    flag += 1

        # If this line is a comment start, indent it to the current level but
        # do not use it to change the running brace-based indent state.
        if line.startswith("#"):
            spaces = tab_space * original_indent
            output.append(f"{' ' * max(spaces, 0)}{line}")
        else:
            if is_continuation:
                spaces = tab_space * (original_indent + 1)
            elif flag == 1:
                spaces = tab_space * (original_indent - 1)
            elif _MARKER_LINE.match(line):
                spaces = (tab_space * original_indent) - (tab_space // 2)
            else:
                spaces = tab_space * original_indent
            output.append(f"{' ' * max(spaces, 0)}{line}")

        # Detect backslash-continuation: line ends with odd number of
        # trailing backslashes (simplification: just check single `\`).
        # Comment lines never propagate continuation to the next line: a
        # comment that ends with ``\`` is still a comment and must not
        # cause the following statement to be indented as a continuation.
        if line.startswith("#"):
            is_continuation = False
        else:
            is_continuation = line.endswith("\\") and not line.endswith("\\\\")

    return "\n".join(output) + "\n"


def _write_text_preserving_mode(ctx: ChopperContext, target: Path, text: str) -> None:
    """Write ``text`` even when prior P5 steps already restored read-only mode."""

    mode: int | None = None
    try:
        if target.is_file():
            mode = stat.S_IMODE(target.stat().st_mode)
            target.chmod(mode | stat.S_IWUSR)
        ctx.fs.write_text(target, text)
    finally:
        if mode is not None:
            target.chmod(mode)


def _tcl_output_paths(manifest: CompiledManifest) -> tuple[Path, ...]:
    return tcl_output_paths(manifest)


def tcl_output_paths(manifest: CompiledManifest) -> tuple[Path, ...]:
    """Return the sorted ``.tcl`` outputs eligible for P5c indentation.

    Only ``PROC_TRIM`` and ``GENERATED`` outputs are returned; ``FULL_COPY``
    is byte-preserved and never normalized (issue #22). Public so the
    runner can reuse the same set when indentation is disabled.
    """
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
    return _build_report(
        tuple(outcomes),
        rebuild_interrupted=report.rebuild_interrupted,
        p4_checkout=report.p4_checkout,
        inputs_preserved=report.inputs_preserved,
    )


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
    return _build_report(
        report.outcomes,
        rebuild_interrupted=True,
        p4_checkout=report.p4_checkout,
        inputs_preserved=report.inputs_preserved,
    )


def _build_report(
    outcomes: tuple[FileOutcome, ...],
    *,
    rebuild_interrupted: bool,
    p4_checkout: P4CheckoutResult | None = None,
    inputs_preserved: int = 0,
) -> TrimReport:
    return TrimReport(
        outcomes=outcomes,
        files_copied=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.PROC_TRIM),
        files_removed=sum(1 for outcome in outcomes if outcome.treatment is FileTreatment.REMOVE),
        procs_kept_total=sum(len(outcome.procs_kept) for outcome in outcomes),
        procs_removed_total=sum(len(outcome.procs_removed) for outcome in outcomes),
        rebuild_interrupted=rebuild_interrupted,
        p4_checkout=p4_checkout,
        inputs_preserved=inputs_preserved,
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
