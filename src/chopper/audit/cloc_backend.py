"""cloc-backed SLOC counting.

Uses the vendored `cloc.pl` (under :mod:`chopper.audit.vendor`) to count
logical source lines with industry-standard language rules — block
comments (``/* … */``, ``<!-- … -->``), Perl POD (``=pod`` / ``=cut``),
Python triple-quoted module docstrings, HEREDOCs, and many more — none
of which the pure-Python fallback in :mod:`chopper.audit.sloc` handles.

This module is *opportunistic*: if perl or `cloc.pl` is missing, or
cloc returns a non-zero exit code, or its JSON is unparseable, the
public helper :func:`count_sloc_via_cloc` returns ``None`` and the
caller falls back to the pure-Python counter. There are no required
runtime dependencies on the user's side.

Caveats
-------
* cloc identifies languages by extension *and* shebang. It does **not**
  recognize the Tcl ``if {0} { … }`` idiom as a block comment — that
  is a Tcl convention, not part of the language grammar.
* cloc counts CSV rows differently than the pure-Python fallback (it
  treats ``,,,`` as code; the fallback treats it as blank). When cloc
  is active, its convention wins.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from importlib import resources
from pathlib import Path

__all__ = ["count_sloc_via_cloc", "is_available", "cloc_script_path"]


# How long to wait (seconds) for a single cloc invocation before giving up
# and falling back. cloc on a single small file usually finishes in <100 ms.
_CLOC_TIMEOUT_SECONDS = 30.0


@lru_cache(maxsize=1)
def _perl_executable() -> str | None:
    """Return the path to a working perl interpreter, or ``None``."""
    return shutil.which("perl")


@lru_cache(maxsize=1)
def cloc_script_path() -> Path | None:
    """Return the on-disk path to the vendored ``cloc.pl``, or ``None``.

    Uses :mod:`importlib.resources` so the script is locatable even when
    chopper is installed from a wheel. Returns ``None`` if the vendored
    copy has been removed (e.g. by a downstream that does not want
    GPL-2 code in its distribution).
    """
    try:
        ref = resources.files("chopper.audit.vendor").joinpath("cloc.pl")
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    try:
        # importlib.resources.as_file gives us a real filesystem path even
        # when the package lives inside a zip; the context manager copies
        # it out if needed. We need a real path because we hand it to a
        # subprocess.
        with resources.as_file(ref) as p:
            real = Path(p)
            if real.is_file():
                return real
    except (FileNotFoundError, OSError):
        return None
    return None


@lru_cache(maxsize=1)
def is_available() -> bool:
    """Return ``True`` iff cloc can run on this system."""
    return _perl_executable() is not None and cloc_script_path() is not None


def count_sloc_via_cloc(path: Path, text: str) -> int | None:
    """Count logical source lines in ``text`` using cloc.

    ``path`` is used only for its suffix — the content actually analyzed
    is ``text``, written to a temporary file with the same extension so
    cloc can pick the right language profile. Returns ``None`` (so the
    caller can fall back) when:

    * cloc / perl is unavailable;
    * the subprocess fails, times out, or emits unparseable JSON;
    * cloc could not identify the language (no ``SUM`` entry).

    Returns ``0`` (not ``None``) for empty / pure-blank input that cloc
    successfully analyzed — that is a valid result, not a failure.
    """
    if not is_available():
        return None

    perl = _perl_executable()
    script = cloc_script_path()
    if perl is None or script is None:  # pragma: no cover — guarded by is_available
        return None

    # Empty / whitespace-only short-circuit: cloc emits no SUM block for an
    # empty file, which we can't distinguish from "language not recognized".
    # Match the pure-Python contract (blank → 0).
    if not text.strip():
        return 0

    suffix = path.suffix or ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=suffix,
            prefix="chopper_sloc_",
            delete=False,
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
    except OSError:
        return None

    try:
        try:
            result = subprocess.run(
                [perl, str(script), "--json", "--quiet", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=_CLOC_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0 or not result.stdout.strip():
            return None

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

        summary = payload.get("SUM") if isinstance(payload, dict) else None
        if not isinstance(summary, dict):
            return None
        code = summary.get("code")
        if not isinstance(code, int):
            return None
        return code
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _selftest() -> int:  # pragma: no cover — manual diagnostic
    """Tiny smoke test: ``python -m chopper.audit.cloc_backend``.

    Prints whether cloc is available and its SLOC count for a small
    Tcl snippet with a comment and a blank line.
    """
    print(f"perl: {_perl_executable()}")
    print(f"cloc.pl: {cloc_script_path()}")
    print(f"available: {is_available()}")
    sample = "set x 1\n# comment\n\nset y 2\n"
    print(f"sample sloc: {count_sloc_via_cloc(Path('sample.tcl'), sample)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_selftest())
