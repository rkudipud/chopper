---
mode: agent
---

# Why was `<name>` dropped (or kept)?

Invoke the **Chopper Domain Companion**.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md), then:

1. Ask me for the proc name or file path in question, and the `.chopper/` bundle path
2. Search `dependency_graph.json` for the symbol — surface its callers, callees, and reachability
3. Check `compiled_manifest.json` for the file's treatment (`FULL_COPY` / `PROC_TRIM` / `GENERATED` / `DROPPED`)
4. Cross-reference against the input JSONs (`input_base.json` + `input_features/NN_name.json`) to identify which include/exclude rule won
5. Report the R1 merge outcome that produced the decision

Deliverables:

- The exact rule (file + line in the JSON input) that drove the decision
- The call-graph context (reachable / unreachable, from which root)
- If the user wanted a different outcome, the minimal JSON patch to flip it

Remember: trace is **reporting-only**. Procs only survive if they are explicitly in `procedures.include` or live in a `files.include` whole-file.
