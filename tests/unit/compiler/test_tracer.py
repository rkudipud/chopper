"""TracerService unit tests — architecture doc §5.4 (P4 trace).

These tests exercise the BFS walk, the lexical namespace resolution
contract, the ``TW-01``/``TW-02``/``TW-03``/``TW-04`` diagnostic
emission, cycle detection, source-edge reporting, and determinism.

The tracer never consumes file text; it consumes ``ProcEntry.calls``
and ``ProcEntry.source_refs`` populated directly by the test helpers.
"""

from __future__ import annotations

from pathlib import Path

from chopper.compiler import TracerService
from chopper.core.models import (
    BaseJson,
    CompiledManifest,
    DependencyGraph,
    Edge,
    FileProvenance,
    FileTreatment,
    LoadedConfig,
    ParsedFile,
    ParseResult,
    ProcDecision,
)
from tests.unit.compiler._helpers import make_ctx, make_proc

_DOMAIN = "my_domain"


def _loaded_with_pool(*tokens: str) -> LoadedConfig:
    """Build a :class:`LoadedConfig` whose only populated field is the tool-command pool.

    The tracer only ever reads ``loaded.tool_command_pool``; the rest of
    the config is irrelevant to these tests. A placeholder :class:`BaseJson`
    satisfies the non-optional field.
    """
    return LoadedConfig(
        base=BaseJson(source_path=Path("base.json"), domain=_DOMAIN),
        tool_command_pool=frozenset(tokens),
    )


# ---------------------------------------------------------------------------
# Small construction helpers local to these tests.
# ---------------------------------------------------------------------------


def _parse(*procs: object) -> ParseResult:
    """Assemble a :class:`ParseResult` from prebuilt :class:`ProcEntry`."""
    files: dict[Path, ParsedFile] = {}
    index: dict[str, object] = {}
    by_file: dict[Path, list] = {}
    for proc in procs:
        by_file.setdefault(proc.source_file, []).append(proc)  # type: ignore[attr-defined]
    for path, entries in sorted(by_file.items()):
        entries.sort(key=lambda e: e.start_line)
        files[path] = ParsedFile(path=path, procs=tuple(entries), encoding="utf-8")
        for e in entries:
            index[e.canonical_name] = e
    sorted_index = {k: index[k] for k in sorted(index)}
    return ParseResult(files=files, index=sorted_index)  # type: ignore[arg-type]


def _manifest_with_seeds(*canonical_names: str) -> CompiledManifest:
    """Build a manifest that names the given canonical procs as PI seeds.

    Every seed's file is stamped ``FULL_COPY`` with a minimal provenance
    record — the tracer doesn't inspect file treatment, only
    ``proc_decisions``, but :class:`CompiledManifest` requires treatment
    ↔ provenance consistency.
    """
    proc_decisions: dict[str, ProcDecision] = {}
    file_decisions: dict[Path, FileTreatment] = {}
    provenance: dict[Path, FileProvenance] = {}
    for cn in sorted(canonical_names):
        source_file = Path(cn.split("::", 1)[0])
        proc_decisions[cn] = ProcDecision(
            canonical_name=cn,
            source_file=source_file,
            selection_source="base:procedures.include",
        )
        if source_file not in file_decisions:
            file_decisions[source_file] = FileTreatment.FULL_COPY
            provenance[source_file] = FileProvenance(
                path=source_file,
                treatment=FileTreatment.FULL_COPY,
                reason="fi-literal",
                input_sources=("base:files.include",),
                vetoed_entries=(),
                proc_model=None,
            )
    sorted_files = {k: file_decisions[k] for k in sorted(file_decisions)}
    sorted_prov = {k: provenance[k] for k in sorted(provenance)}
    return CompiledManifest(
        file_decisions=sorted_files,
        proc_decisions=proc_decisions,
        provenance=sorted_prov,
        stages=(),
    )


# ---------------------------------------------------------------------------
# Empty / trivial seeds
# ---------------------------------------------------------------------------


class TestEmptySeeds:
    def test_no_seeds_returns_empty_graph(self) -> None:
        ctx, sink = make_ctx()
        parsed = _parse(make_proc("a.tcl", "foo"))
        manifest = _manifest_with_seeds()

        graph = TracerService().run(ctx, manifest, parsed)

        assert isinstance(graph, DependencyGraph)
        assert graph.pi_seeds == ()
        assert graph.nodes == ()
        assert graph.pt == ()
        assert graph.edges == ()
        assert sink.codes() == []

    def test_seed_with_no_calls_yields_single_node(self) -> None:
        ctx, sink = make_ctx()
        parsed = _parse(make_proc("a.tcl", "foo"))
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert graph.pi_seeds == ("a.tcl::foo",)
        assert graph.nodes == ("a.tcl::foo",)
        assert graph.pt == ()
        assert graph.edges == ()
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Resolved call chains (BFS expansion)
# ---------------------------------------------------------------------------


