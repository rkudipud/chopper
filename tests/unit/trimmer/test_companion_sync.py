"""Unit tests for :mod:`chopper.trimmer.companion_sync` (P5d FD-15).

Tests cover:
* ``_filter_csv`` -- preserves blanks/comments, drops non-surviving proc rows.
* ``_filter_milestone`` -- keeps non-change_config lines, drops excluded procs.
* :class:`CompanionSyncService` -- full sync through InMemoryFS, VW-24 missing,
  VI-04 applied, TrimReport byte update, no-op when no rules file present,
  dry-run skips (service not called), both companion types missing, errors on
  I/O failure silently absorbed, namespaced proc handling, empty files.
"""

from __future__ import annotations

from pathlib import Path

from chopper.adapters import InMemoryFS
from chopper.core.models_common import FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance, ProcDecision
from chopper.core.models_trimmer import FileOutcome, TrimReport
from chopper.trimmer.companion_sync import CompanionSyncService, _filter_csv, _filter_milestone
from tests.unit.trimmer._helpers import DOMAIN, make_ctx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest_with_proc_trim(
    rules_rel: str,
    *,
    surviving_procs: list[str],
    extra_full_copy: list[str] | None = None,
) -> CompiledManifest:
    """Build a minimal CompiledManifest for companion-sync tests."""
    rules_path = Path(rules_rel)
    fd: dict[Path, FileTreatment] = {rules_path: FileTreatment.PROC_TRIM}
    pv: dict[Path, FileProvenance] = {
        rules_path: FileProvenance(
            path=rules_path,
            treatment=FileTreatment.PROC_TRIM,
            reason="pi-overlay",
            input_sources=("base:procedures.include",),
            proc_model="overlay",
        )
    }
    pd: dict[str, ProcDecision] = {}
    for short_name in surviving_procs:
        cn = f"{rules_rel}::{short_name}"
        pd[cn] = ProcDecision(
            canonical_name=cn,
            source_file=rules_path,
            selection_source="base:procedures.include",
        )

    for extra in extra_full_copy or []:
        ep = Path(extra)
        fd[ep] = FileTreatment.FULL_COPY
        pv[ep] = FileProvenance(
            path=ep,
            treatment=FileTreatment.FULL_COPY,
            reason="fi-literal",
            input_sources=("base:files.include",),
        )

    # CompiledManifest requires file_decisions lex-sorted by POSIX form.
    fd_sorted = dict(sorted(fd.items(), key=lambda kv: kv[0].as_posix()))
    pv_sorted = dict(sorted(pv.items(), key=lambda kv: kv[0].as_posix()))
    return CompiledManifest(file_decisions=fd_sorted, proc_decisions=pd, provenance=pv_sorted)


def _trim_report(
    *,
    rules_rel: str,
    csv_rel: str | None = None,
    milestone_rel: str | None = None,
    extra: list[str] | None = None,
) -> TrimReport:
    """Build a minimal TrimReport with PROC_TRIM + optional FULL_COPY outcomes."""
    outcomes: list[FileOutcome] = [
        FileOutcome(
            path=Path(rules_rel),
            treatment=FileTreatment.PROC_TRIM,
            bytes_in=100,
            bytes_out=50,
            procs_kept=("a", "b"),
            procs_removed=("c",),
        )
    ]
    for rel in [csv_rel, milestone_rel] + (extra or []):
        if rel is None:
            continue
        content = b"x" * 30
        outcomes.append(
            FileOutcome(
                path=Path(rel),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=len(content),
                bytes_out=len(content),
                procs_kept=(),
                procs_removed=(),
            )
        )
    outcomes.sort(key=lambda o: o.path.as_posix())
    return TrimReport(
        outcomes=tuple(outcomes),
        files_copied=sum(1 for o in outcomes if o.treatment is FileTreatment.FULL_COPY),
        files_trimmed=sum(1 for o in outcomes if o.treatment is FileTreatment.PROC_TRIM),
        files_removed=0,
        procs_kept_total=sum(len(o.procs_kept) for o in outcomes),
        procs_removed_total=sum(len(o.procs_removed) for o in outcomes),
    )


