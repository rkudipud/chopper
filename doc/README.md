# Chopper — End-User Documentation

Three guides aimed at different audiences. Start here instead of `technical_docs/` if you are operating or learning the tool.

| Guide | Audience | What's in it |
|---|---|---|
| **[USER_MANUAL.md](USER_MANUAL.md)** | Domain owners, operators | Installation, CLI subcommands, flags, exit codes, troubleshooting cheatsheet |
| **[BEHAVIOR_GUIDE.md](BEHAVIOR_GUIDE.md)** | JSON authors | How merge rules work, what tracing does, JSON patterns by intent, caveats, BKMs, hacks, FAQ |
| **[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)** | Integrators and contributors | Pipeline phases, module layout, ports & adapters, testing, extension points |

For the full specification and engineering-side documents, see [`../technical_docs/`](../technical_docs/).

For JSON schemas and 11 progressive worked examples, see [`../json_kit/`](../json_kit/). That folder is a standalone authoring kit; Chopper itself consumes the schema files from `json_kit/schemas/` at runtime.
