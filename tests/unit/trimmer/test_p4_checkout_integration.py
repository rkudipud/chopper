"""Integration tests for the optional ``--p4`` checkout-before-edit step
wired into :meth:`chopper.trimmer.service.TrimmerService.run`.

The ``chopper.trimmer.p4_checkout`` subprocess wrappers are mocked here --
this file tests *orchestration* (when checkout runs, how success/skip/
failure feed into :class:`~chopper.core.models_trimmer.TrimReport`, and
the rollback/immediate-restore behavior), not the subprocess plumbing
itself (covered by ``tests/unit/trimmer/test_p4_checkout.py``).

See ``technical_docs/ARCHITECTURE.md`` FR-53.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from chopper.core.models_common import DomainState, FileTreatment
from chopper.core.models_compiler import CompiledManifest, FileProvenance, ProcDecision
from chopper.core.models_parser import ParseResult
from chopper.trimmer import TrimmerService
from tests.unit.trimmer._helpers import BACKUP, DOMAIN, make_ctx


def _manifest(file_decisions: dict[str, FileTreatment]) -> CompiledManifest:
    fd: dict[Path, FileTreatment] = {}
    pv: dict[Path, FileProvenance] = {}
    pd: dict[str, ProcDecision] = {}
    for file_str, treatment in sorted(file_decisions.items()):
        path = Path(file_str)
        fd[path] = treatment
        pv[path] = FileProvenance(
            path=path,
            treatment=treatment,
            reason="fi-literal",
            input_sources=("base:files.include",) if treatment is not FileTreatment.REMOVE else (),
        )
        if treatment is FileTreatment.PROC_TRIM:
            cn = f"{path.as_posix()}::keep"
            pd[cn] = ProcDecision(canonical_name=cn, source_file=path, selection_source="base:procedures.include")
    return CompiledManifest(file_decisions=fd, proc_decisions=pd, provenance=pv)


def _state(case: int, *, domain_exists: bool, backup_exists: bool) -> DomainState:
    return DomainState(case=case, domain_exists=domain_exists, backup_exists=backup_exists, hand_edited=False)  # type: ignore[arg-type]


_EMPTY_PARSED = ParseResult(files={}, index={})


# ---------------------------------------------------------------------------
# --p4 not passed at all -- zero behavior change
# ---------------------------------------------------------------------------


def test_p4_flag_off_never_touches_p4_module() -> None:
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=False)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch("chopper.trimmer.service.check_p4_available") as mock_available,
        patch("chopper.trimmer.service.checkout_files") as mock_checkout,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.p4_checkout is None
    mock_available.assert_not_called()
    mock_checkout.assert_not_called()


def test_dry_run_never_touches_p4_even_with_flag_on() -> None:
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, dry_run=True, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch("chopper.trimmer.service.check_p4_available") as mock_available,
        patch("chopper.trimmer.service.checkout_files") as mock_checkout,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.p4_checkout is None
    mock_available.assert_not_called()
    mock_checkout.assert_not_called()


# ---------------------------------------------------------------------------
# Skip paths (no abort, normal trim proceeds)
# ---------------------------------------------------------------------------


def test_p4_skipped_on_retrim_case_2_full_copy_only() -> None:
    """Case 2 re-trim with only FULL_COPY files: p4 check runs but no edit
    paths exist, so checkout is attempted with zero checked-out files."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n", BACKUP / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(2, domain_exists=True, backup_exists=True)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files") as mock_checkout,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    mock_checkout.assert_not_called()  # no PROC_TRIM files → no edit paths
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True
    assert report.p4_checkout.checked_out == ()
    assert not report.rebuild_interrupted
    assert report.files_copied == 1
    assert not report.rebuild_interrupted


