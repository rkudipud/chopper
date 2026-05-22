#!/usr/bin/env python3
"""Push local commits to GitHub using the Git Data API (bypasses git-receive-pack blocks).

Behavior:
- Will try to read credentials from `GITHUB_TOKEN` env var.
- If not present, will attempt `gh auth token` (GitHub CLI).
- Exits with instructions if no token is available.

This script intentionally does NOT embed any token. Place a token in `GITHUB_TOKEN` or authenticate with `gh` before running.
"""

import os
import subprocess
import json
import base64
import sys
import urllib.request
import urllib.error

REPO = os.environ.get("GH_API_PUSH_REPO", "rkudipud/chopper")
BRANCH = os.environ.get("GH_API_PUSH_BRANCH", "main")
PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
REPO_DIR = os.environ.get("GH_API_PUSH_DIR", os.getcwd())

if PROXY:
    proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    opener = urllib.request.build_opener(proxy_handler)
else:
    opener = urllib.request.build_opener()


def get_token():
    # 1) env var
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok.strip()
    # 2) gh auth token
    try:
        gh_path = subprocess.run(["gh", "--version"], capture_output=True)
        if gh_path.returncode == 0:
            tok = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
            if tok:
                return tok
    except FileNotFoundError:
        pass
    return None


def api(method, path, data=None, token=None):
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data is not None else None
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gh-api-push/1.0",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code} {method} {path}: {e.read().decode()}", file=sys.stderr)
        raise


def git(args, cwd=REPO_DIR):
    return subprocess.check_output(["git"] + args, cwd=cwd, text=True).strip()


def main():
    token = get_token()
    if not token:
        print("No GitHub token found.")
        print("- Option A (recommended): export GITHUB_TOKEN=... and run again.")
        print("- Option B: authenticate gh CLI (interactive): gh auth login")
        print("After authenticating, re-run this script.")
        sys.exit(2)

    print(f"Using token from environment/gh CLI. Repo: {REPO} Branch: {BRANCH}")

    # Get remote HEAD
    remote_ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}", token=token)
    remote_sha = remote_ref["object"]["sha"]
    print(f"Remote HEAD: {remote_sha}")

    # Get commits to push (oldest first)
    commits_out = git(["log", f"{remote_sha}..HEAD", "--reverse", "--format=%H"]) or ""
    commit_shas = [s for s in commits_out.splitlines() if s]
    if not commit_shas:
        print("Nothing to push: local HEAD is at or behind remote.")
        return

    print(f"Commits to push: {len(commit_shas)}")
    for sha in commit_shas:
        msg = git(["log", "-1", "--format=%s", sha])
        print(f"  {sha[:12]} {msg}")

    parent_sha = remote_sha

    for commit_sha in commit_shas:
        author_name = git(["log", "-1", "--format=%an", commit_sha])
        author_email = git(["log", "-1", "--format=%ae", commit_sha])
        author_date = git(["log", "-1", "--format=%aI", commit_sha])
        commit_msg = git(["log", "-1", "--format=%B", commit_sha])

        changed = git(["diff-tree", "--no-commit-id", "-r", "--name-status", commit_sha])
        print(f"\nCommit {commit_sha[:12]}: {len(changed.splitlines())} file(s)")

        parent_commit_obj = api("GET", f"/repos/{REPO}/git/commits/{parent_sha}", token=token)
        base_tree_sha = parent_commit_obj["tree"]["sha"]

        tree_items = []
        for line in changed.splitlines():
            status, filepath = line.split("\t", 1)
            if status == "D":
                # To delete a path, set it to null in the tree creation by omitting it (GitHub API does not accept explicit delete entries with null sha)
                # We'll add a tree entry with no blob to implicitly remove it by creating a tree without that path.
                tree_items.append({"path": filepath, "mode": "100644", "type": "blob", "sha": None})
                print(f"  D {filepath}")
            else:
                # Read file content at this commit
                file_content = subprocess.check_output(["git", "show", f"{commit_sha}:{filepath}"], cwd=REPO_DIR)
                blob = api("POST", f"/repos/{REPO}/git/blobs", {"content": base64.b64encode(file_content).decode(), "encoding": "base64"}, token=token)
                mode_out = git(["ls-tree", commit_sha, filepath])
                mode = mode_out.split()[0] if mode_out else "100644"
                tree_items.append({"path": filepath, "mode": mode, "type": "blob", "sha": blob["sha"]})
                print(f"  {status} {filepath} -> blob {blob['sha'][:12]}")

        # Create tree
        tree = api("POST", f"/repos/{REPO}/git/trees", {"base_tree": base_tree_sha, "tree": tree_items}, token=token)
        print(f"  Tree: {tree['sha'][:12]}")

        # Create commit
        new_commit = api("POST", f"/repos/{REPO}/git/commits", {
            "message": commit_msg,
            "tree": tree["sha"],
            "parents": [parent_sha],
            "author": {"name": author_name, "email": author_email, "date": author_date},
            "committer": {"name": author_name, "email": author_email, "date": author_date},
        }, token=token)
        print(f"  Commit: {new_commit['sha'][:12]}")
        parent_sha = new_commit["sha"]

    # Update ref
    api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": parent_sha, "force": False}, token=token)
    print(f"\nPushed! refs/heads/{BRANCH} -> {parent_sha[:12]}")


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError:
        print("API error during push. Check token scopes and network proxy settings.")
        sys.exit(1)
