"""Typed application errors.

Use cases raise :class:`AppError` for user-visible input failures that
stop a request before the pipeline runs (domain lookup, base discovery,
feature-name lookup). Each front end maps the issues to its own
presentation; the CLI maps them to the stderr text and exit codes in
``technical_docs/CLI_REFERENCE.md``. See ``technical_docs/ARCHITECTURE.md``
Sec.5.11.2.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AppError", "AppIssue"]


@dataclass(frozen=True)
class AppIssue:
    """One user-facing problem.

    ``code`` is the registered diagnostic code, or ``None`` when no code
    exists for the condition (the current working directory cannot be
    determined). ``detail`` is an optional extra line shown between the
    message and the hint.
    """

    code: str | None
    message: str
    hint: str
    detail: str | None = None


class AppError(Exception):
    """Raised by a use case when its request cannot be served."""

    def __init__(self, *issues: AppIssue) -> None:
        super().__init__(issues[0].message)
        self.issues: tuple[AppIssue, ...] = issues
