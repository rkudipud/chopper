"""Tests for render_p4_checkout_notice."""

from __future__ import annotations

import io

from chopper.cli.render import render_p4_checkout_notice


class _FakeStream(io.StringIO):
    """``io.StringIO`` with a controllable ``isatty()`` result."""

    def __init__(self, *, isatty: bool) -> None:
        super().__init__()
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty


class TestMessageContent:
    def test_message_contains_reason_and_fallback_notice(self) -> None:
        buf = io.StringIO()
        render_p4_checkout_notice("p4 not found on PATH", plain=True, stream=buf)
        out = buf.getvalue()
        assert "P4 EDIT NOT POSSIBLE" in out
        assert "p4 not found on PATH" in out
        assert "Trimming in place without P4 checkout" in out


class TestColorBehavior:
    def test_color_when_not_plain_and_tty(self) -> None:
        stream = _FakeStream(isatty=True)
        render_p4_checkout_notice("no active P4 client", plain=False, stream=stream)
        out = stream.getvalue()
        assert "\x1b[31m" in out
        assert "\x1b[0m" in out

    def test_no_color_when_plain_even_if_tty(self) -> None:
        stream = _FakeStream(isatty=True)
        render_p4_checkout_notice("no active P4 client", plain=True, stream=stream)
        out = stream.getvalue()
        assert "\x1b[31m" not in out
        assert "\x1b[0m" not in out

    def test_no_color_when_not_plain_and_not_tty(self) -> None:
        stream = _FakeStream(isatty=False)
        render_p4_checkout_notice("no active P4 client", plain=False, stream=stream)
        out = stream.getvalue()
        assert "\x1b[31m" not in out
        assert "\x1b[0m" not in out

    def test_plain_stringio_default_is_not_a_tty(self) -> None:
        buf = io.StringIO()
        render_p4_checkout_notice("no active P4 client", plain=False, stream=buf)
        out = buf.getvalue()
        assert "\x1b[31m" not in out
        assert "\x1b[0m" not in out


class TestDefaultStream:
    def test_no_explicit_stream_does_not_raise(self) -> None:
        render_p4_checkout_notice("p4 not found on PATH", plain=True)
