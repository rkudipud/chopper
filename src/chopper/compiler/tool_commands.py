"""Tool-command pool loader (see architecture doc §3.10, FR-44).

The pool is a frozen set of bare external-tool-command names. The P4
tracer consults it on the ``TW-02 unresolved-proc-call`` branch and
downgrades the emission to ``TI-01 known-tool-command`` when a call
token (raw OR namespace-stripped leaf) matches a pool entry.

Pool composition is the union of two sources:

* **Built-in lists** shipped at ``src/chopper/data/tool_commands/*.commands``
  (seeded 0.5.0 with ``pt.commands``). Always loaded, no opt-out.
* **User-supplied lists** passed via the repeatable CLI flag
  ``--tool-commands`` and stored on :attr:`RunConfig.tool_command_paths`.

**File format.** Plain-text, UTF-8. Whitespace-separated tokens (spaces,
tabs, newlines are all equivalent) — so both "one token per line" and
"a single long line of space-separated tokens" are valid, and the two
styles can be freely mixed in the same file. Blank lines and lines
whose first non-whitespace character is ``#`` are skipped. No escaping,
no quoting, no namespacing — the format matches vendor ``help`` dumps
verbatim.

The module is intentionally minimal: one function, one returned
``frozenset[str]``, no classes, no caching. Keeping it data-only makes
the unit tests trivial and the behaviour obvious.
"""

from __future__ import annotations

from importlib.resources import files as _resource_files
from pathlib import Path

__all__ = [
    "BUILT_IN_PACKAGE",
    "load_pool",
    "parse_tokens",
]


BUILT_IN_PACKAGE = "chopper.data.tool_commands"
"""Package under :mod:`importlib.resources` that owns the built-in lists.

Every ``*.commands`` file in this package is loaded on every run. Adding
a new vendor list is a matter of dropping a file into
``src/chopper/data/tool_commands/`` — no code change required.
"""


def parse_tokens(text: str) -> frozenset[str]:
    """Parse one ``.commands`` file body into a set of bare names.

    Rules (architecture doc §3.10):

    * Skip lines whose first non-whitespace character is ``#``.
    * On every surviving line, split on any whitespace and add each
      non-empty token to the set.

    Empty input yields an empty frozenset — valid and silent.
    """
    tokens: set[str] = set()
    for raw_line in text.splitlines():
        stripped = raw_line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens.update(raw_line.split())
    return frozenset(tokens)


def load_pool(user_paths: tuple[Path, ...] = ()) -> frozenset[str]:
    """Build the pool — union of built-in lists and any user-supplied lists.

    :param user_paths: paths to user-supplied ``.commands`` files
        (typically from ``RunConfig.tool_command_paths``). Duplicates
        across files are automatically collapsed by set union.
    :returns: ``frozenset`` of bare tool-command names. Empty frozenset
        is a valid outcome (it happens when there are no built-in lists
        AND the user passed no flags — most unit-test contexts).

    File read failures on **built-in** resources propagate as
    :class:`OSError` because those resources ship with the wheel and
    their absence is a packaging bug. File read failures on
    **user** paths propagate as :class:`FileNotFoundError` with the
    offending path in the message — the CLI layer translates those
    into a user-friendly error before the pipeline starts.
    """
    tokens: set[str] = set()

    # Built-in lists — iterate every `*.commands` file under the
    # resource package. ``importlib.resources`` returns a traversable
    # that works whether the package is installed as source, a wheel,
    # or a zipped egg.
    try:
        package = _resource_files(BUILT_IN_PACKAGE)
    except (ModuleNotFoundError, FileNotFoundError):
        # Package has no data subfolder yet (fresh checkout / test
        # isolation). Treat as empty built-in set.
        package = None

    if package is not None:
        for entry in sorted(package.iterdir(), key=lambda p: p.name):
            if not entry.is_file() or not entry.name.endswith(".commands"):
                continue
            tokens.update(parse_tokens(entry.read_text(encoding="utf-8")))

    # User-supplied lists.
    for path in user_paths:
        if not path.exists():
            raise FileNotFoundError(f"--tool-commands file not found: {path}")
        tokens.update(parse_tokens(path.read_text(encoding="utf-8")))

    return frozenset(tokens)
