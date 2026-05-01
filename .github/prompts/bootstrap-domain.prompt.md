---
mode: agent
---

# Bootstrap a new Chopper domain

Invoke the **Chopper Domain Companion** in `full-loop` mode.

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md) for the full protocol, then:

1. Ask me for the domain root path
2. Run the Q1–Q5 Discovery Protocol against the path
3. Build the file inventory + classification table and pause for my confirmation
4. If proc-trimming is in scope, build the call-tree trace log and pause again
5. Propose a minimal starter `base.json` — files-only at first, no proc-trim yet
6. Validate it with `python schemas/scripts/validate_jsons.py <domain_root>/`
7. Iterate until the schema passes cleanly

Deliverables I expect back:

- The completed file inventory table
- A minimal `base.json` at `<domain_root>/jsons/base.json`
- Schema validation output showing green
- A shortlist of candidate features to tackle next

Do not run `chopper trim` — dry-run only, and only if I explicitly ask.
