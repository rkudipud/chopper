"""Unit tests for :mod:`chopper.core.tool_commands`."""

from __future__ import annotations

from pathlib import Path

import pytest

from chopper.core import tool_commands


class _Entry:
    def __init__(self, name: str, text: str, *, is_file: bool = True) -> None:
        self.name = name
        self._text = text
        self._is_file = is_file

    def is_file(self) -> bool:
        return self._is_file

    def read_text(self, *, encoding: str = "utf-8") -> str:
        return self._text


class _Package:
    def __init__(self, entries: list[_Entry]) -> None:
        self._entries = entries

    def iterdir(self) -> tuple[_Entry, ...]:
        return tuple(self._entries)


def test_parse_tokens_skips_blank_and_comment_lines() -> None:
    text = "\n  # comment\nread_libs report_timing\n\twrite_sdf\n"

    assert tool_commands.parse_tokens(text) == frozenset({"read_libs", "report_timing", "write_sdf"})


def test_load_pool_unions_sorted_builtin_command_files(monkeypatch: pytest.MonkeyPatch) -> None:
    package = _Package(
        [
            _Entry("z.commands", "z_cmd shared\n"),
            _Entry("ignore.txt", "not_loaded\n"),
            _Entry("subdir.commands", "not_loaded\n", is_file=False),
            _Entry("a.commands", "a_cmd shared\n"),
        ]
    )
    monkeypatch.setattr(tool_commands, "_resource_files", lambda package_name: package)

    assert tool_commands.load_pool() == frozenset({"a_cmd", "z_cmd", "shared"})


def test_load_pool_treats_missing_builtin_package_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(_: str) -> object:
        raise ModuleNotFoundError

    monkeypatch.setattr(tool_commands, "_resource_files", _missing)

    assert tool_commands.load_pool() == frozenset()


def test_load_pool_reads_user_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_commands, "_resource_files", lambda package_name: _Package([]))
    user_path = tmp_path / "tool.commands"
    user_path.write_text("alpha beta\n# skip\ngamma\n", encoding="utf-8")

    assert tool_commands.load_pool((user_path,)) == frozenset({"alpha", "beta", "gamma"})


def test_load_pool_reports_missing_user_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_commands, "_resource_files", lambda package_name: _Package([]))
    missing = tmp_path / "missing.commands"

    with pytest.raises(FileNotFoundError, match="--tool-commands file not found"):
        tool_commands.load_pool((missing,))
