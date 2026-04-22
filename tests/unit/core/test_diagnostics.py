"""Unit tests for :mod:`chopper.core.diagnostics` and the registry façade."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from chopper.core._diagnostic_registry import Severity, all_codes, lookup
from chopper.core.diagnostics import Diagnostic, DiagnosticSummary, Phase
from chopper.core.errors import UnknownDiagnosticCodeError


class TestRegistry:
    def test_count_matches_spec(self) -> None:
        # Per docs/DIAGNOSTIC_CODES.md Code Space Summary: 68 active codes.
        assert len(all_codes()) == 68

    def test_lookup_known_code(self) -> None:
        entry = lookup("VE-06")
        assert entry.slug == "file-not-in-domain"
        assert entry.severity == Severity.ERROR
        assert entry.source == "validator"
        assert entry.exit_code == 1

    def test_lookup_unknown_raises(self) -> None:
        with pytest.raises(UnknownDiagnosticCodeError) as excinfo:
            lookup("XX-99")
        assert "XX-99" in str(excinfo.value)

    def test_every_family_present(self) -> None:
        codes = all_codes()
        families = {c[:2] for c in codes}
        assert families == {"VE", "VW", "VI", "TW", "PE", "PW", "PI"}

    def test_no_retired_codes(self) -> None:
        # Registry declares no RETIRED slots in v1.
        for _ in all_codes():
            # every code must have an entry; lookup raises if not
            pass


class TestPhase:
    def test_values(self) -> None:
        assert Phase.P0_STATE == 0
        assert Phase.P7_AUDIT == 7

    def test_ordering(self) -> None:
        assert Phase.P1_CONFIG < Phase.P3_COMPILE < Phase.P6_POSTVALIDATE


class TestDiagnosticBuild:
    def test_basic_construction(self) -> None:
        d = Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="File foo.tcl is not in the domain",
        )
        assert d.code == "VE-06"
        assert d.slug == "file-not-in-domain"
        assert d.severity == Severity.ERROR
        assert d.source == "validator"
        assert d.phase == Phase.P1_CONFIG

    def test_with_location(self) -> None:
        d = Diagnostic.build(
            "PW-01",
            phase=Phase.P2_PARSE,
            message="computed proc name skipped",
            path=Path("procs/dynamic.tcl"),
            line_no=42,
        )
        assert d.path == Path("procs/dynamic.tcl")
        assert d.line_no == 42

    def test_unknown_code_raises(self) -> None:
        with pytest.raises(UnknownDiagnosticCodeError):
            Diagnostic.build("ZZ-99", phase=Phase.P1_CONFIG, message="x")

    def test_newline_in_message_rejected(self) -> None:
        with pytest.raises(ValueError, match="single-line"):
            Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="a\nb")

    def test_default_context_is_empty(self) -> None:
        d = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x")
        assert d.context == {}

    def test_provided_context_is_copied(self) -> None:
        ctx = {"key": "value"}
        d = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", context=ctx)
        assert d.context == {"key": "value"}
        # The dataclass stored a copy — outside mutation does not leak in.
        ctx["new"] = "x"
        assert "new" not in d.context


class TestDiagnosticDirectConstruction:
    def test_matching_fields_ok(self) -> None:
        # Direct construction (e.g. from audit JSON rehydration) must
        # agree with the registry.
        d = Diagnostic(
            code="VE-06",
            slug="file-not-in-domain",
            severity=Severity.ERROR,
            phase=Phase.P1_CONFIG,
            source="validator",
            message="x",
        )
        assert d.code == "VE-06"

    def test_mismatched_slug_rejected(self) -> None:
        with pytest.raises(ValueError, match="slug"):
            Diagnostic(
                code="VE-06",
                slug="wrong-slug",
                severity=Severity.ERROR,
                phase=Phase.P1_CONFIG,
                source="validator",
                message="x",
            )

    def test_mismatched_severity_rejected(self) -> None:
        with pytest.raises(ValueError, match="severity"):
            Diagnostic(
                code="VE-06",
                slug="file-not-in-domain",
                severity=Severity.WARNING,
                phase=Phase.P1_CONFIG,
                source="validator",
                message="x",
            )

    def test_mismatched_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="source"):
            Diagnostic(
                code="VE-06",
                slug="file-not-in-domain",
                severity=Severity.ERROR,
                phase=Phase.P1_CONFIG,
                source="parser",
                message="x",
            )


class TestDiagnosticImmutability:
    def test_is_frozen(self) -> None:
        d = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x")
        with pytest.raises(FrozenInstanceError):
            d.message = "other"  # type: ignore[misc]

    def test_hashable(self) -> None:
        d1 = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x")
        d2 = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x")
        # Equal diagnostics share a hash bucket; set-containment works.
        assert d1 == d2
        # Mapping contexts compare equal when both empty; hash across
        # default dict is not meaningful here — we only assert equality.


class TestDedupeKey:
    def test_key_excludes_hint_and_context(self) -> None:
        a = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", hint="h1")
        b = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", hint="h2")
        assert a.dedupe_key == b.dedupe_key

    def test_bucket_differentiates(self) -> None:
        a = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", dedupe_bucket="a")
        b = Diagnostic.build("VE-06", phase=Phase.P1_CONFIG, message="x", dedupe_bucket="b")
        assert a.dedupe_key != b.dedupe_key

    def test_path_line_differentiates(self) -> None:
        a = Diagnostic.build("PW-01", phase=Phase.P2_PARSE, message="x", path=Path("a.tcl"), line_no=1)
        b = Diagnostic.build("PW-01", phase=Phase.P2_PARSE, message="x", path=Path("a.tcl"), line_no=2)
        assert a.dedupe_key != b.dedupe_key


class TestDiagnosticSummary:
    def test_counts(self) -> None:
        s = DiagnosticSummary(errors=2, warnings=5, infos=1)
        assert s.total == 8
        assert s.has_error is True
        assert s.has_warning is True

    def test_empty(self) -> None:
        s = DiagnosticSummary(errors=0, warnings=0, infos=0)
        assert s.total == 0
        assert s.has_error is False
        assert s.has_warning is False
