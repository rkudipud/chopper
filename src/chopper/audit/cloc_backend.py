"""cloc-backed SLOC counting.

Uses the vendored `cloc.pl` (under :mod:`chopper.audit.vendor`) to count
logical source lines with industry-standard language rules -- block
comments (``/* ... */``, ``<!-- ... -->``), Perl POD (``=pod`` / ``=cut``),
Python triple-quoted module docstrings, HEREDOCs, and many more -- none
of which the pure-Python fallback in :mod:`chopper.audit.sloc` handles.

This module is *opportunistic*: if perl or `cloc.pl` is missing, or
cloc returns a non-zero exit code, or its JSON is unparseable, the
public helper :func:`count_sloc_via_cloc` returns ``None`` and the
caller falls back to the pure-Python counter. There are no required
runtime dependencies on the user's side.

Caveats
-------
* cloc identifies languages by extension *and* shebang. It does **not**
  recognize the Tcl ``if {0} { ... }`` idiom as a block comment -- that
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

__all__ = [
    "count_sloc_via_cloc",
    "count_sloc_via_cloc_batch",
    "is_available",
    "cloc_script_path",
]


# How long to wait (seconds) for a single cloc invocation before giving up
# and falling back. cloc on a single small file usually finishes in <100 ms.
_CLOC_TIMEOUT_SECONDS = 30.0

# Batch invocation gets a larger budget -- we still want to fall back to the
# pure-Python counter if cloc somehow stalls on a giant input set, but a
# multi-thousand-file domain may legitimately take many seconds.
_CLOC_BATCH_TIMEOUT_SECONDS = 300.0


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

    ``path`` is used only for its suffix -- the content actually analyzed
    is ``text``, written to a temporary file with the same extension so
    cloc can pick the right language profile. Returns ``None`` (so the
    caller can fall back) when:

    * cloc / perl is unavailable;
    * the subprocess fails, times out, or emits unparseable JSON;
    * cloc could not identify the language (no ``SUM`` entry).

    Returns ``0`` (not ``None``) for empty / pure-blank input that cloc
    successfully analyzed -- that is a valid result, not a failure.
    """
    if not is_available():
        return None

    perl = _perl_executable()
    script = cloc_script_path()
    if perl is None or script is None:  # pragma: no cover -- guarded by is_available
        return None

    # Empty / whitespace-only short-circuit: cloc emits no SUM block for an
    # empty file, which we can't distinguish from "language not recognized".
    # Match the pure-Python contract (blank -> 0).
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


def count_sloc_via_cloc_batch(items: list[tuple[Path, str]]) -> list[int | None]:
    """Batch-count logical lines for many ``(path, text)`` pairs in one cloc call.

    Spawns a *single* ``/usr/intel/bin/perl5.40.1 cloc.pl`` subprocess for the whole batch
    instead of one per file. On large domains (thousands of files) this
    turns an O(N)-fork hot path into a single fork, eliminating the
    biggest perf wart flagged by the production-readiness review (S1/L2).

    Returns a list the same length as ``items``. Each slot is the cloc
    "code" count for that input, or ``None`` if cloc could not classify
    it (caller should fall back to the pure-Python counter). Empty /
    whitespace-only input maps to ``0`` directly without invoking cloc.

    The temp directory is removed even on failure paths via
    :class:`tempfile.TemporaryDirectory`. Each input is materialised
    under a unique stem (``f<index>``) that preserves the original
    suffix so cloc picks the right language profile per file.
    """

    n = len(items)
    if n == 0:
        return []
    if not is_available():
        return [None] * n

    perl = _perl_executable()
    script = cloc_script_path()
    if perl is None or script is None:  # pragma: no cover -- guarded by is_available
        return [None] * n

    # Per-slot result, pre-seeded with the empty-text short-circuit so we
    # don't bother cloc with files that contain only whitespace.
    result: list[int | None] = [None] * n
    blank_marker: list[bool] = [False] * n
    for i, (_, text) in enumerate(items):
        if not text.strip():
            result[i] = 0
            blank_marker[i] = True

    try:
        tmp_dir_ctx = tempfile.TemporaryDirectory(prefix="chopper_sloc_batch_")
    except OSError:
        return result

    with tmp_dir_ctx as tmpdir:
        tmp_root = Path(tmpdir)
        tmp_paths: list[Path | None] = [None] * n
        for i, (path, text) in enumerate(items):
            if blank_marker[i]:
                continue
            suffix = path.suffix or ""
            tp = tmp_root / f"f{i:06d}{suffix}"
            try:
                tp.write_text(text, encoding="utf-8")
            except OSError:
                continue
            tmp_paths[i] = tp

        valid = [(i, p) for i, p in enumerate(tmp_paths) if p is not None]
        if not valid:
            return result

        argv = [perl, str(script), "--by-file", "--json", "--quiet"]
        argv.extend(str(p) for _, p in valid)
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=_CLOC_BATCH_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return result
        if proc.returncode != 0 or not proc.stdout.strip():
            return result
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return result
        if not isinstance(payload, dict):
            return result

        # cloc --by-file --json shape:
        #   { "header": {...}, "<path1>": {"code": N, ...}, ..., "SUM": {...} }
        # Keys are the exact strings we passed on argv. Build a map of
        # both the full path string and the basename so we can match
        # reliably regardless of how cloc canonicalised the path.
        per_file: dict[str, int] = {}
        for key, val in payload.items():
            if key in ("header", "SUM"):
                continue
            if isinstance(val, dict) and isinstance(val.get("code"), int):
                per_file[key] = val["code"]
                per_file[Path(key).name] = val["code"]

        for i, tp_opt in enumerate(tmp_paths):
            if tp_opt is None or blank_marker[i]:
                continue
            code = per_file.get(str(tp_opt))
            if code is None:
                code = per_file.get(tp_opt.name)
            if code is not None:
                result[i] = code

    return result


def _selftest() -> int:  # pragma: no cover -- manual diagnostic
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
