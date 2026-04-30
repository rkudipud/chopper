"""End-to-end CLI tests using real :class:`LocalFS` on a tmp_path.

The :mod:`chopper.cli.main` entry point is tested here through
:func:`main(argv)` — no argparse-only stubs, no InMemoryFS mocking.
Each test seeds a real directory on disk, invokes ``main`` with
argv as the user would type, and asserts the exit code + stdout /
stderr capture. This pushes :mod:`chopper.cli.commands` from
21 % → ≥95 % and exercises :mod:`chopper.cli.render` through the
real path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.cli.main import main


def _seed_valid_domain(domain: Path) -> Path:
    """Plant a minimal valid domain + base JSON; return the base path."""

    domain.mkdir(parents=True, exist_ok=True)
    (domain / "vars.tcl").write_text("# vars\nset PI 3.14\n", encoding="utf-8")
    (domain / "helper.tcl").write_text("proc helper_a {} { return 1 }\n", encoding="utf-8")
    jsons = domain / "jsons"
    jsons.mkdir(parents=True, exist_ok=True)
    base_path = jsons / "base.json"
    base_path.write_text(
        json.dumps(
            {
                "$schema": "base-v1",
                "domain": domain.name,
                "files": {"include": ["vars.tcl", "helper.tcl"]},
            }
        ),
        encoding="utf-8",
    )
    return base_path


# ---------------------------------------------------------------------------
# validate subcommand
# ---------------------------------------------------------------------------


class TestValidateSubcommand:
    def test_validate_happy_path_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["validate", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr: {captured.err}"
        # Summary line rendered to stderr by render_result.
        assert "Summary:" in captured.err
        # Audit bundle written.
        assert (domain / ".chopper" / "chopper_run.json").exists()

    def test_validate_with_strict_and_no_warnings_still_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["--strict", "validate", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"strict should not escalate when no warnings; stderr: {captured.err}"

    def test_validate_missing_base_fails_exit_1(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        domain.mkdir(parents=True, exist_ok=True)
        rc = main(["validate", "--domain", str(domain), "--base", str(domain / "jsons" / "ghost.json")])
        captured = capsys.readouterr()
        assert rc == 1, f"stderr: {captured.err}"
        # At least one ERROR diagnostic was rendered.
        assert "ERROR" in captured.err


# ---------------------------------------------------------------------------
# trim subcommand
# ---------------------------------------------------------------------------


class TestTrimSubcommand:
    def test_trim_dry_run_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["trim", "--domain", str(domain), "--base", str(base), "--dry-run"])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr: {captured.err}"
        # Dry-run does not touch domain files; vars.tcl content unchanged.
        assert (domain / "vars.tcl").read_text(encoding="utf-8") == "# vars\nset PI 3.14\n"
        # But audit still wrote.
        assert (domain / ".chopper" / "chopper_run.json").exists()

    def test_trim_live_writes_backup_and_rebuilt_domain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["trim", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr: {captured.err}"
        backup = tmp_path / "mini_backup"
        assert backup.exists(), "backup directory must exist after live trim (Case 1)"
        # Rebuilt domain has the included files.
        assert (domain / "vars.tcl").exists()


# ---------------------------------------------------------------------------
# cleanup subcommand
# ---------------------------------------------------------------------------


class TestCleanupSubcommand:
    def test_cleanup_without_confirm_refuses_exit_2(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        domain.mkdir(parents=True, exist_ok=True)
        rc = main(["cleanup", "--domain", str(domain)])
        captured = capsys.readouterr()
        assert rc == 2, "cleanup must refuse without --confirm"
        # Friendly message routed through render_cleanup_message → stdout.
        assert "--confirm is required" in captured.out

    def test_cleanup_with_no_backup_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        domain.mkdir(parents=True, exist_ok=True)
        rc = main(["cleanup", "--domain", str(domain), "--confirm"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "no backup to remove" in captured.out

    def test_cleanup_removes_existing_backup(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        domain.mkdir(parents=True, exist_ok=True)
        backup = tmp_path / "mini_backup"
        backup.mkdir(parents=True, exist_ok=True)
        (backup / "relic.tcl").write_text("# old", encoding="utf-8")
        rc = main(["cleanup", "--domain", str(domain), "--confirm"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "removed" in captured.out
        assert not backup.exists(), "backup must be gone"


# ---------------------------------------------------------------------------
# Global-flag parsing paths through commands (quiet/plain/project)
# ---------------------------------------------------------------------------


class TestGlobalFlags:
    def test_quiet_flag_uses_silent_progress(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["-q", "validate", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr: {captured.err}"
        # SilentProgress never writes "[P" phase lines to stderr.
        # RichProgress would emit "[P0_STATE] started" etc.
        assert "[P0_STATE] started" not in captured.err

    def test_plain_flag_disables_rich_styling(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)
        rc = main(["--plain", "validate", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr: {captured.err}"

    def test_project_and_base_mutually_exclusive_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["trim", "--project", "p.json", "--base", "b.json"])
        # argparse exits 2 on mutual-exclusivity error.
        assert excinfo.value.code == 2

    def test_trim_requires_base_or_project(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["trim"])


# ---------------------------------------------------------------------------
# Renderer direct tests — exercise render_diagnostics paths
# ---------------------------------------------------------------------------


class TestRenderDirect:
    def test_render_diagnostics_with_path_and_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        from chopper.cli.render import render_diagnostics
        from chopper.core.diagnostics import Diagnostic, Phase

        d = Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="missing file",
            path=Path("vars.tcl"),
            line_no=42,
        )
        import sys

        render_diagnostics([d], stream=sys.stderr)
        captured = capsys.readouterr()
        assert "VE-06" in captured.err
        assert "vars.tcl" in captured.err
        assert ":42" in captured.err

    def test_render_diagnostics_without_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        from chopper.cli.render import render_diagnostics
        from chopper.core.diagnostics import Diagnostic, Phase

        d = Diagnostic.build("VW-03", phase=Phase.P1_CONFIG, message="warn-no-path")
        import sys

        render_diagnostics([d], stream=sys.stderr)
        captured = capsys.readouterr()
        assert "VW-03" in captured.err
        assert "warn-no-path" in captured.err

    def test_render_diagnostics_info_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        from chopper.cli.render import render_diagnostics
        from chopper.core.diagnostics import Diagnostic, Phase

        d = Diagnostic.build("PI-01", phase=Phase.P2_PARSE, message="info-msg")
        import sys

        render_diagnostics([d], stream=sys.stderr)
        captured = capsys.readouterr()
        assert "PI-01" in captured.err
        assert "INFO " in captured.err

    def test_render_diagnostics_defaults_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Covers the ``stream is None`` fallback branch."""
        from chopper.cli.render import render_diagnostics
        from chopper.core.diagnostics import Diagnostic, Phase

        d = Diagnostic.build("VW-03", phase=Phase.P1_CONFIG, message="default-stream")
        render_diagnostics([d])  # no stream = default sys.stderr
        captured = capsys.readouterr()
        assert "default-stream" in captured.err

    def test_render_cleanup_message_default_stream_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        from chopper.cli.render import render_cleanup_message

        render_cleanup_message("hello cleanup")
        captured = capsys.readouterr()
        assert "hello cleanup" in captured.out


