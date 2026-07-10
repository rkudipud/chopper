"""Tests for :func:`chopper.cli.render.render_p4_checkout_opened` (FR-53)."""

from __future__ import annotations

import io
from pathlib import Path

from chopper.cli.render import render_p4_checkout_opened


class TestSingleDomain:
    def test_prints_header_and_paths(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        paths = [tmp_path / "a.tcl", tmp_path / "b.tcl"]
        render_p4_checkout_opened([("my_domain", paths)], stream=buf)
        out = buf.getvalue()
        assert "=== P4 Files Opened for Edit ===" in out
        assert paths[0].as_posix() in out
        assert paths[1].as_posix() in out
        # Single-domain form has no per-domain label line.
        assert "my_domain:" not in out

    def test_empty_paths_prints_nothing(self) -> None:
        buf = io.StringIO()
        render_p4_checkout_opened([("my_domain", [])], stream=buf)
        assert buf.getvalue() == ""

    def test_empty_entries_list_prints_nothing(self) -> None:
        buf = io.StringIO()
        render_p4_checkout_opened([], stream=buf)
        assert buf.getvalue() == ""


class TestMultiDomain:
    def test_prints_labeled_block_per_domain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        paths_a = [tmp_path / "dom_a" / "a.tcl"]
        paths_b = [tmp_path / "dom_b" / "b.tcl"]
        render_p4_checkout_opened(
            [("snps/fev_formality", paths_a), ("cdns/fev_conformal", paths_b)],
            stream=buf,
        )
        out = buf.getvalue()
        assert "=== P4 Files Opened for Edit ===" in out
        assert "snps/fev_formality:" in out
        assert paths_a[0].as_posix() in out
        assert "cdns/fev_conformal:" in out
        assert paths_b[0].as_posix() in out

    def test_domains_with_no_checked_out_files_excluded(self, tmp_path: Path) -> None:
        """Multi-domain input (len(entries) > 1) keeps its per-domain label
        even when only one domain actually checked out files -- matching
        render_audit_bundle_locations, which decides single- vs multi-domain
        form from the original entry count, not the post-filter count."""
        buf = io.StringIO()
        paths_a = [tmp_path / "dom_a" / "a.tcl"]
        render_p4_checkout_opened(
            [("snps/fev_formality", paths_a), ("cdns/no_p4_files", [])],
            stream=buf,
        )
        out = buf.getvalue()
        assert "snps/fev_formality:" in out
        assert paths_a[0].as_posix() in out
        assert "cdns/no_p4_files" not in out

    def test_all_domains_empty_prints_nothing(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        render_p4_checkout_opened(
            [("dom_a", []), ("dom_b", [])],
            stream=buf,
        )
        assert buf.getvalue() == ""