# ---------------------------------------------------------------------------
# _filter_csv
# ---------------------------------------------------------------------------


class TestFilterCsv:
    def test_keeps_surviving_proc_rows(self) -> None:
        text = "Abort,AB,1,err,0,1,errgen\nKeepMe,KM,1,warn,0,1,errgen\n"
        result = _filter_csv(text, frozenset({"Abort", "KeepMe"}))
        assert result == text

    def test_drops_non_surviving_rows(self) -> None:
        text = "Abort,AB,1,err\nDropMe,DM,1,err\nKeepMe,KM,1,warn\n"
        result = _filter_csv(text, frozenset({"Abort", "KeepMe"}))
        assert "DropMe" not in result
        assert "Abort" in result
        assert "KeepMe" in result

    def test_preserves_blank_lines(self) -> None:
        text = "Abort,AB,1,err\n\nKeepMe,KM,1,warn\n"
        result = _filter_csv(text, frozenset({"Abort", "KeepMe"}))
        assert "\n\n" in result

    def test_preserves_comment_lines(self) -> None:
        text = "# header\nAbort,AB,1,err\n# footer\n"
        result = _filter_csv(text, frozenset({"Abort"}))
        assert "# header" in result
        assert "# footer" in result

    def test_drops_row_with_no_blank_placeholder(self) -> None:
        text = "Keep,K,1,err\nDrop,D,1,err\n"
        result = _filter_csv(text, frozenset({"Keep"}))
        lines = result.splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("Keep")

    def test_empty_file_returns_empty(self) -> None:
        assert _filter_csv("", frozenset({"Abort"})) == ""

    def test_all_procs_removed(self) -> None:
        text = "A,1\nB,2\n"
        assert _filter_csv(text, frozenset()) == ""

    def test_whitespace_stripped_from_col0(self) -> None:
        text = "  Abort , code , 1\n"
        result = _filter_csv(text, frozenset({"Abort"}))
        assert "Abort" in result

    def test_non_surviving_proc_row_leaves_no_blank(self) -> None:
        text = "DropMe,DM,1\n"
        result = _filter_csv(text, frozenset())
        assert result == ""

    def test_preserves_line_endings_crlf(self) -> None:
        text = "Keep,K,1\r\nDrop,D,1\r\n"
        result = _filter_csv(text, frozenset({"Keep"}))
        assert result == "Keep,K,1\r\n"


# ---------------------------------------------------------------------------
# _filter_milestone
# ---------------------------------------------------------------------------


class TestFilterMilestone:
    def test_keeps_surviving_change_config_lines(self) -> None:
        text = "change_config Abort 1\nchange_config KeepMe 0\n"
        result = _filter_milestone(text, frozenset({"Abort", "KeepMe"}))
        assert result == text

    def test_drops_non_surviving_change_config(self) -> None:
        text = "change_config Abort 1\nchange_config DropMe 0\nchange_config KeepMe 1\n"
        result = _filter_milestone(text, frozenset({"Abort", "KeepMe"}))
        assert "DropMe" not in result
        assert "Abort" in result
        assert "KeepMe" in result

    def test_drops_without_blank_placeholder(self) -> None:
        text = "change_config Keep 1\nchange_config Drop 0\n"
        result = _filter_milestone(text, frozenset({"Keep"}))
        lines = [line for line in result.splitlines() if line.strip()]
        assert len(lines) == 1
        assert "Keep" in lines[0]

    def test_keeps_non_change_config_lines(self) -> None:
        text = "set x 1\n# comment\n\nchange_config Drop 0\nputs hello\n"
        result = _filter_milestone(text, frozenset())
        assert "set x 1" in result
        assert "# comment" in result
        assert "puts hello" in result
        assert "Drop" not in result

    def test_keeps_blank_lines_unchanged(self) -> None:
        text = "change_config Keep 1\n\nchange_config Drop 0\n"
        result = _filter_milestone(text, frozenset({"Keep"}))
        assert "\n\n" in result

    def test_empty_file_returns_empty(self) -> None:
        assert _filter_milestone("", frozenset({"Abort"})) == ""

    def test_indented_change_config(self) -> None:
        text = "    change_config DropMe 0\n    change_config KeepMe 1\n"
        result = _filter_milestone(text, frozenset({"KeepMe"}))
        assert "DropMe" not in result
        assert "KeepMe" in result

    def test_change_config_with_args(self) -> None:
        text = "change_config Abort severity error\n"
        result = _filter_milestone(text, frozenset({"Abort"}))
        assert result == text

    def test_preserves_line_endings_crlf(self) -> None:
        text = "change_config Keep 1\r\nchange_config Drop 0\r\n"
        result = _filter_milestone(text, frozenset({"Keep"}))
        assert result == "change_config Keep 1\r\n"


