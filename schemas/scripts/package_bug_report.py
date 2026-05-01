#!/usr/bin/env python3
"""Package local bug-report evidence into a single zip bundle.

Usage examples:
  python schemas/scripts/package_bug_report.py /path/to/.chopper
  python schemas/scripts/package_bug_report.py /path/to/.chopper /path/to/report.md
  python schemas/scripts/package_bug_report.py /path/to/.chopper --output /tmp/chopper_bug_bundle.zip
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package Chopper audit artifacts, logs, and reports into a single zip for GitHub issue upload"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="File or directory paths to include in the bundle (.chopper/, logs, markdown reports, screenshots, etc.)",
    )
    parser.add_argument(
        "--output",
        help="Zip file to create (default: ./chopper_bug_bundle_<timestamp>.zip)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output zip if it already exists",
    )
    return parser.parse_args()


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / f"chopper_bug_bundle_{stamp}.zip"


def resolve_output_path(raw_output: str | None) -> Path:
    output = Path(raw_output) if raw_output else default_output_path()
    if output.suffix.lower() != ".zip":
        output = output.with_suffix(".zip")
    return output


def validate_inputs(raw_paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"input path does not exist: {path}")
        resolved.append(path.resolve())
    return resolved


def iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(candidate for candidate in path.rglob("*") if candidate.is_file())


def archive_root(index: int, source: Path) -> Path:
    name = source.name or "root"
    return Path("inputs") / f"{index:02d}_{name}"


def build_manifest(inputs: list[Path], file_count: int, output: Path) -> str:
    lines = [
        "Chopper bug-report bundle",
        f"bundle: {output.resolve().as_posix()}",
        f"input_count: {len(inputs)}",
        f"file_count: {file_count}",
        "",
        "inputs:",
    ]
    for index, source in enumerate(inputs):
        lines.append(f"- [{index:02d}] {source.as_posix()}")
    lines.append("")
    lines.append("Use this zip in the GitHub bug-report form from VS Code or a browser.")
    return "\n".join(lines) + "\n"


def create_bundle(inputs: list[Path], output: Path) -> int:
    file_count = 0
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        for index, source in enumerate(inputs):
            root = archive_root(index, source)
            files = iter_files(source)
            if source.is_file():
                archive.write(source, root.as_posix())
                file_count += 1
                continue
            for file_path in files:
                archive.write(file_path, (root / file_path.relative_to(source)).as_posix())
                file_count += 1
        archive.writestr("bundle_manifest.txt", build_manifest(inputs, file_count, output))
    return file_count


def main() -> int:
    args = parse_args()
    try:
        inputs = validate_inputs(args.paths)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    output = resolve_output_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and not args.force:
        print(f"ERROR: output already exists: {output}")
        print("Re-run with --force to overwrite it.")
        return 2

    file_count = create_bundle(inputs, output)
    print(f"Created bug-report bundle: {output.resolve().as_posix()}")
    print(f"Included {file_count} file(s) from {len(inputs)} input path(s).")
    print("Upload this zip in the GitHub bug form, or point the Chopper Domain Companion at it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
