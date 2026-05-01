"""Cross-source L1/L3 aggregation tests (architecture doc §4 R1, §5.3 step 3).

Exercise the compiler with multiple sources (base + features) to verify
``L1`` (explicit include always wins) and ``L3`` (cross-source additivity;
base inviolable; ``VW-18`` / ``VW-19`` vetoes).
"""

from __future__ import annotations

from pathlib import Path

from chopper.compiler import CompilerService
from chopper.core.models_common import FileTreatment
from tests.unit.compiler._helpers import (
    files_section,
    make_base,
    make_ctx,
    make_feature,
    make_loaded,
    make_parsed,
    proc_ref,
    procs_section,
)

# ---------------------------------------------------------------------------
# L1 — at least one WHOLE → FULL_COPY everywhere
# ---------------------------------------------------------------------------


class TestWholeAlwaysWins:
    def test_whole_base_beats_feature_fe(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(include=("a.tcl",)))
        feat = make_feature("dft", files=files_section(exclude=("a.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
        assert sink.codes() == ["VW-19"]
        pv = manifest.provenance[Path("a.tcl")]
        assert "dft:files.exclude" in pv.vetoed_entries
        assert "base:files.include" in pv.input_sources

    def test_feature_whole_beats_base_pe(self) -> None:
        """A feature's FI lifting a file to FULL_COPY vetoes base PE (VW-18)."""
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)))
        feat = make_feature("dft", files=files_section(include=("a.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
        assert sink.codes() == ["VW-18"]
        pv = manifest.provenance[Path("a.tcl")]
        assert any("base:procedures.exclude" in v for v in pv.vetoed_entries)

    def test_feature_fi_glob_also_produces_full_copy(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"procs/a.tcl": ["foo"]})
        base = make_base()
        feat = make_feature("dft", files=files_section(include=("procs/*.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("procs/a.tcl")] is FileTreatment.FULL_COPY
        assert manifest.provenance[Path("procs/a.tcl")].reason == "fi-glob"


# ---------------------------------------------------------------------------
# L3 — TRIM across sources → PROC_TRIM with unioned keep sets
# ---------------------------------------------------------------------------


class TestTrimUnion:
    def test_pi_union_across_sources(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz", "qux"]})
        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        feat = make_feature("dft", procedures=procs_section(include=(proc_ref("a.tcl", "bar"),)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::bar"}
        assert sink.codes() == []

    def test_feature_pe_vetoed_by_base_pi(self) -> None:
        """Base PI of ``bar`` vetoes feature's PE of ``bar`` → VW-18. Feature's
        row-6 PE-only authoring still contributes ``foo`` via union, so both
        procs survive (architecture doc §4 L3 additive-only)."""
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "bar"),)))
        feat = make_feature("dft", procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::bar"}
        assert sink.codes() == ["VW-18"]
        pv = manifest.provenance[Path("a.tcl")]
        assert "dft:procedures.exclude:a.tcl::bar" in pv.vetoed_entries

    def test_first_source_wins_selection_source(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        feat = make_feature("dft", procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        pd = manifest.proc_decisions["a.tcl::foo"]
        assert pd.selection_source == "base:procedures.include"


# ---------------------------------------------------------------------------
# L3 — order independence for F1/F2
# ---------------------------------------------------------------------------


class TestOrderIndependence:
    def test_two_features_same_result_regardless_of_order(self) -> None:
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        feat_a = make_feature("dft", procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        feat_b = make_feature("power", procedures=procs_section(include=(proc_ref("a.tcl", "bar"),)))

        # Run in both orders, compare surviving sets.
        ctx1, _ = make_ctx()
        loaded_ab = make_loaded(make_base(), feat_a, feat_b)
        m_ab = CompilerService().run(ctx1, loaded_ab, parsed)

        ctx2, _ = make_ctx()
        loaded_ba = make_loaded(make_base(), feat_b, feat_a)
        m_ba = CompilerService().run(ctx2, loaded_ba, parsed)

        assert set(m_ab.proc_decisions) == set(m_ba.proc_decisions)
        assert m_ab.file_decisions == m_ba.file_decisions


# ---------------------------------------------------------------------------
# FE veto surfacing
# ---------------------------------------------------------------------------


class TestFEVetoSurfacing:
    def test_feature_fe_vetoed_by_base_pi(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        feat = make_feature("dft", files=files_section(exclude=("a.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert sink.codes() == ["VW-19"]
        pv = manifest.provenance[Path("a.tcl")]
        assert "dft:files.exclude" in pv.vetoed_entries

    def test_no_veto_when_every_source_excludes(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(exclude=("a.tcl",)))
        feat = make_feature("dft", files=files_section(exclude=("a.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE
        # No contributor exists → no cross-source veto to surface.
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# REMOVE coverage — domain files with no source interest
# ---------------------------------------------------------------------------


class TestDefaultExclude:
    def test_untouched_parsed_file_removed_by_default(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"], "b.tcl": ["bar"]})
        base = make_base(files=files_section(include=("a.tcl",)))
        feat = make_feature("dft", files=files_section(include=("a.tcl",)))
        loaded = make_loaded(base, feat)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("b.tcl")] is FileTreatment.REMOVE
        assert manifest.provenance[Path("b.tcl")].reason == "default-exclude"


# ---------------------------------------------------------------------------
# Literal file in FI but not parsed (non-.tcl companion)
# ---------------------------------------------------------------------------


class TestUnparsedLiteralFile:
    def test_unparsed_literal_fi_appears_as_full_copy_without_procs(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(include=("a.tcl", "config.json")))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("config.json")] is FileTreatment.FULL_COPY
        assert manifest.provenance[Path("config.json")].reason == "fi-literal"
        # No procs from a file the parser never saw.
        assert all(pd.source_file != Path("config.json") for pd in manifest.proc_decisions.values())
