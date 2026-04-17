"""Generate the committed Latin-1 parser fixture used by the docs and tests."""

from __future__ import annotations

from pathlib import Path

FIXTURE_RELATIVE_PATH = Path("edge_cases") / "parser_encoding_latin1_fallback.tcl"


def build_fixture_bytes() -> bytes:
    text = '# -*- coding: latin-1 -*-\nproc legacy_proc {} {\n    # \xdc \xf6 \xe4\n    return "done"\n}\n'
    return text.encode("latin-1")


def write_fixture(base_dir: Path) -> Path:
    fixture_path = base_dir / FIXTURE_RELATIVE_PATH
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_bytes(build_fixture_bytes())
    return fixture_path


def main() -> None:
    fixture_path = write_fixture(Path(__file__).resolve().parent)
    print(f"Wrote {fixture_path}")


if __name__ == "__main__":
    main()
