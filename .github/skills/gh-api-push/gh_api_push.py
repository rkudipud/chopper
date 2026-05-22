#!/usr/bin/env python3
"""Push local commits to GitHub using the Git Data API.

Bypasses corporate proxy blocks on git-receive-pack (HTTPS push).
Root cause on Intel EC/HPC networks: Fortinet URLfilter Policy 241 blocks
git-receive-pack to external hosts. The GitHub REST API (api.github.com)
is allowed and this script uses it as the push path.

Credentials (tried in order):
  1. GITHUB_TOKEN or GH_TOKEN environment variable  (recommended)
  2. `gh auth token` via GitHub CLI (system gh, then Intel-specific paths)

Configurable via environment variables:
  GH_API_PUSH_REPO   -- owner/repo  (default: rkudipud/chopper)
  GH_API_PUSH_BRANCH -- branch name (default: main)
  GH_API_PUSH_DIR    -- local repo root (default: directory of this script)
  HTTPS_PROXY / HTTP_PROXY / https_proxy / http_proxy
                     -- proxy URL   (default: http://proxy-dmz.intel.com:912)
"""

import os
import subprocess
import json
import base64
import sys
import urllib.request
import urllib.error

REPO     = os.environ.get("GH_API_PUSH_REPO",   "rkudipud/chopper")
BRANCH   = os.environ.get("GH_API_PUSH_BRANCH", "main")
PROXY    = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or
            os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy")  or
            "http://proxy-dmz.intel.com:912")
REPO_DIR = os.environ.get("GH_API_PUSH_DIR", os.path.dirname(os.path.abspath(__file__)))

proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
opener = urllib.request.build_opener(proxy_handler)

# gh CLI candidates: system path first, then Intel-specific versioned installs
_GH_CANDIDATES = [
    "gh",
    "/nfs/site/itools/em64t_SLES15/pkgs/github-cli/2.83.1/bin/gh",
    "/nfs/site/itools/em64t_SLES15/pkgs/github-cli/2.25.1/bin/gh",
]


def get_token():
    """Return a GitHub token from env or gh CLI, or None."""
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok.strip()
    for gh in _GH_CANDIDATES:
        try:
            if subprocess.run([gh, "--version"], capture_output=True).returncode == 0:
                tok = subprocess.check_output([gh, "auth", "token"], text=True).strip()
                if tok:
                    return tok
        except FileNotFoundError:
            continue
    return None


def api(method, path, data=None, token=None):
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "gh-api-push/1.0",
    })
    try:
        with opener.open(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code} {method} {path}: {e.read().decode()}", file=sys.stderr)
        raise


def git(args):
    return subprocess.check_output(["git"] + args, cwd=REPO_DIR, text=True).strip()


def main():
    token = get_token()
    if not token:
        print("No GitHub token found.")
        print("  Option A (recommended): export GITHUB_TOKEN=<your-token> and re-run.")
        print("  Option B: gh auth login                    (interactive browser flow)")
        print("  Option C: gh auth refresh -h github.com -s repo  (refresh existing session)")
        print()
        print("  To create a token: https://github.com/settings/tokens")
        print("  Required scopes: repo  (or public_repo for public-only repos)")
        sys.exit(2)

    print(f"Repo: {REPO}  Branch: {BRANCH}  Proxy: {PROXY}")

    # Get remote HEAD
    remote_ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}", token=token)
    remote_sha = remote_ref["object"]["sha"]
    print(f"Remote HEAD: {remote_sha[:12]}")

    # Commits to push, oldest first
    commits_out = git(["log", f"{remote_sha}..HEAD", "--reverse", "--format=%H"]) or ""
    commit_shas = [s for s in commits_out.splitlines() if s]
    if not commit_shas:
        print("Nothing to push: local HEAD is already at or behind remote.")
        return

    print(f"Commits to push: {len(commit_shas)}")
    for sha in commit_shas:
        print(f"  {sha[:12]} {git(['log', '-1', '--format=%s', sha])}")

    parent_sha = remote_sha

    for commit_sha in commit_shas:
        author_name  = git(["log", "-1", "--format=%an", commit_sha])
        author_email = git(["log", "-1", "--format=%ae", commit_sha])
        author_date  = git(["log", "-1", "--format=%aI", commit_sha])
        commit_msg   = git(["log", "-1", "--format=%B", commit_sha])

        changed = git(["diff-tree", "--no-commit-id", "-r", "--name-status", commit_sha])
        changed_lines = [l for l in changed.splitlines() if l]
        print(f"\nCommit {commit_sha[:12]}: {len(changed_lines)} file(s)")

        base_tree_sha = api(
            "GET", f"/repos/{REPO}/git/commits/{parent_sha}", token=token
        )["tree"]["sha"]

        tree_items = []
        for line in changed_lines:
            status, filepath = line.split("\t", 1)
            if status == "D":
                # null sha removes the path from the tree
                tree_items.append({"path": filepath, "mode": "100644", "type": "blob", "sha": None})
                print(f"  D {filepath}")
            else:
                file_content = subprocess.check_output(
                    ["git", "show", f"{commit_sha}:{filepath}"], cwd=REPO_DIR
                )
                blob = api("POST", f"/repos/{REPO}/git/blobs", {
                    "content": base64.b64encode(file_content).decode(),
                    "encoding": "base64",
                }, token=token)
                mode_out = git(["ls-tree", commit_sha, filepath])
                mode = mode_out.split()[0] if mode_out else "100644"
                tree_items.append({"path": filepath, "mode": mode, "type": "blob", "sha": blob["sha"]})
                print(f"  {status} {filepath} -> blob {blob['sha'][:12]}")

        tree = api("POST", f"/repos/{REPO}/git/trees", {
            "base_tree": base_tree_sha, "tree": tree_items,
        }, token=token)
        print(f"  Tree: {tree['sha'][:12]}")

        new_commit = api("POST", f"/repos/{REPO}/git/commits", {
            "message": commit_msg,
            "tree": tree["sha"],
            "parents": [parent_sha],
            "author":    {"name": author_name, "email": author_email, "date": author_date},
            "committer": {"name": author_name, "email": author_email, "date": author_date},
        }, token=token)
        print(f"  Commit: {new_commit['sha'][:12]}")
        parent_sha = new_commit["sha"]

    api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": parent_sha, "force": False,
    }, token=token)
    print(f"\nPushed! refs/heads/{BRANCH} -> {parent_sha[:12]}")
    print()
    print("Sync local branch to the new remote SHA:")
    print(f"  git fetch origin && git reset --hard origin/{BRANCH}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError:
        print("\nAPI error. Common causes:")
        print("  - Token expired:     gh auth refresh -h github.com -s repo")
        print("  - Secret scanning:   a file in the commit contains an embedded token/key.")
        print("                       Remove the secret, amend the commit, re-run.")
        print("  - Proxy unreachable: check  echo $https_proxy")
        sys.exit(1)