def test_p4_case2_retrim_proc_trim_succeeds() -> None:
    """Case 2 re-trim with a PROC_TRIM file: _p4_precopy_from_backup restores
    the file to its backup content, then checkout and trim proceed normally."""
    from chopper.adapters import InMemoryFS
    from chopper.core.models_parser import ParsedFile, ProcEntry

    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc keep {} {}\n",  # trimmed (current domain)
            BACKUP / "a.tcl": "proc keep {} {}\nproc drop {} {}\n",  # original
        }
    )
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(2, domain_exists=True, backup_exists=True)

    proc = ProcEntry(
        canonical_name="a.tcl::keep",
        short_name="keep",
        qualified_name="keep",
        source_file=Path("a.tcl"),
        start_line=1,
        end_line=1,
        body_start_line=1,
        body_end_line=1,
        namespace_path="",
        calls=(),
        source_refs=(),
    )
    parsed = ParseResult(
        files={Path("a.tcl"): ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")},
        index={"a.tcl::keep": proc},
    )

    edit_paths = [Path("a.tcl")]
    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=(tuple(edit_paths), None, None)) as mock_co,
        patch("chopper.trimmer.service.revert_files") as mock_revert,
    ):
        report = TrimmerService().run(ctx, manifest, parsed, state)

    mock_co.assert_called_once()
    mock_revert.assert_not_called()
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True
    assert report.p4_checkout.checked_out == (Path("a.tcl"),)
    assert not report.p4_checkout.failed
    assert not report.rebuild_interrupted
    assert "VE-37" not in sink.codes()
    assert report.files_trimmed == 1


def test_p4_case2_precopy_failure_emits_skip_and_trim_proceeds() -> None:
    """If pre-copy from backup raises OSError, p4 checkout is skipped with a
    notice and the trim proceeds normally (pre-copy failure is non-fatal)."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc keep {} {}\n",
            BACKUP / "a.tcl": "proc keep {} {}\nproc drop {} {}\n",
        }
    )
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(2, domain_exists=True, backup_exists=True)

    from chopper.core.models_parser import ParsedFile, ProcEntry

    proc = ProcEntry(
        canonical_name="a.tcl::keep",
        short_name="keep",
        qualified_name="keep",
        source_file=Path("a.tcl"),
        start_line=1,
        end_line=1,
        body_start_line=1,
        body_end_line=1,
        namespace_path="",
        calls=(),
        source_refs=(),
    )
    parsed = ParseResult(
        files={Path("a.tcl"): ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")},
        index={"a.tcl::keep": proc},
    )

    with (
        patch.object(fs, "copy_file", side_effect=OSError("disk full")),
        patch("chopper.trimmer.service.check_p4_available") as mock_avail,
    ):
        report = TrimmerService().run(ctx, manifest, parsed, state)

    mock_avail.assert_not_called()
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is False
    assert "pre-copy from backup failed" in report.p4_checkout.skip_reason
    assert not report.rebuild_interrupted
    assert report.files_trimmed == 1


def test_p4_case2_p4_edit_failure_aborts_trim() -> None:
    """Case 2 + --p4: pre-copy succeeds but p4 edit fails → VE-37, trim aborts."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc keep {} {}\n",
            BACKUP / "a.tcl": "proc keep {} {}\nproc drop {} {}\n",
        }
    )
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(2, domain_exists=True, backup_exists=True)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch(
            "chopper.trimmer.service.checkout_files",
            return_value=((), Path("a.tcl"), "locked by another user"),
        ),
        patch("chopper.trimmer.service.revert_files"),
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.rebuild_interrupted is True
    assert report.p4_checkout is not None
    assert report.p4_checkout.failed
    assert "VE-37" in sink.codes()


