"""Fail CI if any ``class *Service`` under ``src/chopper/`` has a ``run``
signature that disagrees with the canonical table in
``technical_docs/ARCHITECTURE_PLAN.md`` §9.2.

This is the doc↔code single-source-of-truth gate described in
``technical_docs/FINAL_HANDOFF_REVIEW.md`` PR-4. Agents that silently change a service
signature (param order, types, return type) fail this check.

Extraction approach:

* Source side — parse every ``class *Service`` in ``src/chopper/`` with
  ``ast`` and capture the ``run`` method's signature as a canonical string:
  ``run(self, ctx, ...) -> ReturnType``.
* Docs side — scan ``technical_docs/ARCHITECTURE_PLAN.md`` for the §9.2 service table
  and extract each row's signature string, normalised the same way.

Both sides are normalised to the same shape before comparison, so comment
or whitespace drift in either source does not cause false failures.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCH_PLAN = ROOT / "technical_docs" / "ARCHITECTURE_PLAN.md"
SOURCE_ROOT = ROOT / "src" / "chopper"

# Matches a row in the §9.2 service table. The current shape is:
#   | `ServiceName.run` | `(ctx, ...) -> ReturnType` — optional prose |
# where the first backtick cell holds the dotted method name and the second
# holds the signature proper. Plain free functions use the same shape, e.g.
#   | `validate_pre` | `(ctx, loaded) -> None` — ... |
# so the regex accepts either a bare identifier or ``Identifier.run``.
TABLE_ROW_RE = re.compile(r"^\|\s*`(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\.run)?`\s*\|\s*`(?P<sig>[^`]+)`")


def normalise_signature(sig: str) -> str:
    """Collapse whitespace and reduce to ``(ctx, ...) -> Return`` shape.

    Accepts either ``run(self, ctx, ...) -> T`` (source side) or
    ``(ctx, ...) -> T`` (docs side) and produces the canonical form used
    by both.
    """
    collapsed = re.sub(r"\s+", " ", sig).strip()
    # Strip leading ``run`` / ``run_pre`` etc. method name so both sides
    # agree on the paren-opened shape.
    collapsed = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(", "(", collapsed)
    collapsed = collapsed.replace("(self, ", "(")
    collapsed = collapsed.replace("(self)", "()")
    return collapsed


def load_documented_signatures() -> dict[str, str]:
    """Return ``{ServiceName: normalised_run_signature}`` from the arch plan."""
    if not ARCH_PLAN.is_file():
        print(f"ERROR: architecture plan not found: {ARCH_PLAN}", file=sys.stderr)
        sys.exit(2)
    sigs: dict[str, str] = {}
    for line in ARCH_PLAN.read_text(encoding="utf-8").splitlines():
        match = TABLE_ROW_RE.match(line)
        if match:
            sigs[match.group(1)] = normalise_signature(match.group(2))
    return sigs


def load_source_signatures() -> dict[str, str]:
    """Return ``{ServiceName: normalised_run_signature}`` from the source tree."""
    sigs: dict[str, str] = {}
    if not SOURCE_ROOT.is_dir():
        return sigs
    for py_file in SOURCE_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Service"):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "run":
                    args = ast.unparse(item.args)
                    returns = ast.unparse(item.returns) if item.returns else "None"
                    sigs[node.name] = normalise_signature(f"run({args}) -> {returns}")
                    break
    return sigs


def main() -> int:
    documented = load_documented_signatures()
    source = load_source_signatures()
    if not documented:
        print(
            "ERROR: no Service rows found in technical_docs/ARCHITECTURE_PLAN.md §9.2. "
            "The table layout likely changed — update scripts/check_service_signatures.py.",
            file=sys.stderr,
        )
        return 2

    mismatches: list[tuple[str, str, str]] = []
    for name, src_sig in source.items():
        if name not in documented:
            # A new service not yet in the plan is a contract violation.
            mismatches.append((name, "<not documented>", src_sig))
            continue
        if documented[name] != src_sig:
            mismatches.append((name, documented[name], src_sig))

    if not mismatches:
        print(f"OK: {len(source)} service signatures match technical_docs/ARCHITECTURE_PLAN.md §9.2")
        return 0

    print("ERROR: service signature drift between source and docs:", file=sys.stderr)
    for name, doc_sig, src_sig in mismatches:
        print(f"  {name}", file=sys.stderr)
        print(f"    docs:   {doc_sig}", file=sys.stderr)
        print(f"    source: {src_sig}", file=sys.stderr)
    print(
        "\nUpdate technical_docs/ARCHITECTURE_PLAN.md §9.2 first, then reconcile the source. "
        "The bible-first cascade applies to this table too.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