class TestResolvedCalls:
    def test_single_resolved_call(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("bar",))
        bar = make_proc("a.tcl", "bar", start=10, end=12)
        parsed = _parse(foo, bar)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert graph.nodes == ("a.tcl::bar", "a.tcl::foo")
        assert graph.pt == ("a.tcl::bar",)
        assert len(graph.edges) == 1
        e = graph.edges[0]
        assert e.caller == "a.tcl::foo"
        assert e.callee == "a.tcl::bar"
        assert e.status == "resolved"
        assert e.diagnostic_code is None
        assert sink.codes() == []

    def test_transitive_chain_three_deep(self) -> None:
        ctx, _ = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("bar",))
        bar = make_proc("a.tcl", "bar", start=10, end=12, calls=("baz",))
        baz = make_proc("a.tcl", "baz", start=20, end=22)
        parsed = _parse(foo, bar, baz)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert graph.nodes == ("a.tcl::bar", "a.tcl::baz", "a.tcl::foo")
        assert graph.pt == ("a.tcl::bar", "a.tcl::baz")

    def test_multiple_seeds_explored_in_lex_order(self) -> None:
        ctx, _ = make_ctx()
        # Both seeds call the same proc; only one edge per call-site.
        foo = make_proc("a.tcl", "foo", calls=("shared",))
        bar = make_proc("a.tcl", "bar", start=10, end=12, calls=("shared",))
        shared = make_proc("a.tcl", "shared", start=20, end=22)
        parsed = _parse(foo, bar, shared)
        manifest = _manifest_with_seeds("a.tcl::foo", "a.tcl::bar")

        graph = TracerService().run(ctx, manifest, parsed)

        assert graph.pi_seeds == ("a.tcl::bar", "a.tcl::foo")
        assert graph.nodes == ("a.tcl::bar", "a.tcl::foo", "a.tcl::shared")
        # Two edges, both to shared. Lex-sorted by caller → bar comes first.
        assert [e.caller for e in graph.edges] == ["a.tcl::bar", "a.tcl::foo"]
        for e in graph.edges:
            assert e.callee == "a.tcl::shared"
            assert e.status == "resolved"


# ---------------------------------------------------------------------------
# Ambiguous match — TW-01
# ---------------------------------------------------------------------------


class TestAmbiguousMatch:
    def test_same_qualified_name_in_two_files_emits_tw01(self) -> None:
        """Two files define a proc with the same qualified name — a bare
        call to that name from global scope hits both and emits ``TW-01``
        per architecture doc §5.4 step 8 ("multiple canonical procs match the same
        candidate qualified name")."""
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("helper",))
        # Both helpers share qualified_name "helper" (global scope).
        h1 = make_proc("lib_a.tcl", "helper")
        h2 = make_proc("lib_b.tcl", "helper")
        parsed = _parse(foo, h1, h2)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == ["TW-01"]
        assert graph.nodes == ("a.tcl::foo",)
        assert len(graph.edges) == 1
        assert graph.edges[0].status == "ambiguous"
        assert graph.edges[0].diagnostic_code == "TW-01"
        assert graph.edges[0].callee == ""
        assert graph.unresolved_tokens[0][3] == "TW-01"


# ---------------------------------------------------------------------------
# Unresolved — TW-02
# ---------------------------------------------------------------------------


