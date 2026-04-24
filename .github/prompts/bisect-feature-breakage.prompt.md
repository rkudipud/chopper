---
mode: agent
---

# Bisect the feature that broke trim

Invoke the **Chopper Domain Companion** in `full-loop` mode.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md) — especially the "Bisect the feature that broke trim" playbook — then:

1. Ask me for the project JSON path and the failing command (`chopper validate` or `chopper trim`)
2. Run the command with **base only** (no features) — record exit code
3. Re-run with features added one at a time, honoring `depends_on` order — record exit code for each run
4. The first run that fails names the offending feature
5. Read its `.chopper/diagnostics.json` for the specific code and explain it against [technical_docs/DIAGNOSTIC_CODES.md](../../technical_docs/DIAGNOSTIC_CODES.md)

Deliverables:

- A table: feature-set → exit code → outcome
- The identified breaking feature
- Root-cause explanation with the offending diagnostic code
- A JSON patch or codebase change to fix the break