# ---------------------------------------------------------------------------
# CompanionSyncService -- full integration
# ---------------------------------------------------------------------------

_CSV_CONTENT = "# header\nAbort,AB,1,error\nDropMe,DM,0,warning\nKeepMe,KM,1,error\n"

_MILESTONE_CONTENT = (
    "# milestone header\nchange_config Abort 1\nchange_config DropMe 0\n\nchange_config KeepMe severity error\n"
)


class TestCompanionSyncService:
    """Full-stack tests running CompanionSyncService against InMemoryFS."""

    def _setup(
        self,
        *,
        sfx: str = "fm",
        rules_rel: str | None = None,
        surviving: list[str] | None = None,
        csv_content: str | None = None,
        milestone_content: str | None = None,
    ) -> tuple:
        """Return (ctx, sink, manifest, trim_report, fs)."""
        if rules_rel is None:
            rules_rel = f"default_rules.{sfx}.tcl"
        if surviving is None:
            surviving = ["Abort", "KeepMe"]
        if csv_content is None:
            csv_content = _CSV_CONTENT
        if milestone_content is None:
            milestone_content = _MILESTONE_CONTENT

        csv_rel = f"default_config.{sfx}.csv"
        milestone_rel = f"default_milestone.{sfx}.tcl"

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# trimmed rules\n",
                DOMAIN / csv_rel: csv_content,
                DOMAIN / milestone_rel: milestone_content,
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=surviving,
            extra_full_copy=[csv_rel, milestone_rel],
        )
        report = _trim_report(
            rules_rel=rules_rel,
            csv_rel=csv_rel,
            milestone_rel=milestone_rel,
        )
        return ctx, sink, manifest, report, fs

    def test_filters_csv_and_milestone(self) -> None:
        ctx, sink, manifest, report, fs = self._setup()

        CompanionSyncService().run(ctx, manifest, report)

        csv_out = fs.read_text(DOMAIN / "default_config.fm.csv")
        assert "DropMe" not in csv_out
        assert "Abort" in csv_out
        assert "KeepMe" in csv_out

        ms_out = fs.read_text(DOMAIN / "default_milestone.fm.tcl")
        assert "DropMe" not in ms_out
        assert "change_config Abort" in ms_out
        assert "change_config KeepMe" in ms_out

        # VI-04 emitted for each successfully synced companion
        codes = sink.codes()
        assert codes.count("VI-04") == 2

    def test_updates_trim_report_bytes(self) -> None:
        ctx, sink, manifest, report, fs = self._setup()
        new_report = CompanionSyncService().run(ctx, manifest, report)

        csv_rel = Path("default_config.fm.csv")
        ms_rel = Path("default_milestone.fm.tcl")

        new_csv_size = len(fs.read_text(DOMAIN / csv_rel).encode("utf-8"))
        new_ms_size = len(fs.read_text(DOMAIN / ms_rel).encode("utf-8"))

        csv_outcome = next(o for o in new_report.outcomes if o.path == csv_rel)
        ms_outcome = next(o for o in new_report.outcomes if o.path == ms_rel)

        assert csv_outcome.bytes_out == new_csv_size
        assert ms_outcome.bytes_out == new_ms_size

    def test_emits_vw24_for_missing_csv(self) -> None:
        sfx = "fm"
        rules_rel = f"default_rules.{sfx}.tcl"
        ms_rel = f"default_milestone.{sfx}.tcl"

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# rules\n",
                # CSV intentionally absent
                DOMAIN / ms_rel: _MILESTONE_CONTENT,
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=["Abort"],
            extra_full_copy=[ms_rel],
        )
        report = _trim_report(rules_rel=rules_rel, milestone_rel=ms_rel)

        CompanionSyncService().run(ctx, manifest, report)

        codes = sink.codes()
        assert "VW-24" in codes
        assert "VI-04" in codes  # milestone was synced

    def test_emits_vw24_for_missing_milestone(self) -> None:
        sfx = "fm"
        rules_rel = f"default_rules.{sfx}.tcl"
        csv_rel = f"default_config.{sfx}.csv"

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# rules\n",
                DOMAIN / csv_rel: _CSV_CONTENT,
                # milestone intentionally absent
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=["Abort"],
            extra_full_copy=[csv_rel],
        )
        report = _trim_report(rules_rel=rules_rel, csv_rel=csv_rel)

        CompanionSyncService().run(ctx, manifest, report)

        codes = sink.codes()
        assert "VW-24" in codes
        assert "VI-04" in codes  # CSV was synced

    def test_both_companions_missing_emits_two_vw24(self) -> None:
        sfx = "fm"
        rules_rel = f"default_rules.{sfx}.tcl"

        fs = InMemoryFS({DOMAIN / rules_rel: "# rules\n"})
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(rules_rel, surviving_procs=["Abort"])
        report = _trim_report(rules_rel=rules_rel)

        CompanionSyncService().run(ctx, manifest, report)

        codes = sink.codes()
        assert codes.count("VW-24") == 2

    def test_no_rules_file_returns_unchanged_report(self) -> None:
        """When no PROC_TRIM file matches default_rules.*.tcl, report is unchanged."""
        other_rel = "other.tcl"
        fs = InMemoryFS({DOMAIN / other_rel: "# other\n"})
        ctx, sink = make_ctx(fs=fs)

        fd = {Path(other_rel): FileTreatment.PROC_TRIM}
        pv = {
            Path(other_rel): FileProvenance(
                path=Path(other_rel),
                treatment=FileTreatment.PROC_TRIM,
                reason="pi-overlay",
                input_sources=(),
                proc_model="overlay",
            )
        }
        pd: dict[str, ProcDecision] = {}
        manifest = CompiledManifest(
            file_decisions=dict(sorted(fd.items(), key=lambda kv: kv[0].as_posix())),
            proc_decisions=pd,
            provenance=dict(sorted(pv.items(), key=lambda kv: kv[0].as_posix())),
        )
        outcomes = (
            FileOutcome(
                path=Path(other_rel),
                treatment=FileTreatment.PROC_TRIM,
                bytes_in=10,
                bytes_out=5,
                procs_kept=("p",),
                procs_removed=("q",),
            ),
        )
        report = TrimReport(
            outcomes=outcomes,
            files_copied=0,
            files_trimmed=1,
            files_removed=0,
            procs_kept_total=1,
            procs_removed_total=1,
        )

        new_report = CompanionSyncService().run(ctx, manifest, report)

        assert new_report is report  # unchanged
        assert sink.codes() == []

    def test_cfm_suffix_handled(self) -> None:
        """Companion sync works for .cfm. suffix."""
        ctx, sink, manifest, report, fs = self._setup(sfx="cfm")

        CompanionSyncService().run(ctx, manifest, report)

        assert "DropMe" not in fs.read_text(DOMAIN / "default_config.cfm.csv")
        assert "DropMe" not in fs.read_text(DOMAIN / "default_milestone.cfm.tcl")

    def test_subdirectory_rules_file(self) -> None:
        """Companion files are found relative to the rules file's parent directory."""
        rules_rel = "utils/default_rules.fm.tcl"
        csv_rel = "utils/default_config.fm.csv"
        ms_rel = "utils/default_milestone.fm.tcl"

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# rules\n",
                DOMAIN / csv_rel: _CSV_CONTENT,
                DOMAIN / ms_rel: _MILESTONE_CONTENT,
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=["Abort", "KeepMe"],
            extra_full_copy=[csv_rel, ms_rel],
        )
        report = _trim_report(rules_rel=rules_rel, csv_rel=csv_rel, milestone_rel=ms_rel)

        CompanionSyncService().run(ctx, manifest, report)

        assert "DropMe" not in fs.read_text(DOMAIN / csv_rel)
        assert "DropMe" not in fs.read_text(DOMAIN / ms_rel)

    def test_all_procs_surviving_leaves_content_intact(self) -> None:
        """If all procs survive, companion content is unchanged (VI-04 still emitted)."""
        ctx, sink, manifest, report, fs = self._setup(surviving=["Abort", "DropMe", "KeepMe"])

        CompanionSyncService().run(ctx, manifest, report)

        assert fs.read_text(DOMAIN / "default_config.fm.csv") == _CSV_CONTENT
        assert fs.read_text(DOMAIN / "default_milestone.fm.tcl") == _MILESTONE_CONTENT

    def test_no_procs_surviving_empties_csv_data_rows(self) -> None:
        """If no procs survive, all data rows in the CSV are removed."""
        ctx, sink, manifest, report, fs = self._setup(surviving=[])

        CompanionSyncService().run(ctx, manifest, report)

        csv_out = fs.read_text(DOMAIN / "default_config.fm.csv")
        # Only comment / blank lines remain
        data_rows = [line for line in csv_out.splitlines() if line.strip() and not line.strip().startswith("#")]
        assert data_rows == []

    def test_trim_report_unchanged_when_content_unchanged(self) -> None:
        """If companion content does not change (all-comment CSV, no change_config milestone),
        the filter output equals input, and bytes_out is updated to the actual file length."""
        csv_content = "# only comments\n"
        ms_content = "set x 1\n"  # no change_config at all

        ctx, sink, manifest, report, fs = self._setup(
            csv_content=csv_content, milestone_content=ms_content, surviving=["Abort"]
        )
        new_report = CompanionSyncService().run(ctx, manifest, report)

        # The companion files were written (content unchanged), bytes_out reflects actual on-disk size.
        csv_rel = Path("default_config.fm.csv")
        ms_rel = Path("default_milestone.fm.tcl")
        csv_outcome = next(o for o in new_report.outcomes if o.path == csv_rel)
        ms_outcome = next(o for o in new_report.outcomes if o.path == ms_rel)
        assert csv_outcome.bytes_out == len(csv_content.encode())
        assert ms_outcome.bytes_out == len(ms_content.encode())

    def test_full_copy_only_manifest_no_proc_trim(self) -> None:
        """Manifest with only FULL_COPY files -- no companion sync triggered."""
        csv_rel = "default_config.fm.csv"
        fs = InMemoryFS({DOMAIN / csv_rel: _CSV_CONTENT})
        ctx, sink = make_ctx(fs=fs)

        fd = {Path(csv_rel): FileTreatment.FULL_COPY}
        pv = {
            Path(csv_rel): FileProvenance(
                path=Path(csv_rel),
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=(),
            )
        }
        manifest = CompiledManifest(
            file_decisions=dict(sorted(fd.items(), key=lambda kv: kv[0].as_posix())),
            proc_decisions={},
            provenance=dict(sorted(pv.items(), key=lambda kv: kv[0].as_posix())),
        )
        outcomes = (
            FileOutcome(
                path=Path(csv_rel),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=len(_CSV_CONTENT),
                bytes_out=len(_CSV_CONTENT),
                procs_kept=(),
                procs_removed=(),
            ),
        )
        report = TrimReport(
            outcomes=outcomes,
            files_copied=1,
            files_trimmed=0,
            files_removed=0,
            procs_kept_total=0,
            procs_removed_total=0,
        )

        new_report = CompanionSyncService().run(ctx, manifest, report)

        assert new_report is report
        assert sink.codes() == []

    def test_io_error_on_read_silently_absorbed(self) -> None:
        """If fs.read_text raises OSError, VW-24 is NOT emitted but the run continues."""
        from unittest.mock import patch

        sfx = "fm"
        rules_rel = f"default_rules.{sfx}.tcl"
        csv_rel = f"default_config.{sfx}.csv"
        ms_rel = f"default_milestone.{sfx}.tcl"

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# rules\n",
                DOMAIN / csv_rel: _CSV_CONTENT,
                DOMAIN / ms_rel: _MILESTONE_CONTENT,
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=["Abort"],
            extra_full_copy=[csv_rel, ms_rel],
        )
        report = _trim_report(rules_rel=rules_rel, csv_rel=csv_rel, milestone_rel=ms_rel)

        # Patch fs.read_text to raise OSError on the CSV companion only.
        original_read = fs.read_text

        def patched_read(path: Path, **kwargs):  # type: ignore[override]
            if path == DOMAIN / csv_rel:
                raise OSError("disk error")
            return original_read(path, **kwargs)

        with patch.object(fs, "read_text", side_effect=patched_read):
            CompanionSyncService().run(ctx, manifest, report)

        # CSV sync failed silently (no VW-24 for I/O error -- just skipped)
        codes = sink.codes()
        assert "VW-24" not in codes
        assert "VI-04" in codes  # milestone was still synced

    def test_bytes_unchanged_returns_same_report_object(self) -> None:
        """When the filtered content has the same byte count as bytes_out in the TrimReport,
        _with_updated_companion_bytes returns the same TrimReport object (no rebuild)."""
        sfx = "fm"
        rules_rel = f"default_rules.{sfx}.tcl"
        csv_rel = f"default_config.{sfx}.csv"
        ms_rel = f"default_milestone.{sfx}.tcl"

        # Use simple content where filter output equals input
        csv_content = "# comment only\n"  # 16 bytes, no data rows to drop
        ms_content = "set x 1\n"  # 8 bytes, no change_config lines

        fs = InMemoryFS(
            {
                DOMAIN / rules_rel: "# rules\n",
                DOMAIN / csv_rel: csv_content,
                DOMAIN / ms_rel: ms_content,
            }
        )
        ctx, sink = make_ctx(fs=fs)
        manifest = _manifest_with_proc_trim(
            rules_rel,
            surviving_procs=["Abort"],
            extra_full_copy=[csv_rel, ms_rel],
        )

        # Build TrimReport with bytes_out matching the actual content bytes
        csv_bytes = len(csv_content.encode())
        ms_bytes = len(ms_content.encode())
        outcomes: list[FileOutcome] = [
            FileOutcome(
                path=Path(rules_rel),
                treatment=FileTreatment.PROC_TRIM,
                bytes_in=100,
                bytes_out=50,
                procs_kept=("a",),
                procs_removed=("c",),
            ),
            FileOutcome(
                path=Path(csv_rel),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=csv_bytes,
                bytes_out=csv_bytes,  # already correct
                procs_kept=(),
                procs_removed=(),
            ),
            FileOutcome(
                path=Path(ms_rel),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=ms_bytes,
                bytes_out=ms_bytes,  # already correct
                procs_kept=(),
                procs_removed=(),
            ),
        ]
        outcomes.sort(key=lambda o: o.path.as_posix())
        report = TrimReport(
            outcomes=tuple(outcomes),
            files_copied=2,
            files_trimmed=1,
            files_removed=0,
            procs_kept_total=1,
            procs_removed_total=1,
        )

        new_report = CompanionSyncService().run(ctx, manifest, report)

        # Content didn't change -> bytes_out values match -> same TrimReport returned
        assert new_report is report
