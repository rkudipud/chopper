"""Tests for render_p4_branch_analysis."""

from __future__ import annotations

import io

from chopper.cli.render import render_p4_branch_analysis
from chopper.core.models_common import DomainRunResult


def _dr(
    name: str, branch: bool, edits: int = 0, adds: int = 0, removes: int = 0, exit_code: int = 0
) -> DomainRunResult:
    return DomainRunResult(
        domain_logical_name=name,
        exit_code=exit_code,
        branch_needed=branch,
        edits_count=edits,
        adds_count=adds,
        removes_count=removes,
    )


class TestSingleDomain:
    def test_no_branch_prints_no_branch_needed(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis([_dr("snps/fev_formality", False, removes=5)], stream=buf)
        out = buf.getvalue()
        assert "NO BRANCH NEEDED" in out
        assert "snps/fev_formality" in out

    def test_branch_needed_prints_branch_needed(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis([_dr("snps/fev_formality", True, edits=3)], stream=buf)
        out = buf.getvalue()
        assert "BRANCH NEEDED" in out
        assert "3 edit(s)" in out

    def test_empty_list_prints_nothing(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis([], stream=buf)
        assert buf.getvalue() == ""


class TestMultiDomain:
    def test_multi_domain_all_no_branch(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis(
            [
                _dr("snps/fev_formality", False, removes=3),
                _dr("cdns/fev_conformal", False, removes=1),
            ],
            stream=buf,
        )
        out = buf.getvalue()
        assert "Final verdict" in out
        assert "NO BRANCH NEEDED" in out
        # No domain names in the "Domains needing branch" line
        assert "Domains needing branch" not in out

    def test_multi_domain_some_branch(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis(
            [
                _dr("snps/fev_formality", False, removes=5),
                _dr("cdns/fev_conformal", True, edits=2),
            ],
            stream=buf,
        )
        out = buf.getvalue()
        assert "Final verdict     : BRANCH NEEDED" in out
        assert "Domains needing branch: cdns/fev_conformal" in out

    def test_multi_domain_all_branch(self) -> None:
        buf = io.StringIO()
        render_p4_branch_analysis(
            [
                _dr("snps/fev_formality", True, edits=7),
                _dr("cdns/fev_conformal", True, edits=3, adds=2),
            ],
            stream=buf,
        )
        out = buf.getvalue()
        assert "BRANCH NEEDED" in out
        assert "snps/fev_formality" in out
        assert "cdns/fev_conformal" in out