def test_p4_precopy_skips_when_backup_file_absent() -> None:
    """_p4_precopy_from_backup: PROC_TRIM file missing from backup → skips copy."""
    from chopper.adapters import InMemoryFS

    # PROC_TRIM file exists in domain but NOT in backup (unusual but must not crash)
    fs = InMemoryFS({DOMAIN / "a.tcl": "proc keep {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(2, domain_exists=True, backup_exists=True)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=((), None, None)),
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    # Pre-copy was skipped (backup file missing); checkout still ran but with no paths
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True


def test_p4_precopy_copies_generated_regenerate_in_place() -> None:
    """_p4_precopy_from_backup: existing GENERATED files are pre-copied from backup."""
    from chopper.adapters import InMemoryFS
    from chopper.trimmer.service import TrimmerService

    # GENERATED file exists in both domain (regenerated content) and backup (original)
    fs = InMemoryFS(
        {
            DOMAIN / "stage.tcl": "# regenerated\n",
            BACKUP / "stage.tcl": "# original\n",
        }
    )
    ctx, _sink = make_ctx(fs=fs)
    manifest = _manifest({"stage.tcl": FileTreatment.GENERATED})

    TrimmerService()._p4_precopy_from_backup(ctx, manifest)

    assert fs.read_text(DOMAIN / "stage.tcl") == "# original\n"


def test_p4_case3_skipped_with_notice() -> None:
    """Case 3 (backup only, no domain): p4 checkout is skipped with a
    domain-absent reason; trim still proceeds from backup."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({BACKUP / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(3, domain_exists=False, backup_exists=True)

    with patch("chopper.trimmer.service.check_p4_available") as mock_avail:
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    mock_avail.assert_not_called()
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is False
    assert "absent" in report.p4_checkout.skip_reason
    assert not report.rebuild_interrupted
    assert report.files_copied == 1


def test_p4_skipped_when_p4_unavailable() -> None:
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch(
            "chopper.trimmer.service.check_p4_available",
            return_value=(False, "the 'p4' executable was not found on PATH"),
        ),
        patch("chopper.trimmer.service.checkout_files") as mock_checkout,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is False
    assert report.p4_checkout.skip_reason == "the 'p4' executable was not found on PATH"
    mock_checkout.assert_not_called()
    assert report.files_copied == 1
    assert not report.rebuild_interrupted


def test_p4_attempted_but_no_edit_paths_short_circuits_checkout_call() -> None:
    """FULL_COPY-only manifest: nothing to check out, checkout_files never called."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files") as mock_checkout,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True
    assert report.p4_checkout.checked_out == ()
    mock_checkout.assert_not_called()
    assert not report.rebuild_interrupted


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_p4_checkout_succeeds_and_trim_proceeds_normally() -> None:
    from chopper.adapters import InMemoryFS
    from chopper.core.models_parser import ParsedFile, ProcEntry

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n", DOMAIN / "b.tcl": "proc bar {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM, "b.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    proc = ProcEntry(
        canonical_name="a.tcl::keep",
        short_name="keep",
        qualified_name="keep",
        source_file=Path("a.tcl"),
        start_line=1,
        end_line=1,
        body_start_line=1,
        body_end_line=1,
        namespace_path="",
        calls=(),
        source_refs=(),
    )
    parsed = ParseResult(
        files={Path("a.tcl"): ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")},
        index={"a.tcl::keep": proc},
    )

    edit_paths = [Path("a.tcl")]
    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=(tuple(edit_paths), None, None)) as mock_checkout,
        patch("chopper.trimmer.service.revert_files") as mock_revert,
    ):
        report = TrimmerService().run(ctx, manifest, parsed, state)

    mock_checkout.assert_called_once()
    called_domain_root, called_paths = mock_checkout.call_args[0]
    assert called_domain_root == DOMAIN
    assert list(called_paths) == edit_paths
    mock_revert.assert_not_called()

    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True
    assert report.p4_checkout.checked_out == (Path("a.tcl"),)
    assert not report.p4_checkout.failed
    assert not report.rebuild_interrupted
    assert "VE-37" not in sink.codes()
    # Normal trim output unaffected.
    assert fs.exists(BACKUP / "a.tcl")
    assert fs.read_text(DOMAIN / "b.tcl") == "proc bar {} {}\n"


# ---------------------------------------------------------------------------
# Failure during checkout itself -- abort for all, cheap rollback
# ---------------------------------------------------------------------------


def test_p4_checkout_failure_aborts_reverts_and_leaves_domain_untouched() -> None:
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n", DOMAIN / "b.tcl": "proc bar {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM, "b.tcl": FileTreatment.PROC_TRIM})
    state = _state(1, domain_exists=True, backup_exists=False)

    succeeded = (Path("a.tcl"),)
    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch(
            "chopper.trimmer.service.checkout_files",
            return_value=(succeeded, Path("b.tcl"), "locked by another user"),
        ),
        patch("chopper.trimmer.service.revert_files") as mock_revert,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    mock_revert.assert_called_once_with(DOMAIN, succeeded)

    assert report.rebuild_interrupted is True
    assert report.outcomes == ()
    assert report.p4_checkout is not None
    assert report.p4_checkout.failed
    assert report.p4_checkout.failed_path == Path("b.tcl")
    assert report.p4_checkout.failure_message == "locked by another user"
    assert report.p4_checkout.domain_restored is False  # clear phase never ran
    assert "VE-37" in sink.codes()

    # Backup was created by copy then removed on p4 failure; domain untouched.
    assert fs.exists(DOMAIN / "a.tcl")
    assert fs.exists(DOMAIN / "b.tcl")
    assert not fs.exists(BACKUP)


