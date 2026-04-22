"""Per-source L2 classification tests (bible §4 R1 L2, 16-row matrix).

These tests drive one base JSON (no features) through
:class:`CompilerService` and inspect the resulting manifest to confirm
that every same-source authoring pattern lands on the treatment +
warnings the bible prescribes.
"""

from __future__ import annotations

from pathlib import Path

from chopper.compiler import CompilerService
from chopper.core.models import FileTreatment
from tests.unit.compiler._helpers import (
    default_state,
    files_section,
    make_base,
    make_ctx,
    make_loaded,
    make_parsed,
    proc_ref,
    procs_section,
)

# ---------------------------------------------------------------------------
# Row 1 — nothing selected
# ---------------------------------------------------------------------------


class TestRow1Nothing:
    def test_file_with_no_selection_is_removed(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base()
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE
        assert manifest.provenance[Path("a.tcl")].reason == "default-exclude"
        assert manifest.proc_decisions == {}
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Row 2 — FI only (literal and glob)
# ---------------------------------------------------------------------------


class TestRow2FullCopy:
    def test_fi_literal_produces_full_copy(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(files=files_section(include=("a.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
        assert manifest.provenance[Path("a.tcl")].reason == "fi-literal"
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::bar"}
        for pd in manifest.proc_decisions.values():
            assert pd.selection_source == "base:files.include"
        assert sink.codes() == []

    def test_fi_glob_produces_full_copy_with_glob_reason(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"procs/a.tcl": ["foo"], "procs/b.tcl": ["bar"]})
        base = make_base(files=files_section(include=("procs/*.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        for p in (Path("procs/a.tcl"), Path("procs/b.tcl")):
            assert manifest.file_decisions[p] is FileTreatment.FULL_COPY
            assert manifest.provenance[p].reason == "fi-glob"

    def test_double_star_glob_across_directories(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"rules/r1.fm.tcl": ["a"], "rules/sub/r2.fm.tcl": ["b"]})
        base = make_base(files=files_section(include=("rules/**/*.fm.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("rules/r1.fm.tcl")] is FileTreatment.FULL_COPY
        assert manifest.file_decisions[Path("rules/sub/r2.fm.tcl")] is FileTreatment.FULL_COPY

    def test_empty_glob_expansion_silently_ignored(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(include=("missing/*.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        # No error, file a.tcl still gets default-exclude REMOVE.
        assert sink.codes() == []
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE


# ---------------------------------------------------------------------------
# Rows 3 & 4 — FE interactions (same source)
# ---------------------------------------------------------------------------


class TestRow3AndRow4FE:
    def test_fe_alone_leaves_file_removed(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(exclude=("a.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE
        # FE alone from the only source → no cross-source veto to emit.
        assert sink.codes() == []

    def test_same_source_fi_literal_survives_fe(self) -> None:
        """Row 4: literal FI always wins over same-source FE."""
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(include=("a.tcl",), exclude=("a.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
        assert sink.codes() == []

    def test_same_source_fi_glob_pruned_by_fe(self) -> None:
        """Row 4 glob-only: glob-matched files are pruned by same-source FE."""
        ctx, _ = make_ctx()
        parsed = make_parsed({"procs/a.tcl": ["foo"], "procs/b.tcl": ["bar"]})
        base = make_base(files=files_section(include=("procs/*.tcl",), exclude=("procs/b.tcl",)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("procs/a.tcl")] is FileTreatment.FULL_COPY
        assert manifest.file_decisions[Path("procs/b.tcl")] is FileTreatment.REMOVE


# ---------------------------------------------------------------------------
# Row 5 — PI only
# ---------------------------------------------------------------------------


class TestRow5PIOnly:
    def test_pi_produces_proc_trim_with_listed_procs(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        path = Path("a.tcl")
        assert manifest.file_decisions[path] is FileTreatment.PROC_TRIM
        assert manifest.provenance[path].reason == "pi-additive"
        assert manifest.provenance[path].proc_model == "additive"
        assert set(manifest.proc_decisions) == {"a.tcl::foo"}
        assert manifest.proc_decisions["a.tcl::foo"].selection_source == "base:procedures.include"
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Row 6 — PE only
# ---------------------------------------------------------------------------


class TestRow6PEOnly:
    def test_pe_produces_proc_trim_with_complement(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        path = Path("a.tcl")
        assert manifest.file_decisions[path] is FileTreatment.PROC_TRIM
        assert manifest.provenance[path].reason == "pe-subtractive"
        assert manifest.provenance[path].proc_model == "subtractive"
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::baz"}
        assert sink.codes() == []

    def test_pe_covering_all_procs_emits_vw13(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            procedures=procs_section(
                exclude=(proc_ref("a.tcl", "foo", "bar"),),
            )
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-13"]
        # File still survives as PROC_TRIM with zero procs.
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert manifest.proc_decisions == {}


# ---------------------------------------------------------------------------
# Row 7 — PI + PE same file → VW-12
# ---------------------------------------------------------------------------


class TestRow7PIAndPE:
    def test_pi_wins_pe_ignored_emits_vw12(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(
            procedures=procs_section(
                include=(proc_ref("a.tcl", "foo"),),
                exclude=(proc_ref("a.tcl", "bar"),),
            )
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-12"]
        assert set(manifest.proc_decisions) == {"a.tcl::foo"}


# ---------------------------------------------------------------------------
# Row 8 — FI + PI → VW-09
# ---------------------------------------------------------------------------


class TestRow8FIAndPI:
    def test_full_copy_wins_pi_redundant_emits_vw09(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(include=("a.tcl",)),
            procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-09"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::bar"}


# ---------------------------------------------------------------------------
# Row 9 — FI + PE → PROC_TRIM minus PE
# ---------------------------------------------------------------------------


class TestRow9FIAndPE:
    def test_fi_literal_and_pe_trims_to_complement(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(
            files=files_section(include=("a.tcl",)),
            procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert manifest.provenance[Path("a.tcl")].reason == "fi-and-pe"
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::baz"}
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Row 10 — FI + PI + PE → VW-09 + trim by PE
# ---------------------------------------------------------------------------


class TestRow10FIPIPE:
    def test_emits_vw09_trims_to_all_minus_pe(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(
            files=files_section(include=("a.tcl",)),
            procedures=procs_section(
                include=(proc_ref("a.tcl", "foo"),),
                exclude=(proc_ref("a.tcl", "bar"),),
            ),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-09"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::baz"}


# ---------------------------------------------------------------------------
# Row 11 — FE + PI (no FI, no PE) → PI contributes; FE moot same-source
# ---------------------------------------------------------------------------


class TestRow11FEAndPI:
    def test_pi_contributes_despite_same_source_fe(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(exclude=("a.tcl",)),
            procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo"}
        # No VW-19: the only source is the contributor; no cross-source veto.
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Row 12 — FE + PE (no FI, no PI) → NONE + VW-11
# ---------------------------------------------------------------------------


class TestRow12FEAndPE:
    def test_fe_and_pe_alone_emits_vw11_and_removes(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(exclude=("a.tcl",)),
            procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-11"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.REMOVE


# ---------------------------------------------------------------------------
# Row 13 — FE + PI + PE → VW-12 (PI wins, PE ignored)
# ---------------------------------------------------------------------------


class TestRow13FEPIPE:
    def test_fe_pi_pe_emits_vw12_only(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(exclude=("a.tcl",)),
            procedures=procs_section(
                include=(proc_ref("a.tcl", "foo"),),
                exclude=(proc_ref("a.tcl", "bar"),),
            ),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-12"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo"}


# ---------------------------------------------------------------------------
# Rows 14 / 15 / 16 — FI + FE combined matrix corners
# ---------------------------------------------------------------------------


class TestRows14Through16:
    def test_row14_fi_literal_fe_pi_emits_vw09_full_copy(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(include=("a.tcl",), exclude=("a.tcl",)),
            procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-09"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.FULL_COPY

    def test_row14_fi_glob_fe_pi_same_source_pruned(self) -> None:
        """Row 14 glob-only: same-source FE prunes → nothing survives from FI."""
        ctx, sink = make_ctx()
        parsed = make_parsed({"procs/a.tcl": ["foo"]})
        base = make_base(
            files=files_section(include=("procs/*.tcl",), exclude=("procs/*.tcl",)),
            procedures=procs_section(include=(proc_ref("procs/a.tcl", "foo"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        # FI glob pruned → FI_any is false → we fall to Row 5 (PI only).
        # This is valid behaviour: the bible Row 14 note says "NONE (glob-only, pruned)",
        # but when PI also exists the PI path kicks in. The result is PROC_TRIM.
        assert manifest.file_decisions[Path("procs/a.tcl")] is FileTreatment.PROC_TRIM
        # No VW-09 (FI was pruned, so PI is no longer redundant).
        assert sink.codes() == []

    def test_row15_fi_literal_fe_pe_trims(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar"]})
        base = make_base(
            files=files_section(include=("a.tcl",), exclude=("a.tcl",)),
            procedures=procs_section(exclude=(proc_ref("a.tcl", "bar"),)),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo"}
        assert sink.codes() == []

    def test_row16_fi_literal_fe_pi_pe_emits_vw09_trims(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo", "bar", "baz"]})
        base = make_base(
            files=files_section(include=("a.tcl",), exclude=("a.tcl",)),
            procedures=procs_section(
                include=(proc_ref("a.tcl", "foo"),),
                exclude=(proc_ref("a.tcl", "bar"),),
            ),
        )
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert sink.codes() == ["VW-09"]
        assert manifest.file_decisions[Path("a.tcl")] is FileTreatment.PROC_TRIM
        assert set(manifest.proc_decisions) == {"a.tcl::foo", "a.tcl::baz"}


# ---------------------------------------------------------------------------
# Qualified-name resolution
# ---------------------------------------------------------------------------


class TestQualifiedNameResolution:
    def test_namespaced_proc_matched_by_short_name(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": []})  # replaced below
        # Rebuild with a namespaced proc directly.
        from chopper.core.models import ParsedFile, ParseResult
        from tests.unit.compiler._helpers import make_proc

        proc = make_proc("a.tcl", "helper", qualified="util::helper", namespace="util")
        parsed_file = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        parsed = ParseResult(files={Path("a.tcl"): parsed_file}, index={proc.canonical_name: proc})

        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "helper"),)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert set(manifest.proc_decisions) == {"a.tcl::util::helper"}

    def test_namespaced_proc_matched_by_qualified_name(self) -> None:
        ctx, _ = make_ctx()
        from chopper.core.models import ParsedFile, ParseResult
        from tests.unit.compiler._helpers import make_proc

        proc = make_proc("a.tcl", "helper", qualified="util::helper", namespace="util")
        parsed_file = ParsedFile(path=Path("a.tcl"), procs=(proc,), encoding="utf-8")
        parsed = ParseResult(files={Path("a.tcl"): parsed_file}, index={proc.canonical_name: proc})

        base = make_base(procedures=procs_section(include=(proc_ref("a.tcl", "util::helper"),)))
        loaded = make_loaded(base)

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert set(manifest.proc_decisions) == {"a.tcl::util::helper"}


# ---------------------------------------------------------------------------
# Manifest invariants — key ordering, provenance consistency
# ---------------------------------------------------------------------------


def test_proc_decisions_and_file_decisions_are_lex_sorted() -> None:
    ctx, _ = make_ctx()
    parsed = make_parsed({"z/z.tcl": ["zz"], "a/a.tcl": ["aa"], "m.tcl": ["mm"]})
    base = make_base(files=files_section(include=("**/*.tcl",)))
    loaded = make_loaded(base)

    manifest = CompilerService().run(ctx, loaded, parsed)

    file_keys = [p.as_posix() for p in manifest.file_decisions]
    assert file_keys == sorted(file_keys)
    assert list(manifest.proc_decisions) == sorted(manifest.proc_decisions)


def test_default_state_fixture_exposed() -> None:
    """``default_state()`` remains usable for tests that ever need it."""
    state = default_state()
    assert state.case == 1
