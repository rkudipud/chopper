"""Lock the active-scenario count in tests/TESTING_STRATEGY.md §5.

Per docs/FINAL_HANDOFF_REVIEW.md PR-2, the scenario table in
`tests/TESTING_STRATEGY.md` §5 is the single source of truth for the
integration-scenario roster. Deferred crash-injection scenarios remain named
for planning purposes but are not part of the active gate.

This test parses the scenario table directly and asserts the row count
matches ``EXPECTED_SCENARIO_COUNT``. Adding, removing, or splitting a
scenario forces a conscious edit here — which in turn forces a matching
edit in ``docs/IMPLEMENTATION_ROADMAP.md`` M6.
"""

from __future__ import annotations

import re
from pathlib import Path

EXPECTED_SCENARIO_COUNT = 25

ROOT = Path(__file__).resolve().parents[2]
STRATEGY_DOC = ROOT / "tests" / "TESTING_STRATEGY.md"

# Table row shape: "| <id> | <name> | <stage> | <key assertions> |"
# <id> is an integer, optionally with a trailing letter suffix (11a, 11b, 11c),
# or a range (5-9 or 5–9 with an en-dash). The leading cell may be bold
# (**22**). We accept both hyphen-minus (U+002D) and en-dash (U+2013)
# because Markdown editors frequently auto-convert between them.
ROW_RE = re.compile(
    r"^\|\s*(?:\*\*)?(?P<id>\d+[a-z]?(?:[-\u2013]\d+)?)(?:\*\*)?\s*\|",
)


def _count_scenarios() -> int:
    assert STRATEGY_DOC.is_file(), f"missing doc: {STRATEGY_DOC}"
    in_section = False
    count = 0
    for line in STRATEGY_DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 5. Named Integration Scenarios"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        identifier = match.group("id")
        # A range like "5-9" or "5–9" expands to 5 rows; otherwise one row.
        range_sep = next((ch for ch in ("-", "\u2013") if ch in identifier and identifier[0].isdigit()), None)
        if range_sep is not None:
            lo, hi = (int(part) for part in identifier.split(range_sep, 1))
            count += max(0, hi - lo + 1)
        else:
            count += 1
    return count


def test_scenario_count_matches_roadmap() -> None:
    actual = _count_scenarios()
    assert actual == EXPECTED_SCENARIO_COUNT, (
        f"TESTING_STRATEGY.md §5 lists {actual} scenarios; "
        f"roadmap M6 expects {EXPECTED_SCENARIO_COUNT}. "
        "Update EXPECTED_SCENARIO_COUNT and docs/IMPLEMENTATION_ROADMAP.md M6 together."
    )
