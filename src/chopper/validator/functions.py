"""Pre- and post-trim validation functions (P1b, P6).

Plain module-level functions. Each emits diagnostics via ``ctx.diag``
and returns ``None``.

``validate_pre(ctx, loaded)`` — runs before P2. Emits:

* ``VE-06`` — literal path in ``files.include`` / ``files.exclude``
  not present under :attr:`RunConfig.domain_root`.
* ``VE-09`` — glob pattern with unbalanced ``[...]``.
* ``VE-17`` — project ``domain`` does not match cwd basename
  (case-insensitive).
* ``VE-18`` — same feature path listed twice in ``project.features``.
* ``VW-03`` — glob in ``files.include`` matches zero files on disk.
* ``VW-04`` — feature JSON ``domain`` does not match base.
* ``VI-01`` — base JSON has empty ``files`` / ``procedures`` /
  ``stages`` (likely a feature-driven flow).

``validate_post(ctx, manifest, graph, rewritten)`` — runs after P5.
Emits:

* ``VE-16`` — post-trim brace imbalance in a rewritten file.
* ``VW-05`` — surviving proc calls a proc not in the manifest.
* ``VW-06`` — surviving proc sources / iproc_sources a file not in
  the manifest.
* ``VW-14``–``VW-17`` — F3 step references missing files / procs /
  out-of-domain paths.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

from chopper.core.context import ChopperContext
from chopper.core.diagnostics import Diagnostic, Phase
from chopper.core.models import (
    CompiledManifest,
    DependencyGraph,
    FeatureJson,
    FilesSection,
    LoadedConfig,
    StageSpec,
)

__all__ = ["validate_post", "validate_pre"]


# ---------------------------------------------------------------------------
# validate_pre — P1b
# ---------------------------------------------------------------------------


def validate_pre(ctx: ChopperContext, loaded: LoadedConfig) -> None:
    """Run Phase 1 structural checks on ``loaded``.

    Ordering is deterministic: VI-01 first (whole-base advisory),
    then per-feature domain mismatch (VW-04), project checks (VE-17,
    VE-18), and finally path/glob checks walked base→features.
    """

    _check_empty_base(ctx, loaded)
    _check_project_level(ctx, loaded)
    _check_feature_domain(ctx, loaded)
    _check_paths(ctx, loaded.base.domain, "base", loaded.base.files)
    for feature in loaded.features:
        _check_paths(ctx, loaded.base.domain, feature.name, feature.files)


def _check_empty_base(ctx: ChopperContext, loaded: LoadedConfig) -> None:
    base = loaded.base
    has_files = bool(base.files.include or base.files.exclude)
    has_procs = bool(base.procedures.include or base.procedures.exclude)
    has_stages = bool(base.stages)
    if not (has_files or has_procs or has_stages):
        ctx.diag.emit(
            Diagnostic.build(
                "VI-01",
                phase=Phase.P1_CONFIG,
                message=f"Base JSON '{base.source_path.as_posix()}' declares no files, procs, or stages",
                path=base.source_path,
            )
        )


def _check_project_level(ctx: ChopperContext, loaded: LoadedConfig) -> None:
    project = loaded.project
    if project is None:
        return

    # VE-17: project.domain vs cwd basename (case-insensitive).
    cwd_name = ctx.config.domain_root.name
    if cwd_name.casefold() != project.domain.casefold():
        ctx.diag.emit(
            Diagnostic.build(
                "VE-17",
                phase=Phase.P1_CONFIG,
                message=(f"Project JSON domain {project.domain!r} does not match domain-root basename {cwd_name!r}"),
                path=project.source_path,
            )
        )

    # VE-18: duplicate feature path in project.features.
    seen: set[Path] = set()
    for entry in project.features:
        resolved = Path(entry).resolve() if Path(entry).is_absolute() else Path(entry)
        if resolved in seen:
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-18",
                    phase=Phase.P1_CONFIG,
                    message=f"Duplicate feature entry in project.features: {entry!s}",
                    path=project.source_path,
                )
            )
        seen.add(resolved)


def _check_feature_domain(ctx: ChopperContext, loaded: LoadedConfig) -> None:
    base_domain = loaded.base.domain
    for feature in loaded.features:
        if feature.domain is None:
            continue
        if feature.domain != base_domain:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-04",
                    phase=Phase.P1_CONFIG,
                    message=(
                        f"Feature {feature.name!r} declares domain {feature.domain!r}; base domain is {base_domain!r}"
                    ),
                    path=feature.source_path,
                )
            )


def _check_paths(
    ctx: ChopperContext,
    base_domain: str,
    source_key: str,
    files: FilesSection,
) -> None:
    """Walk include/exclude patterns for one source and emit path diagnostics.

    The schema already rejects absolute paths and ``..`` segments, so
    we do not re-check those; what remains is existence for literals
    and syntax-plus-match checks for globs.
    """

    # FI includes.
    for pattern in files.include:
        _check_pattern(ctx, pattern, source_key=source_key, field="files.include")

    # FE excludes — same rules apply (literal must exist; glob must be
    # well-formed). ``VW-03 glob-matches-nothing`` does not fire for
    # excludes; a zero-match exclude is harmless.
    for pattern in files.exclude:
        _check_pattern(ctx, pattern, source_key=source_key, field="files.exclude", is_include=False)

    _ = base_domain  # reserved for future feature-vs-base domain diffs.


def _check_pattern(
    ctx: ChopperContext,
    pattern: str,
    *,
    source_key: str,
    field: str,
    is_include: bool = True,
) -> None:
    """Emit path diagnostics for a single include/exclude pattern."""

    if _is_glob(pattern):
        if not _glob_syntax_ok(pattern):
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-09",
                    phase=Phase.P1_CONFIG,
                    message=f"Malformed glob pattern in {source_key}.{field}: {pattern!r}",
                )
            )
            return
        if is_include and not _glob_has_matches(ctx, pattern):
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-03",
                    phase=Phase.P1_CONFIG,
                    message=f"Glob in {source_key}.{field} matched zero files: {pattern!r}",
                )
            )
        return

    # Literal path.
    rel = Path(pattern)
    target = ctx.config.domain_root / rel
    if not ctx.fs.exists(target):
        ctx.diag.emit(
            Diagnostic.build(
                "VE-06",
                phase=Phase.P1_CONFIG,
                message=f"File in {source_key}.{field} not found under domain: {pattern!r}",
                path=rel,
            )
        )


# ---------------------------------------------------------------------------
# Glob helpers
# ---------------------------------------------------------------------------


_GLOB_META = re.compile(r"[*?\[]")


def _is_glob(pattern: str) -> bool:
    return bool(_GLOB_META.search(pattern))


def _glob_syntax_ok(pattern: str) -> bool:
    """Reject patterns with unbalanced ``[`` brackets.

    ``*``, ``?``, and ``**`` are always well-formed. The only syntactic
    failure mode for fnmatch-style globs is an unterminated character
    class ``[...]``; we walk the string once and flag the first unbalanced
    bracket.
    """

    depth = 0
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "[":
            if depth > 0:
                return False
            depth += 1
        elif ch == "]":
            if depth == 0:
                return False
            depth -= 1
        i += 1
    return depth == 0


def _glob_has_matches(ctx: ChopperContext, pattern: str) -> bool:
    """Return ``True`` iff ``pattern`` matches any file under ``domain_root``.

    The :class:`FileSystemPort` protocol does not expose a recursive glob
    method, so we BFS the tree via :meth:`list` and test each domain-relative
    POSIX path using the same ``**``-aware regex translation as the P1/P3
    glob engines.  :meth:`PurePosixPath.match` is intentionally avoided
    because its ``**`` support is Python-version-dependent (added in 3.12).
    Early-exits on the first matching file.
    """
    import re as _re  # noqa: PLC0415
    from fnmatch import fnmatchcase as _fnmatchcase  # noqa: PLC0415

    from chopper.config.service import _glob_to_regex_local  # noqa: PLC0415

    regex = _glob_to_regex_local(pattern)
    domain = ctx.config.domain_root
    if not ctx.fs.exists(domain):
        return False

    frontier: list[Path] = [domain]
    while frontier:
        current = frontier.pop(0)
        try:
            children = ctx.fs.list(current)
        except (FileNotFoundError, NotADirectoryError, OSError):
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
            else:
                if regex is not None:
                    if isinstance(regex, _re.Pattern) and regex.fullmatch(rel_posix):
                        return True
                elif _fnmatchcase(rel_posix, pattern):
                    return True
    return False


# ---------------------------------------------------------------------------
# validate_post — P6
# ---------------------------------------------------------------------------


def validate_post(
    ctx: ChopperContext,
    manifest: CompiledManifest,
    graph: DependencyGraph,
    rewritten: Sequence[Path],
) -> None:
    """Run Phase 2 correctness checks on the rebuilt domain.

    ``rewritten`` is the tuple of paths the trimmer actually wrote
    during P5 (verbatim copies are excluded — they were validated at
    P2). In dry-run, ``rewritten`` is empty and filesystem-reading
    checks (``VE-16``) are skipped; manifest-derivable checks still
    run.
    """

    _check_brace_balance(ctx, rewritten)
    _check_dangling_refs(ctx, manifest, graph)
    _check_stage_steps(ctx, manifest)


def _check_brace_balance(ctx: ChopperContext, rewritten: Sequence[Path]) -> None:
    """Re-tokenise each rewritten file and count brace balance.

    ``VE-16`` is an internal-consistency assertion (exit 3): PE-02
    already rejects malformed files at P2, so the only way a rewritten
    file can be unbalanced is a trimmer bug.
    """

    for path in rewritten:
        try:
            text = ctx.fs.read_text(path)
        except (OSError, UnicodeDecodeError):
            # The trimmer wrote this file seconds ago; a read failure
            # here is a programmer error worth flagging, but VE-16 is
            # specifically about brace balance. Skip silently — the
            # runner's P5 gate already handles filesystem-layer errors.
            continue
        if _brace_delta(text) != 0:
            ctx.diag.emit(
                Diagnostic.build(
                    "VE-16",
                    phase=Phase.P6_POSTVALIDATE,
                    message=f"Post-trim brace imbalance in {path.as_posix()!s}",
                    path=path,
                )
            )


def _brace_delta(text: str) -> int:
    """Return ``count('{') - count('}')`` ignoring backslash-escaped braces.

    This is a minimal-sufficient check for the internal-consistency
    assertion VE-16. Full Tcl tokenisation (quotes, comments,
    here-docs) is not required because the parser's P2 pass is the
    authoritative brace checker; at P6 we only need to detect the
    trimmer having introduced new imbalance.
    """

    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return depth


def _check_dangling_refs(ctx: ChopperContext, manifest: CompiledManifest, graph: DependencyGraph) -> None:
    """Emit VW-05 / VW-06 from the P4 dependency graph.

    The graph already resolved every call token against the parsed
    proc index. Here we re-ask: does the resolved target survive the
    manifest? A ``proc_call`` edge whose callee is absent from
    ``manifest.proc_decisions`` is dangling; a ``source`` /
    ``iproc_source`` edge whose callee path is absent from
    ``manifest.file_decisions`` is a removed-source reference.
    """

    surviving_procs = frozenset(manifest.proc_decisions.keys())
    surviving_files = frozenset(manifest.file_decisions.keys())

    for edge in graph.edges:
        if edge.status != "resolved":
            # Unresolved / ambiguous / dynamic edges were diagnosed at
            # P4 via TW-*; VW-05/VW-06 only care about resolved calls
            # into things the manifest removed.
            continue
        if edge.caller not in surviving_procs:
            # The caller itself did not survive; calls *from* it are
            # moot for post-trim correctness.
            continue
        if edge.kind == "proc_call":
            if edge.callee not in surviving_procs:
                ctx.diag.emit(
                    Diagnostic.build(
                        "VW-05",
                        phase=Phase.P6_POSTVALIDATE,
                        message=(f"Surviving proc {edge.caller!r} calls removed proc {edge.callee!r}"),
                        path=_path_from_canonical(edge.caller),
                        line_no=edge.line,
                    )
                )
        else:  # source / iproc_source
            callee_path = Path(edge.callee)
            if callee_path not in surviving_files and not _source_matches_surviving_file(callee_path, surviving_files):
                ctx.diag.emit(
                    Diagnostic.build(
                        "VW-06",
                        phase=Phase.P6_POSTVALIDATE,
                        message=(f"Surviving proc {edge.caller!r} {edge.kind}s removed file {edge.callee!r}"),
                        path=_path_from_canonical(edge.caller),
                        line_no=edge.line,
                    )
                )


def _source_matches_surviving_file(callee: Path, surviving_files: frozenset[Path]) -> bool:
    """Return ``True`` if any surviving file path ends with ``callee``.

    Tcl ``source`` statements often use bare filenames (e.g.
    ``source write_power_reports.tcl``) even when the domain-relative
    path contains a subdirectory prefix
    (e.g. ``onepower/write_power_reports.tcl``). A literal
    ``callee not in surviving_files`` check would therefore emit a
    false-positive VW-06 for every such bare-filename source.

    The fix: if ``callee`` is not an exact key in ``surviving_files``,
    also accept any surviving file whose POSIX path ends with
    ``'/' + callee.as_posix()``.
    """
    callee_posix = callee.as_posix()
    suffix = "/" + callee_posix
    return any(sf.as_posix().endswith(suffix) for sf in surviving_files)


def _path_from_canonical(canonical_name: str) -> Path | None:
    """Recover the source-file :class:`Path` from a proc canonical name.

    Canonical names follow ``<source_file.as_posix()>::<qualified_name>``.
    Domain paths are POSIX-relative and never contain ``::``, so the
    first ``::`` is the unambiguous boundary.
    """
    sep = canonical_name.find("::")
    if sep < 0:
        return None
    return Path(canonical_name[:sep])


# ---------------------------------------------------------------------------
# Stage step cross-validation (VW-14 / VW-15 / VW-16 / VW-17)
# ---------------------------------------------------------------------------


_SOURCE_CMD_RE = re.compile(r"^\s*(?:source|iproc_source)\s+(\S+)\s*$")
_FILE_EXT_SUFFIXES = (".tcl", ".pl", ".py", ".csh", ".sh", ".bash")


def _check_stage_steps(ctx: ChopperContext, manifest: CompiledManifest) -> None:
    if not manifest.stages:
        return

    surviving_files = frozenset(manifest.file_decisions.keys())
    surviving_proc_short = _surviving_proc_shorts(manifest)

    for stage in manifest.stages:
        for step in stage.steps:
            _classify_and_emit(
                ctx,
                stage=stage,
                step=step,
                surviving_files=surviving_files,
                surviving_proc_shorts=surviving_proc_short,
            )


def _surviving_proc_shorts(manifest: CompiledManifest) -> frozenset[str]:
    """Map surviving canonical names back to their bare proc short-names.

    Canonical form is ``<file>::<qualified_name>``; the
    qualified name may carry ``::`` namespace segments. For VW-15 we
    match bare tokens against the final segment of the qualified name.
    """

    shorts: set[str] = set()
    for canonical in manifest.proc_decisions:
        _, _, qualified = canonical.partition("::")
        short = qualified.split("::")[-1] if qualified else canonical
        shorts.add(short)
    return frozenset(shorts)


def _classify_and_emit(
    ctx: ChopperContext,
    *,
    stage: StageSpec,
    step: str,
    surviving_files: frozenset[Path],
    surviving_proc_shorts: frozenset[str],
) -> None:
    stripped = step.strip()
    if not stripped:
        return

    # VW-17: advisory for absolute paths or upward traversal.
    if _is_external_reference(stripped):
        ctx.diag.emit(
            Diagnostic.build(
                "VW-17",
                phase=Phase.P6_POSTVALIDATE,
                message=(f"Stage {stage.name!r} step references external path: {stripped!r}"),
            )
        )
        return

    # VW-16: source / iproc_source <path>.
    m = _SOURCE_CMD_RE.match(stripped)
    if m is not None:
        target = PurePosixPath(m.group(1))
        if Path(target) not in surviving_files:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-16",
                    phase=Phase.P6_POSTVALIDATE,
                    message=(f"Stage {stage.name!r} source step targets missing file: {target!s}"),
                )
            )
        return

    # VW-14: bare file path with a known extension.
    if _looks_like_file_literal(stripped):
        target = PurePosixPath(stripped)
        if Path(target) not in surviving_files:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-14",
                    phase=Phase.P6_POSTVALIDATE,
                    message=(f"Stage {stage.name!r} step file missing from trim output: {stripped!r}"),
                )
            )
        return

    # VW-15: bare proc token.
    if _looks_like_bare_proc(stripped):
        proc_name = stripped.split()[0]
        if proc_name not in surviving_proc_shorts:
            ctx.diag.emit(
                Diagnostic.build(
                    "VW-15",
                    phase=Phase.P6_POSTVALIDATE,
                    message=(f"Stage {stage.name!r} step proc not in trim output: {proc_name!r}"),
                )
            )


def _is_external_reference(step: str) -> bool:
    head = step.split()[0] if step.split() else step
    if head.startswith("/") or (len(head) >= 2 and head[1] == ":"):
        return True
    parts = PurePosixPath(head).parts
    return any(p == ".." for p in parts)


def _looks_like_file_literal(step: str) -> bool:
    head = step.split()[0] if step.split() else step
    return any(head.endswith(ext) for ext in _FILE_EXT_SUFFIXES)


def _looks_like_bare_proc(step: str) -> bool:
    head = step.split()[0] if step.split() else step
    if "/" in head or "\\" in head:
        return False
    if any(head.endswith(ext) for ext in _FILE_EXT_SUFFIXES):
        return False
    return bool(head) and not head.startswith("#")


# ---------------------------------------------------------------------------
# Unused-import guards (kept to make the intent clear for reviewers).
# ---------------------------------------------------------------------------


_ = (FeatureJson, Iterable)
