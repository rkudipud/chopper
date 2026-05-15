"""Per-file coverage tests for src/chopper/audit/internal_error.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from pathlib import Path
from unittest.mock import patch


from chopper.core.diagnostics import Diagnostic
from chopper.core.diagnostics import Phase
import tempfile


from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_internal_error_cwd_fallback_uses_tempdir() -> None:
    """When Path.cwd() raises (NFS inode replaced), _resolve_audit_root must
    fall back to a tempdir so the crash log is still written somewhere."""
    import tempfile

    from chopper.audit.internal_error import _resolve_audit_root

    with patch("pathlib.Path.cwd", side_effect=OSError("cwd gone")):
        result = _resolve_audit_root(ctx=None, override=None)
    assert str(result).startswith(tempfile.gettempdir())


def test_write_internal_error_log_with_diagnostic_path_and_lineno() -> None:
    """write_internal_error_log covers the path + line_no branches of _format_diagnostics."""
    from chopper.audit.internal_error import write_internal_error_log

    ctx = _ctx()
    ctx.diag.emit(
        Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="missing file",
            path=Path("sub/file.tcl"),
            line_no=17,
        )
    )
    result = write_internal_error_log(ctx, run_id="aaa111", exc=ValueError("test"))
    assert result.kind == "ValueError"


def test_write_internal_error_log_with_diagnostic_path_no_lineno() -> None:
    """write_internal_error_log covers the path-but-no-line_no branch of _format_diagnostics."""
    from chopper.audit.internal_error import write_internal_error_log

    ctx = _ctx()
    ctx.diag.emit(
        Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="missing file",
            path=Path("sub/other.tcl"),
        )
    )
    result = write_internal_error_log(ctx, run_id="bbb222", exc=ValueError("no lineno"))
    assert result.kind == "ValueError"


def test_write_internal_error_log_diagnostic_without_path() -> None:
    """_format_diagnostics branch 157->161: when diag.path is None, skip location append."""
    from chopper.audit.internal_error import write_internal_error_log

    ctx = _ctx()
    # Emit a diagnostic that has NO path — triggers the 157->161 False branch
    ctx.diag.emit(
        Diagnostic.build(
            "VE-06",
            phase=Phase.P1_CONFIG,
            message="path-less diagnostic to cover branch",
        )
    )
    result = write_internal_error_log(ctx, run_id="no-path-test", exc=RuntimeError("check"))
    assert result.kind == "RuntimeError"
