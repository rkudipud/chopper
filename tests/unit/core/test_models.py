"""Unit tests for :mod:`chopper.core.models` — the Stage 0 shared dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from chopper.core.models import DomainState, FileStat, FileTreatment


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
