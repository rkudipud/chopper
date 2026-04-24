"""End-to-end :class:`CompilerService` tests.

These exercise the full public surface: ``ChopperContext`` + ``LoadedConfig``
+ ``ParseResult`` → frozen ``CompiledManifest`` with correct manifest
invariants.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.compiler import CompilerService
from chopper.core.models import CompiledManifest, FileTreatment
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


class TestServiceContract:
    def test_run_returns_frozen_manifest(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        loaded = make_loaded(make_base(files=files_section(include=("a.tcl",))))

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert isinstance(manifest, CompiledManifest)
        # Frozen dataclass guarantees attribute mutation raises.
        with pytest.raises(Exception):
            manifest.stages = (object(),)  # type: ignore[misc]

    def test_stages_empty_in_stage_2b(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        loaded = make_loaded(make_base(files=files_section(include=("a.tcl",))))

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert manifest.stages == ()

    def test_provenance_covers_every_file_decision(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"], "b.tcl": ["bar"]})
        loaded = make_loaded(make_base(files=files_section(include=("a.tcl",))))

        manifest = CompilerService().run(ctx, loaded, parsed)

        assert set(manifest.provenance) == set(manifest.file_decisions)
        for path, treatment in manifest.file_decisions.items():
            assert manifest.provenance[path].treatment is treatment


class TestDeterminism:
    def test_same_inputs_yield_identical_manifests(self) -> None:
        parsed = make_parsed({"a.tcl": ["foo"], "b.tcl": ["bar"]})
        base = make_base(
            files=files_section(include=("a.tcl",)),
            procedures=procs_section(include=(proc_ref("b.tcl", "bar"),)),
        )
        loaded = make_loaded(base)

        ctx1, _ = make_ctx()
        ctx2, _ = make_ctx()
        m1 = CompilerService().run(ctx1, loaded, parsed)
        m2 = CompilerService().run(ctx2, loaded, parsed)

        assert m1 == m2

    def test_diagnostic_emission_order_is_stable(self) -> None:
        """Two runs over the same inputs emit the same diagnostic codes in
        the same order (architecture doc §5.3 emission determinism)."""
        parsed = make_parsed({"a.tcl": ["foo", "bar"], "b.tcl": ["baz"]})
        base = make_base(
            # Row 8 (FI+PI → VW-09) on a.tcl; Row 7 (PI+PE → VW-12) on b.tcl.
            files=files_section(include=("a.tcl",)),
            procedures=procs_section(
                include=(proc_ref("a.tcl", "foo"), proc_ref("b.tcl", "baz")),
                exclude=(proc_ref("b.tcl", "baz"),),
            ),
        )
        loaded = make_loaded(base)

        ctx1, sink1 = make_ctx()
        ctx2, sink2 = make_ctx()
        CompilerService().run(ctx1, loaded, parsed)
        CompilerService().run(ctx2, loaded, parsed)

        assert sink1.codes() == sink2.codes()
        # Emission iterates files lex-sorted: a.tcl before b.tcl, so VW-09 precedes VW-12.
        assert sink1.codes() == ["VW-09", "VW-12"]


class TestRealisticScenario:
    def test_base_plus_two_features_full_pipeline(self) -> None:
        ctx, sink = make_ctx()
        parsed = make_parsed(
            {
                "core/main.tcl": ["main", "init"],
                "core/utils.tcl": ["helper", "cleanup"],
                "features/dft.tcl": ["dft_setup", "dft_run"],
                "features/power.tcl": ["power_setup"],
            }
        )
        base = make_base(
            files=files_section(include=("core/main.tcl",)),
            procedures=procs_section(include=(proc_ref("core/utils.tcl", "helper"),)),
        )
        dft = make_feature(
            "dft",
            files=files_section(include=("features/dft.tcl",)),
        )
        power = make_feature(
            "power",
            procedures=procs_section(include=(proc_ref("features/power.tcl", "power_setup"),)),
        )
        loaded = make_loaded(base, dft, power)

        manifest = CompilerService().run(ctx, loaded, parsed)

        decisions = {p.as_posix(): t for p, t in manifest.file_decisions.items()}
        assert decisions == {
            "core/main.tcl": FileTreatment.FULL_COPY,
            "core/utils.tcl": FileTreatment.PROC_TRIM,
            "features/dft.tcl": FileTreatment.FULL_COPY,
            "features/power.tcl": FileTreatment.PROC_TRIM,
        }
        assert set(manifest.proc_decisions) == {
            "core/main.tcl::main",
            "core/main.tcl::init",
            "core/utils.tcl::helper",
            "features/dft.tcl::dft_setup",
            "features/dft.tcl::dft_run",
            "features/power.tcl::power_setup",
        }
        assert sink.codes() == []

    def test_input_sources_tag_includes_winning_json_field(self) -> None:
        ctx, _ = make_ctx()
        parsed = make_parsed({"a.tcl": ["foo"]})
        base = make_base(files=files_section(include=("a.tcl",)))
        dft = make_feature("dft", procedures=procs_section(include=(proc_ref("a.tcl", "foo"),)))
        loaded = make_loaded(base, dft)

        manifest = CompilerService().run(ctx, loaded, parsed)

        pv = manifest.provenance[Path("a.tcl")]
        assert "base:files.include" in pv.input_sources
        # Note: dft's PI is a TRIM signal but the file is FULL_COPY because of base.
        # The contribution still gets a tag in input_sources.
        assert "dft:procedures.include" in pv.input_sources
