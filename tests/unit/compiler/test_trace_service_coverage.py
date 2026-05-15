"""Per-file coverage tests for src/chopper/compiler/trace_service.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations

from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _codes,
    _ctx,
    _Progress,
    _Sink,
)


def test_trace_resolution_absolute_double_colon_strips_prefix() -> None:
    from chopper.compiler.trace_service import _candidate_qnames

    assert _candidate_qnames("::ns::foo", caller_namespace="other") == ("ns::foo",)


def test_trace_resolution_bare_token_no_namespace_returns_single() -> None:
    from chopper.compiler.trace_service import _candidate_qnames

    assert _candidate_qnames("foo", caller_namespace="") == ("foo",)


def test_trace_dynamic_tokens_short_circuit() -> None:
    from chopper.compiler.trace_service import _is_dynamic

    assert _is_dynamic("$var")
    assert _is_dynamic("[expr 1]")
    assert _is_dynamic("eval")
    assert _is_dynamic("uplevel#0")
    assert _is_dynamic("apply")
    assert _is_dynamic("")
    assert not _is_dynamic("plain_proc")


def test_trace_resolve_token_skipped_for_dynamic() -> None:
    """_resolve_token is not directly tested here — dynamic tokens are
    consumed at the BFS layer. We just exercise the helper _is_dynamic."""
    from chopper.compiler.trace_service import _is_dynamic

    assert _is_dynamic("$cmd")
    assert _is_dynamic("[expr 1]")


def test_candidate_qnames_strips_leading_double_colon() -> None:
    """_candidate_qnames returns a single candidate when the token starts with '::'."""
    from chopper.compiler.trace_service import _candidate_qnames

    result = _candidate_qnames("::some_ns::my_proc", "other_ns")
    assert result == ("some_ns::my_proc",)


def test_emit_cycle_diagnostics_self_loop_emits_tw04() -> None:
    """_emit_cycle_diagnostics must emit TW-04 for a single-node self-referencing proc."""
    from chopper.compiler.trace_service import _emit_cycle_diagnostics
    from chopper.core.models_compiler import Edge

    ctx = _ctx()
    # Self-loop: foo calls foo
    edge = Edge(
        caller="lib/helpers.tcl::foo",
        callee="lib/helpers.tcl::foo",
        kind="proc_call",
        status="resolved",
        token="foo",
        line=5,
    )
    _emit_cycle_diagnostics(ctx, [edge])
    assert "TW-04" in _codes(ctx)


def test_is_dynamic_true_for_variable_substitution() -> None:
    """_is_dynamic returns True when the token contains '$' (variable substitution)."""
    from chopper.compiler.trace_service import _is_dynamic

    assert _is_dynamic("$some_var") is True
    assert _is_dynamic("[expr 1+1]") is True
    assert _is_dynamic("plain_proc") is False
    assert _is_dynamic("") is True  # empty token is always dynamic


def test_path_from_canonical_no_separator_returns_none() -> None:
    """_path_from_canonical returns None when no '::' in canonical_name (line 406)."""
    from chopper.compiler.trace_service import _path_from_canonical

    result = _path_from_canonical("bare_proc_no_separator")
    assert result is None