# ---------------------------------------------------------------------------
# Failure AFTER checkout succeeded -- immediate restore
# ---------------------------------------------------------------------------


def test_later_dispatch_failure_after_checkout_success_restores_domain_immediately() -> None:
    from chopper.adapters import InMemoryFS

    # PROC_TRIM requested for a.tcl but ParseResult has no entry for it --
    # TrimmerService._dispatch raises FileNotFoundError, which is the
    # existing VE-24 abort path.
    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(1, domain_exists=True, backup_exists=False)
    parsed = ParseResult(files={}, index={})  # deliberately missing a.tcl's ParsedFile

    checked_out = (Path("a.tcl"),)
    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=(checked_out, None, None)),
        patch("chopper.trimmer.service.revert_files") as mock_revert,
    ):
        report = TrimmerService().run(ctx, manifest, parsed, state)

    mock_revert.assert_called_once_with(DOMAIN, list(checked_out))

    assert report.rebuild_interrupted is True
    assert report.p4_checkout is not None
    assert report.p4_checkout.attempted is True
    assert not report.p4_checkout.failed
    assert report.p4_checkout.reverted == checked_out
    assert report.p4_checkout.domain_restored is True
    assert "VE-24" in sink.codes()

    # Immediate restore: domain/ exists again with the ORIGINAL content;
    # the partial rebuild + domain_backup/ are both gone.
    assert fs.exists(DOMAIN / "a.tcl")
    assert fs.read_text(DOMAIN / "a.tcl") == "proc foo {} {}\n"
    assert not fs.exists(BACKUP)


# ---------------------------------------------------------------------------
# _compute_p4_edit_paths -- regenerate-in-place GENERATED branch
# ---------------------------------------------------------------------------


def test_compute_p4_edit_paths_includes_regenerate_in_place_generated_file() -> None:
    from chopper.adapters import InMemoryFS
    from chopper.trimmer.service import _compute_p4_edit_paths

    fs = InMemoryFS(
        {
            DOMAIN / "a.tcl": "proc foo {} {}\n",  # PROC_TRIM
            DOMAIN / "stage.tcl": "# existing stage\n",  # GENERATED, regenerate-in-place
        }
    )
    ctx, _sink = make_ctx(fs=fs)
    manifest = _manifest(
        {
            "a.tcl": FileTreatment.PROC_TRIM,
            "stage.tcl": FileTreatment.GENERATED,
            "new_stage.tcl": FileTreatment.GENERATED,  # not on disk -- p4 add territory, excluded
        }
    )

    paths = _compute_p4_edit_paths(ctx, manifest)

    assert paths == [Path("a.tcl"), Path("stage.tcl")]


# ---------------------------------------------------------------------------
# _rollback_late_failure -- direct unit tests for defensive branches not
# reachable through the full TrimmerService.run() flow (checked_out is only
# ever non-empty when state.case == 1, since _perform_p4_checkout gates
# checkout on that case; these tests exercise the helper's own guards
# directly, matching the existing precedent of unit-testing private
# trimmer.service helpers -- see test_service.py's _plan_only_report import).
# ---------------------------------------------------------------------------


def test_rollback_late_failure_noop_variants() -> None:
    from chopper.core.models_trimmer import P4CheckoutResult
    from chopper.trimmer.service import _rollback_late_failure

    ctx, _sink = make_ctx()
    state = _state(1, domain_exists=True, backup_exists=False)

    with patch("chopper.trimmer.service.revert_files") as mock_revert:
        assert _rollback_late_failure(ctx, None, state) is None
        assert (
            _rollback_late_failure(ctx, P4CheckoutResult(attempted=False, skip_reason="unavailable"), state) is not None
        )
        assert (
            _rollback_late_failure(
                ctx,
                P4CheckoutResult(attempted=True, failed_path=Path("a.tcl"), failure_message="boom"),
                state,
            )
            is not None
        )
        assert _rollback_late_failure(ctx, P4CheckoutResult(attempted=True, checked_out=()), state) is not None
    mock_revert.assert_not_called()