class TestUnresolvedMatch:
    def test_bare_name_with_no_match_emits_tw02(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("missing_util",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == ["TW-02"]
        assert graph.nodes == ("a.tcl::foo",)
        assert graph.edges[0].status == "unresolved"
        assert graph.edges[0].diagnostic_code == "TW-02"

    def test_tw02_diagnostic_carries_caller_path(self) -> None:
        """Bug ``diagnostics_file_null_for_p4_p6.md``: TW-02 emitted ``file: null``.

        The fix populates ``Diagnostic.path`` from ``caller.source_file``
        so the audit JSON ``file`` field is a real domain-relative POSIX
        path, not None. Same wiring covers TW-01 / TW-03 / TW-04 / TI-01.
        """
        from pathlib import Path

        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("missing_util",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        TracerService().run(ctx, manifest, parsed)

        assert len(sink.emissions) == 1
        assert sink.emissions[0].code == "TW-02"
        assert sink.emissions[0].path == Path("a.tcl"), (
            f"TW-02 must carry caller's source_file, got {sink.emissions[0].path!r}"
        )


# ---------------------------------------------------------------------------
# Tool-command pool — TI-01 (architecture doc §3.10, FR-44)
# ---------------------------------------------------------------------------


class TestToolCommandPool:
    """The pool downgrades TW-02 → TI-01 on raw-name or leaf match.

    Coverage:
      * Raw-token match (``get_app_var`` in pool, bare call).
      * Namespace-stripped leaf match (``::pt::get_app_var`` call).
      * Pool does NOT intercept TW-01 (ambiguous) or TW-03 (dynamic).
      * Empty pool / no ``loaded`` argument preserves pre-0.5.0 behaviour.
      * Pool-matched edges are excluded from ``unresolved_tokens``.
    """

    def test_raw_token_match_emits_ti01_not_tw02(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("get_app_var",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")
        loaded = _loaded_with_pool("get_app_var")

        graph = TracerService().run(ctx, manifest, parsed, loaded)

        assert sink.codes() == ["TI-01"]
        assert graph.edges[0].status == "tool_command"
        assert graph.edges[0].diagnostic_code == "TI-01"
        assert graph.edges[0].callee == ""
        # Must NOT appear in unresolved_tokens — that channel is for
        # genuinely-unresolved TW-* only.
        assert graph.unresolved_tokens == ()

    def test_namespace_leaf_match_emits_ti01(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("::pt::get_app_var",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")
        # Pool contains bare name; call site uses fully-qualified form.
        loaded = _loaded_with_pool("get_app_var")

        graph = TracerService().run(ctx, manifest, parsed, loaded)

        assert sink.codes() == ["TI-01"]
        assert graph.edges[0].status == "tool_command"
        assert graph.edges[0].token == "::pt::get_app_var"

    def test_empty_pool_preserves_tw02(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("get_app_var",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")
        loaded = _loaded_with_pool()  # empty

        graph = TracerService().run(ctx, manifest, parsed, loaded)

        assert sink.codes() == ["TW-02"]
        assert graph.edges[0].status == "unresolved"

    def test_loaded_none_preserves_tw02(self) -> None:
        """Passing ``loaded=None`` (or omitting it) keeps pre-0.5.0 behaviour."""
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("get_app_var",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == ["TW-02"]
        assert graph.edges[0].status == "unresolved"

    def test_pool_does_not_intercept_tw03_dynamic(self) -> None:
        """A dynamic call form (e.g. ``$cmd``) still emits TW-03 regardless of pool."""
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("$get_app_var",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")
        # Even if the token-without-$ is in the pool, dynamic form wins.
        loaded = _loaded_with_pool("get_app_var", "$get_app_var")

        graph = TracerService().run(ctx, manifest, parsed, loaded)

        assert sink.codes() == ["TW-03"]
        assert graph.edges[0].status == "dynamic"

    def test_pool_does_not_intercept_resolved_proc(self) -> None:
        """An in-domain proc always resolves to itself — pool is irrelevant."""
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("helper",))
        helper = make_proc("a.tcl", "helper")
        parsed = _parse(foo, helper)
        manifest = _manifest_with_seeds("a.tcl::foo")
        # Pool contains "helper"; must NOT fire because helper resolves.
        loaded = _loaded_with_pool("helper")

        graph = TracerService().run(ctx, manifest, parsed, loaded)

        assert sink.codes() == []  # no diagnostics
        assert graph.edges[0].status == "resolved"
        assert graph.edges[0].callee == "a.tcl::helper"


# ---------------------------------------------------------------------------
# Dynamic — TW-03
# ---------------------------------------------------------------------------


class TestDynamicCall:
    def test_dollar_variable_token_emits_tw03(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("$cmd",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == ["TW-03"]
        assert graph.edges[0].status == "dynamic"
        assert graph.edges[0].diagnostic_code == "TW-03"

    def test_bracketed_command_substitution_emits_tw03(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("[expr {$x}]",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == ["TW-03"]


# ---------------------------------------------------------------------------
# Cycles — TW-04
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_self_recursion_emits_tw04(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", calls=("foo",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        assert "TW-04" in sink.codes()
        # The resolved self-edge is recorded.
        assert any(e.caller == e.callee == "a.tcl::foo" for e in graph.edges)

    def test_two_proc_cycle_emits_single_tw04(self) -> None:
        ctx, sink = make_ctx()
        a = make_proc("m.tcl", "a", calls=("b",))
        b = make_proc("m.tcl", "b", start=10, end=12, calls=("a",))
        parsed = _parse(a, b)
        manifest = _manifest_with_seeds("m.tcl::a")

        graph = TracerService().run(ctx, manifest, parsed)

        tw04 = [c for c in sink.codes() if c == "TW-04"]
        assert len(tw04) == 1
        assert graph.nodes == ("m.tcl::a", "m.tcl::b")


# ---------------------------------------------------------------------------
# Namespace-qualified resolution (architecture doc §5.4 step 6)
# ---------------------------------------------------------------------------


class TestNamespaceResolution:
    def test_absolute_double_colon_resolves_to_qualified(self) -> None:
        ctx, sink = make_ctx()
        caller = make_proc("a.tcl", "caller", calls=("::util::helper",))
        helper = make_proc("u.tcl", "helper", qualified="util::helper", namespace="util")
        parsed = _parse(caller, helper)
        manifest = _manifest_with_seeds("a.tcl::caller")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == []
        assert "u.tcl::util::helper" in graph.nodes
        assert graph.edges[0].status == "resolved"
        assert graph.edges[0].callee == "u.tcl::util::helper"

    def test_bare_name_resolves_under_caller_namespace_first(self) -> None:
        ctx, sink = make_ctx()
        # Caller is in `util`; local helper shadows a global one.
        caller = make_proc("a.tcl", "caller", qualified="util::caller", namespace="util", calls=("helper",))
        local = make_proc("u.tcl", "helper", qualified="util::helper", namespace="util")
        glob = make_proc("g.tcl", "helper", qualified="helper", namespace="")
        parsed = _parse(caller, local, glob)
        manifest = _manifest_with_seeds("a.tcl::util::caller")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == []
        # Caller-namespace candidate wins → util::helper.
        resolved_callee = graph.edges[0].callee
        assert resolved_callee == "u.tcl::util::helper"

    def test_bare_name_falls_back_to_global(self) -> None:
        ctx, sink = make_ctx()
        # Caller in `util::sub`, no `util::sub::helper`, only a global helper.
        caller = make_proc("a.tcl", "c", qualified="util::sub::c", namespace="util::sub", calls=("helper",))
        glob = make_proc("g.tcl", "helper", qualified="helper", namespace="")
        parsed = _parse(caller, glob)
        manifest = _manifest_with_seeds("a.tcl::util::sub::c")

        graph = TracerService().run(ctx, manifest, parsed)

        assert sink.codes() == []
        assert graph.edges[0].callee == "g.tcl::helper"


# ---------------------------------------------------------------------------
# Source / iproc_source edges
# ---------------------------------------------------------------------------


class TestSourceEdges:
    def test_source_refs_recorded_as_file_edges(self) -> None:
        ctx, sink = make_ctx()
        foo = make_proc("a.tcl", "foo", source_refs=("lib/helpers.tcl",))
        parsed = _parse(foo)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        source_edges = [e for e in graph.edges if e.kind == "source"]
        assert len(source_edges) == 1
        assert source_edges[0].callee == "lib/helpers.tcl"
        assert source_edges[0].status == "resolved"
        # Reporting-only: the source file does not appear in nodes.
        assert "lib/helpers.tcl" not in graph.nodes
        assert sink.codes() == []


# ---------------------------------------------------------------------------
# Manifest immutability and determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_runs_produce_identical_graph(self) -> None:
        foo = make_proc("a.tcl", "foo", calls=("bar",))
        bar = make_proc("a.tcl", "bar", start=10, end=12, calls=("baz",))
        baz = make_proc("a.tcl", "baz", start=20, end=22)
        parsed = _parse(foo, bar, baz)
        manifest = _manifest_with_seeds("a.tcl::foo")

        ctx1, _ = make_ctx()
        ctx2, _ = make_ctx()
        g1 = TracerService().run(ctx1, manifest, parsed)
        g2 = TracerService().run(ctx2, manifest, parsed)

        assert g1 == g2

    def test_graph_is_frozen(self) -> None:
        ctx, _ = make_ctx()
        parsed = _parse(make_proc("a.tcl", "foo"))
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        import pytest

        with pytest.raises(Exception):
            graph.nodes = ("mutated",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Edge-record invariants
# ---------------------------------------------------------------------------


class TestEdgeInvariants:
    def test_edges_lex_sorted_by_caller_kind_line_token_callee(self) -> None:
        ctx, _ = make_ctx()
        # Two calls from same caller, two source refs; all should sort deterministically.
        foo = make_proc(
            "a.tcl",
            "foo",
            calls=("aa", "bb"),
            source_refs=("lib/a.tcl", "lib/b.tcl"),
        )
        aa = make_proc("a.tcl", "aa", start=10, end=12)
        bb = make_proc("a.tcl", "bb", start=20, end=22)
        parsed = _parse(foo, aa, bb)
        manifest = _manifest_with_seeds("a.tcl::foo")

        graph = TracerService().run(ctx, manifest, parsed)

        keys = [(e.caller, e.kind, e.line, e.token, e.callee) for e in graph.edges]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# End-to-end BFS example from architecture doc §5.4 (worked example)
# ---------------------------------------------------------------------------


class TestArchitectureDocWorkedExample:
    def test_architecture_doc_example_emits_tw01_tw02_tw03_tw04(self) -> None:
        """End-to-end BFS walk matching architecture doc §5.4 "Worked BFS example".

        Two files each define a global-scope ``proc helper {}`` so they
        share qualified name ``helper``; a bare call to ``helper`` from
        ``step_a`` therefore matches both canonical procs and fires
        ``TW-01`` per §5.4 step 8.
        """
        ctx, sink = make_ctx()
        main = make_proc(
            "flow.tcl",
            "main",
            start=1,
            end=6,
            calls=("step_a", "step_b", "$dyn_cmd"),
        )
        step_a = make_proc(
            "flow.tcl",
            "step_a",
            start=10,
            end=13,
            calls=("helper", "recursive"),
        )
        step_b = make_proc(
            "flow.tcl",
            "step_b",
            start=20,
            end=22,
            calls=("missing_util",),
        )
        recursive = make_proc(
            "flow.tcl",
            "recursive",
            start=30,
            end=32,
            calls=("recursive",),
        )
        # Two canonical procs share qualified_name "helper" → TW-01.
        helper_a = make_proc("utils_a.tcl", "helper")
        helper_b = make_proc("utils_b.tcl", "helper")
        parsed = _parse(main, step_a, step_b, recursive, helper_a, helper_b)
        manifest = _manifest_with_seeds("flow.tcl::main")

        graph = TracerService().run(ctx, manifest, parsed)

        codes = set(sink.codes())
        assert {"TW-01", "TW-02", "TW-03", "TW-04"} <= codes

        # `main`, `step_a`, `step_b`, `recursive` all reachable; helper procs not.
        assert "flow.tcl::main" in graph.nodes
        assert "flow.tcl::step_a" in graph.nodes
        assert "flow.tcl::step_b" in graph.nodes
        assert "flow.tcl::recursive" in graph.nodes
        assert "utils_a.tcl::helper" not in graph.nodes
        assert "utils_b.tcl::helper" not in graph.nodes


# ---------------------------------------------------------------------------
# Edge class direct validation (frozen invariants)
# ---------------------------------------------------------------------------


class TestEdgeClass:
    def test_resolved_edge_requires_callee(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="callee is required"):
            Edge(caller="a.tcl::x", callee="", kind="proc_call", status="resolved", token="t", line=1)

    def test_unresolved_edge_requires_diagnostic_code(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="diagnostic_code is required"):
            Edge(caller="a.tcl::x", callee="", kind="proc_call", status="unresolved", token="t", line=1)

    def test_resolved_edge_forbids_diagnostic_code(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="must be None for resolved"):
            Edge(
                caller="a.tcl::x",
                callee="a.tcl::y",
                kind="proc_call",
                status="resolved",
                token="t",
                line=1,
                diagnostic_code="TW-02",
            )


# ---------------------------------------------------------------------------
# DependencyGraph invariant smoke tests
# ---------------------------------------------------------------------------


class TestDependencyGraphInvariants:
    def test_nodes_must_be_lex_sorted(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="nodes must be lex-sorted"):
            DependencyGraph(
                pi_seeds=(),
                nodes=("b", "a"),
                pt=(),
                edges=(),
                reachable_from_includes=frozenset({"a", "b"}),
            )

    def test_pt_must_equal_nodes_minus_seeds(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="pt must equal"):
            DependencyGraph(
                pi_seeds=("a",),
                nodes=("a", "b"),
                pt=("a",),
                edges=(),
                reachable_from_includes=frozenset({"a", "b"}),
            )
