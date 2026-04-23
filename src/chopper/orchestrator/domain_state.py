"""Phase 0 domain-state classification.

:class:`DomainStateService` observes ``<domain>/`` and
``<domain>_backup/`` through ``ctx.fs`` and returns a frozen
:class:`DomainState` record classifying the workspace into one of four
cases:

+------+---------------+-------------------+---------------------------+
| Case | ``domain/``   | ``domain_backup/``| Downstream behavior       |
+======+===============+===================+===========================+
| 1    | exists        | missing           | First trim                |
+------+---------------+-------------------+---------------------------+
| 2    | exists        | exists            | Re-trim                   |
+------+---------------+-------------------+---------------------------+
| 3    | missing       | exists            | Recovery re-trim          |
+------+---------------+-------------------+---------------------------+
| 4    | missing       | missing           | Fatal (``VE-21``)         |
+------+---------------+-------------------+---------------------------+

Case 4 is the only state that emits a diagnostic (``VE-21``). Cases
1–3 are purely classificatory; downstream services react to the case
number.

The service does not mutate the filesystem. Safe under ``--dry-run``.
"""

from __future__ import annotations

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import DomainState

__all__ = ["DomainStateService"]


class DomainStateService:
    """Phase 0 classifier. See module docstring."""

    def run(self, ctx: ChopperContext) -> DomainState:
        """Classify the current workspace and return a :class:`DomainState`.

        Emits ``VE-21`` when both the domain and backup directories are
        missing (Case 4). The caller is responsible for mapping that
        diagnostic to exit code 2; this service returns the state record
        unconditionally so the runner can log and continue its audit
        writeout even on a fatal Case 4.
        """

        domain_root = ctx.config.domain_root
        backup_root = ctx.config.backup_root
        domain_exists = ctx.fs.exists(domain_root)
        backup_exists = ctx.fs.exists(backup_root)

        case: int
        if domain_exists and not backup_exists:
            case = 1
        elif domain_exists and backup_exists:
            case = 2
        elif not domain_exists and backup_exists:
            case = 3
        else:
            case = 4
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-21",
                    phase=Phase.P0_STATE,
                    message=(
                        f"Neither {domain_root.as_posix()!r} nor {backup_root.as_posix()!r} exists; no domain to trim"
                    ),
                    hint=(
                        "Verify the current working directory and the --project path; "
                        "Chopper must be invoked from the parent of the domain directory"
                    ),
                )
            )

        assert case in (1, 2, 3, 4)
        return DomainState(
            case=case,  # type: ignore[arg-type]
            domain_exists=domain_exists,
            backup_exists=backup_exists,
            hand_edited=False,
        )
