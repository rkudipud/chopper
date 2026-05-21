"""Unit tests for chopper.core.errors — the programmer-error hierarchy."""

from __future__ import annotations

import pytest

from chopper.core.errors import ChopperError, ProgrammerError, UnknownDiagnosticCodeError


def test_chopper_error_is_exception() -> None:
    assert issubclass(ChopperError, Exception)


def test_unknown_code_error_is_chopper_error() -> None:
    assert issubclass(UnknownDiagnosticCodeError, ChopperError)


def test_programmer_error_is_chopper_error() -> None:
    assert issubclass(ProgrammerError, ChopperError)


def test_raise_and_catch_via_base() -> None:
    with pytest.raises(ChopperError):
        raise UnknownDiagnosticCodeError("ZZ-99")

    with pytest.raises(ChopperError):
        raise ProgrammerError("invariant violated")


def test_error_message_preserved() -> None:
    err = UnknownDiagnosticCodeError("PE-99")
    assert "PE-99" in str(err)
