---
mode: agent
---

# File a Chopper bug report automatically

Invoke the **Chopper Domain Companion**.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md), then file the bug report end to end when the required evidence is available:

1. Ask me for the `.chopper/` bundle from the failing run (or the full command + terminal output if the run never produced one). If I only have Unix filesystem paths to a `.chopper/` directory, log, or markdown report, package them first with `python schemas/scripts/package_bug_report.py <paths...>`.
2. Extract these facts from the bundle:
   - Chopper version (from `chopper_run.json`)
   - Exit code and failing phase
   - The top offending diagnostic codes (from `diagnostics.json`)
   - A minimal reproducible JSON input (trim down `input_base.json` to the smallest failing case)
3. Classify the issue against [technical_docs/RISKS_AND_PITFALLS.md](../../technical_docs/RISKS_AND_PITFALLS.md) — is this a known pitfall, a new risk, or truly novel?
4. Produce the final issue fields and write a payload JSON for `python schemas/scripts/file_bug_report.py --payload <payload> --create`. Include:
   - a short issue title
   - what happened (expected vs actual)
   - steps to reproduce written directly in the field
   - terminal output or a real log excerpt
   - audit artifacts attached or an explanation for why none were produced
   - minimal JSON reproduction or an explanation for why it cannot be shared verbatim
5. Run `python schemas/scripts/file_bug_report.py --payload <payload> --create` so the GitHub issue is created automatically when `gh` is available and authenticated.
6. Treat local rendered output as the default fallback. If automatic issue creation fails, the helper must keep the generated issue body and local evidence bundle and return those paths in the same run.
7. Never emit empty headings, empty fenced code blocks, `_No response_`, or a filesystem path to an external markdown report as a substitute for the issue contents. If something is unavailable, write one short sentence explaining why.
8. Never claim a binary attachment was uploaded automatically. The issue body may be filed automatically, but any local zip bundle still requires the GitHub attachment UI when the raw files are needed.

Deliverables:

- The created GitHub issue URL when automatic filing succeeds
- The rendered issue body path when automatic filing falls back to simple local output
- The minimal JSON reproduction
- The local bundle path, if one was prepared

Do not attempt to fix Chopper's source — surface the bug cleanly so a maintainer can.
