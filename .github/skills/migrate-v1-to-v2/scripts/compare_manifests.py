"""Diff two Chopper dry-run snapshots to prove what one migration step changed.

Usage: python compare_manifests.py BEFORE AFTER

BEFORE / AFTER is either a ``compiled_manifest.json`` file or a snapshot folder
holding copies of ``.chopper/compiled_manifest.json``, ``files_kept.txt``,
``p4_commands.txt`` and ``diagnostics.json``. A folder also diffs the kept-path
set, the Perforce commands, and the diagnostic codes.

Provenance labels (``contributed_by``, ``selection_source``) are ignored on
purpose: they move to whichever layer contributed last, without changing what
is kept. Per-file ``excluded_procs`` is ignored because Chopper always writes it
as ``null``; the surviving-proc set is the real F2 decision.

Prints nothing when the snapshots agree. Exit code is always 0.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _manifest(root: Path) -> dict:
    path = root / "compiled_manifest.json" if root.is_dir() else root
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(root: Path, name: str) -> set[str]:
    path = root / name
    if not root.is_dir() or not path.is_file():
        return set()
    rows = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return {row for row in rows if row and not row.startswith("#")}


def _codes(root: Path) -> Counter[str]:
    path = root / "diagnostics.json"
    if not root.is_dir() or not path.is_file():
        return Counter()
    return Counter(d["code"] for d in json.loads(path.read_text(encoding="utf-8"))["diagnostics"])


def _facts(root: Path) -> dict[str, dict[str, object]]:
    m = _manifest(root)
    return {
        "file": {f["path"]: (f["treatment"], tuple(sorted(f["surviving_procs"] or ()))) for f in m["files"]},
        "proc": {p["canonical_name"]: "kept" for p in (m.get("procedures") or {}).get("surviving", [])},
        "stage": {s["name"]: {"steps": s["steps"], "inputs": s["inputs"]} for s in m.get("flow_actions") or []},
        "kept": {row.split("\t")[0]: "kept" for row in _lines(root, "files_kept.txt")},
        "p4": {row: "cmd" for row in _lines(root, "p4_commands.txt")},
        "diag": dict(_codes(root)),
    }


def main(before: str, after: str) -> None:
    old, new = _facts(Path(before)), _facts(Path(after))
    for section in old:
        a, b = old[section], new[section]
        for key in sorted(a.keys() | b.keys()):
            if a.get(key) == b.get(key):
                continue
            if key not in a:
                print(f"+ {section:5} {key}  {b[key]}")
            elif key not in b:
                print(f"- {section:5} {key}  {a[key]}")
            else:
                print(f"~ {section:5} {key}  {a[key]} -> {b[key]}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
