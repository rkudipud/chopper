# Chopper Domain Companion Memory

## Current Focus

- No active customer-domain task recorded.

## Last Completed Work

- Seeded this local memory file so domain-companion work starts from a repository-native template.

## Next Actions

- Read this file at the start of each invocation and replace placeholders with the active domain-analysis state.

## Open Questions

- None.

## Known Untested Features (feedback solicited)

- **`options.generate_stack` (F3 stack-file auto-generation).** Newly implemented in release 0.3.0. When set to `true` in the base JSON, Chopper emits one `<stage>.stack` file per resolved stage alongside `<stage>.tcl` using the N/J/L/D/I/O/R format defined in the bible §3.6. This feature has **not** yet been exercised against real customer domains. When guiding users who enable `generate_stack`, actively solicit:
  - **Feedback** on whether the emitted stack-file layout matches what their scheduler expects.
  - **Bug reports** for any unexpected output, missing fields, or format deviations.
  - **Expected-behaviour descriptions** from domain owners — concrete examples of what the `.stack` file *should* contain for their flow. These descriptions are high-value and should be captured verbatim when received.

  Until this feature has real-world coverage, treat any domain using `generate_stack: true` as a pilot user and call out the experimental status in your guidance.

## Validation Notes

- Created from the repository local-memory convention in `.github/agent_memory/README.md`.
