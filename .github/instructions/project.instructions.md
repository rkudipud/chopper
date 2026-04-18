
---
applyTo: '**'
---

# Project Instructions

Authoritative conventions and guardrails for working in this codebase. Read this file at the start of every task. Add new rules here as patterns are discovered; never scatter project-level conventions across ad-hoc comments or other docs.

---

## Diagnostic Codes

### Single Source of Truth

`docs/DIAGNOSTIC_CODES.md` is the **only** file that houses diagnostic codes. It is the single source of truth for every code in the `VE`, `VW`, `VI`, `TW`, `PE`, `PW`, and `PI` families.

- All other documentation and implementation code **must reference codes by their identifier** (e.g., `VE-06`), never by their prose description.
- If a description changes, the identifier stays stable — all cross-references remain accurate automatically.
- No other file may define, duplicate, or restate code metadata such as severity, phase, source, exit behavior, slug, description, or recovery hint.
- Diagnostic code tables outside `docs/DIAGNOSTIC_CODES.md` are not allowed.

### Reference Style (Required Outside the Registry)

When any file outside `docs/DIAGNOSTIC_CODES.md` mentions diagnostics:

- Use the exact code token only (for example: `PE-01`, `PW-11`, `TW-02`).
- Link or refer to the registry using a workspace-relative path: `docs/DIAGNOSTIC_CODES.md`.
- Use section-level references when needed (for example: "see `docs/DIAGNOSTIC_CODES.md`, Parse Warnings").
- Keep wording behavioral and local (for example: "emit `PW-11` in this branch"), not definitional.

Forbidden outside the registry:

- Rewriting what a code means (description, severity, hint, exit code, slug, etc.).
- Recreating code catalogs, mapping tables, or expanded code glossaries.
- Introducing aliases or ad-hoc variants (for example: `TRACE-AMBIG-01`).

### Adding a New Code

1. **Pick the lowest available reserved slot** in the correct `<FAMILY><SEV>` band from the Code Space Summary table in `docs/DIAGNOSTIC_CODES.md`.
2. **Fill in the row** following the exact column structure of the existing table — code, phase, source, exit, description, recovery hint.
3. **Update the Active / Reserved counts** in the Code Space Summary table.
4. **Implement the constant** in `src/chopper/core/diagnostics.py` before any code references it.
5. **Reference it by code only** in any documentation or test assertions.

Do not invent ad-hoc codes or reuse retired slots. Reserved rows exist precisely so new codes have a home — use them in sequence.

### Naming Convention (recap)

Codes follow `<FAMILY><SEV>-<NN>`: family (`V`, `T`, `P`) + severity (`E`, `W`, `I`) + two-digit sequence. Example: `VE-06` = Validation Error #6, `PW-04` = Parse Warning #4.

---

## Editing Conventions

### No Addendums

Never append a change as an addendum at the end of a document. Make the edit **in place**, in the section where the content belongs. If a document is out of date, update it directly — do not accumulate footnotes or trailing corrections.

### Cascading Updates

When content changes in one document, scan for all documents that reference or depend on that content and update them in the same pass. A change is only complete when every related reference is consistent. Leaving supporting documents stale causes misinformation and erodes the single-source-of-truth principle.

This applies to:

- Diagnostic code descriptions (registry → implementation constants → test assertions → docs)
- Architecture decisions (design doc → technical requirements → pitfalls guide)
- CLI flag names or schema fields (spec → help text → user reference manual)

### Targeted, In-Place Edits

Every edit must be made at the correct location in the correct document. Do not make a change in one place and leave related content elsewhere outdated. Always consider the broader impact of a change before committing it.

---

<!-- Add new sections below as project conventions grow. -->