# ---------------------------------------------------------------------------
# Regression: issue #12 — files.include glob silent no-op
# ---------------------------------------------------------------------------


class TestGlobFilesIncludeRegression:
    """End-to-end regression for issue #12: files referenced *only* via a
    glob pattern in files.include must survive the trim.  Before the fix,
    the P1 surface-file collection skipped globs, so P2 never parsed the
    matched files and P3 glob expansion found nothing to match."""

    def _seed_glob_domain(self, domain: Path) -> tuple[Path, Path]:
        """Plant a domain with a glob-only subdirectory + feature JSON."""
        domain.mkdir(parents=True, exist_ok=True)
        (domain / "core.tcl").write_text("proc core_setup {} {}\n", encoding="utf-8")

        reports = domain / "server_reports"
        reports.mkdir()
        (reports / "activity.tcl").write_text("proc report_activity {} {}\n", encoding="utf-8")
        (reports / "power.tcl").write_text("proc report_power {} {}\n", encoding="utf-8")

        jsons = domain / "jsons"
        jsons.mkdir()
        base_path = jsons / "base.json"
        base_path.write_text(
            json.dumps(
                {
                    "$schema": "base-v1",
                    "domain": domain.name,
                    "files": {"include": ["core.tcl"]},
                }
            ),
            encoding="utf-8",
        )
        feat_path = jsons / "srv.feature.json"
        feat_path.write_text(
            json.dumps(
                {
                    "$schema": "feature-v1",
                    "name": "srv",
                    "files": {"include": ["server_reports/**"]},
                }
            ),
            encoding="utf-8",
        )
        return base_path, feat_path

    def test_trim_glob_only_subdir_files_survive(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "power"
        base, feat = self._seed_glob_domain(domain)

        rc = main(
            [
                "trim",
                "--domain",
                str(domain),
                "--base",
                str(base),
                "--features",
                str(feat),
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0, f"trim should exit 0; stderr:\n{captured.err}"

        # Read compiled_manifest.json from the audit bundle
        import json as _json

        manifest_path = domain / ".chopper" / "compiled_manifest.json"
        assert manifest_path.exists(), "audit bundle must contain compiled_manifest.json"
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        surviving = {d["path"] for d in manifest.get("files", []) if d.get("treatment") != "remove"}

        assert "server_reports/activity.tcl" in surviving, (
            "server_reports/activity.tcl must survive — referenced only via glob server_reports/**"
        )
        assert "server_reports/power.tcl" in surviving, (
            "server_reports/power.tcl must survive — referenced only via glob server_reports/**"
        )

    def test_validate_glob_only_subdir_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        domain = tmp_path / "power"
        base, feat = self._seed_glob_domain(domain)

        rc = main(
            [
                "validate",
                "--domain",
                str(domain),
                "--base",
                str(base),
                "--features",
                str(feat),
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0, f"validate should exit 0; stderr:\n{captured.err}"
        # VW-03 must NOT fire — glob matches files on disk
        assert "VW-03" not in captured.err


class TestFullDomainProcIndex:
    """Option A: P2 builds a full-domain proc index so the P4 tracer can
    resolve a call from a surfaced file into a proc defined in a file
    the user did not include — and ``dependency_graph.json`` records the
    actual defining path.  Trace remains reporting-only: the non-surfaced
    file is **not** copied; it just appears in the graph so the user can
    add it to the JSON in the next iteration.
    """

    def _seed_cross_file_call_domain(self, domain: Path) -> Path:
        """Seed a domain where ``foo.tcl`` (surfaced) calls ``bar`` from
        ``helper.tcl`` (NOT surfaced)."""
        domain.mkdir(parents=True, exist_ok=True)
        (domain / "foo.tcl").write_text("proc foo {} {\n    bar\n}\n", encoding="utf-8")
        (domain / "helper.tcl").write_text("proc bar {} { return 42 }\n", encoding="utf-8")
        jsons = domain / "jsons"
        jsons.mkdir()
        base_path = jsons / "base.json"
        base_path.write_text(
            json.dumps(
                {
                    "$schema": "base-v1",
                    "domain": domain.name,
                    "files": {"include": ["foo.tcl"]},
                    "procedures": {"include": [{"file": "foo.tcl", "procs": ["foo"]}]},
                }
            ),
            encoding="utf-8",
        )
        return base_path

    def test_trace_resolves_callee_in_non_surfaced_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        domain = tmp_path / "xref"
        base = self._seed_cross_file_call_domain(domain)

        rc = main(["trim", "--domain", str(domain), "--base", str(base), "--dry-run"])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr:\n{captured.err}"

        # dependency_graph.json must record the resolved edge from foo
        # with a ``to`` pointing at bar's canonical name (helper.tcl::bar),
        # not flag it as unresolvable (TW-02).
        graph_path = domain / ".chopper" / "dependency_graph.json"
        assert graph_path.exists()
        graph = json.loads(graph_path.read_text(encoding="utf-8"))

        edges = graph.get("edges", [])
        foo_edges = [e for e in edges if e.get("from", "").endswith("::foo")]
        assert foo_edges, "expected at least one edge from foo in dependency_graph.json"
        # Exactly one foo → bar edge, status resolved, callee = helper.tcl::bar.
        resolved = [e for e in foo_edges if e.get("status") == "resolved" and e.get("to") == "helper.tcl::bar"]
        assert resolved, (
            "expected a resolved edge from foo to helper.tcl::bar via the full-domain index; "
            f"got foo edges: {foo_edges!r}"
        )

        # TW-02 must NOT fire for the resolved call.
        assert "TW-02" not in captured.err

    def test_non_surfaced_file_is_not_copied(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Trace is reporting-only: helper.tcl appears in the graph but
        is NOT copied into the rebuilt domain (Critical Principle #7)."""
        domain = tmp_path / "xref2"
        base = self._seed_cross_file_call_domain(domain)

        rc = main(["trim", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0, f"stderr:\n{captured.err}"

        # foo.tcl survived; helper.tcl was NOT copied.
        assert (domain / "foo.tcl").exists()
        assert not (domain / "helper.tcl").exists(), (
            "helper.tcl must NOT be copied — trace is reporting-only and the user did not include it"
        )

        # compiled_manifest.json: helper.tcl absent (it was never in the
        # surface set, so the manifest does not name it).
        manifest = json.loads((domain / ".chopper" / "compiled_manifest.json").read_text(encoding="utf-8"))
        manifest_paths = {entry["path"] for entry in manifest.get("files", [])}
        assert "foo.tcl" in manifest_paths
        assert "helper.tcl" not in manifest_paths
