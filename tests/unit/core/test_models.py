"""Unit tests for :mod:`chopper.core.models` — the Stage 0 shared dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from chopper.core.diagnostics import DiagnosticSummary
from chopper.core.models import (
    AddStepAction,
    AuditArtifact,
    AuditManifest,
    CompiledManifest,
    DependencyGraph,
    DomainState,
    Edge,
    FileOutcome,
    FileProvenance,
    FileStat,
    FileTreatment,
    GeneratedArtifact,
    LoadedConfig,
    ParsedFile,
    ParseResult,
    ProcDecision,
    ProcEntry,
    ProcEntryRef,
    RunRecord,
    RunResult,
    StageDefinition,
    StageSpec,
    TrimReport,
)


class TestFileTreatment:
    def test_values(self) -> None:
        assert FileTreatment.FULL_COPY.value == "FULL_COPY"
        assert FileTreatment.PROC_TRIM.value == "PROC_TRIM"
        assert FileTreatment.GENERATED.value == "GENERATED"
        assert FileTreatment.REMOVE.value == "REMOVE"

    def test_is_str_subclass_for_json(self) -> None:
        # Inheriting from str means json.dumps serialises the enum directly.
        assert isinstance(FileTreatment.FULL_COPY, str)

    def test_members_exhaustive(self) -> None:
        # Bible §5.5 defines exactly these four dispositions; adding a fifth
        # without touching the spec is a drift regression.
        assert {m.name for m in FileTreatment} == {"FULL_COPY", "PROC_TRIM", "GENERATED", "REMOVE"}


class TestDomainState:
    def test_case_1_first_trim(self) -> None:
        state = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
        assert state.case == 1
        assert state.domain_exists is True
        assert state.backup_exists is False

    def test_case_2_retrim(self) -> None:
        state = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=True)
        assert state.case == 2
        assert state.hand_edited is True

    def test_case_3_recovery(self) -> None:
        state = DomainState(case=3, domain_exists=False, backup_exists=True, hand_edited=False)
        assert state.case == 3
        assert state.domain_exists is False

    def test_case_4_fatal(self) -> None:
        state = DomainState(case=4, domain_exists=False, backup_exists=False, hand_edited=False)
        assert state.case == 4

    def test_is_frozen(self) -> None:
        state = DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False)
        with pytest.raises(FrozenInstanceError):
            state.case = 2  # type: ignore[misc]

    def test_equality_by_fields(self) -> None:
        a = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
        b = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
        assert a == b
        assert hash(a) == hash(b)


class TestFileStat:
    def test_file(self) -> None:
        stat = FileStat(size=1024, mtime=1.0, is_dir=False)
        assert stat.size == 1024
        assert stat.is_dir is False

    def test_dir(self) -> None:
        stat = FileStat(size=0, mtime=0.0, is_dir=True)
        assert stat.is_dir is True

    def test_is_frozen(self) -> None:
        stat = FileStat(size=1, mtime=0.0, is_dir=False)
        with pytest.raises(FrozenInstanceError):
            stat.size = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Merged from test_models_invariants.py (spec: module-aligned test file per source).
# ---------------------------------------------------------------------------


class TestProcEntryRef:
    def test_valid(self) -> None:
        ref = ProcEntryRef(file=Path("a.tcl"), procs=("foo",))
        assert ref.procs == ("foo",)

    def test_empty_procs_rejected(self) -> None:
        with pytest.raises(ValueError, match="procs must be non-empty"):
            ProcEntryRef(file=Path("a.tcl"), procs=())


# ---------------------------------------------------------------------------
# StageDefinition
# ---------------------------------------------------------------------------


class TestStageDefinition:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name must be non-empty"):
            StageDefinition(name="", load_from="base.tcl", steps=("a",))

    def test_empty_steps_rejected(self) -> None:
        with pytest.raises(ValueError, match="steps must be non-empty"):
            StageDefinition(name="syn", load_from="base.tcl", steps=())


# ---------------------------------------------------------------------------
# AddStepAction
# ---------------------------------------------------------------------------


class TestAddStepAction:
    def test_empty_items_rejected(self) -> None:
        with pytest.raises(ValueError, match="items must be non-empty"):
            AddStepAction(action="add_step_after", stage="syn", reference="setup", items=())


# ---------------------------------------------------------------------------
# ProcDecision
# ---------------------------------------------------------------------------


class TestProcDecision:
    def test_valid(self) -> None:
        dec = ProcDecision(
            canonical_name="utils.tcl::helper",
            source_file=Path("utils.tcl"),
            selection_source="base:files.include",
        )
        assert dec.canonical_name.endswith("helper")

    def test_canonical_name_without_double_colon_rejected(self) -> None:
        with pytest.raises(ValueError, match="canonical_name"):
            ProcDecision(
                canonical_name="no-double-colon",
                source_file=Path("utils.tcl"),
                selection_source="base:files.include",
            )

    def test_selection_source_without_colon_rejected(self) -> None:
        with pytest.raises(ValueError, match="selection_source"):
            ProcDecision(
                canonical_name="utils.tcl::helper",
                source_file=Path("utils.tcl"),
                selection_source="no-colon",
            )


# ---------------------------------------------------------------------------
# FileProvenance
# ---------------------------------------------------------------------------


class TestFileProvenance:
    def test_valid(self) -> None:
        fp = FileProvenance(path=Path("a.tcl"), treatment=FileTreatment.FULL_COPY, reason="fi-literal")
        assert fp.proc_model is None

    def test_input_sources_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="input_sources must be lex-sorted"):
            FileProvenance(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=("b:x", "a:x"),
            )

    def test_vetoed_entries_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="vetoed_entries must be lex-sorted"):
            FileProvenance(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                vetoed_entries=("b:x", "a:x"),
            )

    def test_proc_model_on_non_proc_trim_rejected(self) -> None:
        with pytest.raises(ValueError, match="proc_model is only valid for PROC_TRIM"):
            FileProvenance(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                proc_model="additive",
            )


# ---------------------------------------------------------------------------
# StageSpec
# ---------------------------------------------------------------------------


class TestStageSpec:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name must be non-empty"):
            StageSpec(name="", steps=("a",))

    def test_empty_steps_rejected(self) -> None:
        with pytest.raises(ValueError, match="steps must be non-empty"):
            StageSpec(name="syn", steps=())


# ---------------------------------------------------------------------------
# LoadedConfig
# ---------------------------------------------------------------------------


class TestLoadedConfig:
    def test_surface_files_unsorted_rejected(self) -> None:
        from chopper.core.models import BaseJson

        base = BaseJson(source_path=Path("base.json"), domain="d")
        with pytest.raises(ValueError, match="surface_files must be sorted"):
            LoadedConfig(base=base, surface_files=(Path("b.tcl"), Path("a.tcl")))

    def test_duplicate_feature_names_rejected(self) -> None:
        from chopper.core.models import BaseJson, FeatureJson

        base = BaseJson(source_path=Path("base.json"), domain="d")
        f1 = FeatureJson(source_path=Path("f1.json"), name="dupe")
        f2 = FeatureJson(source_path=Path("f2.json"), name="dupe")
        with pytest.raises(ValueError, match="duplicate names"):
            LoadedConfig(base=base, features=(f1, f2))


# ---------------------------------------------------------------------------
# CompiledManifest
# ---------------------------------------------------------------------------


def _make_provenance(path: Path, treatment: FileTreatment = FileTreatment.FULL_COPY) -> FileProvenance:
    return FileProvenance(path=path, treatment=treatment, reason="fi-literal")


class TestCompiledManifest:
    def test_file_decisions_unsorted_rejected(self) -> None:
        # Python 3.7+ dicts preserve insertion order; construct unsorted keys.
        fd = {Path("b.tcl"): FileTreatment.FULL_COPY, Path("a.tcl"): FileTreatment.FULL_COPY}
        pv = {Path("a.tcl"): _make_provenance(Path("a.tcl")), Path("b.tcl"): _make_provenance(Path("b.tcl"))}
        with pytest.raises(ValueError, match="file_decisions must be lex-sorted"):
            CompiledManifest(file_decisions=fd, provenance=pv)

    def test_proc_decisions_unsorted_rejected(self) -> None:
        fd = {Path("a.tcl"): FileTreatment.FULL_COPY}
        pv = {Path("a.tcl"): _make_provenance(Path("a.tcl"))}
        pd = {
            "a.tcl::z_last": ProcDecision(
                canonical_name="a.tcl::z_last",
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            ),
            "a.tcl::a_first": ProcDecision(
                canonical_name="a.tcl::a_first",
                source_file=Path("a.tcl"),
                selection_source="base:files.include",
            ),
        }
        with pytest.raises(ValueError, match="proc_decisions keys must be lex-sorted"):
            CompiledManifest(file_decisions=fd, proc_decisions=pd, provenance=pv)

    def test_provenance_unsorted_rejected(self) -> None:
        fd = {Path("a.tcl"): FileTreatment.FULL_COPY, Path("b.tcl"): FileTreatment.FULL_COPY}
        pv = {Path("b.tcl"): _make_provenance(Path("b.tcl")), Path("a.tcl"): _make_provenance(Path("a.tcl"))}
        with pytest.raises(ValueError, match="provenance must be lex-sorted"):
            CompiledManifest(file_decisions=fd, provenance=pv)

    def test_provenance_keyset_mismatch_rejected(self) -> None:
        fd = {Path("a.tcl"): FileTreatment.FULL_COPY}
        pv = {Path("b.tcl"): _make_provenance(Path("b.tcl"))}
        with pytest.raises(ValueError, match="provenance keys must match"):
            CompiledManifest(file_decisions=fd, provenance=pv)

    def test_provenance_decision_treatment_drift_rejected(self) -> None:
        fd = {Path("a.tcl"): FileTreatment.FULL_COPY}
        pv = {Path("a.tcl"): _make_provenance(Path("a.tcl"), treatment=FileTreatment.REMOVE)}
        with pytest.raises(ValueError, match="provenance/decision mismatch"):
            CompiledManifest(file_decisions=fd, provenance=pv)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


class TestEdge:
    def test_resolved_without_callee_rejected(self) -> None:
        with pytest.raises(ValueError, match="callee is required"):
            Edge(caller="a.tcl::foo", callee="", kind="proc_call", status="resolved", token="bar", line=5)

    def test_resolved_with_diagnostic_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="diagnostic_code must be None"):
            Edge(
                caller="a.tcl::foo",
                callee="a.tcl::bar",
                kind="proc_call",
                status="resolved",
                token="bar",
                line=5,
                diagnostic_code="TW-01",
            )

    def test_unresolved_without_diagnostic_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="diagnostic_code is required"):
            Edge(caller="a.tcl::foo", callee="", kind="proc_call", status="unresolved", token="bar", line=5)

    def test_non_positive_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="line must be 1-indexed positive"):
            Edge(
                caller="a.tcl::foo",
                callee="",
                kind="proc_call",
                status="unresolved",
                token="bar",
                line=0,
                diagnostic_code="TW-02",
            )


# ---------------------------------------------------------------------------
# DependencyGraph
# ---------------------------------------------------------------------------


class TestDependencyGraph:
    def _valid(self, **overrides: object) -> DependencyGraph:
        kwargs: dict[str, object] = dict(
            pi_seeds=("a.tcl::a",),
            nodes=("a.tcl::a",),
            pt=(),
            edges=(),
            reachable_from_includes=frozenset({"a.tcl::a"}),
        )
        kwargs.update(overrides)
        return DependencyGraph(**kwargs)  # type: ignore[arg-type]

    def test_valid(self) -> None:
        g = self._valid()
        assert g.nodes == ("a.tcl::a",)

    def test_nodes_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="nodes must be lex-sorted"):
            self._valid(
                nodes=("b", "a"),
                pi_seeds=("a",),
                reachable_from_includes=frozenset({"a", "b"}),
                pt=("b",),
            )

    def test_nodes_non_unique_rejected(self) -> None:
        with pytest.raises(ValueError, match="nodes must be unique"):
            self._valid(
                nodes=("a", "a"),
                pi_seeds=("a",),
                reachable_from_includes=frozenset({"a"}),
                pt=(),
            )

    def test_pi_seeds_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="pi_seeds must be lex-sorted"):
            self._valid(
                pi_seeds=("b", "a"),
                nodes=("a", "b"),
                reachable_from_includes=frozenset({"a", "b"}),
                pt=(),
            )

    def test_pi_seeds_not_subset_rejected(self) -> None:
        with pytest.raises(ValueError, match="pi_seeds must be a subset"):
            self._valid(
                pi_seeds=("zzz",),
                nodes=("a",),
                reachable_from_includes=frozenset({"a"}),
                pt=(),
            )

    def test_pt_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="pt must equal"):
            self._valid(
                pi_seeds=("a",),
                nodes=("a", "b"),
                reachable_from_includes=frozenset({"a", "b"}),
                pt=(),  # expected ("b",)
            )

    def test_reachable_from_includes_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="reachable_from_includes"):
            self._valid(
                pi_seeds=("a",),
                nodes=("a",),
                reachable_from_includes=frozenset(),
                pt=(),
            )

    def test_edges_unsorted_rejected(self) -> None:
        e1 = Edge(caller="a.tcl::z", callee="a.tcl::a", kind="proc_call", status="resolved", token="a", line=1)
        e2 = Edge(caller="a.tcl::a", callee="a.tcl::a", kind="proc_call", status="resolved", token="a", line=1)
        with pytest.raises(ValueError, match="edges must be sorted"):
            self._valid(edges=(e1, e2))


# ---------------------------------------------------------------------------
# FileOutcome
# ---------------------------------------------------------------------------


class TestFileOutcome:
    def test_negative_bytes_in_rejected(self) -> None:
        with pytest.raises(ValueError, match="byte counts must be non-negative"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=-1,
                bytes_out=0,
                procs_kept=(),
                procs_removed=(),
            )

    def test_negative_bytes_out_rejected(self) -> None:
        with pytest.raises(ValueError, match="byte counts must be non-negative"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.PROC_TRIM,
                bytes_in=10,
                bytes_out=-5,
                procs_kept=(),
                procs_removed=(),
            )

    def test_procs_kept_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="procs_kept must be lex-sorted"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=10,
                bytes_out=10,
                procs_kept=("z", "a"),
                procs_removed=(),
            )

    def test_procs_removed_unsorted_rejected(self) -> None:
        with pytest.raises(ValueError, match="procs_removed must be lex-sorted"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.PROC_TRIM,
                bytes_in=10,
                bytes_out=5,
                procs_kept=(),
                procs_removed=("z", "a"),
            )

    def test_remove_with_nonzero_bytes_out_rejected(self) -> None:
        with pytest.raises(ValueError, match="REMOVE treatment requires bytes_out == 0"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.REMOVE,
                bytes_in=10,
                bytes_out=5,
                procs_kept=(),
                procs_removed=(),
            )

    def test_full_copy_with_procs_removed_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not list procs_removed"):
            FileOutcome(
                path=Path("a.tcl"),
                treatment=FileTreatment.FULL_COPY,
                bytes_in=10,
                bytes_out=10,
                procs_kept=(),
                procs_removed=("foo",),
            )


# ---------------------------------------------------------------------------
# TrimReport
# ---------------------------------------------------------------------------


def _make_outcome(
    path: str,
    treatment: FileTreatment = FileTreatment.FULL_COPY,
    *,
    procs_kept: tuple[str, ...] = (),
    procs_removed: tuple[str, ...] = (),
) -> FileOutcome:
    return FileOutcome(
        path=Path(path),
        treatment=treatment,
        bytes_in=10 if treatment is not FileTreatment.REMOVE else 0,
        bytes_out=10 if treatment is not FileTreatment.REMOVE else 0,
        procs_kept=procs_kept,
        procs_removed=procs_removed,
    )


class TestTrimReport:
    def test_outcomes_unsorted_rejected(self) -> None:
        outcomes = (_make_outcome("b.tcl"), _make_outcome("a.tcl"))
        with pytest.raises(ValueError, match="outcomes must be lex-sorted"):
            TrimReport(
                outcomes=outcomes,
                files_copied=2,
                files_trimmed=0,
                files_removed=0,
                procs_kept_total=0,
                procs_removed_total=0,
            )

    def test_files_copied_mismatch_rejected(self) -> None:
        outcomes = (_make_outcome("a.tcl"),)
        with pytest.raises(ValueError, match="files_copied mismatch"):
            TrimReport(
                outcomes=outcomes,
                files_copied=99,
                files_trimmed=0,
                files_removed=0,
                procs_kept_total=0,
                procs_removed_total=0,
            )

    def test_files_trimmed_mismatch_rejected(self) -> None:
        outcomes = (_make_outcome("a.tcl"),)
        with pytest.raises(ValueError, match="files_trimmed mismatch"):
            TrimReport(
                outcomes=outcomes,
                files_copied=1,
                files_trimmed=99,
                files_removed=0,
                procs_kept_total=0,
                procs_removed_total=0,
            )

    def test_files_removed_mismatch_rejected(self) -> None:
        outcomes = (_make_outcome("a.tcl"),)
        with pytest.raises(ValueError, match="files_removed mismatch"):
            TrimReport(
                outcomes=outcomes,
                files_copied=1,
                files_trimmed=0,
                files_removed=99,
                procs_kept_total=0,
                procs_removed_total=0,
            )

    def test_procs_kept_total_mismatch_rejected(self) -> None:
        outcomes = (_make_outcome("a.tcl", procs_kept=("foo",)),)
        with pytest.raises(ValueError, match="procs_kept_total mismatch"):
            TrimReport(
                outcomes=outcomes,
                files_copied=1,
                files_trimmed=0,
                files_removed=0,
                procs_kept_total=99,
                procs_removed_total=0,
            )

    def test_procs_removed_total_mismatch_rejected(self) -> None:
        outcomes = (
            _make_outcome(
                "a.tcl",
                treatment=FileTreatment.PROC_TRIM,
                procs_kept=(),
                procs_removed=("bar",),
            ),
        )
        with pytest.raises(ValueError, match="procs_removed_total mismatch"):
            TrimReport(
                outcomes=outcomes,
                files_copied=0,
                files_trimmed=1,
                files_removed=0,
                procs_kept_total=0,
                procs_removed_total=99,
            )


# ---------------------------------------------------------------------------
# GeneratedArtifact
# ---------------------------------------------------------------------------


class TestGeneratedArtifact:
    def test_empty_source_stage_rejected(self) -> None:
        with pytest.raises(ValueError, match="source_stage must be non-empty"):
            GeneratedArtifact(path=Path("syn.tcl"), kind="tcl", content="", source_stage="")


# ---------------------------------------------------------------------------
# AuditArtifact
# ---------------------------------------------------------------------------


_SHA = "a" * 64


class TestAuditArtifact:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name must be non-empty"):
            AuditArtifact(name="", path=Path("a"), size=1, sha256=_SHA)

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValueError, match="size must be non-negative"):
            AuditArtifact(name="x.json", path=Path("x"), size=-1, sha256=_SHA)

    def test_sha256_wrong_length_rejected(self) -> None:
        with pytest.raises(ValueError, match="sha256 must be a 64-char hex"):
            AuditArtifact(name="x.json", path=Path("x"), size=1, sha256="abcd")

    def test_sha256_non_hex_rejected(self) -> None:
        with pytest.raises(ValueError, match="sha256 must be a 64-char hex"):
            AuditArtifact(name="x.json", path=Path("x"), size=1, sha256="Z" * 64)


# ---------------------------------------------------------------------------
# AuditManifest
# ---------------------------------------------------------------------------


def _art(name: str) -> AuditArtifact:
    return AuditArtifact(name=name, path=Path(name), size=1, sha256=_SHA)


class TestAuditManifest:
    def _now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)

    def test_empty_run_id_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            AuditManifest(run_id="", started_at=now, ended_at=now, exit_code=0, artifacts=())

    def test_invalid_exit_code_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="exit_code must be 0/1/2/3"):
            AuditManifest(run_id="r", started_at=now, ended_at=now, exit_code=99, artifacts=())

    def test_ended_before_started_rejected(self) -> None:
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 1, 2, tzinfo=UTC)
        with pytest.raises(ValueError, match="ended_at must be >= started_at"):
            AuditManifest(run_id="r", started_at=later, ended_at=earlier, exit_code=0, artifacts=())

    def test_artifacts_unsorted_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="artifacts must be lex-sorted"):
            AuditManifest(
                run_id="r",
                started_at=now,
                ended_at=now,
                exit_code=0,
                artifacts=(_art("b.json"), _art("a.json")),
            )

    def test_artifacts_duplicate_names_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="artifacts must have unique names"):
            AuditManifest(
                run_id="r",
                started_at=now,
                ended_at=now,
                exit_code=0,
                artifacts=(_art("a.json"), _art("a.json")),
            )


# ---------------------------------------------------------------------------
# RunRecord
# ---------------------------------------------------------------------------


class TestRunRecord:
    def _now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)

    def test_empty_run_id_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            RunRecord(run_id="", command="trim", started_at=now, ended_at=now, exit_code=0)

    def test_invalid_exit_code_rejected(self) -> None:
        now = self._now()
        with pytest.raises(ValueError, match="exit_code must be 0/1/2/3"):
            RunRecord(run_id="r", command="trim", started_at=now, ended_at=now, exit_code=5)

    def test_ended_before_started_rejected(self) -> None:
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 1, 2, tzinfo=UTC)
        with pytest.raises(ValueError, match="ended_at must be >= started_at"):
            RunRecord(run_id="r", command="trim", started_at=later, ended_at=earlier, exit_code=0)


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


class TestRunResult:
    def test_invalid_exit_code_rejected(self) -> None:
        summary = DiagnosticSummary(errors=0, warnings=0, infos=0)
        with pytest.raises(ValueError, match="exit_code must be 0/1/2/3"):
            RunResult(exit_code=42, summary=summary)


# ---------------------------------------------------------------------------
# Merged from test_parser_models.py (spec: module-aligned test file per source).
# ---------------------------------------------------------------------------


def _make_proc(
    *,
    short: str = "helper",
    qualified: str = "helper",
    file: str = "utils.tcl",
    start: int = 1,
    end: int = 3,
    body_start: int | None = None,
    body_end: int | None = None,
    namespace_path: str = "",
    calls: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    dpa: tuple[int, int] | None = None,
    comment: tuple[int, int] | None = None,
) -> ProcEntry:
    path = Path(file)
    return ProcEntry(
        canonical_name=f"{path.as_posix()}::{qualified}",
        short_name=short,
        qualified_name=qualified,
        source_file=path,
        start_line=start,
        end_line=end,
        body_start_line=body_start if body_start is not None else start + 1,
        body_end_line=body_end if body_end is not None else end - 1,
        namespace_path=namespace_path,
        calls=calls,
        source_refs=source_refs,
        dpa_start_line=dpa[0] if dpa else None,
        dpa_end_line=dpa[1] if dpa else None,
        comment_start_line=comment[0] if comment else None,
        comment_end_line=comment[1] if comment else None,
    )


class TestProcEntryCanonicalName:
    """TCL_PARSER_SPEC §4.3.1 canonical-name test vectors."""

    @pytest.mark.parametrize(
        ("file_path", "qualified_name", "expected"),
        [
            ("utils.tcl", "helper", "utils.tcl::helper"),
            ("utils.tcl", "a::helper", "utils.tcl::a::helper"),
            ("utils.tcl", "a::b::helper", "utils.tcl::a::b::helper"),
            ("utils.tcl", "abs::x", "utils.tcl::abs::x"),
            ("common/helpers.tcl", "foo", "common/helpers.tcl::foo"),
            ("common/helpers.tcl", "ns::foo", "common/helpers.tcl::ns::foo"),
            ("sub/dir/f.tcl", "p::q::r", "sub/dir/f.tcl::p::q::r"),
        ],
    )
    def test_canonical_name_matches_spec_vector(self, file_path: str, qualified_name: str, expected: str) -> None:
        proc = ProcEntry(
            canonical_name=expected,
            short_name=qualified_name.rsplit("::", 1)[-1],
            qualified_name=qualified_name,
            source_file=Path(file_path),
            start_line=1,
            end_line=3,
            body_start_line=2,
            body_end_line=2,
            namespace_path="",
        )
        assert proc.canonical_name == expected

    def test_canonical_name_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="canonical_name"):
            ProcEntry(
                canonical_name="wrong::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=1,
                end_line=3,
                body_start_line=2,
                body_end_line=2,
                namespace_path="",
            )


class TestProcEntryLineInvariants:
    def test_valid_spans(self) -> None:
        proc = _make_proc(start=5, end=10, body_start=6, body_end=9)
        assert proc.start_line <= proc.body_start_line <= proc.body_end_line <= proc.end_line

    def test_one_line_proc(self) -> None:
        # §6.2 edge case: one-line proc ⇒ start==end==body_start==body_end.
        proc = _make_proc(start=5, end=5, body_start=5, body_end=5)
        assert proc.start_line == proc.end_line == 5

    def test_empty_multiline_body_allowed(self) -> None:
        # §6.2 edge case: body_start > body_end means empty body.
        proc = _make_proc(start=3, end=4, body_start=4, body_end=3)
        assert proc.body_start_line > proc.body_end_line

    def test_whitespace_body(self) -> None:
        # §6.2 edge case: blank lines inside body.
        proc = _make_proc(start=6, end=9, body_start=7, body_end=8)
        assert proc.body_end_line == 8

    def test_zero_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive 1-indexed"):
            _make_proc(start=0, end=3)

    def test_negative_line_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive 1-indexed"):
            _make_proc(start=1, end=3, body_start=-1)

    def test_start_after_end_rejected(self) -> None:
        with pytest.raises(ValueError, match="start_line"):
            _make_proc(start=10, end=5, body_start=5, body_end=5)

    def test_body_outside_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="body_start_line"):
            _make_proc(start=5, end=10, body_start=20, body_end=9)

    def test_body_end_outside_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="body_end_line"):
            _make_proc(start=5, end=10, body_start=6, body_end=20)


class TestProcEntryOptionalSpans:
    def test_dpa_both_set(self) -> None:
        proc = _make_proc(dpa=(11, 13))
        assert proc.dpa_start_line == 11
        assert proc.dpa_end_line == 13

    def test_dpa_only_start_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa_start_line and dpa_end_line"):
            ProcEntry(
                canonical_name="utils.tcl::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=1,
                end_line=3,
                body_start_line=2,
                body_end_line=2,
                namespace_path="",
                dpa_start_line=5,
                dpa_end_line=None,
            )

    def test_dpa_inverted_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa_start_line"):
            _make_proc(dpa=(13, 11))

    def test_dpa_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="dpa span"):
            _make_proc(dpa=(0, 2))

    def test_comment_both_set(self) -> None:
        proc = _make_proc(comment=(1, 4), start=5, end=8)
        assert proc.comment_start_line == 1
        assert proc.comment_end_line == 4

    def test_comment_only_end_rejected(self) -> None:
        with pytest.raises(ValueError, match="comment_start_line and comment_end_line"):
            ProcEntry(
                canonical_name="utils.tcl::helper",
                short_name="helper",
                qualified_name="helper",
                source_file=Path("utils.tcl"),
                start_line=5,
                end_line=7,
                body_start_line=6,
                body_end_line=6,
                namespace_path="",
                comment_end_line=4,
            )


class TestProcEntryCallsContract:
    def test_empty_calls_allowed(self) -> None:
        proc = _make_proc(calls=())
        assert proc.calls == ()

    def test_sorted_unique_calls_accepted(self) -> None:
        proc = _make_proc(calls=("a", "b", "c"))
        assert proc.calls == ("a", "b", "c")

    def test_unsorted_calls_rejected(self) -> None:
        with pytest.raises(ValueError, match="calls must be"):
            _make_proc(calls=("b", "a"))

    def test_duplicate_calls_rejected(self) -> None:
        with pytest.raises(ValueError, match="calls must be"):
            _make_proc(calls=("a", "a", "b"))


class TestParsedFile:
    def test_single_proc(self) -> None:
        proc = _make_proc(file="x.tcl", start=1, end=3)
        pf = ParsedFile(path=Path("x.tcl"), procs=(proc,), encoding="utf-8")
        assert pf.procs == (proc,)

    def test_procs_sorted_by_start_line(self) -> None:
        p1 = _make_proc(short="a", qualified="a", file="x.tcl", start=1, end=3)
        p2 = _make_proc(short="b", qualified="b", file="x.tcl", start=5, end=7)
        pf = ParsedFile(path=Path("x.tcl"), procs=(p1, p2), encoding="utf-8")
        assert pf.procs[0].start_line == 1

    def test_procs_out_of_order_rejected(self) -> None:
        p1 = _make_proc(short="a", qualified="a", file="x.tcl", start=5, end=7)
        p2 = _make_proc(short="b", qualified="b", file="x.tcl", start=1, end=3)
        with pytest.raises(ValueError, match="sorted by start_line"):
            ParsedFile(path=Path("x.tcl"), procs=(p1, p2), encoding="utf-8")

    def test_proc_path_mismatch_rejected(self) -> None:
        proc = _make_proc(file="a.tcl")
        with pytest.raises(ValueError, match="source_file"):
            ParsedFile(path=Path("b.tcl"), procs=(proc,), encoding="utf-8")

    def test_latin1_encoding(self) -> None:
        pf = ParsedFile(path=Path("x.tcl"), procs=(), encoding="latin-1")
        assert pf.encoding == "latin-1"


class TestParseResult:
    def test_empty(self) -> None:
        pr = ParseResult()
        assert pr.files == {}
        assert pr.index == {}

    def test_single_file_single_proc(self) -> None:
        proc = _make_proc(file="a.tcl", short="helper", qualified="helper")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        pr = ParseResult(files={Path("a.tcl"): pf}, index={proc.canonical_name: proc})
        assert pr.index["a.tcl::helper"] is proc

    def test_index_missing_proc_rejected(self) -> None:
        proc = _make_proc(file="a.tcl")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        with pytest.raises(ValueError, match="index keys diverge"):
            ParseResult(files={Path("a.tcl"): pf}, index={})

    def test_index_extra_key_rejected(self) -> None:
        proc = _make_proc(file="a.tcl", short="helper", qualified="helper")
        pf = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        # Fabricate a second ProcEntry that isn't in any ParsedFile.
        stray = _make_proc(file="b.tcl", short="stray", qualified="stray")
        with pytest.raises(ValueError, match="index keys diverge"):
            ParseResult(
                files={Path("a.tcl"): pf},
                index={proc.canonical_name: proc, stray.canonical_name: stray},
            )

    def test_duplicate_canonical_across_files_rejected(self) -> None:
        p1 = _make_proc(file="a.tcl", short="helper", qualified="helper")
        # Construct a collision by reusing the canonical string across a different file.
        p2 = ProcEntry(
            canonical_name=p1.canonical_name,
            short_name="helper",
            qualified_name="helper",
            source_file=Path("a.tcl"),  # deliberately same file-path to reach ParseResult check
            start_line=10,
            end_line=12,
            body_start_line=11,
            body_end_line=11,
            namespace_path="",
        )
        pf = ParsedFile(path=Path("a.tcl"), procs=(p1, p2), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate canonical_name"):
            ParseResult(files={Path("a.tcl"): pf}, index={p1.canonical_name: p1})

    def test_index_must_be_sorted(self) -> None:
        p_b = _make_proc(file="a.tcl", short="b", qualified="b")
        p_a = _make_proc(file="a.tcl", short="a", qualified="a", start=5, end=7)
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_b, p_a), encoding="utf-8")
        # Build an index in *non-sorted* insertion order.
        idx = {p_b.canonical_name: p_b, p_a.canonical_name: p_a}
        with pytest.raises(ValueError, match="lexicographically sorted"):
            ParseResult(files={Path("a.tcl"): pf}, index=idx)

    def test_sorted_index_accepted(self) -> None:
        p_a = _make_proc(file="a.tcl", short="a", qualified="a", start=5, end=7)
        p_b = _make_proc(file="a.tcl", short="b", qualified="b", start=1, end=3)
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_b, p_a), encoding="utf-8")
        idx = {p_a.canonical_name: p_a, p_b.canonical_name: p_b}
        pr = ParseResult(files={Path("a.tcl"): pf}, index=idx)
        assert list(pr.index.keys()) == sorted(pr.index.keys())

    def test_index_entry_refers_to_different_instance_rejected(self) -> None:
        # The same canonical_name but a distinct ProcEntry instance — a shape
        # the service layer must never produce.
        kwargs = {
            "canonical_name": "a.tcl::helper",
            "short_name": "helper",
            "qualified_name": "helper",
            "source_file": Path("a.tcl"),
            "start_line": 1,
            "end_line": 3,
            "body_start_line": 2,
            "body_end_line": 2,
            "namespace_path": "",
        }
        p_in_files = ProcEntry(**kwargs)
        p_in_index = ProcEntry(**kwargs)  # equal but not the same instance
        pf = ParsedFile(path=Path("a.tcl"), procs=(p_in_files,), encoding="utf-8")
        with pytest.raises(ValueError, match="same ProcEntry instance"):
            ParseResult(files={Path("a.tcl"): pf}, index={p_in_index.canonical_name: p_in_index})


# ---------------------------------------------------------------------------
# Merged from test_trim_report_invariants.py (spec: module-aligned test file per source).
# ---------------------------------------------------------------------------


def _outcome(
    path: str,
    treatment: FileTreatment,
    *,
    kept: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
    bytes_in: int = 0,
    bytes_out: int = 0,
) -> FileOutcome:
    return FileOutcome(
        path=Path(path),
        treatment=treatment,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
        procs_kept=kept,
        procs_removed=removed,
    )


def test_file_outcome_rejects_unsorted_procs() -> None:
    with pytest.raises(ValueError, match="procs_kept must be lex-sorted"):
        _outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("b", "a"))


def test_file_outcome_rejects_remove_with_bytes_out() -> None:
    with pytest.raises(ValueError, match="REMOVE treatment requires bytes_out == 0"):
        _outcome("a.tcl", FileTreatment.REMOVE, bytes_in=10, bytes_out=5)


def test_file_outcome_rejects_full_copy_with_procs_removed() -> None:
    with pytest.raises(ValueError, match="must not list procs_removed"):
        _outcome("a.tcl", FileTreatment.FULL_COPY, removed=("x",))


def test_file_outcome_rejects_negative_bytes() -> None:
    with pytest.raises(ValueError, match="byte counts must be non-negative"):
        _outcome("a.tcl", FileTreatment.FULL_COPY, bytes_in=-1)


def test_trim_report_rejects_unsorted_outcomes() -> None:
    outcomes = (
        _outcome("z.tcl", FileTreatment.FULL_COPY),
        _outcome("a.tcl", FileTreatment.FULL_COPY),
    )
    with pytest.raises(ValueError, match="lex-sorted by POSIX path"):
        TrimReport(
            outcomes=outcomes,
            files_copied=2,
            files_trimmed=0,
            files_removed=0,
            procs_kept_total=0,
            procs_removed_total=0,
        )


def test_trim_report_rejects_derived_count_drift() -> None:
    outcomes = (_outcome("a.tcl", FileTreatment.FULL_COPY),)
    with pytest.raises(ValueError, match="files_copied mismatch"):
        TrimReport(
            outcomes=outcomes,
            files_copied=99,
            files_trimmed=0,
            files_removed=0,
            procs_kept_total=0,
            procs_removed_total=0,
        )


def test_trim_report_rejects_proc_count_drift() -> None:
    outcomes = (_outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("a::x",), removed=("a::y",)),)
    with pytest.raises(ValueError, match="procs_kept_total mismatch"):
        TrimReport(
            outcomes=outcomes,
            files_copied=0,
            files_trimmed=1,
            files_removed=0,
            procs_kept_total=5,
            procs_removed_total=1,
        )


def test_trim_report_accepts_consistent_totals() -> None:
    outcomes = (
        _outcome("a.tcl", FileTreatment.PROC_TRIM, kept=("a::x",), removed=("a::y",), bytes_in=10, bytes_out=5),
        _outcome("b.tcl", FileTreatment.FULL_COPY, kept=("b::z",), bytes_in=3, bytes_out=3),
        _outcome("c.tcl", FileTreatment.REMOVE, bytes_in=7),
    )
    report = TrimReport(
        outcomes=outcomes,
        files_copied=1,
        files_trimmed=1,
        files_removed=1,
        procs_kept_total=2,
        procs_removed_total=1,
    )
    assert report.rebuild_interrupted is False
    assert len(report.outcomes) == 3
