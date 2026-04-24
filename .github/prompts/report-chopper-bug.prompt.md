---
mode: agent
---

# Help me file a Chopper bug report

Invoke the **Chopper Domain Companion**.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md), then walk me through filing a high-quality bug report:

1. Ask me for the `.chopper/` bundle from the failing run (or the full command + terminal output if the run never produced one)
2. Extract these facts from the bundle:
   - Chopper version (from `chopper_run.json`)
   - Exit code and failing phase
   - The top offending diagnostic codes (from `diagnostics.json`)
   - A minimal reproducible JSON input (trim down `input_base.json` to the smallest failing case)
3. Classify the issue against [technical_docs/RISKS_AND_PITFALLS.md](../../technical_docs/RISKS_AND_PITFALLS.md) — is this a known pitfall, a new risk, or truly novel?
4. Draft a bug report with: summary, reproduction steps, expected vs actual, artifacts to attach, minimal JSON

Deliverables:

- A ready-to-submit bug report in Markdown
- The minimal JSON reproduction
- A list of audit artifacts I should attach

Do not attempt to fix Chopper's source — surface the bug cleanly so a maintainer can.
