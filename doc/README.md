# Chopper — End-User Documentation

Four guides aimed at different audiences. Start here instead of `technical_docs/` if you are operating, integrating, or learning the codebase.

| Guide | Audience | What's in it |
| --- | --- | --- |
| **[USER_MANUAL.md](USER_MANUAL.md)** | Domain owners, operators | Command usage, flags, workflows, exit codes, and troubleshooting |
| **[BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md)** | JSON authors | Merge logic, tracing behavior, authoring patterns, caveats, BKMs, hacks, and FAQ |
| **[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)** | Integrators and contributors | Short architecture map, pipeline summary, ports, diagnostics, and extension boundaries |
| **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** | Engineers onboarding to the code | Deep implementation walkthrough with Mermaid diagrams, service flow, test layout, and code-reading order |

Use them in this order if you are new:

1. Read [USER_MANUAL.md](USER_MANUAL.md) to learn how to run Chopper.
2. Read [BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md) to understand how JSON selections are interpreted.
3. Read [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) for the short architectural map.
4. Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) when you want the actual code-level walkthrough.

For the full specification and engineering-side documents, see [`../technical_docs/`](../technical_docs/).

For JSON schemas and 11 progressive worked examples, see [`../json_kit/`](../json_kit/). That folder is a standalone authoring kit; Chopper itself consumes the schema files from `json_kit/schemas/` at runtime.
