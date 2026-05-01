---
mode: agent
---

# Validate my Chopper JSONs

Invoke the **Chopper Domain Companion** in `analyze-only` mode (no CLI calls to `chopper`).

Read [.github/agents/chopper-domain-companion.agent.md](../agents/chopper-domain-companion.agent.md), then:

1. Ask me for the domain root (or infer from the workspace)
2. Run `python schemas/scripts/validate_jsons.py <domain_root>/`
3. Parse every schema error against the **Schema Error → Fix Mapping** table in the companion card
4. For each finding, show: the offending JSON location, the rule it violates, the exact fix as a JSON patch
5. Run the companion's semantic checks (depends_on ordering, flow_action references, stage-name uniqueness, domain match)

Deliverables:

- Green/red status per JSON file
- A prioritized fix list with concrete patches
- A "ready to run `chopper validate`" go/no-go recommendation

Do not invoke `chopper` itself — schema-only.
