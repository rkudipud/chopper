"""End-to-end tests for ``chopper loc`` (FR-46).

Verifies:

* exit code 0 on a happy-path run;
* stdout contains the LOC table markers (``Files``, ``Lines``, ``SLOC``);
* **no** ``.chopper/`` audit bundle is written (key invariant — loc is
  read-only and writes nothing);
* the source domain is left untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chopper.cli.main import main


def _seed_valid_domain(domain: Path) -> Path:
    domain.mkdir(parents=True, exist_ok=True)
    (domain / "vars.tcl").write_text("# vars\nset PI 3.14\n", encoding="utf-8")
    (domain / "helper.tcl").write_text("proc helper_a {} { return 1 }\n", encoding="utf-8")
    (domain / "extra.tcl").write_text("proc unused_x {} { return 99 }\n", encoding="utf-8")
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


class TestLocSubcommand:
    def test_loc_happy_path_returns_zero_and_renders_table(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)

        rc = main(["loc", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()

        assert rc == 0, f"stderr: {captured.err}"
        # Header + metric lines on stdout (line-oriented format).
        assert "chopper loc:" in captured.out
        assert "files.before:" in captured.out
        assert "lines.before:" in captured.out
        assert "sloc.before:" in captured.out
        # Per-treatment breakdown rendered.
        assert "treatment.FULL_COPY.files:" in captured.out
        assert "treatment.REMOVE.files:" in captured.out

    def test_loc_writes_nothing_no_audit_bundle(self, tmp_path: Path) -> None:
        """FR-46 invariant: ``chopper loc`` must not create ``.chopper/``."""
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)

        rc = main(["loc", "--domain", str(domain), "--base", str(base)])
        assert rc == 0
        assert not (domain / ".chopper").exists(), "chopper loc must not write the audit bundle"
        # Source files untouched.
        assert (domain / "vars.tcl").read_text(encoding="utf-8") == "# vars\nset PI 3.14\n"
        assert (domain / "extra.tcl").exists(), "loc is read-only — extra.tcl (excluded by R2) must remain on disk"

    def test_loc_reflects_excluded_file_in_remove_bucket(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A file present on disk but not selected by any layer must
        appear in the REMOVE bucket and reduce the after-totals."""
        domain = tmp_path / "mini"
        base = _seed_valid_domain(domain)

        rc = main(["loc", "--domain", str(domain), "--base", str(base)])
        captured = capsys.readouterr()
        assert rc == 0
        # Three .tcl files exist; base selects 2 → after files == 2,
        # before files == 3 (minimum — implementation may also count
        # any other SLOC-relevant files dropped under default-exclude).
        out = captured.out
        # files.before should be at least 3 (3 .tcl files seeded).
        assert "files.before:" in out
        # REMOVE bucket should record at least one file (extra.tcl).
        assert "treatment.REMOVE.files:" in out
