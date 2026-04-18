# Chopper — Future Planned Developments

> **Status:** Living Document  
> **Purpose:** Track potential improvements, enhancements, and deferred work items for future releases  

---

## Parser Enhancements

### FD-01: Quote Context Tracking at Depth > 0 (Extended Analysis)

**Origin:** Final Review Finding F-03

Inside a brace-delimited proc body (depth > 0), Tcl Rule 6 suppresses all substitution processing — meaning `"` characters are literal text and do not create quoted-string contexts. The current parser spec (TCL_PARSER_SPEC.md §3.3) has an implementation clarification that `in_quote` is not toggled inside brace-delimited blocks.

However, there is a subtle edge case at depth 0 where `proc` arguments are being parsed before the body brace opens. Consider:

```tcl
proc foo "arg1 arg2" {
    set x 1
}
```

Here the args word is double-quoted (not brace-delimited). The parser must correctly identify the body opening brace `{` that follows the quoted args, without being confused by any braces that might appear inside the quoted args.

**Future Enhancement:** If real-world domains contain quoted proc argument lists (extremely rare), extend the parser to handle this case. For v1, the spec correctly notes that Chopper only recognizes brace-delimited bodies and logs a WARNING for non-brace bodies.

---


## CLI / UX Enhancements

### FD-06: Interactive Feature Selection TUI

Provide a terminal-based interactive UI for browsing available features, previewing their effects, and composing a project JSON.

**Deferred because:** CLI-first approach is correct for v1. The service-layer and renderer-adapter architecture (TECHNICAL_REQUIREMENTS.md §5) enables this without engine changes.

### FD-07: GUI Client

JSON-over-stdio wire protocol (TECHNICAL_REQUIREMENTS.md §5.2) enables a future GUI. Not implemented in v1 but architecturally enabled.

---


