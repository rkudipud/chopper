"""Run-scoped context records for Chopper.

:class:`ChopperContext` is a **port bundle plus run config**, not an
immutable data record. Its three port fields (``fs``, ``diag``,
``progress``) are all effectful; only the ``config`` field — a
:class:`RunConfig` of frozen flags and paths — is pure.
``@dataclass(frozen=True)`` on the wrapper guarantees that **port
bindings cannot be rebound mid-run**; it does not make the ports
themselves pure. Readers should treat ``ctx.<port>.<method>(...)`` as
"call into a possibly-effectful adapter."

:class:`PresentationConfig` is intentionally separate. It is CLI-local
and drives adapter selection (quiet vs. rich progress, plain-text vs.
coloured output). It never enters the service layer; services read only
``ctx.config`` (the :class:`RunConfig`).

There is no ``clock`` port, no ``serde`` port, no ``audit`` port.
Services call :func:`datetime.datetime.now` directly, use
:func:`chopper.core.serialization.dump_model` as a plain helper, and
write audit artifacts through ``ctx.fs``.

There is no ``mode`` field on :class:`RunConfig`. The CLI dispatches on
subcommand name (``validate`` / ``trim`` / ``cleanup``); ``cleanup``
never enters :class:`~chopper.orchestrator.runner.ChopperRunner` at all
(it is a standalone ``shutil.rmtree(<domain>_backup)`` function).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chopper.core.protocols import DiagnosticSink, FileSystemPort, ProgressSink

__all__ = ["ChopperContext", "PresentationConfig", "RunConfig"]


@dataclass(frozen=True)
class RunConfig:
    """Pure engine-behaviour config. No methods, no effects.

    All fields are required — the CLI layer is responsible for resolving
    defaults (typically from :mod:`chopper.cli.main`) before constructing
    this record. Keeping the type strict means services never have to
    guard against ``None`` paths.

    * ``domain_root``: the directory Chopper is about to trim (or has
      trimmed). Must exist on disk when the runner starts; the P0 domain-
      state detector is responsible for producing a :class:`DomainState`
      before phases run.
    * ``backup_root``: the shadow copy — ``<domain>_backup/`` — created
      by the trim lifecycle.
    * ``audit_root``: the ``.chopper/`` bundle directory inside
      ``domain_root``.
    * ``strict``: exit-code policy only. When ``True``, the CLI returns
      exit code 2 if any ``VW``/``PW``/``TW`` warning was emitted. It
      does not rewrite :attr:`Diagnostic.severity`.
    * ``dry_run``: services skip all filesystem mutations; audit bundles
      and diagnostic output still flow.
    * ``project_path``: path to a ``project-v1`` JSON when the
      CLI was invoked with ``--project``; ``None`` otherwise. Mutually
      exclusive with ``base_path`` / ``feature_paths`` — the CLI enforces
      ``VE-11`` before :class:`RunConfig` is constructed, so services
      may assume at most one of the two modes is populated.
    * ``base_path``: path to the base JSON when invoked with ``--base``;
      ``None`` when ``project_path`` is set (the project JSON resolves
      its own base).
    * ``feature_paths``: tuple of feature JSON paths when invoked with
      ``--features``; empty when ``project_path`` is set. Order is
      authoritative for F3 ``flow_actions`` sequencing.
    * ``tool_command_paths``: tuple of paths to user-supplied tool-
      command list files (from the repeatable CLI flag
      ``--tool-commands``). These extend the always-loaded built-in
      pool under ``src/chopper/data/tool_commands/`` (see
      ``technical_docs/chopper_description.md`` §3.10). The order does
      not affect behaviour — the pool is a set — but is preserved for
      audit reproducibility.
    """

    domain_root: Path
    backup_root: Path
    audit_root: Path
    strict: bool
    dry_run: bool
    project_path: Path | None = None
    base_path: Path | None = None
    feature_paths: tuple[Path, ...] = ()
    tool_command_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PresentationConfig:
    """CLI-side UX config. Drives adapter selection; never read by services.

    Flag-to-effect mapping (see CLI_HELP_TEXT_REFERENCE):

    * ``verbose`` (``-v``): raises the CLI progress renderer to
      DEBUG-level detail. Chopper has no internal structured-logging
      channel; this flag only affects the CLI-attached renderer.
    * ``quiet`` (``-q``): selects ``SilentProgress``; suppresses progress
      output (CI / grid).
    * ``plain`` (``--plain``): selects a Rich console reconfigured with
      ``no_color=True`` and the live progress bar disabled. ASCII only.

    Rich honours ``NO_COLOR`` automatically.
    """

    verbose: bool = False
    quiet: bool = False
    plain: bool = False


@dataclass(frozen=True)
class ChopperContext:
    """Port bundle + run config. Frozen bindings; ports are effectful.

    Constructed exactly once per run — by ``cli/main.py`` in production,
    by ``make_test_context()`` in tests.
    Services receive ``ctx`` plus the typed inputs they declare; nothing
    else. No module-level globals, no singletons, no thread-locals.
    """

    config: RunConfig
    fs: FileSystemPort
    diag: DiagnosticSink
    progress: ProgressSink
