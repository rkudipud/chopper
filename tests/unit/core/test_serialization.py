"""Unit tests for :mod:`chopper.core.serialization`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from pathlib import Path

import pytest

from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_common import DomainState, FileTreatment
from chopper.core.serialization import dump_model, loads


class TestPrimitives:
    def test_dict(self) -> None:
        out = dump_model({"b": 1, "a": 2})
        assert loads(out) == {"a": 2, "b": 1}
        # sort_keys=True means 'a' precedes 'b' in the text.
        assert out.index('"a"') < out.index('"b"')

    def test_list(self) -> None:
        assert loads(dump_model([1, 2, 3])) == [1, 2, 3]

    def test_none(self) -> None:
        assert loads(dump_model(None)) is None

    def test_trailing_newline(self) -> None:
        assert dump_model({}).endswith("\n")


class TestPathEncoding:
    def test_posix_on_all_platforms(self) -> None:
        p = Path("a") / "b" / "c.tcl"
        out = dump_model({"path": p})
        # POSIX form regardless of OS.
        assert '"a/b/c.tcl"' in out

    def test_pure_path_variants(self) -> None:
        # Path subtypes all encode via as_posix().
        p = Path("procs/core.tcl")
        assert "procs/core.tcl" in dump_model({"p": p})


class TestEnumEncoding:
    def test_str_enum(self) -> None:
        out = dump_model({"t": FileTreatment.PROC_TRIM})
        assert loads(out) == {"t": "PROC_TRIM"}

    def test_int_enum(self) -> None:
        out = dump_model({"p": Phase.P3_COMPILE})
        assert loads(out) == {"p": 3}

    def test_custom_enum(self) -> None:
        class Color(StrEnum):
            RED = "red"

        assert loads(dump_model({"c": Color.RED})) == {"c": "red"}

    def test_non_str_int_enum_uses_value(self) -> None:
        class Level(IntEnum):
            LOW = 10

        assert loads(dump_model({"l": Level.LOW})) == {"l": 10}


class TestDatetime:
    def test_datetime_iso(self) -> None:
        ts = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
        out = dump_model({"t": ts})
        assert "2026-04-20T12:00:00+00:00" in out

    def test_timedelta_seconds(self) -> None:
        td = timedelta(seconds=1.5)
        assert loads(dump_model({"d": td})) == {"d": 1.5}


class TestCollections:
    def test_tuple_preserves_order(self) -> None:
        assert loads(dump_model({"xs": (3, 1, 2)})) == {"xs": [3, 1, 2]}

    def test_set_sorted(self) -> None:
        out = dump_model({"xs": {"b", "a", "c"}})
        assert loads(out) == {"xs": ["a", "b", "c"]}

    def test_frozenset_sorted(self) -> None:
        out = dump_model({"xs": frozenset([3, 1, 2])})
        assert loads(out) == {"xs": [1, 2, 3]}


class TestDataclass:
    def test_frozen_dataclass(self) -> None:
        state = DomainState(case=2, domain_exists=True, backup_exists=True, hand_edited=False)
        out = dump_model(state)
        parsed = loads(out)
        assert parsed == {
            "case": 2,
            "domain_exists": True,
            "backup_exists": True,
            "hand_edited": False,
        }

    def test_nested_dataclass(self) -> None:
        @dataclass(frozen=True)
        class Outer:
            inner: DomainState
            name: str

        outer = Outer(
            inner=DomainState(case=1, domain_exists=True, backup_exists=False, hand_edited=False),
            name="test",
        )
        parsed = loads(dump_model(outer))
        assert parsed["name"] == "test"
        assert parsed["inner"]["case"] == 1

    def test_diagnostic_round_trip(self) -> None:
        diag = Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="file missing",
            path=Path("procs/a.tcl"),
            line_no=5,
        )
        parsed = loads(dump_model(diag))
        assert parsed["code"] == "VE-06"
        assert parsed["slug"] == "file-not-in-domain"
        assert parsed["severity"] == "error"
        assert parsed["phase"] == 1
        assert parsed["path"] == "procs/a.tcl"


class TestDeterminism:
    def test_stable_output_across_dict_insertion_orders(self) -> None:
        a = dump_model({"x": 1, "y": 2, "z": 3})
        b = dump_model({"z": 3, "y": 2, "x": 1})
        assert a == b

    def test_sets_stable(self) -> None:
        a = dump_model({"xs": {1, 2, 3}})
        b = dump_model({"xs": {3, 2, 1}})
        assert a == b


class TestRejectUnsupported:
    def test_unserialisable_raises(self) -> None:
        class Opaque:
            pass

        with pytest.raises(TypeError, match="not JSON-serialisable"):
            dump_model({"o": Opaque()})

    def test_heterogeneous_set_is_deterministic(self) -> None:
        # Heterogeneous sets (e.g. {1, "a"}) are allowed: the encoder
        # falls back to a (type_name, repr) sort key for stability.
        a = dump_model({"xs": {1, "a"}})
        b = dump_model({"xs": {"a", 1}})
        assert a == b


# ------------------------------------------------------------------
# Extracted from test_final_coverage_push.py (module-aligned consolidation).
# ------------------------------------------------------------------


def test_serialization_encodes_intenum_via_value() -> None:
    """``IntEnum`` values must serialise via ``.value`` (line 49). Use a
    plain Enum with non-int value because dataclasses.asdict pre-converts
    IntEnum to int already."""
    from enum import Enum

    from chopper.core.serialization import dump_model

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    @dataclass(frozen=True)
    class Thing:
        color: Color

    text = dump_model(Thing(color=Color.RED))
    payload = json.loads(text)
    assert payload["color"] == "red"


# ------------------------------------------------------------------
# Extracted from test_small_modules_torture.py (module-aligned consolidation).
# ------------------------------------------------------------------


def test_serialization_encodes_timedelta_as_seconds() -> None:
    from chopper.core.serialization import _encode

    td = timedelta(hours=1, minutes=30)
    assert _encode(td) == 5400.0
