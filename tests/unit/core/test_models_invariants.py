"""Torture tests for frozen-model ``__post_init__`` invariants.

Every ``raise ValueError`` branch in :mod:`chopper.core.models` that
is not already covered by :mod:`tests.unit.core.test_parser_models`
or :mod:`tests.unit.core.test_models` has a dedicated negative test
here. These are pure constructor tests — no I/O, no adapters — and
they pin the shape of the frozen-manifest contract so silent drift
in ``__post_init__`` is impossible.

Each test constructs a minimal valid witness, then mutates one field
into the invalid shape and asserts the expected ``ValueError``. The
match string targets a stable substring of the message so wording
tweaks that preserve the invariant name do not break the test.
"""

from __future__ import annotations

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
    Edge,
    FileOutcome,
    FileProvenance,
    FileTreatment,
    GeneratedArtifact,
    LoadedConfig,
    ProcDecision,
    ProcEntryRef,
    RunRecord,
    RunResult,
    StageDefinition,
    StageSpec,
    TrimReport,
)

# ---------------------------------------------------------------------------
# ProcEntryRef
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
