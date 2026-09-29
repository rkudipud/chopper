"""Every relative link in the living markdown docs must resolve to a file.

Four retired documents left twenty dangling links behind before 4.9.1;
this keeps a deleted or renamed doc from silently orphaning its readers.
Links with a query string (GitHub web routes such as the issue-template
URL) are not files and are skipped, as is anything inside a code fence.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = sorted(
    {
        *ROOT.glob("*.md"),
        *(ROOT / "technical_docs").glob("*.md"),
        *(ROOT / "user_docs").glob("*.md"),
        *(ROOT / "tests").glob("*.md"),
        *(ROOT / "examples").rglob("*.md"),
        *(ROOT / ".github").rglob("*.md"),
    }
)
LINK = re.compile(r"\]\((?![a-z]+:|#)([^)\s#?]+)(?:#[^)\s]*)?\)")


def _broken_links(doc: Path) -> list[str]:
    broken = []
    in_fence = False
    for line_no, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            broken += [
                f"{doc.relative_to(ROOT).as_posix()}:{line_no} -> {target}"
                for target in LINK.findall(line)
                if not (doc.parent / target).exists()
            ]
    return broken


def test_relative_doc_links_resolve() -> None:
    assert len(DOCS) > 30  # guard against the globs silently matching nothing
    assert [link for doc in DOCS for link in _broken_links(doc)] == []
