---
mode: agent
---

# Package Chopper bug artifacts from Unix paths

Invoke the **Chopper Domain Companion**.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md), then help me package local evidence for a GitHub bug report directly from VS Code on a Unix host:

1. Ask me for one or more Unix paths to a `.chopper/` directory, a terminal log, a markdown report, or screenshots.
2. Use `python scripts/package_bug_report.py <paths...>` to create a single zip bundle. If I provide an explicit output path, pass `--output`.
3. Summarize exactly which files were bundled and which evidence still needs to be pasted into the issue form as text.
4. If I want to file the issue now, open the GitHub bug form in VS Code and tell me which generated zip to upload.
5. Never claim the upload already happened automatically; GitHub still requires the browser file picker or drag-and-drop step for the final attachment.

Deliverables:

- The generated zip path
- A short inventory of bundled files
- The issue-form fields that still need manual text entry