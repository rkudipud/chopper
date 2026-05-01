#!/usr/bin/env python3
"""Render and optionally file a Chopper bug report from a JSON payload.

`--create` is best-effort by default. The helper always prepares the local
issue body (and optional evidence bundle) first, then attempts `gh issue
create`. If the GitHub step fails, it falls back to the already-rendered local
output instead of requiring a second pass.

Usage examples:
  python schemas/scripts/file_bug_report.py --payload /tmp/bug_payload.json --dry-run
  python schemas/scripts/file_bug_report.py --payload /tmp/bug_payload.json --create

Payload shape:
{
  "repo": "rkudipud/chopper",
  "title": "[Bug] Example title",
  "command": "chopper trim --dry-run",
  "platform": "Linux",
  "ec_site": "local",
  "python_version": "Python 3.11.9",
  "what_happened": "Expected vs actual.",
  "reproduce": "1. ...\n2. ...",
  "terminal_output": "[P0_STATE] started\n...",
  "audit_bundle": "Attached diagnostics.json and chopper_run.json.",
  "json_files": "base.json: {...}",
  "additional_context": "Optional.",
  "attachments": ["/abs/path/to/.chopper", "/abs/path/to/report.md"]
}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from package_bug_report import create_bundle, validate_inputs

REQUIRED_FIELDS = (
    "title",
    "command",
    "platform",
    "ec_site",
    "python_version",
    "what_happened",
    "reproduce",
    "terminal_output",
    "audit_bundle",
    "json_files",
)

BUG_LABEL = "bug"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and optionally create a GitHub issue for a Chopper bug report")
    parser.add_argument("--payload", required=True, help="JSON payload describing the issue body and attachment paths")
    parser.add_argument("--output-dir", help="Directory for generated files (default: payload directory)")
    parser.add_argument("--repo", help="GitHub repo as owner/name (default: payload repo or origin remote)")
    parser.add_argument("--create", action="store_true", help="Create the GitHub issue with gh issue create")
    parser.add_argument("--dry-run", action="store_true", help="Render files only; do not create the GitHub issue")
    parser.add_argument("--force", action="store_true", help="Overwrite generated files if they already exist")
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload field '{key}' must be a non-empty string")
    return value.strip()


def attachments_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("attachments", [])
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError("payload field 'attachments' must be an array of non-empty strings")
    return [item.strip() for item in raw]


def output_dir_from_args(args: argparse.Namespace, payload_path: Path) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    return payload_path.resolve().parent


def ensure_writable(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output already exists: {path}")


def discover_repo() -> str | None:
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    remote = result.stdout.strip()
    if not remote:
        return None
    if remote.startswith("git@github.com:"):
        path = remote.split(":", 1)[1]
    elif "github.com/" in remote:
        path = remote.split("github.com/", 1)[1]
    else:
        return None
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def create_attachment_bundle(attachments: list[str], output_dir: Path, force: bool) -> Path | None:
    if not attachments:
        return None
    bundle_path = output_dir / "bug_report_bundle.zip"
    ensure_writable(bundle_path, force)
    inputs = validate_inputs(attachments)
    create_bundle(inputs, bundle_path)
    return bundle_path


def render_issue_body(payload: dict[str, Any], bundle_path: Path | None) -> str:
    additional_context = payload.get("additional_context")
    if not isinstance(additional_context, str) or not additional_context.strip():
        additional_context = "None."

    audit_section = require_text(payload, "audit_bundle")
    if bundle_path is not None:
        audit_section += (
            "\n\nCompanion note: a local evidence bundle was prepared separately. "
            "Binary bundle upload was not automatic."
        )

    body = f"""### Which command triggered the bug?

{require_text(payload, "command")}

### Platform

{require_text(payload, "platform")}

### EC site / zone

{require_text(payload, "ec_site")}

### Python version

{require_text(payload, "python_version")}

### What happened?

{require_text(payload, "what_happened")}

### Steps to reproduce

{require_text(payload, "reproduce")}

### Terminal output or log excerpt

```text
{require_text(payload, "terminal_output")}
```

### Audit artifacts attached or why unavailable

{audit_section}

### Minimal JSON reproduction or why you cannot share it

```text
{require_text(payload, "json_files")}
```

### Anything else?

{additional_context}

### Checklist

- [x] I searched existing open issues and this is not a duplicate.
- [x] I pasted terminal output or a real log excerpt, not an empty code block.
- [x] I attached audit artifacts or explained why no audit bundle was produced.
- [x] I pasted a minimal JSON reproduction or explained why I cannot share it verbatim.
"""
    return body


def write_issue_body(body: str, output_dir: Path, force: bool) -> Path:
    body_path = output_dir / "bug_report_issue.md"
    ensure_writable(body_path, force)
    body_path.write_text(body, encoding="utf-8")
    return body_path


def create_issue(repo: str, title: str, body_path: Path) -> str:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body-file",
            str(body_path),
            "--label",
            BUG_LABEL,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "gh issue create failed"
        raise RuntimeError(stderr)
    return result.stdout.strip()


def issue_form_url(repo: str) -> str:
    return f"https://github.com/{repo}/issues/new?template=bug_report.yml"


def fallback_to_local_output(reason: str, body_path: Path, bundle_path: Path | None, repo: str | None) -> int:
    print(f"WARNING: automatic issue creation failed; falling back to local output: {reason}")
    print(f"Issue body is available at: {body_path.resolve().as_posix()}")
    if bundle_path is not None:
        print(f"Local bundle is available at: {bundle_path.resolve().as_posix()}")
    if repo:
        print(f"GitHub issue form: {issue_form_url(repo)}")
    return 0


def main() -> int:
    args = parse_args()
    payload_path = Path(args.payload).expanduser().resolve()
    try:
        payload = load_payload(payload_path)
        for key in REQUIRED_FIELDS:
            require_text(payload, key)
        attachments = attachments_from_payload(payload)
        output_dir = output_dir_from_args(args, payload_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = create_attachment_bundle(attachments, output_dir, args.force)
        body = render_issue_body(payload, bundle_path)
        body_path = write_issue_body(body, output_dir, args.force)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"Prepared issue body: {body_path.resolve().as_posix()}")
    if bundle_path is not None:
        print(f"Prepared local bundle: {bundle_path.resolve().as_posix()}")

    if args.dry_run or not args.create:
        print("Simple fallback behavior active: GitHub issue was not created.")
        return 0

    repo = args.repo or payload.get("repo") or discover_repo()
    if not isinstance(repo, str) or not repo.strip():
        return fallback_to_local_output(
            "no GitHub repo available; pass --repo or include 'repo' in the payload",
            body_path,
            bundle_path,
            None,
        )

    repo = repo.strip()

    try:
        issue_url = create_issue(repo, require_text(payload, "title"), body_path)
    except FileNotFoundError:
        return fallback_to_local_output("`gh` was not found on PATH", body_path, bundle_path, repo)
    except RuntimeError as exc:
        return fallback_to_local_output(str(exc), body_path, bundle_path, repo)

    print(f"Created GitHub issue: {issue_url}")
    if bundle_path is not None:
        print("Binary attachment upload remains a separate GitHub UI step if the raw bundle is still needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
