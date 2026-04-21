#!/usr/bin/env python3
"""Validate Chopper JSON files against repository schemas.

Usage examples:
  python validate_jsons.py
  python validate_jsons.py examples/08_base_plus_one_feature
  python validate_jsons.py my_domain/chopper
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import jsonschema
except ImportError:
    print("ERROR: Missing dependency 'jsonschema'. Install with: python -m pip install jsonschema")
    sys.exit(2)


SCHEMA_IDS = {
    "chopper/base/v1": "base-v1.schema.json",
    "chopper/feature/v1": "feature-v1.schema.json",
    "chopper/project/v1": "project-v1.schema.json",
}


def iter_json_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen = set()
    for path in paths:
        if not path.exists():
            print(f"WARN path does not exist: {path}")
            continue
        if path.is_file() and path.suffix.lower() == ".json":
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path
            continue
        if path.is_dir():
            for candidate in sorted(path.rglob("*.json")):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate


def load_schemas(schema_dir: Path) -> Dict[str, dict]:
    schemas: Dict[str, dict] = {}
    for schema_id, filename in SCHEMA_IDS.items():
        schema_path = schema_dir / filename
        with schema_path.open("r", encoding="utf-8") as handle:
            schemas[schema_id] = json.load(handle)
    return schemas


def validate_file(json_file: Path, schemas: Dict[str, dict]) -> Tuple[str, str]:
    try:
        with json_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return "parse_error", f"PARSE_ERR {json_file}: {exc}"

    if not isinstance(data, dict):
        return "skipped", f"SKIP {json_file}: top-level JSON is {type(data).__name__}, expected object"

    schema_id = data.get("$schema")
    if schema_id not in schemas:
        return "skipped", f"SKIP {json_file}: unrecognized or missing $schema ({schema_id})"

    try:
        jsonschema.validate(data, schemas[schema_id])
        return "ok", f"OK   {json_file}"
    except jsonschema.ValidationError as exc:
        location = list(exc.absolute_path)
        return "schema_error", f"ERR  {json_file}: {exc.message} (at: {location})"


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent
    default_schema_dir = repo_root / "schemas"

    parser = argparse.ArgumentParser(description="Validate Chopper JSON files against schemas")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="JSON file(s) or directory path(s) to validate (default: current directory)",
    )
    parser.add_argument(
        "--schema-dir",
        default=str(default_schema_dir),
        help=f"Directory containing schema files (default: {default_schema_dir})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_paths = [Path(p) for p in args.paths]
    schema_dir = Path(args.schema_dir)

    if not schema_dir.exists() or not schema_dir.is_dir():
        print(f"ERROR schema directory not found: {schema_dir}")
        return 2

    try:
        schemas = load_schemas(schema_dir)
    except Exception as exc:
        print(f"ERROR failed to load schemas from {schema_dir}: {exc}")
        return 2

    files = list(iter_json_files(target_paths))
    if not files:
        print("No JSON files found in the provided path(s).")
        return 0

    counts = {
        "ok": 0,
        "schema_error": 0,
        "parse_error": 0,
        "skipped": 0,
    }

    for json_file in files:
        status, message = validate_file(json_file, schemas)
        counts[status] += 1
        print(message)

    print(
        "\nSummary: "
        f"{counts['ok']} valid, "
        f"{counts['schema_error']} schema errors, "
        f"{counts['parse_error']} parse errors, "
        f"{counts['skipped']} skipped"
    )

    if counts["schema_error"] > 0 or counts["parse_error"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
