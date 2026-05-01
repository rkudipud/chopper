"""``.chopper/internal-error.log`` writer (programmer-error path, exit 3).

Per architecture doc §5.5.10 / §5.12.5, an unhandled exception that
escapes a service must terminate the run with exit code 3 and leave a
plain-text crash log under ``.chopper/`` so users have a deterministic
artifact to attach to a bug report. The log is intentionally rendered
without going through :mod:`chopper.core.serialization` so it stays
readable even if the serialiser itself is the source of the crash.

The writer also returns an :class:`InternalError` summary that the
runner attaches to :class:`RunResult.internal_error` so GUIs / CI can
surface the failure without parsing the log file.

Public API: :func:`write_internal_error_log`.
"""

from __future__ import annotations

import platform
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from chopper import __version__ as _chopper_version
from chopper.core.models_audit import InternalError

if TYPE_CHECKING:
    from chopper.core.context import ChopperContext

__all__ = ["write_internal_error_log"]

_LOG_NAME = "internal-error.log"


def write_internal_error_log(
    ctx: ChopperContext | None,
    *,
    run_id: str,
    exc: BaseException,
    audit_root: Path | None = None,
) -> InternalError:
    """Write ``.chopper/internal-error.log`` and return the summary record.

    Parameters
    ----------
    ctx:
        The active :class:`ChopperContext`, or ``None`` if the crash
        happened before the context was constructed (CLI-level guard).
        When ``None``, the log is written via raw ``Path.write_text``
        rather than through ``ctx.fs``.
    run_id:
        UUID v4 hex from the runner. When the CLI guard fires before a
        run_id has been minted, callers pass an empty string and a
        synthetic timestamp-only id is used.
    exc:
        The exception being reported.
    audit_root:
        Override for the log directory. When omitted, ``ctx.config.audit_root``
        is used (preferred); when ``ctx`` is also ``None`` the writer
        falls back to ``Path.cwd() / '.chopper'``.

    Returns
    -------
    InternalError
        ``{kind, message, log_path}`` summary suitable for attaching to
        :attr:`RunResult.internal_error`. ``log_path`` is ``None`` when
        the writer itself failed to put bytes on disk; the in-memory
        record still surfaces the failure.
    """

    kind = type(exc).__name__
    message = str(exc) or kind

    target_dir = _resolve_audit_root(ctx, audit_root)
    log_path = target_dir / _LOG_NAME

    payload = _render(ctx, run_id=run_id, exc=exc)

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(payload, encoding="utf-8")
    except OSError:
        # Last-resort fallback: the user's filesystem is hostile (full
        # disk, permission denied). The traceback is more important
        # than the log artifact, so dump to stderr and report log_path
        # as None. The runner still returns exit 3.
        sys.stderr.write(payload)
        return InternalError(kind=kind, message=message, log_path=None)

    return InternalError(kind=kind, message=message, log_path=log_path)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_audit_root(ctx: ChopperContext | None, override: Path | None) -> Path:
    if override is not None:
        return override
    if ctx is not None:
        return ctx.config.audit_root
    return Path.cwd() / ".chopper"


def _render(ctx: ChopperContext | None, *, run_id: str, exc: BaseException) -> str:
    """Render the plain-text crash log body."""

    lines: list[str] = []
    lines.append("# chopper internal-error.log")
    lines.append(f"run_id: {run_id or 'unknown'}")
    lines.append(f"timestamp: {datetime.now(UTC).isoformat()}")
    lines.append(f"chopper_version: {_chopper_version}")
    lines.append(f"python_version: {platform.python_version()}")
    lines.append(f"platform: {platform.platform()}")
    lines.append("")
    lines.append("## traceback")
    lines.append(_format_traceback(exc))
    lines.append("")

    lines.append("## diagnostic snapshot")
    lines.extend(_format_diagnostics(ctx))
    lines.append("")

    lines.append("## active RunConfig")
    lines.extend(_format_runconfig(ctx))
    lines.append("")

    return "\n".join(lines) + "\n"


def _format_traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()


def _format_diagnostics(ctx: ChopperContext | None) -> list[str]:
    if ctx is None:
        return ["(no context — crash occurred before runner started)"]
    try:
        snapshot = ctx.diag.snapshot()
    except Exception as introspection_exc:  # pragma: no cover - defensive
        return [f"(snapshot unavailable: {introspection_exc!r})"]
    if not snapshot:
        return ["(no diagnostics emitted before crash)"]
    out: list[str] = []
    for diag in snapshot:
        location = ""
        if diag.path is not None:
            location = f" at {diag.path.as_posix()}"
            if diag.line_no is not None:
                location += f":{diag.line_no}"
        out.append(f"[{diag.severity.value.upper()}] {diag.code} {diag.slug}{location}: {diag.message}")
    return out


def _format_runconfig(ctx: ChopperContext | None) -> list[str]:
    if ctx is None:
        return ["(no context)"]
    try:
        cfg = ctx.config
    except Exception as introspection_exc:  # pragma: no cover - defensive
        return [f"(config unavailable: {introspection_exc!r})"]
    fields: list[str] = []
    for name in (
        "domain_root",
        "audit_root",
        "base_path",
        "feature_paths",
        "project_path",
        "dry_run",
        "strict",
    ):
        value = getattr(cfg, name, None)
        fields.append(f"{name}: {value!r}")
    return fields