def test_rollback_late_failure_skips_restore_when_case_is_not_1() -> None:
    """Direct unit test of the ``state.case != 1`` branch: revert still
    happens, but no restore is attempted (there is no rename to reverse)."""
    from chopper.core.models_trimmer import P4CheckoutResult
    from chopper.trimmer.service import _rollback_late_failure

    ctx, _sink = make_ctx()
    state = _state(2, domain_exists=True, backup_exists=True)
    checked_out = (Path("a.tcl"),)
    p4_result = P4CheckoutResult(attempted=True, checked_out=checked_out)

    with patch("chopper.trimmer.service.revert_files") as mock_revert:
        result = _rollback_late_failure(ctx, p4_result, state)

    mock_revert.assert_called_once_with(DOMAIN, list(checked_out))
    assert result is not None
    assert result.reverted == checked_out
    assert result.domain_restored is False


def test_rollback_late_failure_skips_remove_when_domain_already_absent() -> None:
    """``ctx.fs.exists(domain)`` False branch: nothing to remove, restore
    (rename backup -> domain) still proceeds."""
    from chopper.adapters import InMemoryFS
    from chopper.core.models_trimmer import P4CheckoutResult
    from chopper.trimmer.service import _rollback_late_failure

    fs = InMemoryFS({BACKUP / "a.tcl": "proc foo {} {}\n"})  # domain/ absent, backup/ present
    ctx, _sink = make_ctx(fs=fs)
    state = _state(1, domain_exists=False, backup_exists=True)
    checked_out = (Path("a.tcl"),)
    p4_result = P4CheckoutResult(attempted=True, checked_out=checked_out)

    with patch("chopper.trimmer.service.revert_files"):
        result = _rollback_late_failure(ctx, p4_result, state)

    assert result is not None
    assert result.domain_restored is True
    assert fs.exists(DOMAIN / "a.tcl")
    assert not fs.exists(BACKUP)


def test_rollback_late_failure_skips_rename_when_backup_absent() -> None:
    """``ctx.fs.exists(backup)`` False branch: nothing to rename back, so
    ``domain_restored`` stays False even though ``domain/`` was removed."""
    from chopper.adapters import InMemoryFS
    from chopper.core.models_trimmer import P4CheckoutResult
    from chopper.trimmer.service import _rollback_late_failure

    fs = InMemoryFS({DOMAIN / "partial.tcl": "partial rebuild\n"})  # no backup at all
    ctx, _sink = make_ctx(fs=fs)
    state = _state(1, domain_exists=True, backup_exists=False)
    checked_out = (Path("a.tcl"),)
    p4_result = P4CheckoutResult(attempted=True, checked_out=checked_out)

    with patch("chopper.trimmer.service.revert_files"):
        result = _rollback_late_failure(ctx, p4_result, state)

    assert result is not None
    assert result.domain_restored is False
    assert not fs.exists(DOMAIN / "partial.tcl")  # still removed, just nothing to restore


def test_rollback_late_failure_swallows_oserror_during_restore() -> None:
    """A filesystem error during the restore attempt itself must not
    propagate -- the original failure's diagnostic is what the user sees."""
    from chopper.adapters import InMemoryFS
    from chopper.core.models_trimmer import P4CheckoutResult
    from chopper.trimmer.service import _rollback_late_failure

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n", BACKUP / "a.tcl": "proc foo {} {}\n"})
    ctx, _sink = make_ctx(fs=fs)
    state = _state(1, domain_exists=True, backup_exists=True)
    checked_out = (Path("a.tcl"),)
    p4_result = P4CheckoutResult(attempted=True, checked_out=checked_out)

    with (
        patch("chopper.trimmer.service.revert_files"),
        patch.object(fs, "rename", side_effect=OSError("disk full")),
    ):
        result = _rollback_late_failure(ctx, p4_result, state)

    assert result is not None
    assert result.domain_restored is False


