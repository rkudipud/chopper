#!/usr/bin/env python3
"""Push local commits to GitHub using the Git Data API (bypasses Fortinet proxy git-receive-pack block).

Credentials (in priority order):
  1. GITHUB_TOKEN or GH_TOKEN environment variable
  2. `gh auth token` via GitHub CLI
If neither is available the script exits with setup instructions.
"""
import subprocess, json, base64, sys, os, urllib.request, urllib.error

REPO = "rkudipud/chopper"
BRANCH = "main"
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "http://proxy-dmz.intel.com:912"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
opener = urllib.request.build_opener(proxy_handler)


def get_token():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok.strip()
    # Try gh CLI in common locations
    for gh in ["gh", "/nfs/site/itools/em64t_SLES15/pkgs/github-cli/2.83.1/bin/gh",
               "/nfs/site/itools/em64t_SLES15/pkgs/github-cli/2.25.1/bin/gh"]:
        try:
            result = subprocess.run([gh, "--version"], capture_output=True)
            if result.returncode == 0:
                tok = subprocess.check_output([gh, "auth", "token"], text=True).strip()
                if tok:
                    return tok
        except FileNotFoundError:
            continue
    return None


TOKEN = get_token()
if not TOKEN:
    print("No GitHub token found.")
    print("Option A: export GITHUB_TOKEN=<your-token> and re-run.")
    print("Option B: run 'gh auth login' then re-run.")
    print("\nTo create a token: https://github.com/settings/tokens")
    print("Required scopes: repo (for private repos) or public_repo (for public repos).")
    sys.exit(2)

def api(method, path, data=None):
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "gh-api-push/1.0",
    })
    try:
        with opener.open(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code} {method} {path}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

def git(args, cwd=REPO_DIR):
    return subprocess.check_output(["git"] + args, cwd=cwd, text=True).strip()

# Get remote HEAD
remote_sha = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")["object"]["sha"]
print(f"Remote HEAD: {remote_sha}")

# Get commits to push (oldest first)
commits_out = git(["log", f"{remote_sha}..HEAD", "--reverse", "--format=%H"])
commit_shas = [s for s in commits_out.splitlines() if s]
print(f"Commits to push: {len(commit_shas)}")
for sha in commit_shas:
    msg = git(["log", "-1", "--format=%s", sha])
    print(f"  {sha[:12]} {msg}")

parent_sha = remote_sha

for commit_sha in commit_shas:
    # Get commit metadata from local git
    author_name  = git(["log", "-1", "--format=%an", commit_sha])
    author_email = git(["log", "-1", "--format=%ae", commit_sha])
    author_date  = git(["log", "-1", "--format=%aI", commit_sha])
    commit_msg   = git(["log", "-1", "--format=%B", commit_sha])

    # Get changed files
    changed = git(["diff-tree", "--no-commit-id", "-r", "--name-status", commit_sha])
    print(f"\nCommit {commit_sha[:12]}: {len(changed.splitlines())} file(s)")

    # Get the parent tree SHA from GitHub
    parent_commit_obj = api("GET", f"/repos/{REPO}/git/commits/{parent_sha}")
    base_tree_sha = parent_commit_obj["tree"]["sha"]

    tree_items = []
    for line in changed.splitlines():
        status, filepath = line.split("\t", 1)
        if status == "D":
            tree_items.append({"path": filepath, "mode": "100644", "type": "blob", "sha": None})
            print(f"  D {filepath}")
        else:
            # Read file content at this commit
            file_content = subprocess.check_output(
                ["git", "show", f"{commit_sha}:{filepath}"], cwd=REPO_DIR
            )
            # Create blob
            blob = api("POST", f"/repos/{REPO}/git/blobs", {
                "content": base64.b64encode(file_content).decode(),
                "encoding": "base64"
            })
            # Determine mode (executable?)
            mode_out = git(["ls-tree", commit_sha, filepath])
            mode = mode_out.split()[0] if mode_out else "100644"
            tree_items.append({"path": filepath, "mode": mode, "type": "blob", "sha": blob["sha"]})
            print(f"  {status} {filepath} -> blob {blob['sha'][:12]}")

    # Create tree
    tree = api("POST", f"/repos/{REPO}/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items
    })
    print(f"  Tree: {tree['sha'][:12]}")

    # Create commit
    new_commit = api("POST", f"/repos/{REPO}/git/commits", {
        "message": commit_msg,
        "tree": tree["sha"],
        "parents": [parent_sha],
        "author": {"name": author_name, "email": author_email, "date": author_date},
        "committer": {"name": author_name, "email": author_email, "date": author_date},
    })
    print(f"  Commit: {new_commit['sha'][:12]}")
    parent_sha = new_commit["sha"]

# Update ref
api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {
    "sha": parent_sha,
    "force": False
})
print(f"\nPushed! refs/heads/{BRANCH} -> {parent_sha[:12]}")
