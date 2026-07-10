"""Tests for :func:`chopper.cli.render.render_p4_checkout_enabled_notice` (FR-53)."""

from __future__ import annotations

import io

from chopper.cli.render import render_p4_checkout_enabled_notice


def test_prints_enabled_notice() -> None:
    buf = io.StringIO()
    render_p4_checkout_enabled_notice(stream=buf)
    out = buf.getvalue()
    assert "--p4 enabled" in out
    assert "p4 edit" in out


def test_flushes_stream() -> None:
    buf = io.StringIO()
    render_p4_checkout_enabled_notice(stream=buf)
    # StringIO.flush() is a no-op but must not raise; content must be present
    # immediately without needing an explicit close().
    assert buf.getvalue() != ""
