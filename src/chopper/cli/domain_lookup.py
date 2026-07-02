"""Domain name resolution via ``$ward/global/<vendor>/<name>``.

Resolves the ``--domain`` CLI argument to a concrete filesystem path using
three modes:

1. **Path-mode (absolute):** argument starts with a drive letter or ``/``;
   used as-is with no ``$ward`` lookup.
2. **Path-mode (relative-existing):** argument is an existing directory
   relative to the current working directory; used as-is.
3. **Name-mode:** argument is a bare name (e.g. ``fev_formality``) or a
   vendor-qualified name (e.g. ``snps/fev_formality``); resolved under
   ``$ward/global/``.

See ``technical_docs/ARCHITECTURE.md`` Section 5.1.0.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = ["DomainLookupResult", "resolve_domain"]


@dataclass(frozen=True)
class DomainLookupResult:
    """Outcome of a successful domain-name resolution.

    Attributes:
        domain_root: The resolved filesystem path to the domain directory.
        ward_root:   The resolved ``$ward`` root, or ``None`` in path-mode.
        domain_logical_name: ``"vendor/name"`` string (e.g. ``"snps/fev_formality"``),
            or ``None`` in path-mode.
    """

    domain_root: Path
    ward_root: Path | None
    domain_logical_name: str | None


def resolve_domain(
    domain_arg: str,
    emit_diagnostic: Callable[[str, str, str], None],
) -> DomainLookupResult | None:
    """Resolve a ``--domain`` argument to a :class:`DomainLookupResult`.

    Returns ``None`` and calls *emit_diagnostic* when resolution fails
    (VE-32, VE-33, or VE-34). The caller is responsible for converting
    the emitted diagnostic into a process exit.

    Three forms:
    - Absolute path -> path-mode, no ward lookup.
    - Existing relative directory -> path-mode, no ward lookup.
    - Name or vendor/name -> name-mode, requires ``$ward``.

    Args:
        domain_arg: The raw string from the ``--domain`` CLI flag.
        emit_diagnostic: Callable ``(code, message, hint) -> None``; called
            once when an error is detected. Callers wire this to their
            diagnostic sink or stderr writer.
    """
    # Form 1: absolute path
    if Path(domain_arg).is_absolute():
        return DomainLookupResult(
            domain_root=Path(domain_arg).resolve(),
            ward_root=None,
            domain_logical_name=None,
        )

    # Form 2: existing relative directory
    candidate = Path(domain_arg)
    if candidate.is_dir():
        return DomainLookupResult(
            domain_root=candidate.resolve(),
            ward_root=None,
            domain_logical_name=None,
        )

    # Form 3: name-mode lookup via $ward
    return _resolve_by_name(domain_arg, emit_diagnostic)


def _resolve_by_name(
    name_arg: str,
    emit_diagnostic: Callable[[str, str, str], None],
) -> DomainLookupResult | None:
    """Resolve a bare name or vendor/name under ``$ward/global/``."""
    ward_str = os.environ.get("ward")
    if not ward_str:
        emit_diagnostic(
            "VE-32",
            (
                f"--domain {name_arg!r} looks like a domain name, but the $ward "
                "environment variable is not set; Chopper cannot locate $ward/global/ "
                "for name-based lookup."
            ),
            (
                "Set ward to your workspace root (e.g. setenv ward /p/workarea/my_ward), "
                "or pass --domain as an absolute filesystem path to bypass name-based lookup."
            ),
        )
        return None

    ward_root = Path(ward_str).resolve()
    global_root = ward_root / "global"

    # Vendor-qualified: "vendor/name"
    if "/" in name_arg:
        parts = name_arg.split("/", 1)
        vendor, domain_name = parts[0], parts[1]
        target = global_root / vendor / domain_name
        if not target.is_dir():
            emit_diagnostic(
                "VE-33",
                (f"Domain {name_arg!r} was not found: {target.as_posix()!r} is not an existing directory."),
                (
                    f"Check that {global_root.as_posix()}/{vendor}/{domain_name} exists. "
                    "Run `ls $ward/global/<vendor>/` to see available domains."
                ),
            )
            return None
        return DomainLookupResult(
            domain_root=target.resolve(),
            ward_root=ward_root,
            domain_logical_name=f"{vendor}/{domain_name}",
        )

    # Bare name: search all vendor dirs
    bare_name = name_arg
    if not global_root.is_dir():
        emit_diagnostic(
            "VE-33",
            (f"Domain {bare_name!r} not found: $ward/global/ does not exist at {global_root.as_posix()!r}."),
            "Verify that $ward points to a valid workspace root containing a 'global/' directory.",
        )
        return None

    matches: list[tuple[str, Path]] = []
    try:
        for vendor_dir in sorted(global_root.iterdir()):
            if not vendor_dir.is_dir():
                continue
            candidate = vendor_dir / bare_name
            if candidate.is_dir():
                matches.append((vendor_dir.name, candidate.resolve()))
    except OSError as exc:
        emit_diagnostic(
            "VE-33",
            f"Could not enumerate $ward/global/ ({exc}): domain {bare_name!r} search failed.",
            "Verify filesystem permissions on $ward/global/.",
        )
        return None

    if not matches:
        emit_diagnostic(
            "VE-33",
            f"Domain {bare_name!r} was not found under any vendor in {global_root.as_posix()!r}.",
            (
                f"Run `ls {global_root.as_posix()}/` to see available vendors, "
                f"then `ls {global_root.as_posix()}/<vendor>/` to see domains. "
                "Use --domain vendor/name to target a specific vendor."
            ),
        )
        return None

    if len(matches) > 1:
        found_list = ", ".join(f"{v}/{bare_name} ({p.as_posix()})" for v, p in matches)
        emit_diagnostic(
            "VE-34",
            (f"Domain name {bare_name!r} is ambiguous: found in multiple vendor directories: {found_list}."),
            (
                f"Use explicit vendor/domain notation, e.g. --domain {matches[0][0]}/{bare_name} "
                "to pick a specific vendor's copy."
            ),
        )
        return None

    vendor_name, resolved = matches[0]
    return DomainLookupResult(
        domain_root=resolved,
        ward_root=ward_root,
        domain_logical_name=f"{vendor_name}/{bare_name}",
    )
