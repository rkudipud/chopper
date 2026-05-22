---
title: GitHub API Push (gh-api-push)
summary: "Help users push local commits via the Git Data API when `git push` is blocked by network filtering. The skill includes a token-free script that attempts to obtain a token from environment or `gh` and clear usage steps."
---

## Purpose

This skill helps developers push local commits to GitHub using the Git Data API (blob → tree → commit → update-ref) when the environment blocks the normal `git push` flow (for example, corporate URL filters that block `git-receive-pack`). It does not embed any secrets.

## Files added by this skill

- `.github/skills/gh-api-push/gh_api_push.py` — the token-free script users run to push commits via the Git Data API.

## How the script obtains credentials

The script tries, in this order:
1. Read `GITHUB_TOKEN` from the environment (recommended for automation).
2. Run `gh auth token` (GitHub CLI) if `gh` is installed and returns a token.

If neither is available the script exits with a short help message explaining how to obtain a personal access token or run `gh auth login` / `gh auth refresh`.

Note: The script does not add SSH keys or request extra scopes. If you need to upload SSH keys programmatically, use `gh auth refresh -s admin:public_key` and `gh ssh-key add` manually (the `admin:public_key` scope is sensitive and should be requested interactively).

## Usage

1. Export a token (recommended):

```bash
export GITHUB_TOKEN="ghp_..."
python3 .github/skills/gh-api-push/gh_api_push.py
```

2. Or rely on `gh` if already authenticated:

```bash
# ensure `gh auth status` is OK
python3 .github/skills/gh-api-push/gh_api_push.py
```

If the script reports missing credentials, follow the short instructions it prints.

## Safety

- The skill stores no tokens in the repository.
- The script uses the GitHub REST API and respects repo permissions.
- The user must ensure the token has `repo` scope for private repositories.

## Location

Script path: `.github/skills/gh-api-push/gh_api_push.py`


## Notes for maintainers

- Keep the script token-free and prefer `GITHUB_TOKEN` or `gh` discovery.
- When updating, validate on a small test repo before recommending to users.
