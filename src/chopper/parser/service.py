"""Parser service — the boundary layer around the pure parser utilities.

Two public surfaces:

* :func:`parse_file` — pure, callback-driven utility. Accepts already-
  decoded text, runs tokenizer + proc extractor, and forwards diagnostic
  records through an optional ``on_diagnostic`` callback. Returns a plain
  ``list[ProcEntry]``. No :class:`ChopperContext` or filesystem knowledge.
  Unit tests target this directly.

* :class:`ParserService` — orchestrator-facing service. Owns filesystem
  reads through ``ctx.fs``, UTF-8 → Latin-1 fallback (emitting
  ``PW-02``), and the path-normalization contract: every :class:`Path`
  in ``files`` is normalized to domain-relative POSIX form before being
  passed to :func:`parse_file`.

Diagnostic translation:

* Tokenizer structural errors → ``PE-02 unbalanced-braces``.
* ``ExtractorDiagnostic.kind`` → registered codes via ``_DIAG_CODE_MAP``.
* UTF-8 decode failure → ``PW-02 utf8-decode-failure``.

Every diagnostic is built via :meth:`Diagnostic.build`, so slug /
severity / source are always registry-derived.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models_config import LoadedConfig
from chopper.core.models_parser import ParsedFile, ParseResult, ProcEntry

from .proc_extractor import ExtractorDiagnostic, ExtractorDiagnosticKind, extract_procs
from .tokenizer import TokenizerError, tokenize

if TYPE_CHECKING:
    from chopper.core.context import ChopperContext

__all__ = [
    "DiagnosticCollector",
    "ParserService",
    "parse_file",
]


DiagnosticCollector = Callable[[Diagnostic], None]
"""Callback forwarded into :func:`parse_file`.

