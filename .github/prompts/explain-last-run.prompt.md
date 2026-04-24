---
mode: agent
---

# Explain my last Chopper run

Invoke the **Chopper Domain Companion**.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md) — especially the "Audit artifacts you must know how to interpret" section — then:

1. Find the most recent `.chopper/` directory in the workspace (or ask me for the path)
2. Read `chopper_run.json` and report: exit code, phase results, wall time
3. Read `diagnostics.json` and group by severity — explain each non-info code against [technical_docs/DIAGNOSTIC_CODES.md](../../technical_docs/DIAGNOSTIC_CODES.md)
4. Read `trim_report.txt` and summarize what physically changed on disk
5. Read `compiled_manifest.json` and flag any surprising `FULL_COPY` / `PROC_TRIM` / `GENERATED` / `DROPPED` decisions
6. Recommend the single next action — JSON edit, re-run, or accept

Deliverables:

- One-paragraph run summary
- Per-diagnostic explanation with a concrete fix
- A single "next action" recommendation