# ---------------------------------------------------------------------------
# New two-phase backup (copy, not rename) -- Case 1 + --p4 coverage
# ---------------------------------------------------------------------------


def test_p4_backup_phase_removes_chopper_dir_before_copy() -> None:
    """.chopper/ in the domain is removed before copy_tree so it is not
    included in the backup (copy_tree contract forbids it)."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS(
        {
            DOMAIN / ".chopper" / "chopper_run.json": "{}",
            DOMAIN / "a.tcl": "proc foo {} {}\n",
        }
    )
    ctx, _sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=((), None, None)),
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert not fs.exists(DOMAIN / ".chopper")
    assert not fs.exists(BACKUP / ".chopper")
    assert fs.exists(BACKUP / "a.tcl")
    assert not report.rebuild_interrupted


def test_p4_backup_phase_oserror_emits_ve23_cleans_partial_backup() -> None:
    """copy_tree failure: VE-23 emitted, partial backup cleaned up, domain untouched."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch.object(fs, "copy_tree", side_effect=OSError("disk full")),
        patch("chopper.trimmer.service.check_p4_available") as mock_avail,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    mock_avail.assert_not_called()
    assert report.rebuild_interrupted is True
    assert report.p4_checkout is None
    assert "VE-23" in sink.codes()
    assert fs.exists(DOMAIN / "a.tcl")


def test_p4_backup_phase_oserror_inner_cleanup_also_fails_swallowed() -> None:
    """copy_tree fails AND the backup-cleanup remove also raises -- swallowed, VE-23 still emitted."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.FULL_COPY})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch.object(fs, "copy_tree", side_effect=OSError("disk full")),
        patch.object(fs, "remove", side_effect=OSError("remove failed too")),
        patch("chopper.trimmer.service.check_p4_available") as mock_avail,
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    mock_avail.assert_not_called()
    assert report.rebuild_interrupted is True
    assert "VE-23" in sink.codes()


def test_p4_checkout_failure_backup_cleanup_oserror_swallowed() -> None:
    """p4 edit fails AND the post-failure backup removal raises -- swallowed, VE-37 still reported."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(1, domain_exists=True, backup_exists=False)

    with (
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=((), Path("a.tcl"), "locked")),
        patch("chopper.trimmer.service.revert_files"),
        patch.object(fs, "remove", side_effect=OSError("remove failed")),
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.rebuild_interrupted is True
    assert report.p4_checkout is not None
    assert report.p4_checkout.failed
    assert "VE-37" in sink.codes()


def test_p4_clear_phase_oserror_triggers_rollback_and_ve23() -> None:
    """_p4_clear_phase raises OSError: rollback called, VE-23 emitted."""
    from chopper.adapters import InMemoryFS

    fs = InMemoryFS({DOMAIN / "a.tcl": "proc foo {} {}\n"})
    ctx, sink = make_ctx(fs=fs, p4_checkout=True)
    manifest = _manifest({"a.tcl": FileTreatment.PROC_TRIM})
    state = _state(1, domain_exists=True, backup_exists=False)

    checked_out = (Path("a.tcl"),)
    real_copy_tree = fs.copy_tree
    remove_calls: list[Path] = []

    def _remove_side_effect(path: Path, *, recursive: bool = False) -> None:
        remove_calls.append(path)
        raise OSError("clear failed")

    with (
        patch.object(fs, "copy_tree", side_effect=real_copy_tree),
        patch.object(fs, "remove", side_effect=_remove_side_effect),
        patch("chopper.trimmer.service.check_p4_available", return_value=(True, None)),
        patch("chopper.trimmer.service.checkout_files", return_value=(checked_out, None, None)),
        patch("chopper.trimmer.service.revert_files"),
    ):
        report = TrimmerService().run(ctx, manifest, _EMPTY_PARSED, state)

    assert report.rebuild_interrupted is True
    assert report.p4_checkout is not None
    assert not report.p4_checkout.failed
    assert "VE-23" in sink.codes()
    assert DOMAIN in remove_calls