Takes a single :class:`Diagnostic` and returns ``None``. The service
layer wires this to ``ctx.diag.emit``; tests wire it to a list.
"""


# ---------------------------------------------------------------------------
# Diagnostic-code translation
# ---------------------------------------------------------------------------
#
# ExtractorDiagnostic.kind is a :class:`Literal` (see proc_extractor); the
# map below converts each literal to the registered code. Adding a kind
# requires adding an entry here AND registering the code in the registry
# (enforced by scripts/check_diagnostic_registry.py).

_DIAG_CODE_MAP: dict[ExtractorDiagnosticKind, str] = {
    "computed-proc-name": "PW-01",
    "non-brace-body": "PW-03",
    "computed-namespace-name": "PW-04",
    "duplicate-proc-definition": "PE-01",
    "dpa-name-mismatch": "PW-11",
    "dpa-orphan": "PI-04",
}


# Only ``.tcl`` files are parsed by P2. Per the architecture doc (OOS-01,
# ``technical_docs/chopper_description.md`` §1.3), non-Tcl companion
# files named in ``files.include`` / ``procedures.*`` (Perl, Python,
# shell, config) participate in F1 file-level treatment only — they must
# never enter the Tcl tokenizer, which would mis-read language-native
# constructs (e.g. a ``}`` inside a Python string literal) as a
# structural brace imbalance and emit a spurious ``PE-02``. The
# compiler already assumes this contract (see
# ``compiler/merge_service._collect_universe``: *"literal FI can refer
# to non-``.tcl`` companion files that the parser does not cover"*).
#
# Match is case-insensitive on the suffix to cover authored variants
# like ``.TCL``. No new diagnostic is emitted on skip — the behavior is
# silent by design (non-Tcl files are not an error condition).
_TCL_SUFFIX = ".tcl"


# ---------------------------------------------------------------------------
# parse_file — pure utility
# ---------------------------------------------------------------------------


def parse_file(
    file_path: Path,
    text: str,
    on_diagnostic: DiagnosticCollector | None = None,
) -> list[ProcEntry]:
    """Parse a Tcl file and extract proc definitions (pure utility).

    :param file_path: Domain-relative :class:`~pathlib.Path` recorded on
        every returned :class:`~chopper.core.models_parser.ProcEntry`. The caller
        (:class:`ParserService`) is responsible for normalizing this to
        the domain-relative POSIX form before invocation.
    :param text: Already-decoded file content. The service layer owns the
        decode step so this utility can stay purely textual and trivially
        unit-testable.
    :param on_diagnostic: Optional callback invoked once per
        :class:`Diagnostic`. When ``None``, diagnostics are silently
        discarded.
    :returns: List of :class:`ProcEntry` records. Empty list is a valid
        outcome.

    Contract table:

    * Tokenizer error (``negative_depth`` / ``unclosed_braces``) → emit
      ``PE-02`` and return ``[]`` regardless of any procs extracted.
    * Otherwise, run the proc extractor; translate each
      :class:`ExtractorDiagnostic` to the registered code and forward.
    """
    tok_result = tokenize(text)
    if tok_result.errors:
        # §2.1.1 row 5: any structural brace error → emit PE-02 and
        # return []. Only emit once per file, at the first offending line.
        first_err: TokenizerError = tok_result.errors[0]
        if on_diagnostic is not None:
            on_diagnostic(
                Diagnostic.build(
                    "PE-02",
                    phase=Phase.P2_PARSE,
                    message=f"Unbalanced braces: {first_err.kind.replace('_', ' ')}",
                    path=file_path,
                    line_no=first_err.line_no,
                    hint="Check for missing or extra '}' in the file",
                )
            )
        return []

    result = extract_procs(file_path, text)
    if on_diagnostic is not None:
        for ext_diag in result.diagnostics:
            on_diagnostic(_translate_extractor_diagnostic(ext_diag, file_path))

    return list(result.procs)


def _translate_extractor_diagnostic(ext_diag: ExtractorDiagnostic, file_path: Path) -> Diagnostic:
    """Map an :class:`ExtractorDiagnostic` to a registered :class:`Diagnostic`."""
    code = _DIAG_CODE_MAP[ext_diag.kind]
    message = _message_for(ext_diag)
    return Diagnostic.build(
        code,
        phase=Phase.P2_PARSE,
        message=message,
        path=file_path,
        line_no=ext_diag.line_no,
    )


def _message_for(ext_diag: ExtractorDiagnostic) -> str:
    """Human-readable single-line message for an extractor diagnostic."""
    if ext_diag.kind == "computed-proc-name":
        return f"Computed proc name skipped: {ext_diag.detail}"
    if ext_diag.kind == "non-brace-body":
        return f"Proc '{ext_diag.detail}' has non-brace body; skipped"
    if ext_diag.kind == "computed-namespace-name":
        return f"Computed namespace name; body not parsed: {ext_diag.detail}"
    if ext_diag.kind == "duplicate-proc-definition":
        return ext_diag.detail
    if ext_diag.kind == "dpa-name-mismatch":
        return ext_diag.detail
    if ext_diag.kind == "dpa-orphan":
        return f"define_proc_attributes with no preceding proc: {ext_diag.detail}"
    # Unreachable if _DIAG_CODE_MAP and ExtractorDiagnosticKind stay in sync.
    raise AssertionError(f"unmapped extractor diagnostic kind: {ext_diag.kind!r}")


# ---------------------------------------------------------------------------
# ParserService — orchestrator-facing service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParserService:
    """P2 service wrapping :func:`parse_file`.

    Contract:

    1. Read each file through ``ctx.fs.read_text`` (never
       :meth:`pathlib.Path.read_text` directly) — the filesystem port is
       the only I/O surface.
    2. Attempt UTF-8 decode first; on :class:`UnicodeDecodeError`, retry
       with Latin-1 and emit ``PW-02``. Latin-1 always succeeds on any
       byte sequence.
    3. Normalize every input :class:`Path` to a domain-relative POSIX
       string. Rejecting absolute paths or upward traversal is the
       caller's responsibility (compiler / config layer); at this stage
       we assume inputs are already within the domain.
    4. Forward every diagnostic emitted by :func:`parse_file` into
       ``ctx.diag.emit``.
     5. Build :class:`~chopper.core.models_parser.ParsedFile` per file and
         :class:`~chopper.core.models_parser.ParseResult` for the domain.

    The service is a frozen dataclass with no fields. Instantiating via
    ``ParserService()`` keeps the unit simple to substitute in tests.
    """

    def run(self, ctx: ChopperContext, files: Sequence[Path], *, loaded: LoadedConfig | None = None) -> ParseResult:
        """Parse every file in ``files`` and return the aggregate result.

        :param ctx: Run context with ``fs`` and ``diag`` ports bound.
        :param files: Paths to parse with diagnostics. Each is normalized
            to the domain-relative POSIX form before being recorded on
            the resulting :class:`ProcEntry` records. This is the
            *surface* set: the user-facing slice that produces
            :class:`ParsedFile` entries in :attr:`ParseResult.files` and
            emits parser diagnostics into ``ctx.diag``.
        :param loaded: Optional :class:`LoadedConfig` from P1. When provided
            and ``domain_file_cache`` is non-empty, the parser reuses it
            for full-domain harvest instead of re-walking the filesystem
            (O1 optimization). Pass ``None`` in unit tests that bypass
            the config layer.
        :returns: :class:`ParseResult` whose ``files`` map covers the
            surface set and whose ``index`` is a **full-domain** proc
            index (every ``.tcl`` definition under ``domain_root``) so
            the P4 tracer can resolve calls into files the user did not
            surface and report their actual defining path. Trace remains
            reporting-only \u2014 the wider index never changes which files
            or procs survive (see Critical Principle #7).

        Ordering:

        * The ``files`` iterable is **not** required to be sorted on input.
        * The returned :attr:`ParseResult.files` mapping is built in
          lexicographic POSIX-path order so downstream consumers that
          iterate it (e.g. audit hashing) observe a deterministic view.
        * The returned :attr:`ParseResult.index` is sorted
          lexicographically by canonical-name at construction per
          :class:`ParseResult` invariant 2.
        """
        # Normalize the surface set once. Non-Tcl companion files
        # (``.py``, ``.pl``, ``.csh``, ``.cfg``, \u2026) are dropped here \u2014
        # the Tcl tokenizer must not see them (see module-level
        # ``_TCL_SUFFIX`` commentary). They still receive F1 file-level
        # treatment downstream because the compiler's
        # ``_collect_universe`` adds literal ``files.include`` paths to
        # the manifest universe independently of ``ParseResult.files``.
        normalized: list[Path] = [self._normalize(ctx, raw) for raw in files]
        surface_tcl: list[Path] = [p for p in normalized if p.suffix.lower() == _TCL_SUFFIX]
        # Dedup while preserving order: duplicates could occur from glob
        # overlap in the caller. Using dict.fromkeys keeps the first seen.
        surface_sorted = sorted(dict.fromkeys(surface_tcl), key=lambda p: p.as_posix())
        surface_set: set[Path] = set(surface_sorted)

        parsed_files: dict[Path, ParsedFile] = {}
        index: dict[str, ProcEntry] = {}

        # ------------------------------------------------------------
        # Phase 2a \u2014 surface parse (with diagnostics).
        # ------------------------------------------------------------
        for path in surface_sorted:
            parsed = self._parse_one(ctx, path, emit_diagnostics=True)
            parsed_files[path] = parsed
            for proc in parsed.procs:
                # The extractor already guarantees unique canonical names
                # within a file (see PE-01 dedup). Cross-file collisions
                # are impossible because canonical names embed the path.
                index[proc.canonical_name] = proc

        # ------------------------------------------------------------
        # Phase 2b — full-domain proc-index harvest (silent).
        # ------------------------------------------------------------
        # Every ``.tcl`` file under ``domain_root`` that is NOT in the
        # surface set is parsed here for the sole purpose of populating
        # ``index``. No :class:`ParsedFile` is recorded in ``files``;
        # diagnostics are silently dropped because the user did not ask
        # us to scrutinise these files — they exist only so the P4
        # tracer can name a definition's real location when it resolves
        # a call from a surfaced caller into a non-surfaced callee.
        for path in self._enumerate_domain_tcl(ctx, loaded):
            if path in surface_set:
                continue
            try:
                parsed = self._parse_one(ctx, path, emit_diagnostics=False)
            except OSError:
                # File vanished between enumeration and read; skip silently.
                continue
            for proc in parsed.procs:
                index.setdefault(proc.canonical_name, proc)

        # Reconstruct the index in lex order to satisfy ParseResult
        # invariant 2.
        sorted_index = {k: index[k] for k in sorted(index.keys())}
        return ParseResult(files=parsed_files, index=sorted_index)

    def _enumerate_domain_tcl(self, ctx: ChopperContext, loaded: LoadedConfig | None = None) -> list[Path]:
        """Return every ``.tcl`` file under ``domain_root``, lex-sorted.

        O1 optimization: when ``loaded.domain_file_cache`` is non-empty,
        filters the cached list for ``.tcl`` files instead of re-walking
        the filesystem. This reuses the domain walk that P1 performed
        during glob expansion in :func:`_collect_surface_files`.

        The ``.chopper/`` audit directory is always excluded — it is
        Chopper's own bookkeeping, never user code. Returns an empty
        list when ``domain_root`` does not exist (covers in-memory
        unit-test fixtures that synthesise no real domain).
        """
        # O1 fast path: reuse P1's domain walk if available.
        if loaded is not None and loaded.domain_file_cache:
            tcl_files = [rel for rel, _ in loaded.domain_file_cache if rel.suffix.lower() == _TCL_SUFFIX]
            tcl_files.sort(key=lambda p: p.as_posix())
            return tcl_files

        # Fallback: full BFS walk (P1 had no globs so no cache).
        from collections import deque  # noqa: PLC0415

        domain = ctx.config.domain_root
        if not ctx.fs.exists(domain):
            return []

        results: list[Path] = []
        frontier: deque[Path] = deque([domain])
        while frontier:
            current = frontier.popleft()
            try:
                children = ctx.fs.list(current)
            except OSError:
                continue
            for child in children:
                try:
                    rel = child.relative_to(domain)
                except ValueError:
                    continue
                rel_posix = rel.as_posix()
                if rel_posix == ".chopper" or rel_posix.startswith(".chopper/"):
                    continue
                try:
                    st = ctx.fs.stat(child)
                except OSError:
                    continue
                if st.is_dir:
                    frontier.append(child)
                elif rel.suffix.lower() == _TCL_SUFFIX:
                    results.append(rel)
        results.sort(key=lambda p: p.as_posix())
        return results

    @staticmethod
    def _normalize(ctx: ChopperContext, raw: Path) -> Path:
        """Return the domain-relative POSIX form of ``raw``.

        If ``raw`` is absolute, compute its form relative to
        ``ctx.config.domain_root``. If ``raw`` is already relative, it is
        assumed to be domain-relative (the caller's contract) and
        returned unchanged except for :meth:`Path` normalization (``.``
        removal, separator canonicalization).

        The return value is still a :class:`Path`; the POSIX form
        surfaces via :meth:`Path.as_posix` when the canonical-name is
        assembled in :class:`ProcEntry`.
        """
        if raw.is_absolute():
            try:
                return raw.relative_to(ctx.config.domain_root)
            except ValueError:
                # Path lies outside domain_root — keep as-is. The
                # compiler / config layer is responsible for rejecting
                # such paths with a VE-06; the parser does not gate.
                return raw
        # Collapse any leading "./" and OS-specific separators via Path
        # round-trip. `Path("a/b/c.tcl")` already stores components in a
        # normalized form on all platforms.
        return Path(*raw.parts)

    def _parse_one(self, ctx: ChopperContext, path: Path, *, emit_diagnostics: bool = True) -> ParsedFile:
        """Read ``path`` through ``ctx.fs``, decode, parse.

        :param emit_diagnostics: When ``True`` (the surface-parse path),
            every parser diagnostic is forwarded to ``ctx.diag.emit``.
            When ``False`` (the full-domain-index harvest path),
            diagnostics are silently dropped \u2014 the file is not part of
            the user's selection so emitting ``PE-02`` / ``PW-*`` against
            it would be misleading. The proc index, however, still
            captures every successfully-extracted definition so the P4
            tracer can resolve calls into non-surfaced files.
        """
        sink = ctx.diag.emit if emit_diagnostics else _noop_diagnostic
        text, encoding = self._read_with_fallback(ctx, path, sink)
        procs = parse_file(path, text, on_diagnostic=sink)
        return ParsedFile(path=path, procs=tuple(procs), encoding=encoding)

    @staticmethod
    def _resolve_for_read(ctx: ChopperContext, path: Path) -> Path:
        """Return the filesystem path to hand to :meth:`FileSystemPort.read_text`.

        ``path`` is stored in domain-relative form everywhere downstream
        (canonical names, ParsedFile keys, diagnostics). When the port
        is a real-disk adapter (:class:`LocalFS`), it cannot resolve a
        bare relative path without a base. The parser owns that
        resolution here by prepending ``ctx.config.domain_root`` when
        ``path`` is relative.

        :class:`InMemoryFS` stores its keys under relative paths that
        happen to live under the domain root too (tests seed files at
        ``DOMAIN / "a.tcl"``), so prepending the domain root is safe
        for both adapters.
        """
        if path.is_absolute() or path.anchor:
            return path
        return ctx.config.domain_root / path

    def _read_with_fallback(
        self,
        ctx: ChopperContext,
        path: Path,
        sink: DiagnosticCollector,
    ) -> tuple[str, Literal["utf-8", "latin-1"]]:
        """UTF-8 decode with Latin-1 fallback.

        Returns ``(text, encoding)`` where ``encoding`` is the label
        recorded on :class:`ParsedFile` (``"utf-8"`` or ``"latin-1"``).
        Emits ``PW-02`` exactly once per file on fallback. ``sink`` is
        the parser's diagnostic collector \u2014 ``ctx.diag.emit`` for
        surface files, :func:`_noop_diagnostic` for the silent
        full-domain-index harvest.

        Implementation note: :class:`FileSystemPort.read_text` accepts an
        ``encoding`` kwarg; we call it twice if the first raises
        :class:`UnicodeDecodeError`. Latin-1 is a total 8-bit decoder,
        so the second call never fails on well-formed bytes.
        """
        read_path = self._resolve_for_read(ctx, path)
        try:
            text = ctx.fs.read_text(read_path, encoding="utf-8")
            return text, "utf-8"
        except UnicodeDecodeError:
            text = ctx.fs.read_text(read_path, encoding="latin-1")
            sink(
                Diagnostic.build(
                    "PW-02",
                    phase=Phase.P2_PARSE,
                    message="UTF-8 decode failed; falling back to Latin-1",
                    path=path,
                    hint="Consider re-encoding the file as UTF-8",
                )
            )
            return text, "latin-1"


def _noop_diagnostic(_diag: Diagnostic) -> None:
    """Diagnostic sink that drops every event.

    Used by :class:`ParserService` when parsing files outside the
    surface set (full-domain proc-index harvest). The user did not name
    these files; emitting ``PE-02`` or ``PW-*`` against them would be
    misleading. The procs they define still enter the index so trace
    can resolve cross-file calls.
    """
    return None
