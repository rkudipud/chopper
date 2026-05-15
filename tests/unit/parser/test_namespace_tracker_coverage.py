"""Per-file coverage tests for src/chopper/parser/namespace_tracker.py.

Redistributed from the omnibus ``tests/unit/test_coverage_98.py`` and
``tests/unit/test_coverage_99.py`` files; see ``tests/unit/_coverage_helpers.py``
for shared fixtures.
"""

from __future__ import annotations



from tests.unit._coverage_helpers import (  # noqa: F401
    AUDIT,
    BACKUP,
    DOMAIN,
    _Progress,
    _Sink,
    _codes,
    _ctx,
)


def test_namespace_tracker_post_init_skips_push_when_stack_nonempty() -> None:
    """NamespaceTracker.__post_init__ skips the append when _stack is already populated (141->exit)."""
    from chopper.parser.namespace_tracker import ContextFrame, ContextKind, NamespaceTracker

    pre_frame = ContextFrame(ContextKind.FILE_ROOT, 0)
    tracker = NamespaceTracker(_stack=[pre_frame])
    # Stack must still have exactly the one pre-populated frame (not appended again)
    assert len(tracker._stack) == 1
    assert tracker._stack[0] is pre_frame


def test_namespace_tracker_rbrace_at_file_root_does_not_pop() -> None:
    """RBRACE when top frame is FILE_ROOT → condition at line 309 is False → 309->319."""
    from chopper.parser.tokenizer import Token, TokenKind
    from chopper.parser.namespace_tracker import ContextFrame, ContextKind, NamespaceTracker

    # Create a tracker with depth=1 but only FILE_ROOT on the stack.
    # This simulates a LBRACE that somehow didn't push a new frame.
    # When RBRACE fires: depth→0, top=FILE_ROOT, condition False → 309->319.
    tracker = NamespaceTracker(
        _stack=[ContextFrame(ContextKind.FILE_ROOT, 0)],
        _depth=1,
    )
    assert tracker.depth == 1
    # Feed RBRACE → depth 0, top is FILE_ROOT → condition False at line 309
    tracker.feed(Token(kind=TokenKind.RBRACE, value="}", line_no=1, brace_depth=0, at_command_position=False))
    assert tracker.depth == 0
    # FILE_ROOT frame must still be on the stack (not popped)
    assert len(tracker._stack) == 1
    assert tracker._stack[0].kind is ContextKind.FILE_ROOT


def test_namespace_tracker_rbrace_namespace_eval_empty_nsstack() -> None:
    """RBRACE with NAMESPACE_EVAL top but empty _namespace_stack → 316->319 (no pop from empty)."""
    from chopper.parser.tokenizer import Token, TokenKind
    from chopper.parser.namespace_tracker import ContextFrame, ContextKind, NamespaceTracker

    # Build a tracker in a state where the top frame is NAMESPACE_EVAL at depth 0,
    # _depth is currently 1 (inside the eval body), and _namespace_stack is empty.
    tracker = NamespaceTracker(
        _stack=[
            ContextFrame(ContextKind.FILE_ROOT, 0),
            ContextFrame(ContextKind.NAMESPACE_EVAL, 0),
        ],
        _namespace_stack=[],
        _depth=1,
    )
    # Feed RBRACE → depth becomes 0, top is NAMESPACE_EVAL at 0 → pop,
    # then `if self._namespace_stack:` → False (empty) → 316->319, no crash
    tracker.feed(Token(kind=TokenKind.RBRACE, value="}", line_no=1, brace_depth=0, at_command_position=False))
    assert tracker.depth == 0
    # NAMESPACE_EVAL frame was popped
    assert len(tracker._stack) == 1
    assert tracker._stack[0].kind is ContextKind.FILE_ROOT
