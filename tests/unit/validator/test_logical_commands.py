from __future__ import annotations

from chopper.validator.functions import _logical_commands


def test_logical_commands_group_continuations_and_blocks() -> None:
    steps = [
        "define_proc_attributes example \\",
        '    -info "Example" \\',
        "    -define_args {",
        '        {value "A value" "" string required}',
        "    }",
        "set choices [list \\",
        "    alpha \\",
        "]",
        "if {$first",
        "    || $second",
        "} {",
        "}",
        "# Continued comment \\",
        "    EXAMPLE=1",
        "set x 1",
    ]
    cmds = _logical_commands(steps)
    assert [c.split()[0] for c in cmds] == ["define_proc_attributes", "set", "if", "#", "set"]
