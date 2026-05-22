# Chopper — Implementation Reference

> **Scope.** Per-module engineering specifications, implementation pitfalls, and the recorded design decisions that shaped both. This document is the working reference for engineers writing or modifying any of Chopper's services. The architecture doc ([ARCHITECTURE.md](ARCHITECTURE.md)) defines the system contract; this doc describes how each module honors that contract in code.

> **What changed in this consolidation.** This file replaces four previous docs that drifted apart over time:
>
> - The Tcl parser engineering spec
> - The technical-risks and implementation-pitfalls ledger (P-01 … P-48 + TC-01 … TC-10)
> - The parser implementation decision log (D-1b-01 … D-1e-03)
> - The future-planned-developments ledger (OOS-01 … OOS-04 + FD-01 … FD-14)
>
> All content is preserved, but it is now organised **by module** rather than by document type, so the spec for a behaviour, the pitfalls that motivated it, and the decisions taken when implementing it sit next to each other. References that previously pointed at one of the four sources have been rewritten to point at the corresponding section of this doc.

## Contents

1. [Parser Module](#1-parser-module) — Tcl parser engineering spec, parser pitfalls (P-01 … P-07, P-32 … P-43, P-46 … P-48), and parser decisions (D-1b-01 … D-1e-03)
2. [Compiler & Tracer Module](#2-compiler--tracer-module) — Merge algorithm and trace expansion (P-08 … P-12, P-41, P-42)
3. [Trimmer Module](#3-trimmer-module) — Backup / rebuild / write contract (P-13, P-15, P-37, P-44)
4. [Validator Module](#4-validator-module) — Pre/post-trim integrity checks (P-16, P-17)
5. [Audit & Diagnostics](#5-audit--diagnostics) — Diagnostic emission and audit-bundle invariants (P-18, P-19)
6. [Backup & Recovery](#6-backup--recovery) — Re-trim semantics (P-20)
7. [Configuration & Paths](#7-configuration--paths) — Path normalization, config-file resolution (P-21, P-22)
8. [CLI & Presentation](#8-cli--presentation) — Dry-run, project JSON path resolution, mutually-exclusive flags, --strict, cleanup (P-23, P-25, P-26, P-27, P-28)
9. [Hook Files](#9-hook-files) — `-use_hooks` discovery-only contract (P-29)
10. [Project JSON](#10-project-json) — Project-mode metadata flow and domain consistency (P-30, P-31)
11. [Testing Strategy](#11-testing-strategy) — Stage gating and edge-case timing (P-24)
12. [Quick Reference](#12-quick-reference-common-mistakes-by-module) — One-table-per-mistake summary
13. [Standalone Risk Items](#13-standalone-risk-items) — TC-06, TC-09 (no dedicated pitfall)
- [Appendix A: Out of Scope (OOS-01 … OOS-04)](#appendix-a-permanently-out-of-scope)
- [Appendix B: Deferred Work (FD-01 … FD-14)](#appendix-b-deferred-work-items)

---

## 1. Parser Module

The parser is the foundation of F2 (proc-level trimming) and transitive tracing. Every rule in this section is derived from the Tcl 8.6 Dodekalogue (the twelve rules that define Tcl syntax and semantics) and adapted for Chopper's static analysis context.

The architecture doc [ARCHITECTURE.md](ARCHITECTURE.md) §5.4 fixes the parser's role in the pipeline (P2). This section is the engineering specification: tokenization rules, proc-detection algorithm, call-extraction rules, the `ProcEntry` output shape, edge cases, the test-fixture catalog, and the design decisions taken during implementation.

**Risk statements covered by this section.**

> **TC-01 — Tcl Proc Boundary Detection.** Chopper must correctly find proc boundaries even with nested braces and namespace constructs. Without a reliable parser, F2 (proc-level trimming) is not viable.
>
> **TC-02 — Canonical Proc Naming.** Resolved to **file + proc name** with namespace-qualified synthesis. Canonical form: `file.tcl::proc_name`. Incorrect canonicalization breaks JSON stability and traceability. JSON authoring uses the short proc name; Chopper resolves the canonical form internally.

---

### 1.1 Purpose

This document specifies the tokenization, parsing, and indexing rules for Chopper's Tcl parser. The parser is the foundation of F2 (proc-level trimming) and transitive tracing. Every rule here is derived from the Tcl 8.6 Dodekalogue (the twelve rules that define Tcl syntax and semantics) and adapted for Chopper's static analysis context.

**Non-goal:** Chopper does not execute or interpret Tcl. It performs structural analysis only — finding proc boundaries, extracting namespace context, and identifying static call references. find the line numbers for the proc definition in the file.

---

---

### 1.2 Input Contract

| Property | Requirement |
|---|---|
| **Input unit** | One Tcl file at a time, identified by domain-relative path |
| **Encoding** | Attempt UTF-8 first; on decode failure, fall back to Latin-1 and log a WARNING diagnostic |
| **Line endings** | Normalize all line endings to `\n` on read (strip `\r`) |
| **Line indexing** | 1-indexed. Line 1 is the first line of the file |
| **Span convention** | Inclusive: `start_line=5, end_line=10` means lines 5, 6, 7, 8, 9, 10 ; internal markers for initial comments, proc body and set_proc_Attributes (if available)|
| **Output** | A list of `ProcEntry` records (see §1.6) |

#### 1.2.1 Public Function Signature

**Canonical public entry point:** `ParserService.run(ctx, files) -> ParseResult`, defined in [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §1.9.2. The service is what the orchestrator and every other service depend on. The `parse_file()` function below is the **pure internal utility** the service wraps — it knows nothing about `ChopperContext`, `DiagnosticSink`, or the filesystem port, and operates on already-decoded text supplied by the service. Implementations and unit tests should target `parse_file()` directly; integration tests and the runner use `ParserService.run()`.

```python
def parse_file(
    file_path: Path,
    text: str,
    on_diagnostic: DiagnosticCollector | None = None,
) -> list[ProcEntry]:
    """Parse a Tcl file and extract proc definitions.

    Args:
        file_path: Domain-relative or absolute path identifying the Tcl file.
        text: Already-decoded file content supplied by ParserService.
        on_diagnostic: Optional callback for emitting Diagnostic records
            (PE-01, PW-01, PW-02, etc. — see technical_docs/DIAGNOSTIC_CODES.md).
            When None, diagnostics are silently discarded.

    Returns:
        List of ProcEntry records. May be empty (not an error).
        Return contract on PE-* diagnostics is specified in
        technical_docs/ARCHITECTURE.md §5.4.1.
    """
```

**Design rationale:** The parser is an internal utility module, not a top-level service endpoint. It returns `list[ProcEntry]` (not a result dataclass) because:

#### 1.2.2 Return-Value Contract on Diagnostics

The architecture doc [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.4.1 is authoritative for the per-file return-value contract. Duplicated here for parser implementers:

| Condition in file | `parse_file()` returns | Diagnostic emitted |
|---|---|---|
| Clean parse, zero procs defined | `[]` (empty list) | — |
| Clean parse, N procs defined | `[ProcEntry, ..., ProcEntry]` (length N) | — |
| Duplicate proc definition in same file | Full list; **last-wins** replaces the earlier entry in-place at the same index | `PE-01 duplicate-proc-definition` (one per collision) |
| Unbalanced braces (depth never returns to 0 or goes negative) | `[]` (empty list) | `PE-02 unbalanced-braces` |
| Two procs collapse to the same short name after namespace stripping | Full list with both entries; F2 short-name lookup becomes ambiguous | `PE-03 ambiguous-short-name` |
| Computed proc name (`proc $n {...}`) | Full list minus the skipped proc | `PW-01 computed-proc-name` |
| UTF-8 decode fails, Latin-1 fallback succeeds | Full list on Latin-1 content | `PW-02 utf8-decode-failure` |
| Non-brace body (`proc foo "..."`) | Full list minus the skipped proc | `PW-03 non-brace-body` |
| `namespace eval` with computed name | Full list minus any procs the computed namespace would have contained | `PW-04 computed-namespace-name` |

**Golden tests assert both the return value and the emitted diagnostic set** for every row above. See [`tests/FIXTURE_CATALOG.md`](../tests/FIXTURE_CATALOG.md) for the fixtures that exercise each row.

---

---

### 1.3 Tokenization Rules

Chopper uses a simplified, brace-aware tokenizer that follows Tcl 8.6 Rules [1], [6], [9], and [10]. The tokenizer does NOT interpret variables, commands, or expressions — it only tracks structural delimiters.

#### 1.3.0 State-Machine Summary

The tokenizer state is the tuple `(brace_depth: int, in_quote: bool, quoted_bracket_depth: int, in_comment: bool, context_stack_top)` where `context_stack_top` is one of `FILE_ROOT | NAMESPACE_EVAL | CONTROL_FLOW | PROC_BODY` (see §1.4.2 for the full context stack). Transitions are per-character within the current logical line; `\\\n` line continuation (§1.3.2) does not reset state. The table below specifies every structural transition; characters not listed are inert and only advance position.

**Tcl Endekas/Dodekalogue Rule 5 (Double quotes), authoritative:** an unescaped `"` at a *word boundary* opens a quoted word **at any brace depth**. Inside the quoted word, `;`, `\n`, whitespace and `}` are LITERAL; only an unescaped `"` at quoted-bracket-depth 0 closes the word. `[...]` inside a quoted word is command substitution (§1.3.3.3); the inner command is parsed as Tcl and any `"` inside the substitution belongs to the inner command, not the outer word. (See this doc Pitfall P-01 for the production bug that motivated this clarification.)

| Current state | Input | Next state | Side effect |
|---|---|---|---|
| `brace_depth=d`, `in_quote=False`, `in_comment=False` | unescaped `{` | `brace_depth=d+1` | If the `{` opens a proc body, push `PROC_BODY` onto context stack. If it opens `namespace eval`, push `NAMESPACE_EVAL` + push the name onto namespace stack. If it opens a control-flow body (`if`, `for`, `foreach`, `while`, `switch`, `catch`, `eval`), push `CONTROL_FLOW`. |
| `brace_depth=d>0`, `in_quote=False`, `in_comment=False` | unescaped `}` | `brace_depth=d-1` | If the new depth matches the `entered_at_depth` of the context-stack top, pop the context. If popping `NAMESPACE_EVAL`, also pop the namespace stack. If popping `PROC_BODY`, finalize the current `ProcEntry` (record `end_line`). |
| any | `\` followed by `\n` | (unchanged) | Log-only; `PW-05 backslash-continuation` on first occurrence in a file. Does **not** reset `in_comment` or `in_quote`. |
| `in_quote=False`, `in_comment=False`, at word boundary, **any `brace_depth`** | unescaped `"` | `in_quote=True`, `quoted_bracket_depth=0` | Open a quoted word per Endekas Rule 5. Applies inside proc bodies, switch arms, control-flow bodies — anywhere a word boundary exists. |
| `in_quote=True`, `quoted_bracket_depth=0` | unescaped `"` | `in_quote=False` | Close the quoted word. Escaped `\"` does not close. |
| `in_quote=True` | unescaped `[` | `quoted_bracket_depth+=1` | Enter command substitution inside the quoted word. |
| `in_quote=True`, `quoted_bracket_depth>0` | unescaped `]` | `quoted_bracket_depth-=1` | Exit one level of command substitution. While `quoted_bracket_depth>0`, `"` is parsed by the inner command, not as the outer word's terminator. |
| `in_quote=True`, `quoted_bracket_depth=0` | `{` / `}` / `;` / `\n` / whitespace | (unchanged) | Literal characters; `brace_depth` unchanged, no command split. |
| `brace_depth=d`, `in_quote=False`, `in_comment=False`, at command position | `#` | `in_comment=True` | Comment extends to end of logical line (respecting `\\\n` continuation). |
| `in_comment=True` | `\n` not preceded by `\` | `in_comment=False` | End of comment line. |
| `in_comment=True` | `{` / `}` | (unchanged) | Inert; `brace_depth` unchanged. |
| any | `[` / `]` (outside `in_quote`) | (unchanged) | Inert for brace tracking. Call-extraction (§5) inspects bracketed tokens separately. |
| `brace_depth<0` at any point | — | (error) | Emit `PE-02 unbalanced-braces`; `parse_file()` returns `[]`. |
| end-of-file with `brace_depth>0` | — | (error) | Emit `PE-02 unbalanced-braces`; `parse_file()` returns `[]`. |

**Order of precedence when multiple conditions would apply on the same character:** `in_comment` beats `in_quote` beats brace tracking. `in_quote=True` suppresses `#` → comment. `\` before any special character escapes it for the purpose of state transitions (escape counting is "odd number of trailing backslashes escapes").

#### 1.3.1 Brace Matching (Tcl Rule 6)

Braces `{` and `}` define word boundaries in Tcl. Chopper must track brace depth accurately.

**Rules:**
1. An unescaped `{` increments brace depth by 1.
2. An unescaped `}` decrements brace depth by 1.
3. A brace preceded by an odd number of consecutive backslashes is **escaped** and does NOT affect depth.
4. Inside braces, no substitutions occur for the *value* of the brace-quoted word (no `$`, `[...]` substitution at this level). However, when the brace-quoted region is later interpreted as Tcl script (e.g. a proc body, an `if`/`while`/`foreach` body, a `namespace eval` body), it is re-parsed as Tcl and Endekas Rule 5 applies inside it — `"` opens a quoted word at the inner depth. Chopper's tokenizer therefore tracks `in_quote` independently of `brace_depth`.
5. The only exception inside braces: backslash-newline (`\` immediately before `\n`) is a line continuation at the parser level. This affects the **line count** but does NOT affect brace depth.
6. Nested braces must balance: `{ { } }` is valid (depth goes 0→1→2→1→0).

**Why this matters:** Proc bodies are brace-delimited. Incorrect brace tracking means incorrect proc boundaries.

#### 1.3.2 Backslash Continuation (Tcl Rule 9)

A backslash `\` immediately before a newline character joins the next line.

**Rules:**
1. When `\` appears immediately before `\n`, the parser treats the next line as a continuation of the current line.
2. Continuation only occurs when the backslash count before `\n` is **odd**.
3. For brace-depth tracking, continuation does NOT change depth — it only affects line numbering.
4. For line counting purposes, each `\n` in the source (including inside continuations) increments the line counter.

**Implementation note:** Do NOT physically join lines. Track them as separate source lines but recognize that a `\` at end-of-line means the logical command continues.

#### 1.3.3 Double Quotes (Tcl Endekas/Dodekalogue Rule 5)

Double-quoted strings `"..."` group content into a single word and enable substitutions (`$var`, `[cmd]`, `\x`) inside that word.

**Authoritative rule:** an unescaped `"` at a *true word boundary* opens a quoted word **at any brace depth**. Chopper treats these prefixes as valid quote-open boundaries: start-of-input, whitespace, `;`, and `[`. Other prefixes (notably `{`, `}`, `]`, or another `"`) do not open a quoted word; the `"` is literal in that position. This is required for Tcl rule-5 correctness and prevents phantom-quote brace desync in brace words (see Pitfall P-01 / P-01a).

**Rules for Chopper:**
1. `"` at a word boundary opens a quoted word regardless of `brace_depth`.
2. Inside a quoted word:
   - `;`, `\n`, whitespace, `{`, `}` are **literal characters**. They do NOT split commands and do NOT change `brace_depth`.
   - `\"` is an escaped literal quote and does NOT close the word.
   - `\<other>` follows ordinary Tcl backslash-escape rules.
   - `[...]` is command substitution. The contents are parsed as Tcl with full rules (including a fresh quote/brace context). Track this with a separate `quoted_bracket_depth` counter so an inner `"` cannot close the outer word until brackets balance.
3. The quoted word ends at the next unescaped `"` encountered while `quoted_bracket_depth == 0`.
4. A genuine unbalanced `{` *inside a string literal* is still a Tcl error, but the file-level brace-depth check at EOF catches it via `PE-02`. The tokenizer does not need to inspect string contents for brace balance.

**Brace-word / adjacent-quote guard (Endekas rules 5 + 6):** quote-open detection must use the boundary whitelist above, not just a single-byte `{` exception. This covers both `"` immediately after `{` (e.g. `set q {"}`, `regexp {".*"} $line`) and multi-quote-pair brace words (e.g. `string map {" " ""}`) where a later `"` follows another `"` and must stay literal. Without this guard, phantom quoted-word state can swallow the closing `}` and produce false `PE-02`. Regression fixtures: [`tests/fixtures/edge_cases/parser_literal_quote_in_braced_word.tcl`](../tests/fixtures/edge_cases/parser_literal_quote_in_braced_word.tcl) and [`tests/fixtures/edge_cases/parser_braced_word_multi_quote_pairs.tcl`](../tests/fixtures/edge_cases/parser_braced_word_multi_quote_pairs.tcl).

##### 1.3.3.1 Pre-Body Quote Rule (Outside Brace-Delimited Blocks)

While the parser is at `brace_depth == 0` scanning the proc name or args specification before the proc body `{` opens, the rules above apply unchanged:
- A word that begins with `"` is a quoted word.
- Inside it, braces and other word-boundary characters are literal.
- The word ends at the next unescaped `"` at `quoted_bracket_depth == 0`.

Example: `proc foo "arg1 {arg2}" { body }` — the `{` inside the quoted args is literal, does not increment `brace_depth`. The body `{` is found after the closing `"`.

##### 1.3.3.2 In-Body Rule (Inside Brace-Delimited Blocks)

Once the parser is inside a brace-delimited block (`brace_depth > 0`) — proc body, `namespace eval` body, control-flow body — the **same** quote rule applies:

- `"` at a word boundary opens a quoted word.
- The quoted word's contents are literal w.r.t. command separation and brace counting.
- `[...]` inside the quoted word is a substitution; track it with `quoted_bracket_depth`.
- `{` and `}` inside the quoted word are **literal** (they do NOT change `brace_depth`).
- The word ends at the matching unescaped `"`.

Example (production pattern): `puts "$intel_info applied; defined by $used"` inside any proc body. The `;` is literal; no command split; no spurious extraction of `defined` as a proc.

**Mnemonic:** Quotes always group. Brace depth and quoted-word state are independent counters.

#### 1.3.4 Comments (Tcl Rule 10)

A `#` character is a comment only when it appears where Tcl expects the first word of a command.

**Rules:**
1. `#` at the start of a line (ignoring leading whitespace) begins a comment.
2. `#` after a semicolon `;` with optional whitespace begins a comment.
3. `#` inside a brace block follows the same rule — it is a comment only in command position.
4. Comment extends to the next unescaped newline.
5. A `\` at end of a comment line continues the comment onto the next line.
6. Comment lines are preserved in line numbering — they do not compress line counts.
7. Braces inside comments DO NOT affect brace depth (comments are inert).

**Critical edge case:** Inside a proc body (which is a brace-delimited block), `#` at command position IS a comment. But the `}` that closes a comment line could be confused with the closing brace of the proc. The parser must NOT count braces inside comments.

#### 1.3.5 Command Substitution (`[...]`) (Tcl Rule 7)

**Rules for Chopper:**
1. Square brackets `[` and `]` denote command substitution.
2. Inside brace-delimited blocks (including proc bodies), `[...]` is NOT executed but is still text.
3. For brace tracking purposes, brackets are irrelevant — only braces matter for proc boundary detection.
4. For **call extraction** (tracing), bracketed expressions like `[helper_proc arg1]` are parsed to extract the proc name (first token after `[`).

---

#### 1.3.6 Tokenizer Implementation Decisions

##### D-1b-01: LBRACE records depth *before* increment; RBRACE records depth *after* decrement

**Context.** A consumer of `Token.brace_depth` needs to know "what depth am I at?" intuitively for both opens and closes. The tokenizer had two equally valid choices: record the depth at the token's position (LBRACE=0, RBRACE=0 for `{}`) or record the depth after the token's effect.

**Decision.** LBRACE records the depth *before* the brace increments it; RBRACE records the depth *after* the brace decrements it. Both end up as the depth of the *enclosing* scope in which the brace sits, which reads correctly for `token.brace_depth == 0` checks on either kind.

**Rationale.** Downstream consumers (NamespaceTracker, proc extractor) test "is this brace at top level?" via `brace_depth == 0`, which should be true for both the opening `{` of a top-level proc and the matching `}`. The spec (§1.3.1) does not dictate which convention to use — it says only that "depth increments on `{` and decrements on `}`".

**Outcome.** Documented in `Token.brace_depth` docstring at [src/chopper/parser/tokenizer.py](../src/chopper/parser/tokenizer.py). Unit-tested in `TestBraces::test_empty_braces` at [tests/unit/parser/test_tokenizer.py](../tests/unit/parser/test_tokenizer.py).

##### D-1b-02: Four devil's-advocate hardening tests — spec-compliant `;` + `#` inside braces

**Context.** A mid-stage review raised the claim that `;` followed by `#` inside a brace-delimited data block would swallow the closing `}` as part of the comment, which would be a spec-violating bug.

**Decision.** The behaviour is **by design** per §1.3.0 state table + §1.3.4 rule 3 + §1.3.3.2. Brace-delimited bodies **are** Tcl scripts (the spec says so explicitly for `proc` bodies, and there is no syntactic distinction between a proc body and any other brace-delimited script). A `;` at any depth terminates the current command and re-establishes command position; a subsequent `#` at command position starts a comment that scans to the next unescaped newline.

**Rationale.** The spec endorses this behaviour via the worked example in §1.3.3.2 ("`set x { a ; # comment\n }` — the `#` activates a comment inside the brace"). Changing it would have required a spec edit; the spec was correct.

**Outcome.** Added 4 hardening tests to [tests/unit/parser/test_tokenizer.py](../tests/unit/parser/test_tokenizer.py) (`test_semicolon_inside_braces_still_emits_token`, `test_comment_after_semicolon_inside_braces_activates`, `test_dangling_backslash_at_eof`, `test_escaped_open_brace_in_word_stays_word`) to document the spec-compliant behaviour and prevent a future "fix" from regressing it.

---



---

### 1.4 Proc Detection

#### 1.4.1 Proc Definition Pattern

The standard Tcl proc definition is:

```
proc <name> <args> <body>
```

Where:
- `proc` is a literal keyword appearing as the first word of a command
- `<name>` is the proc's name (may be namespace-qualified)
- `<args>` is the argument list (typically brace-delimited)
- `<body>` is the proc body (always brace-delimited for Chopper's purposes)

#### 1.4.2 Detection Algorithm

The parser maintains a **context stack** to determine where procs may be recognized. Each entry on the stack records a context type and the brace_depth at which that context was entered.

**Context types:**

| Context Type | Entered When | Procs Recognized Inside? |
|---|---|---|
| `FILE_ROOT` | Always present as stack bottom | **YES** |
| `NAMESPACE_EVAL` | `namespace eval <name> {` encountered | **YES** |
| `CONTROL_FLOW` | `if`, `for`, `foreach`, `while`, `switch`, `catch`, `eval` body `{` encountered | **NO** |
| `PROC_BODY` | Proc body `{` entered | **NO** |

**Detection rule:** A `proc` keyword at command position is recognized as a top-level proc definition **if and only if** the current top-of-stack context type is `FILE_ROOT` or `NAMESPACE_EVAL`.

**Algorithm:**

```
context_stack = [(FILE_ROOT, brace_depth=0)]

For each line in the file:
  1. Check the top of context_stack.
     If top.context_type is CONTROL_FLOW or PROC_BODY:
       - Do NOT recognize `proc` definitions here (debug-level log)
       - Still track brace_depth for closing `}`
       - When brace_depth returns to top.entered_at_depth, pop the stack
       - Continue to next line

  2. If top.context_type is FILE_ROOT or NAMESPACE_EVAL:
     Check if the line matches: ^\s*(proc)\s+(\S+)
     If yes:
       a. Extract the proc name (second word)
       b. Scan forward from the proc name until an unescaped `{`
          is found at the current brace_depth. Everything between
          the proc name and that `{` is the args specification.
          Do NOT parse the args word contents — only locate the
          body opening brace.
       c. The `{` increments brace_depth by 1 — this is the body open
       d. Push (PROC_BODY, brace_depth_before_open) onto context_stack
       e. Track brace_depth line-by-line until it returns to
          brace_depth_before_open → that `}` is the body close
       f. Pop PROC_BODY from context_stack
       g. Record: start_line = line with `proc` keyword
                  end_line   = line with closing `}`
                  body_start_line = line immediately after the opening `{`
                  body_end_line   = line immediately before the closing `}`
       h. Scan ahead from end_line for a DPA block (§1.4.6). If found within
          3 blank lines, record dpa_start_line / dpa_end_line and advance
          the line cursor past the DPA block so the main loop skips it.
       i. Scan backward from start_line for a contiguous comment block (§1.4.7).
          Record comment_start_line / comment_end_line.

  3. If the line matches: ^\s*(namespace)\s+(eval)\s+(\S+)\s*\{
     Push (NAMESPACE_EVAL, current_brace_depth) onto context_stack
     Push the namespace name onto namespace_stack
     When brace_depth returns to entered_at_depth, pop both stacks

  4. If the line matches a control-flow keyword (if, for, foreach,
     foreach_in_collection, while, switch, catch, eval) followed by a body `{`:
     Push (CONTROL_FLOW, current_brace_depth) onto context_stack
     When brace_depth returns to entered_at_depth, pop the stack
     Note: `foreach_in_collection` is a Synopsys EDA iterator — handle
     identically to `foreach`; see §1.7.14 and Pitfall P-36.
```

**Worked example — proc inside `if` inside `namespace eval`:**

```tcl
namespace eval ns {          # line 1: brace_depth 0→1, push NAMESPACE_EVAL
  if { $cond } {             # line 2: brace_depth 1→2→3, push CONTROL_FLOW
    proc foo {} { return 1 } # line 3: top is CONTROL_FLOW → NOT recognized
  }                          # line 4: brace_depth 3→2, pop CONTROL_FLOW
  proc bar {} { return 2 }   # line 5: top is NAMESPACE_EVAL → RECOGNIZED as ns::bar
}                            # line 6: brace_depth 1→0, pop NAMESPACE_EVAL
```

Result: only `bar` is indexed (as `ns::bar`). `foo` is skipped with a debug-level log.

#### 1.4.3 Proc Name Resolution

| Source Pattern | Resolved Name |
|---|---|
| `proc foo {args} {...}` at file root | `foo` |
| `proc ::ns::foo {args} {...}` at file root | `ns::foo` (strip leading `::`) |
| `proc foo {args} {...}` inside `namespace eval ns { ... }` | `ns::foo` |
| `proc foo {args} {...}` inside `namespace eval a { namespace eval b { ... } }` | `a::b::foo` |
| `proc ::abs::foo {args} {...}` inside `namespace eval ns { ... }` | `abs::foo` (absolute overrides namespace context) |
| `proc ${prefix}_foo {args} {...}` | **SKIP** — log WARNING (computed name, unresolvable) |

##### 1.4.3.1 Canonical-Name Test Vectors

The architecture doc [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.4.1 fixes the canonical-name format as `"<domain-relative-posix-path>::<qualified_name>"`. The table below is the authoritative test-vector set every parser implementation must match. Inputs are `(file_path, namespace_stack_at_proc_line, proc_short_name)`; outputs are the resulting `canonical_name` used as the key in `ParseResult.index`.

| `file_path` | `namespace_stack` | `proc_short_name` | `canonical_name` | Notes |
|---|---|---|---|---|
| `utils.tcl` | `[]` | `helper` | `utils.tcl::helper` | File root, bare name |
| `utils.tcl` | `["a"]` | `helper` | `utils.tcl::a::helper` | Single-level namespace |
| `utils.tcl` | `["a", "b"]` | `helper` | `utils.tcl::a::b::helper` | Nested namespace |
| `utils.tcl` | `[]` | `::abs::x` | `utils.tcl::abs::x` | Absolute name at file root (leading `::` stripped) |
| `utils.tcl` | `["a"]` | `::abs::x` | `utils.tcl::abs::x` | Absolute name overrides active namespace |
| `utils.tcl` | `["a", "b"]` | `::abs::c::x` | `utils.tcl::abs::c::x` | Absolute name overrides nested namespace |
| `common/helpers.tcl` | `[]` | `foo` | `common/helpers.tcl::foo` | Subdirectory file, bare name |
| `common/helpers.tcl` | `["ns"]` | `foo` | `common/helpers.tcl::ns::foo` | Subdirectory + namespace |
| `sub/dir/f.tcl` | `["p", "q"]` | `r` | `sub/dir/f.tcl::p::q::r` | Deep path + nested namespace |
| `utils.tcl` | `[]` | `${prefix}_foo` | **(not indexed)** | Emits `PW-01 computed-proc-name`; proc is skipped entirely |

**Enforcement.** `ParseResult` validates this format at construction. `tests/unit/parser/test_canonical_name.py` must parametrize across every row above. See also architecture doc §5.4.1 (the authoritative registry) and this doc TC-02.

##### 1.4.3.2 Source / `iproc_source` Edges

`source` and `iproc_source` tokens encountered in proc bodies become **edges** in the dependency graph, identical in type to proc-call edges. They are **reporting-only**:

- They never cause any file to be copied into the trimmed domain.
- They never cause any proc to survive trim.
- The sourced file's survival requires an explicit `files.include` entry; a sourced proc's survival requires an explicit `procedures.include` entry.
- A `source` referencing a file that did not survive trim emits `VW-06 source-file-removed` in P6.

See architecture doc §5.4 R3 (source-edge survival effect) and §3.4 (hook semantics) for the authoritative contract.

#### 1.4.4 Where Procs Are Recognized

| Context | Proc Recognized? | Rationale |
|---|---|---|
| File top level (depth 0) | **YES** | Standard proc definition location |
| Inside `namespace eval <name> { ... }` | **YES** | Procs inherit namespace context |
| Inside nested `namespace eval` blocks | **YES** | Multi-level namespace nesting |
| Inside `if { ... }` block | **NO** | Conditional definition — too dynamic |
| Inside `for`, `foreach`, `while` block | **NO** | Loop-based definition — too dynamic |
| Inside another `proc` body | **NO** | Nested proc — not a reliable top-level definition |
| Inside `catch { ... }` block | **NO** | Error-handling context — too dynamic |
| Inside `eval { ... }` block | **NO** | Dynamic evaluation — not statically analyzable |

**Rule:** Only procs at file top-level or inside `namespace eval` blocks are indexed. All other contexts are ignored with a debug-level log message.

**Call extraction scope:** Call extraction (§5) applies **only** to procs that are recognized and indexed per this table. Bodies of unrecognized procs (defined inside `if`, `for`, `catch`, etc.) are NOT searched for calls and are NOT included in the traced dependency graph. A debug-level log is emitted for each skipped unrecognized proc definition.

#### 1.4.5 Namespace Eval Detection

```
namespace eval <name> { <body> }
```

**Rules:**
1. `namespace` must be the first word of a command (at command position).
2. `eval` must be the second word.
3. `<name>` is the namespace name (third word).
4. `<body>` is brace-delimited.
5. Nesting is tracked: inside `namespace eval a { namespace eval b { ... } }`, the active namespace path is `a::b`.
6. Multiple `namespace eval` blocks for the same namespace in one file are supported — each contributes procs to that namespace.
7. `namespace eval` with a computed name (contains `$`) is logged as a WARNING and its body is NOT parsed for procs.

##### 1.4.5.1 Namespace Stack Pop Timing — Worked Example

The namespace stack and context stack interact through brace_depth transitions. Here is a concrete trace for two sequential `namespace eval` blocks:

```tcl
# Line 1: (file start)
namespace eval a {            # Line 2
    proc p1 {} { return 1 }   # Line 3
}                              # Line 4
                               # Line 5 (blank)
namespace eval b {            # Line 6
    proc p2 {} { return 2 }   # Line 7
}                              # Line 8
```

| Line | Token | brace_depth | namespace_stack | context_stack top | Action |
|------|-------|-------------|-----------------|-------------------|--------|
| 1 | (start of file) | 0 | `[]` | FILE_ROOT | — |
| 2 | `namespace eval a {` | 0→1 | `["a"]` | NAMESPACE_EVAL(entered@0) | Push NS + context |
| 3 | `proc p1 {} { return 1 }` | 1→2→1 | `["a"]` | NAMESPACE_EVAL | **Recognized:** `a::p1` |
| 4 | `}` | 1→0 | `[]` | FILE_ROOT | **Pop:** depth returned to 0 → pop NAMESPACE_EVAL, pop `"a"` from namespace_stack |
| 5 | (blank) | 0 | `[]` | FILE_ROOT | — |
| 6 | `namespace eval b {` | 0→1 | `["b"]` | NAMESPACE_EVAL(entered@0) | Push NS + context |
| 7 | `proc p2 {} { return 2 }` | 1→2→1 | `["b"]` | NAMESPACE_EVAL | **Recognized:** `b::p2` |
| 8 | `}` | 1→0 | `[]` | FILE_ROOT | **Pop:** depth returned to 0 → pop NAMESPACE_EVAL, pop `"b"` from namespace_stack |

**Result:** `p1.qualified_name = "a::p1"`, `p2.qualified_name = "b::p2"`. The namespace context resets completely between blocks — `p2` is NOT in namespace `a`.

**Test fixture:** `parser_namespace_reset_after_block.tcl` (Fixture 7 in FIXTURE_CATALOG.md) must verify this behavior.

---

#### 1.4.6 define_proc_attributes (DPA) Detection

In Intel/Synopsys VLSI EDA codebases, virtually every user proc is immediately followed by a `define_proc_attributes` (or `define_proc_arguments`) block — a Synopsys Tcl convention for annotating proc metadata and argument specifications. In production files like `default_fm_procs.tcl`, this pattern appears on **100% of proc definitions**:

```tcl
proc read_libs {} {
    ...
}
define_proc_attributes read_libs \
   -info "To read Synopsys .db designs or technology libraries for LP and Non-LP runs"
```

**Detection rules:**

1. After recording the proc's closing `}` at `end_line`, peek ahead.
2. Skip blank lines only (up to 3). Do NOT skip comment lines — a comment between `}` and the DPA line breaks the association.
3. If the next non-blank line matches `^\s*define_proc_(attributes|arguments)\s+`:
   a. Extract the proc name using the algorithm below.
   b. Validate: the extracted DPA name must match `qualified_name` of the proc just closed. Mismatch → emit `PW-11` and do NOT associate.
    c. Collect the full physical DPA block. Continue while either condition holds:
        - the current physical line ends with an unescaped `\`; or
        - the DPA command has an open brace-delimited payload (for example `-define_args { ... }`) whose outer brace has not yet closed.
        In production Synopsys files the command often uses `\` on the keyword and `-info` lines, then relies on brace balance alone for the interior `-define_args` rows. A continuation-only scan truncates `dpa_end_line` and leaves orphaned metadata lines behind after trim.
   d. Record `dpa_start_line` and `dpa_end_line` on the `ProcEntry`.
   e. **Cursor advance after DPA block.** After recording the DPA block, the main-loop line cursor must be advanced past **all physical source lines** consumed by the block — including every backslash-continuation line. Each `\<newline>` pair is one physical source line and must increment the cursor by 1. Advancing by logical lines instead of physical lines causes an off-by-one error in `start_line` for every subsequent proc in the file. In production EDA files (e.g., `default_fm_procs.tcl`) every proc has a multi-line DPA block with continuation lines, so this error is systematic — all proc spans after the first DPA are wrong if step (e) is omitted.
4. No DPA found within the lookahead window → `dpa_start_line = dpa_end_line = None`.

**DPA proc name extraction.** Per the Tcl `define_proc_attributes` calling convention (Synopsys SDC/PT), the proc name is **the first whitespace-delimited token after the keyword** — independent of how many `-flag value` pairs follow, how those values are brace-quoted, or how many physical lines the call spans via `\`-continuation. Earlier revisions of this spec attempted a regex-based "strip known flags" walk; in production that walk could not balance nested `{…}` arg descriptors and concatenated parts of the option list onto the name, producing false `PW-11` plus `PI-04` diagnostics on every DPA block with multi-line `-define_args` (see this doc Pitfall P-40 and bug report `PW-11_PI-04_dpa_line_continuation_misparse.md`). The correct, simple implementation follows:

```python
import re

_DPA_KEYWORD_RE = re.compile(r"^\s*define_proc_(attributes|arguments)\s+")

def extract_dpa_proc_name(joined_line: str) -> str:
    """Extract the proc name from a (possibly continuation-joined) DPA line.

    Tcl convention: `define_proc_(attributes|arguments) <proc_name> ?<options>...?`
    The name is the first whitespace-delimited token after the keyword. Nothing else
    in the option list — regardless of nested braces, quotes, or how many physical
    lines it spans — contributes to the name.
    """
    text = joined_line.rstrip("\r\n").rstrip("\\").rstrip()
    text = _DPA_KEYWORD_RE.sub("", text, count=1)
    if not text:
        return ""
    name = text.split(None, 1)[0]
    return name[2:] if name.startswith("::") else name
```

**Implementation requirement:** the orphan-DPA `PI-04` message detail must also strip a trailing `\r\n` and any trailing `\` so the user-facing diagnostic does not end on a stray continuation backslash.

**New diagnostic codes for DPA:**

| Code | Severity | When Emitted |
|------|----------|--------------|
| `PW-11` | WARNING | DPA proc name does not match the preceding proc's `qualified_name` |
| `PI-04` | INFO | `define_proc_attributes` found with no associated preceding proc in the file |

**Why it matters:** The trimmer must atomically drop the DPA block together with its proc when excluded, and keep both when included. Without DPA span tracking, trimmed files contain orphaned `define_proc_attributes` metadata that confuse downstream Synopsys tooling.

---

#### 1.4.7 Structured Doc-Comment Block Detection

In Intel/Synopsys EDA Tcl files, proc definitions are preceded by a structured banner comment block. This pattern is present on **100% of procs** in `default_fm_procs.tcl`. The banner can have any number of `#field: value` lines — the backward scan is field-agnostic:

```tcl
########################################################################
#proc       : del_seq_rpt
#purpose    : proc called in fevlite to dump out del_seq.xml
#usage      : del_seq_rpt design
#Owner      : global various
#BU         : global
#CTH release: global
#HSD        : global
########################################################################
proc del_seq_rpt { design } {
```

**Detection rules:**

1. When a `proc` keyword is found at `start_line`, scan backward through contiguous comment-only lines.
2. A line qualifies if it matches `^\s*#` (comment line, regardless of content).
3. Stop scanning backward at a blank line or any non-comment line.
4. Record `comment_start_line` (earliest comment line found) and `comment_end_line = start_line - 1`.
5. No preceding comment → `comment_start_line = comment_end_line = None`.

**Constraint:** Braces inside comment lines are completely inert (Pitfall P-07). The backward scan runs on already-parsed line data and does not affect the forward brace-tracking state machine.

**Why it matters:** The trimmer must drop the comment banner together with its associated proc (SNORT sticky-bit concept adapted to Chopper). Without comment span tracking, trimmed output leaves orphaned `########` banner blocks floating between kept procs.

---

#### 1.4.8 NamespaceTracker Implementation Decisions

##### D-1c-01: Sticky control-flow flag — persists until command terminator

**Context.** Control-flow commands routinely take multiple brace-delimited words on a single command: `if {cond} {body}`, `foreach v {list} {body}`, `while {cond} {body}`. The initial implementation classified only the **first** brace after a control-flow keyword as `CONTROL_FLOW` and reverted to default (`OTHER`) for subsequent braces in the same command, which caused the body brace of `if {cond} {body}` to land as `OTHER` and allow spurious proc recognition inside the `if` body.

**Decision.** Introduce a sticky `_in_control_flow_command` boolean on `NamespaceTracker`. Set it on any control-flow-keyword WORD at command position. Clear it on the next `NEWLINE`, `SEMICOLON`, or `COMMENT`. Every `LBRACE` while the flag is true produces a `CONTROL_FLOW` frame, regardless of how many brace words the command contains.

**Rationale.** The spec's §1.4.2 table lists `if`/`foreach`/`while`/`switch`/`catch`/`eval`/`for` as commands whose body braces push `CONTROL_FLOW`. The spec does not prescribe mechanism — only outcome. Sticky flag is the simplest mechanism that produces the right outcome for all variants.

**Outcome.** `_in_control_flow_command` field on [src/chopper/parser/namespace_tracker.py](../src/chopper/parser/namespace_tracker.py). Tested parametrically in `TestControlFlow::test_control_flow_keyword_pushes_context` at [tests/unit/parser/test_namespace_tracker.py](../tests/unit/parser/test_namespace_tracker.py).

##### D-1c-02: Computed-namespace body is `OTHER`, not `NAMESPACE_EVAL`, and does not push onto the namespace stack

**Context.** §1.4.5 rule 7 mandates that `namespace eval $var { ... }` emits `PW-04` and does not parse the body for procs. The body frame's kind was initially set to `NAMESPACE_EVAL` with a synthetic namespace name, which caused nested `namespace eval` statements inside it to be qualified against a computed parent, producing nonsense qualified names.

**Decision.** Push `ContextKind.OTHER` for the body frame (not `NAMESPACE_EVAL`), and do **not** push anything onto the namespace stack. `can_define_proc()` returns `False` for `OTHER`, which is exactly what the spec requires.

**Rationale.** "Do not parse the body for procs" is stronger than "procs do not get the computed-name prefix". Using `OTHER` closes the whole scope to proc recognition, consistent with the spec's intent.

**Outcome.** Implemented in `_check_namespace_eval` at [src/chopper/parser/namespace_tracker.py](../src/chopper/parser/namespace_tracker.py). Tested in `TestNamespaceEval::test_computed_namespace_name_emits_diagnostic` and `test_computed_namespace_with_brackets` at [tests/unit/parser/test_namespace_tracker.py](../tests/unit/parser/test_namespace_tracker.py).

---



#### 1.4.9 ProcExtractor Implementation Decisions

##### D-1d-01: Early PW-01 guard *before* running layout scan

**Context.** For `proc ${prefix}_foo {} { body }`, the initial implementation let `_scan_proc_layout` run — which tried to classify `${prefix}_foo` as the name word, `{}` as the args word, and the next quoted/plain word as a non-brace body. The result was `PW-03 non-brace-body` on a proc that should have produced `PW-01 computed-proc-name`.

**Decision.** Add `_peek_name_token` helper that returns the name WORD following `proc`. Before calling `_scan_proc_layout`, check the peeked name with `_is_computed_name`. If computed, emit `PW-01` immediately, advance past the `proc` keyword, and skip layout scanning for this definition.

**Rationale.** The spec (§1.4.3) is clear that computed names drop the proc from the index with `PW-01`; the layout-level fallback (`PW-03`) is for a genuinely malformed body shape. Distinguishing at the right level means the diagnostic the user sees reflects the real problem.

**Outcome.** `_peek_name_token` helper + guard in `extract_procs` main loop at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py). Tested in `TestDiagnostics::test_computed_proc_name_pw01` and `test_computed_proc_name_with_bracket` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

##### D-1d-02: Duplicate detection keeps LAST definition; emits one PE-01 at the last line

**Context.** §1.6.3 invariant 4 says "two procs with the same short_name in one file → emit `PE-01`; the last definition wins in the index". Implementation needed to decide (a) how many diagnostics to emit per duplicate group, (b) which line number to attach, and (c) which entry survives.

**Decision.** One `PE-01` per duplicate *group* (not per occurrence). The diagnostic's `line_no` is the **last** definition's `start_line` — the one that survives in the index, so the user is pointed at the authoritative entry. The detail string records both the first and last line numbers for disambiguation.

**Rationale.** Multi-emission (one per duplicate) would produce `N-1` diagnostics for `N` duplicates — noise. Attaching the first line's number would point at the dead entry. Attaching the last ties the diagnostic to the row that actually made it into the final parse result.

**Outcome.** `_deduplicate_short_names` at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py). Tested in `TestDiagnostics::test_duplicate_proc_pe01` and `TestProcEntryInvariants::test_dedupe_diag_unique_per_short` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

##### D-1d-03: DPA blank-line window is source-relative, not namespace-aware

**Context.** §1.4.6 permits up to 3 blank lines between a `proc` close and its `define_proc_attributes` block. A mid-stage test failed because a DPA placed **after** the closing `}` of the enclosing namespace was not associated with its proc — the `}` line broke the 3-blank-line window.

**Decision.** Do **not** make the DPA scan namespace-aware. The 3-blank-line window is measured in source-order lines; any non-blank non-DPA line (including a namespace-closing `}`) breaks the association. Relocate problematic DPA blocks inside the enclosing namespace block.

**Rationale.** The spec (§1.4.6) specifies "up to 3 blank lines" — it does not list "namespace close brace" as a permitted interruption. Making the parser namespace-aware here would let DPAs attach across namespace boundaries, which is not what the spec says. The correct fix is authoring the DPA inside the namespace block, and that is how the test fixture is now structured.

**Outcome.** Test fixture updated to place DPA inside the namespace block. `_scan_dpa` at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py) unchanged (simple line-based scan). Tested in `TestDPA::test_dpa_matches_namespaced_proc` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

---



---

### 1.5 Call Extraction (For Tracing)

Call extraction identifies proc calls within a proc body for transitive dependency tracing.

#### 1.5.1 What Chopper Extracts

From each proc body, Chopper extracts:

| Pattern | Example | Extracted |
|---|---|---|
| Direct proc call (first word of command) | `helper_proc arg1 arg2` | `helper_proc` |
| Bracketed proc call | `[helper_proc arg1]` | `helper_proc` |
| Namespace-qualified call | `::ns::helper arg1` | `ns::helper` |
| Call after semicolon | `set x 1; helper_proc` | `helper_proc` |
| Call inside control structures | `if {$cond} { helper_proc }` | `helper_proc` |

#### 1.5.2 What Chopper Does NOT Extract

| Pattern | Example | Reason |
|---|---|---|
| Variable-based call | `$cmd arg1 arg2` | Dynamic dispatch — unresolvable |
| Eval-based call | `eval "helper_proc arg1"` | Eval content is a string — unresolvable |
| Uplevel-based call | `uplevel 1 helper_proc` | Caller context — unresolvable |
| String in quotes | `set x "helper_proc"` | Data, not a call |
| Interp alias | `interp alias {} foo {} bar` | Dynamic alias — unresolvable |
| Apply lambda | `apply {args { helper_proc }}` | Lambda body — too dynamic |
| Name in log string | `iproc_msg -info "read_libs invoked"` | String arg to log proc — proc name is data |
| Name in print label | `echo "read_libs : done"` | Print label position — data, not a call |
| Proc name as option-flag arg | `set_app_var search_path ""` | Argument to a `-flag` option |
| EDA vendor command | `report_failing_points`, `read_verilog`, `set_top` | Synopsys/Cadence built-in — not a user proc |

All unresolvable patterns produce structured diagnostics with reason codes.

#### 1.5.3 Call Extraction Algorithm

**Input contract — hybrid token-stream + regex filter (do NOT regex raw text).**
Call extraction (`call_extractor_body.py`) consumes the **already-tokenized command-position token stream** produced by `tokenizer.py`, filtered to tokens whose context-stack top is `PROC_BODY`. Comments, quoted strings, and brace-escaped bodies are already suppressed by tokenizer state flags — the call extractor never re-scans the raw file text for calls.

Within each command-position token, regex is permitted (and encouraged) for the *downstream* classification work: identifying the shape of the first word (bare vs `::`-qualified vs dynamic), applying the SNORT-derived 4-level suppression cascade in §1.5.7, and extracting DPA proc-name arguments. SNORT's `_IsProcFoundInLine()` has been proven on Intel EDA codebases for 15+ years and its regex patterns are reused verbatim inside this layer. The invariant is only this: **regex operates on token values, never on raw file lines.** Using raw-line regex re-introduces the false-positive classes that the tokenizer already eliminated (quoted strings, comments, nested bodies).

```
For each WORD token t in tokens[body_lbrace_idx + 1 : body_rbrace_idx]:
  1. If t.at_command_position is True — t is a first-word candidate:
     a. If t.value in {"source", "iproc_source"} — extract the literal path argument
        via flag-aware scan (§1.5.5) and append to source_refs. Mark the flag/path
        token indices as consumed so they are not re-scanned as calls below.
     b. Else apply the §1.5.7 suppression cascade. If not suppressed, classify t.value
        against the first-word regex (bare / ::-qualified), reject dynamic names
        (contains `$`, starts with `[`), reject TCL_BUILTINS, and add the canonical
        form (leading `::` stripped) to calls.
  2. Whether t was first-word or not, and whether or not it was suppressed, if t is
     a WORD token not marked consumed, regex-scan t.value for `\[<name>` embedded
     bracket calls. Each match's first word is classified via the same path as 1b
     and added to calls when it passes. This uniformly handles §1.5.3 step 4 for free
     (non-cmd) arg tokens AND §1.5.7 Level 3's "embedded [real_call] inside a log
     string" exception.
  3. NEVER extract second-or-later tokens of a command as call candidates. The DPA
     proc name in `define_proc_attributes <name> ...` is the canonical trap — see
     pitfall P-35. Suppression at step 1b on `define_proc_attributes`,
     `set_app_var`, `set`, `info`, etc. is achieved by those first words being
     members of TCL_BUILTINS (so step 1b's classifier returns None) or LOG_PROC_NAMES
     (so §1.5.7 suppresses), plus the walk never reads their argument tokens as
     first-word candidates because `Token.at_command_position` is False there.

At the end, return (tuple(sorted(calls)), tuple(source_refs)). `calls` is
deduplicated and lex-sorted (§1.6.1 invariant 5); `source_refs` preserves source
order without dedup (§1.6.1 invariant 6).
```

**Why this ordering — and why there is no explicit "recurse into control-flow body" step.** The tokenizer eliminates ~90% of false positives structurally (quotes, comments, brace bodies); the SNORT suppression cascade eliminates the remaining content-dependent false positives (log-string mentions, option-flag arguments, vendor commands). Running regex first on raw lines inverts this and recreates the exact class of bugs SNORT spent 15 years fixing.

Control-structure bodies (`if`, `foreach`, `foreach_in_collection`, `while`, `switch`, `catch`, `try`) do **not** need an explicit recursion step. The tokenizer re-establishes `at_command_position == True` at every brace-depth transition — the first WORD after a `NEWLINE` or `{`-transition inside any body is automatically a command-position token, regardless of how deeply nested. The flat body walk above therefore visits every in-body command without recursion, which also eliminates the stack-overflow risk noted in the original phrasing and removes an entire class of "skip-to-command-boundary" bugs where a top-level scan would fast-forward past control-flow body contents. See this doc entry **D-1e-01** for the incident and resolution.

##### 1.5.3.1 Skip-Index Pre-Pass (Opaque Commands & `switch` Pattern Labels)

Before the main walk above runs, `call_extractor_structural` performs a structural pre-pass that builds a `skip_indices: set[int]` of tokens to be excluded from BOTH command-position classification AND embedded-bracket regex scanning. This pre-pass enforces three Tcl semantics that the tokenizer cannot determine on its own (because the tokenizer does not know what command name a brace-quoted argument belongs to):

**(a) Opaque-brace commands** — `regexp`, `regsub`, `exec`, `glob`, `string match`. When any of these names appears at command position (either at `at_command_position == True` from the tokenizer OR as the first WORD after an `LBRACE` token at the range's enclosing depth — see §1.5.3.0.2 below), every `LBRACE…RBRACE` token range that constitutes a *value argument* to that command is marked entirely as `skip`. This prevents regex character classes (`{[A-Za-z_]+}`), regex alternations (`{Warning|Error|Fatal}`), `exec grep -P {…}` patterns, and glob patterns from being mis-extracted as proc calls. Reference: this doc Pitfall P-38; fixture `tests/fixtures/bug_reports/regex_literals.tcl`.

**(b) `switch` pattern labels** — for `switch ?-options? string {pattern body ?pattern body…?}`, the body's *odd-indexed* WORD tokens are pattern literals (not commands) and must be marked `skip`. A body of `-` is a fall-through marker. Bodies (the `{…}` immediately following each pattern) are NOT marked `skip` — code inside them is real Tcl and is walked normally. Reference: this doc Pitfall P-39; fixture `tests/fixtures/bug_reports/switch_patterns.tcl`.

**(c) Code-block recursion** — for `if`, `elseif`, `else`, `while`, `for`, `foreach`, `foreach_in_collection`, `catch`, `try`, `eval`, `uplevel`, `namespace eval`, `expr`, the pre-pass recurses into each `{…}` body argument and re-runs (a)/(b) at the inner depth. Without this, an opaque command nested inside `if {[catch {exec grep -P {…}}]}` would be reached only by the main walk (which does not apply rule (a)) and produce false positives. The recursion descends with the heuristic that the first WORD inside any code-block LBRACE is at command position, with subsequent command positions reset on NEWLINE / SEMICOLON at that depth.

**Implementation:** `call_extractor_structural.compute_skip_indices(tokens)` returns the union skip set; `call_extractor_body.extract_body_refs` consults it before classifying any WORD as a call, and bracket substitutions inside skipped ranges are themselves skipped. Public suppression sets live in `call_extractor_constants.py`. The pre-pass also walks `[…]` bracket substitutions so that, e.g., `[regexp {…} $s]` inside a regular command argument is also opaque.

##### 1.5.3.2 Why First-WORD-After-LBRACE Heuristic Is Needed

The tokenizer flags `at_command_position` only at file/proc-body command boundaries it can detect from the surface stream. It does NOT flag the first WORD inside an arbitrary `{…}` argument as cmd-pos, because at the time of tokenisation the tokenizer cannot know whether that brace is a code body (`if {…}`) or a value (`set x {a b c}`). The pre-pass resolves this ambiguity by command name: only when the enclosing command name is in `_CODE_BRACE_COMMANDS` does it descend into the body and treat its first WORD as cmd-position.


#### 1.5.4 Deterministic Proc Name Resolution Contract

Call extraction produces textual proc-call tokens. The tracer resolves those tokens using the caller proc's `namespace_path` and the following deterministic v1 contract.

**Resolution order:**

1. **Absolute qualified call** — token starts with `::`
    - Example: `::signoff::helper`
    - Candidate list: `signoff::helper` only

2. **Relative qualified call** — token contains `::` but does not start with `::`
    - Example from caller namespace `flow::setup`: `signoff::helper`
    - Candidate list: `flow::setup::signoff::helper`, then `signoff::helper`

3. **Bare call** — token contains no `::`
    - Example from caller namespace `flow::setup`: `helper`
    - Candidate list: `flow::setup::helper`, then `helper`

**Matching contract:**

1. Evaluate candidate qualified names in order.
2. For a given candidate qualified name, search the selected-domain proc index for canonical procs whose `qualified_name` exactly matches that candidate.
3. If exactly one canonical proc matches, resolve the call to that proc and stop.
4. If more than one canonical proc matches the same candidate qualified name, emit `TW-01` and stop unresolved.
5. If no candidate qualified name resolves inside the selected domain, emit `TW-02` and stop unresolved.

**Out of scope for v1:**

- `namespace import`
- command path lookup
- `namespace unknown`
- runtime aliasing / `interp alias`
- runtime redefinition order across sourced files

These are not guessed. Dynamic or syntactically unresolvable call forms still emit `TW-03`.

#### 1.5.5 Source/iproc_source Extraction

File dependencies are extracted separately from proc calls:

| Pattern | Extraction |
|---|---|
| `source <literal_path>` | File dependency on `<literal_path>` |
| `iproc_source -file <literal_path>` | File dependency |
| `iproc_source -file <path> -optional` | Optional file dependency |
| `iproc_source -file <path> -required` | Required file dependency |
| `iproc_source -file <path> -use_hooks` | File dependency + hook-file discovery only; hook files must be explicitly listed in JSON to be copied |
| `iproc_source -file <path> -quiet` | File dependency (quiet is flow-level, not Chopper-level) |
| `source $var` or `iproc_source -file $var` | Unresolvable — log WARNING |
| `source -echo -verbose <path>` | File dependency (strip option flags first, then extract path token) |

---

#### 1.5.6 Trace Diagnostic and Call-Tree Alignment Contract

Parser extraction, tracer resolution, and architecture artifacts must share one diagnostic and edge vocabulary.

**Trace warning mapping (from `technical_docs/DIAGNOSTIC_CODES.md`):**

| Scenario | Code |
|---|---|
| Ambiguous proc match after namespace resolution | `TW-01` |
| No in-domain match after namespace resolution (external/cross-domain) | `TW-02` |
| Dynamic or syntactically unresolvable call form (`$cmd`, `eval`, `uplevel`) | `TW-03` |
| Cycle in resolved proc call graph | `TW-04` |

**Division of responsibility:**

- Parser emits candidate call tokens and file-dependency candidates with line context.
- Tracer resolves candidates to canonical in-domain procs and emits `TW-*` warnings when unresolved/ambiguous/dynamic/cyclic.
- Compiler writes resolved results into `dependency_graph.json` and `trim_report.json`.

**Shared edge record shape (for `dependency_graph.json`):**

| Field | Meaning |
|---|---|
| `edge_type` | `proc_call`, `source`, or `iproc_source` |
| `from` | Caller canonical proc or source-file context |
| `to` | Resolved callee canonical proc or file path |
| `status` | `resolved`, `ambiguous`, `unresolved`, or `dynamic` |
| `diagnostic_code` | Optional `TW-*` code for warning edges |
| `line` | Source line where the edge was discovered |

**Structured log event pattern (optional JSON lines):**

```json
{"phase":"trace","event":"edge_resolved","edge_type":"proc_call","from":"a.tcl::p1","to":"b.tcl::p2","line":42}
{"phase":"trace","event":"edge_unresolved","edge_type":"proc_call","from":"a.tcl::p1","token":"$cmd","diagnostic_code":"TW-03","line":57}
```

Parser debug logs may still exist for engineering visibility, but machine-readable diagnostics and edge records are the authoritative trace contract.

---

#### 1.5.7 Call Detection False-Positive Filter

Real EDA Tcl code (e.g., `default_fm_procs.tcl`) is dense with patterns where a proc name appears on a line but is **not** a call — it is mentioned in a log string, assigned to a variable, or used as a metadata annotation. Chopper's call extractor must suppress these false positives.

Adapted from SNORT's production-proven `_IsProcFoundInLine()` 4-level cascading filter (15+ years on Intel EDA codebases).

**Suppression rules — suppress a candidate token if ANY level matches:**

| Level | Condition | Example suppressed |
|-------|-----------|-------------------|
| 2a | Line is a comment (`^\s*#`) | `# read_libs is invoked here` |
| 2b | Token appears as a variable ref (`\$<token>`) | `puts $read_libs` |
| 2c | Token in `define_proc_attributes` position | `define_proc_attributes read_libs` |
| 2d | Token in `[gs]et_app_var` argument | `get_app_var search_path` |
| 2e | Token in proc argument-list position (`\{<token>[\s\}]`) | `proc foo {read_libs} { }` |
| 2f | Token in `set PROC`/`set self` assignment | `set PROC read_libs` |
| 2g | Token in `info exists` expression | `info exists read_libs` |
| 3 | Token appears **only** inside a string arg to a known log proc | `iproc_msg -info "read_libs is invoked"` |
| 4 | Token used as a print label in `echo`/`puts` | `echo "read_libs : phase done"` |

**Known log procedures** (proc names appearing only in their string arguments are suppressed at Level 3):

```python
LOG_PROC_NAMES: frozenset[str] = frozenset({
    'iproc_msg', 'puts', 'echo',
    'print_info', 'print_warning', 'print_error', 'print_fatal',
    'rdt_print_info', 'rdt_print_warn', 'rdt_print_error',
    'log_message', 'printvar', 'time_stamp',
})
```

**Level 3 exception — embedded bracket calls are real:** If the proc name appears inside `[...]` within a log string, that is a genuine embedded call and must NOT be suppressed:

```tcl
iproc_msg -info "read_rtl_2stage invoked"       # SUPPRESS — name in string only
iproc_msg -info "[read_rtl_2stage $args]"       # KEEP — embedded bracket call
```

**`foreach_in_collection` structural handling:**
`foreach_in_collection` is a Synopsys Formality/DC EDA iterator. Treat it exactly like `foreach` for the context stack: push `CONTROL_FLOW` when its body `{` is encountered; parse the body for calls; do NOT emit a traced call for `foreach_in_collection` itself (it is a Synopsys built-in, not a user proc).

**Synopsys/Cadence EDA flow control commands** (appear as first words of commands in proc bodies; they are NOT user procs and will produce `TW-02` at trace time — this is expected and correct behavior, not an error):

```python
EDA_FLOW_COMMANDS: frozenset[str] = frozenset({
    # Cadence LEC
    'vpx', 'vpxmode', 'tclmode',
    # Synopsys Formality / DC
    'redirect', 'tcl_set_command_name_echo', 'echo',
    'annotate_trace', 'current_design', 'current_container',
    'set_top', 'read_verilog', 'read_sverilog', 'read_db',
    'set_app_var', 'get_app_var',
})
```

These commands can appear at any nesting level (not just top-level). They have no special brace-counting behaviour — they are ordinary Tcl commands for structural purposes. At call-extraction time they produce `TW-02` because they are not in the domain's user proc index. This is expected output; the domain owner is informed but the trim proceeds.

**`redirect -variable varname "command string"`:** The double-quoted string argument is data passed to `redirect`. The string may contain EDA command names (e.g., `"report_unmapped_points -extra"`). Because these names appear inside a string argument — not as the first word of a command — they are NOT extracted as call candidates. Chopper's call extractor only traces the first word of a command, not the contents of string arguments.

---

#### 1.5.8 CallExtractor Implementation Decisions

##### D-1e-01: Flat token walk replaces depth-based "skip to command boundary"

**Context.** The first implementation of `extract_body_refs` consumed tokens per-command: at a command-position WORD, classify the first word, scan remaining tokens in the command for embedded `[call]` patterns, then *skip forward to the next command boundary* (NEWLINE/SEMICOLON at the same brace depth as the command's first word). Control-flow body contents were dropped: `if {cond} {helper_proc}` at depth 1 caused `_skip_to_command_boundary` to fast-forward from the `if` keyword past its `NEWLINE` at depth 1 — sailing over `helper_proc` at depth 2.

**Decision.** Delete `_skip_to_command_boundary` and `_scan_bracket_calls_in_command`. Walk every WORD token in the body range one at a time. For command-position WORDs, classify the first word. For every WORD (command-position or not, suppressed or not), regex-scan the value for embedded `[<name>` bracket calls. The tokenizer's `at_command_position` flag naturally re-establishes itself at every brace-depth transition, so body-internal command-position tokens are visited without any explicit recursion.

**Rationale.** §1.5.3 step 3d says "recurse into control-structure body"; the spec endorses iterative / stack-based implementations explicitly ("Implementations should use an iterative or stack-based approach to avoid Python stack overflow on deeply nested control structures"). The flat walk *is* the iterative form — and it has the additional benefit of eliminating the depth-matching bug class that led here. The uniform bracket scan on all WORD tokens handles §1.5.3 step 4 (bracket sub-calls) and §1.5.7 Level 3 exception (real `[call]` inside a log-proc string argument) with a single rule.

**Outcome.** Rewritten `extract_body_refs` at [src/chopper/parser/call_extractor_body.py](../src/chopper/parser/call_extractor_body.py). §1.5.3 algorithm block in [technical_docs/this doc (parser section)](this doc (parser section)) rewritten to match (with an explicit note that control-flow recursion is not needed). Tested in `TestControlFlowBodies` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py).

##### D-1e-02: Suppression check is identifier-only; structural suppression leans on `TCL_BUILTINS` and `at_command_position`

**Context.** The `_should_suppress_first_word` helper initially took the token list and its index and implemented a command-structure check for each of §1.5.7 Levels 2b–2g (`set PROC x`, `info exists x`, `define_proc_attributes x`, etc.). This duplicated logic the tokenizer and classifier already provided.

**Decision.** Shrink `_should_suppress_first_word(first_word: str) -> bool` to pure identifier tests. It handles only the two classes that are **not** covered by other mechanisms: EDA log-proc names (`LOG_PROC_NAMES`) and EDA app-var commands (`set_app_var` / `get_app_var`, which are not in `TCL_BUILTINS`). Every other §1.5.7 level is satisfied structurally:

- Level 2a (comment lines) — tokenizer never emits COMMENT at command position in a WORD stream.
- Levels 2b, 2e — variable refs and arg-list positions are not at command position.
- Levels 2c, 2f, 2g — `define_proc_attributes`, `set`, `info` are in `TCL_BUILTINS`; `_classify_call_candidate` rejects them. Their arguments are not at command position.
- Level 2d (`set_app_var` / `get_app_var`) — explicit identifier check.
- Level 3 (log-proc string args) — explicit identifier check (the log proc itself is suppressed; the uniform bracket scan still picks up embedded real `[call]` inside string args).
- Level 4 (print labels) — labels are not at command position; structurally handled.

**Rationale.** Duplicating the structural check adds code that needs unit tests for every §1.5.7 level and creates two sources of truth. Leaning on the tokenizer's `at_command_position` flag plus `TCL_BUILTINS` membership is simpler and satisfies every spec-required suppression.

**Outcome.** `should_suppress_first_word` at [src/chopper/parser/call_extractor_classify.py](../src/chopper/parser/call_extractor_classify.py) is identifier-only. Suppression matrix is tested in `TestSuppression` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py); every §1.5.7 level has at least one test case.

##### D-1e-03: `source` / `iproc_source` consume their argument indices to prevent double-count

**Context.** After the flat-walk restructure, `source common/helpers.tcl` correctly produced a `source_refs` entry — but the path token `common/helpers.tcl`, as an ordinary WORD, was also picked up by the free bracket scan pass (no `[` in it, but the token was considered), and in pathological cases (e.g. `iproc_source -file [derive_path]`) the bracket scan would extract `derive_path` as a call candidate.

**Decision.** `_extract_source_path_with_indices` returns not just the path string but a `set[int]` of token indices consumed by the source command (the keyword is left alone; the flag tokens and the path token are all marked consumed). The caller unions these into a `consumed` set and skips those tokens in the free bracket-scan pass.

**Rationale.** `source` is explicitly a file dependency, not a proc call (§1.5.5). Its argument tokens must not leak into `calls` under any shape — neither as literal text nor via embedded bracket expansion.

**Outcome.** `extract_source_path_with_indices` at [src/chopper/parser/call_extractor_sources.py](../src/chopper/parser/call_extractor_sources.py) plus the `consumed` set in [src/chopper/parser/call_extractor_body.py](../src/chopper/parser/call_extractor_body.py). Tested in `TestSourceRefs::test_source_not_a_call_edge` and `test_source_dynamic_path_dropped` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py).

---

### 1.6 Output: ProcEntry

Each detected proc produces one `ProcEntry` record:

| Field | Type | Description |
|---|---|---|
| `canonical_name` | `str` | `relative/path.tcl::qualified_name` |
| `short_name` | `str` | Name as it would appear in JSON `procs` array |
| `qualified_name` | `str` | Namespace-qualified name with leading `::` stripped |
| `source_file` | `PurePosixPath` | Domain-relative Tcl file path |
| `start_line` | `int` | First line of proc definition (the `proc` keyword line) |
| `end_line` | `int` | Last line of proc definition (the closing `}` line) |
| `body_start_line` | `int` | Line immediately after the opening `{` of the proc body (see §1.4.2 step 2g) |
| `body_end_line` | `int` | Line immediately before the closing `}` of the proc body (see §1.4.2 step 2g) |
| `namespace_path` | `str` | Namespace context from enclosing `namespace eval` (empty string if at file root) |
| `dpa_start_line` | `Optional[int]` | First line of the `define_proc_attributes` block immediately following this proc (`None` if absent) |
| `dpa_end_line` | `Optional[int]` | Last line of the `define_proc_attributes` block immediately following this proc (`None` if absent) |
| `comment_start_line` | `Optional[int]` | First line of the structured doc-comment block immediately preceding this proc (`None` if absent) |
| `comment_end_line` | `Optional[int]` | Last line of the structured doc-comment block immediately preceding this proc (`None` if absent) |
| `calls` | `tuple[str, ...]` | Raw proc-call tokens extracted from the proc body after false-positive filtering (§1.5.7); empty tuple if none found or body is empty. These are unresolved textual tokens — the tracer resolves them using §1.5.4 and the caller's `namespace_path`. |
| `source_refs` | `tuple[str, ...]` | Literal file paths extracted from `source` and `iproc_source` calls in the proc body (§1.5.5); empty tuple if none found. Computed paths (`source $var`) are excluded and produce `PW-09`. |

#### 1.6.1 Invariants

1. `start_line <= body_start_line <= body_end_line <= end_line`
2. `canonical_name` is unique within the proc index for one domain. Duplicate canonical names are an ERROR.
3. `short_name` is unique within the same source file. Duplicate short names in the same file are an ERROR.
4. If the same short name is defined twice in the same file, the **last definition wins** for index materialization so downstream tooling has one deterministic span to report, but Chopper emits an ERROR diagnostic and the file is invalid for trim/trace work until fixed.
5. `calls` contains only syntactically literal call tokens — no `$` variables, no `[...]` wrappers (stripped at extraction per §1.5.3). Tokens are deduplicated and sorted lexicographically within each `ProcEntry`.
6. `source_refs` contains only domain-relative POSIX path strings. Paths computed at runtime are excluded; paths from `-use_hooks` calls are included as plain paths (hook-file discovery is an analysis concern, not a field variant).

#### 1.6.2 Boundary Definitions for `body_start_line` / `body_end_line`

These fields are defined operationally as follows:

- `body_start_line` = the source line immediately **after** the line containing the opening `{` of the proc body.
- `body_end_line` = the source line immediately **before** the line containing the closing `}` of the proc body.

**Edge cases:**

| Form | Example | start_line | end_line | body_start_line | body_end_line |
|---|---|---|---|---|---|
| One-line proc | `proc foo {} { return 1 }` (line 5) | 5 | 5 | 5 | 5 |
| Empty multi-line body | `proc foo {} {` (line 3) / `}` (line 4) | 3 | 4 | 4 | 3 |
| Whitespace-only body | `proc foo {} {` (line 6) / (blank line 7) / (blank line 8) / `}` (line 9) | 6 | 9 | 7 | 8 |

For the empty multi-line body case, `body_start_line > body_end_line` signals an empty body. Consumers must check for `body_start_line > body_end_line` before iterating body lines and treat it as zero lines of content.

#### 1.6.3 Duplicate Proc Validation Timing and Emission

`PE-01 duplicate-proc-definition` is checked at the end of parsing **each source file**, not after all files in the domain are parsed. The check compares `short_name` values within a single file's `ProcEntry` list. This keeps the parser's per-file invariant local and side-effect-free.

**Timing:** After the parser finishes processing all lines of one file and has produced its list of `ProcEntry` records, scan for duplicate `short_name` values within that list. Emit `PE-01` for each duplicate group; the **last definition wins** for index materialization (per Invariant 4 in §1.6.1) so downstream tooling has one deterministic span to report, but the file is marked invalid for trim/trace until the duplicates are resolved.

**Error-message format:**

```
PE-01 (ERROR): Duplicate proc definition for '<short_name>' in '<source_file>'
  First definition: line <first_start_line>
  Last definition:  line <last_start_line> (used for index)
  Hint: Remove one definition or rename the proc.
```

**Location field:** `<source_file>:<first_start_line>`.

**Cross-file `canonical_name` uniqueness** (Invariant 2) is a separate check performed later during domain-wide proc index assembly by the compiler, not by the parser. It may reuse `PE-01` with an extended message or register its own code; the parser itself only enforces the per-file check.

---

---

### 1.7 Edge Cases and Adversarial Inputs

#### 1.7.1 Brace in Quoted Text Inside a Braced Proc Body

```tcl
proc problematic_proc {args} {
    set data "this has { an open brace"
    return $data
}
```

**Handling:** This input is structurally invalid Tcl. The proc body is itself a brace-delimited word, so the unescaped `{` inside the quoted text still increments brace depth under Tcl Rule 6. Chopper must report an unbalanced-brace parse error here rather than inventing a quote context inside the braced proc body.

#### 1.7.2 Backslash Line Continuation

```tcl
proc split_definition \
    {arg1 arg2} \
    {
    return [list $arg1 $arg2]
}
```

**Handling:** The `proc` keyword, name, args, and body opening may span multiple lines via `\` continuation. The parser must handle this by recognizing continuation before parsing words.

#### 1.7.3 Empty File

```tcl
# This file has no proc definitions
# Just comments and maybe some top-level code
set x 1
```

**Handling:** Returns an empty proc index for this file. This is not an error.

#### 1.7.4 Proc with No Body Braces (Theoretical)

```tcl
proc foo args "return hello"
```

**Handling:** While Tcl allows a quoted body, this is extremely rare in practice. Chopper logs a WARNING and skips this proc. The parser only recognizes brace-delimited bodies.

#### 1.7.5 Deeply Nested Namespace

```tcl
namespace eval a {
    namespace eval b {
        namespace eval c {
            proc deep_proc {} {
                return "deep"
            }
        }
    }
}
```

**Handling:** Namespace path is `a::b::c`. Canonical name is `file.tcl::a::b::c::deep_proc`.

#### 1.7.6 Multiple Namespace Blocks

```tcl
namespace eval utils {
    proc helper_a {} { return "a" }
}

namespace eval utils {
    proc helper_b {} { return "b" }
}
```

**Handling:** Both procs are in namespace `utils`. This is standard Tcl — namespaces accumulate across multiple `namespace eval` blocks.

#### 1.7.7 Mixed Encoding

```tcl
# -*- coding: latin-1 -*-
proc legacy_proc {} {
    # Comment with ü ö ä characters
    return "done"
}
```

**Handling:** UTF-8 decode fails; fall back to Latin-1 with a WARNING. Proc boundaries are still detected correctly because brace matching is byte-level.

#### 1.7.8 Proc Inside If Block

```tcl
if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}
```

**Handling:** `conditional_proc` is NOT indexed. It is inside a conditional block, not at file top level or inside `namespace eval`. Debug-level log message notes the skip.

#### 1.7.9 Computed Proc Name

```tcl
proc ${prefix}_handler {} {
    return "dynamic"
}
```

**Handling:** The proc name contains `$` — it is computed at runtime. Chopper logs a WARNING diagnostic and does NOT index this proc.

#### 1.7.10 Duplicate Proc Definition

```tcl
proc read_data {} {
    return "version 1"
}

proc read_data {} {
    return "version 2"
}
```

**Handling:** Both definitions are detected. The LAST definition wins for proc-index materialization (matching Tcl runtime semantics), but Chopper emits an ERROR diagnostic for the duplicate and treats the file as invalid input for trim/trace until the duplicate is fixed. The proc index contains only the second definition's span so diagnostics and owner review point at the definition Tcl would execute.

---

#### 1.7.11 Proc Args with Default Values Containing Nested Braces

```tcl
proc read_rtl_2stage { rtlfile root_module { container "r" } { ctech_type "ADD" } } {
    ...
}
```

**Handling:** The args specification is a single brace-delimited word. Inside it, `{ container "r" }` is a Tcl argument descriptor with a default value. Brace depth trace for the relevant tokens on the proc line:

| Token | depth delta | cumulative |
|-------|-------------|------------|
| `{` (args open) | +1 | 1 |
| `{` (container default open) | +1 | 2 |
| `}` (container default close) | -1 | 1 |
| `{` (ctech_type default open) | +1 | 2 |
| `}` (ctech_type default close) | -1 | 1 |
| `}` (args close) | -1 | 0 |
| `{` (body open) | +1 | 1 ← body |

The §1.4.2 step b algorithm correctly finds the body `{` because it scans for an unescaped `{` at the **original** depth (0), which is only reached after the entire args word closes. The args word is a single complete brace-balanced token.

**Why it matters:** This is one of the most common proc signatures in VLSI EDA Tcl (`default_fm_procs.tcl` uses it throughout). Prematurely treating a default-value `}` as the proc body close corrupts all subsequent proc boundaries in the file.

#### 1.7.12 define_proc_attributes Immediately After Proc Closing Brace

```tcl
proc read_libs {} {
    ...
}
define_proc_attributes read_libs \
   -info "To read Synopsys .db designs or technology libraries for LP and Non-LP runs"
```

**Handling:** The DPA block starts on the line immediately after the proc's closing `}`. The parser captures it per §1.4.6, setting `dpa_start_line` to the `define_proc_attributes` line and `dpa_end_line` to the last continuation line (the one without a trailing `\`). The trimmer must drop this block whenever `read_libs` is excluded, and keep it whenever `read_libs` is kept.

#### 1.7.13 Structured Comment Banner Before Proc

```tcl
################################################################################
#proc      : read_libs
#purpose   : To read Synopsys .db designs or technology libraries for LP and Non-LP runs
#usage     : read_libs
################################################################################
proc read_libs {} {
```

**Handling:** The parser detects the contiguous comment block per §1.4.7 and stores `comment_start_line` to `comment_end_line = start_line - 1` on the `ProcEntry`. The 6 comment lines (including the `####` delimiters) are captured as a single unit. Braces inside comments (e.g., a future `#usage: foo {args}` line) are completely inert and never affect brace depth.

#### 1.7.14 foreach_in_collection (Synopsys EDA Iterator)

```tcl
foreach_in_collection item [all_clock_gating_latches] {
    puts $item [get_attribute $item full_name]
}
```

**Handling:** `foreach_in_collection` is a Synopsys Formality/DC EDA iterator command. Push `CONTROL_FLOW` context when its body `{` is encountered (same as `foreach`). Parse the body for call candidates. Apply the §1.5.7 false-positive filter — `get_attribute` and similar EDA vendor calls inside will be suppressed. Do NOT emit a traced call for `foreach_in_collection` itself (it is a Synopsys built-in, not a user proc).

---

---

### 1.8 Parser Architecture

#### 1.8.1 Two-Phase Design

The parser operates in two phases:

**Phase 1: Structure Detection**
- Input: file content as string
- Process: Track brace depth, identify `proc` and `namespace eval` boundaries
- Output: List of `ProcEntry` records with line spans

**Phase 2: Call Extraction** (used by tracer, not by proc index builder)
- Input: `ProcEntry` record (specifically, the body lines)
- Process: Extract candidate proc calls and file references from body text
- Output: List of call references and file references

#### 1.8.2 State Machine

The structure detector tracks:

| State Variable | Type | Description |
|---|---|---|
| `brace_depth` | `int` | Current nesting depth of braces |
| `namespace_stack` | `list[str]` | Stack of active namespace names |
| `in_quote` | `bool` | Whether currently inside a quote-delimited word while parsing outside a braced word |
| `in_comment` | `bool` | Whether current line is a comment |
| `continuation` | `bool` | Whether previous line ended with `\` |
| `current_proc` | `Optional[ProcBuilder]` | Partial proc being accumulated |
| `expecting_body` | `bool` | Whether we've seen `proc name args` and are waiting for `{` |
| `awaiting_dpa` | `bool` | Whether the main loop just closed a proc body and should peek ahead for DPA (§1.4.6) |
| `pending_comment_start` | `Optional[int]` | Start line of the accumulated comment block preceding the current candidate proc (§1.4.7) |

#### 1.8.3 Performance Target

For a domain like power/ (~60 Tcl files, ~150+ procs), performance should be reasonable for interactive use. No strict timing constraints are imposed.

The parser is purely CPU-bound string processing. No external dependencies required.

> **Implementation note:** Prefer bulk string operations (`str.find()`, `str.index()`) to jump between braces, quotes, and newlines rather than iterating character-by-character. Measure against the 60-file synthetic domain from `tests/fixtures/gen_large_domain.py`.

#### 1.8.4 Diagnostic Emission Contract

The parser does **not** return diagnostics in its return value. Instead, it emits them via the optional `on_diagnostic` callback (`DiagnosticCollector = Callable[[Diagnostic], None]`), defined in `core/protocols.py`.

All parser diagnostic codes (`PE-*`, `PW-*`, `PI-*`) — including severity, description, recovery hints, and the exact algorithm section where each fires — are defined exclusively in [`technical_docs/DIAGNOSTIC_CODES.md`](../technical_docs/DIAGNOSTIC_CODES.md) (sections 5–7). Implementation must use constants from `src/chopper/core/diagnostics.py` derived from that registry; do not introduce new codes without first registering them there.

**Emission pattern:**
```python
# Inside parse_file():
if on_diagnostic is not None:
    on_diagnostic(Diagnostic(
        severity=Severity.ERROR,
        code="PE-01",
        message=f"Duplicate proc definition for '{short_name}' in '{rel_path}'",
        location=f"{rel_path}:{start_line}",
        hint="Remove one definition or rename the proc.",
        source=DiagnosticSource.PARSER,
    ))
```

**Caller integration (compiler):**
```python
# ParserService bridges DiagnosticSink to parser's DiagnosticCollector
entries = parse_file(file_path=tcl_file, text=text, on_diagnostic=progress.on_diagnostic)
```

**Unit test isolation:**
```python
# Test without diagnostics (simple)
entries = parse_file(file_path=file, text=source_text)

# Test with diagnostic capture
diags: list[Diagnostic] = []
entries = parse_file(file_path=file, text=source_text, on_diagnostic=diags.append)
assert any(d.code == "PE-01" for d in diags)
```

---

#### 1.8.5 Parser-to-Pipeline Integration

The parser is Phase 2 of Chopper's 8-phase pipeline. `list[ProcEntry]` is its sole typed output contract. Two downstream consumers use it for different purposes.

##### 1.8.5.1 Fields Used by the Trimmer (Phase 5)

The trimmer operates per-file: it reconstructs each proc-trimmed file by keeping or removing line ranges.

| Field | Trimmer Use |
|---|---|
| `source_file` | Identifies which file to operate on |
| `start_line` / `end_line` | Core proc span |
| `dpa_start_line` / `dpa_end_line` | Atomic drop with proc when excluded (Pitfall P-33) |
| `comment_start_line` / `comment_end_line` | Atomic drop with proc when excluded (Pitfall P-34) |
| `body_start_line` / `body_end_line` | Boundary for `RunResult.trim_stats.loc_removed` counting |

**Full atomic unit per proc** — the trimmer handles each `ProcEntry` as one indivisible block:

- **Keep:** preserve lines `comment_start_line` (or `start_line` if `None`) through `dpa_end_line` (or `end_line` if `None`) inclusive.
- **Drop:** remove that same contiguous range.

The trimmer sorts all proc decisions for a file by `comment_start_line` (falling back to `start_line`) before processing, then reassembles the file from surviving line ranges in source order.

##### 1.8.5.2 Fields Used by the Compiler / Tracer (Phases 3–4)

The compiler builds two in-memory structures from `list[ProcEntry]`:

**Proc index** — maps canonical names to entries for JSON validation and trace-time resolution:

```python
proc_index: dict[str, ProcEntry] = {e.canonical_name: e for e in all_entries}
```

**Call graph edges** — directed edges for BFS trace expansion (see [ARCHITECTURE.md](ARCHITECTURE.md) §5.4, P4 trace phase). Because `calls` is pre-populated by the parser, the tracer needs no secondary file read:

```python
# Edge: caller canonical_name → unresolved call token
# Tracer resolves tokens via §1.5.4 using e.namespace_path
call_edges: list[tuple[str, str]] = [
    (e.canonical_name, token)
    for e in all_entries
    for token in e.calls
]
```

**File dependency edges** — for `source` / `iproc_source` file-level dependencies:

```python
source_edges: list[tuple[str, str]] = [
    (e.canonical_name, ref)
    for e in all_entries
    for ref in e.source_refs
]
```

Trace expansion starts BFS from the seed proc set (explicit `procedures.include` entries), follows `call_edges` breadth-first with the frontier **sorted lexicographically at each step** for determinism ([ARCHITECTURE.md](ARCHITECTURE.md) §5.4 and NFR-03), and collects all reachable `ProcEntry` records as additional keeps.

##### 1.8.5.3 Fields Used by `chopper trim --dry-run` (`dependency_graph.json`)

`chopper trim --dry-run` materialises the complete dependency graph from parser output without any extra file reads:

| `dependency_graph.json` edge type | `ProcEntry` field | Example |
|---|---|---|
| Proc-call edge | `calls` | `fev_formality/procs.tcl::read_libs` → `read_db_files` |
| File-source edge | `source_refs` | `fev_formality/procs.tcl::read_libs` → `shared/db_helper.tcl` |
| Proc location node | `canonical_name`, `source_file`, `start_line`, `end_line` | node at lines 10–25 |

Every `ProcEntry` is a graph node. Every `calls` token (resolved or unresolved) and every `source_refs` path is a directed edge. Unresolved tokens appear as `TW-02` or `TW-03` diagnostics in `trim_report.json` and the optional JSON-lines log stream.

---

---

### 1.9 Test Strategy

#### 1.9.1 Fixture Categories

| Category | Fixtures | Purpose |
|---|---|---|
| **basic** | Single proc, multiple procs, empty file | Baseline correctness |
| **namespace** | Nested namespace, multiple blocks, absolute names | Namespace resolution |
| **brace** | Unescaped brace inside quoted text in a braced body, nested braces, unbalanced (error) | Brace tracking |
| **continuation** | Split proc def, split body lines | Line continuation |
| **comments** | Comment before proc, comment with braces, inline comment | Comment handling |
| **edge_cases** | Computed name, proc in if, duplicate names, empty body | Adversarial inputs |
| **encoding** | UTF-8, Latin-1, mixed | Encoding fallback |
| **call_extraction** | Direct calls, bracketed, dynamic, source/iproc_source | Tracing support |

#### 1.9.2 Property-Based Invariants

1. **Span consistency:** For every `ProcEntry`, all lines in `[start_line, end_line]` exist in the source file.
2. **Body subset:** `{body_start_line, body_end_line}` is a strict subset of `{start_line, end_line}`.
3. **No overlap:** No two `ProcEntry` spans overlap.
4. **Canonical uniqueness:** All `canonical_name` values are unique.
5. **Roundtrip:** Extracting proc spans from a file and re-joining them produces valid Tcl (brace balance preserved per proc).

---

---

### 1.10 References

| Source | Relevance |
|---|---|
| [Tcl 8.6 Dodekalogue](https://wiki.tcl-lang.org/page/Dodekalogue) | The twelve rules defining Tcl syntax |
| [Tcl proc manual](https://www.tcl-lang.org/man/tcl8.6/TclCmd/proc.htm) | `proc name args body` syntax |
| [Tcl namespace manual](https://www.tcl-lang.org/man/tcl8.6/TclCmd/namespace.htm) | `namespace eval` semantics |
| [BNF for Tcl](https://wiki.tcl-lang.org/page/BNF+for+Tcl) | Why Tcl has no formal BNF (context-sensitive language) |
| [ARCHITECTURE.md](ARCHITECTURE.md) §5.4 | Proc index contract and trace expansion algorithm |
| [ARCHITECTURE.md](ARCHITECTURE.md) §9 and this doc (TC-01, TC-02) | Technical challenges for proc boundary detection |

---

### Pitfall P-46: Escaped `\[` in a Quoted String Must Not Be Extracted as a Proc Call

**THE TRAP (bug report: GitHub #25):**

```tcl
# ANSI escape sequence in a double-quoted word
puts -nonewline "\x1b\[H\x1b\[2J"

# Escaped bracket used for literal text
append status_str " \[flow_setup\]"
```

`BRACKET_CALL_RE` scans the raw token value for `[<identifier>` patterns. The tokenizer correctly *does not* increment `quoted_bracket_depth` for a `\[` (backslash precedes `[`, so `_is_escaped` returns True), but the token value still contains the raw backslash-bracket bytes. When the regex later scans the token value it finds `\[H` and `\[flow_setup` and emits `H` and `flow_setup` as proc-call candidates — false positives that produce TW-02 warnings.

**Correct Behavior:** Before accepting a `BRACKET_CALL_RE` match as a proc-call candidate, check whether the `[` at `match.start()` in the token value is preceded by an **odd** number of backslashes. An odd count means the bracket is backslash-escaped (a literal `[` in Tcl), not a command-substitution opener. The match must be silently discarded.

An **even** count (including zero) means the backslashes cancel each other out and the `[` is a real command-substitution opener:

| Source text | Preceding `\` count | Escaped? | Action |
|---|---|---|---|
| `\[H`    | 1 (odd)  | Yes | Discard — `H` is not a call |
| `\\[H`   | 2 (even) | No  | Keep — `H` is a real call candidate |
| `\\\[H`  | 3 (odd)  | Yes | Discard |
| `[H`     | 0 (even) | No  | Keep |

**Implementation Requirement:**

In `src/chopper/parser/call_extractor_body.py`, add a private helper:

```python
def _bracket_is_escaped(text: str, bracket_pos: int) -> bool:
    count = 0
    j = bracket_pos - 1
    while j >= 0 and text[j] == "\\":
        count += 1
        j -= 1
    return count % 2 == 1
```

Apply it in the `BRACKET_CALL_RE.finditer` loop before calling `classify_call_candidate`:

```python
for match in BRACKET_CALL_RE.finditer(token.value):
    if _bracket_is_escaped(token.value, match.start()):
        continue  # \[ is a literal character, not command substitution
    candidate = classify_call_candidate(match.group(1))
    if candidate is not None:
        calls.add(candidate)
```

**Why It Matters:** ANSI escape sequences (`\[H`, `\[2J`, etc.) and any literal string that uses `\[` to embed a bracket are common in EDA logging, status-display, and report-generation code. Without this fix, every such string emits a spurious TW-02 warning for the identifier following the escaped bracket. Users then either incorrectly add those identifiers to `procedures.include` (polluting their JSON) or spend time investigating phantom unresolved-call warnings.

**Tests:**
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_ansi_escape_sequence_not_a_call`
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_escaped_bracket_string_literal_not_a_call`
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_unescaped_bracket_still_extracted`
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_double_backslash_bracket_extracted`
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_multiple_escaped_brackets_all_suppressed`
- `tests/unit/parser/test_call_extractor.py::TestEscapedBracketCalls::test_mixed_escaped_and_real_bracket`

**Fixture:** `tests/fixtures/edge_cases/parser_escaped_bracket_in_string.tcl`

---

### Pitfall P-47: Brace-Delimited Switch Patterns with `[...]` Content Generate False Call Candidates

**THE TRAP:**

```tcl
proc classify {ch} {
    switch $ch {
        {[a-z]} { lower_handler $ch }   ;# brace-delimited literal pattern
        {[0-9]} { numeric_handler $ch }
        default { other_handler $ch }
    }
}
```

`mark_switch_pattern_words` (P-39) marks only WORD tokens at `inner_depth` as skip. A brace-delimited pattern `{[a-z]}` produces an LBRACE at `inner_depth` — **not** a WORD — and its interior WORD `[a-z]` sits at `inner_depth + 1`. Neither is added to `skip_indices`. When `extract_body_refs` later processes the WORD `[a-z]`, `BRACKET_CALL_RE` matches `[a` and emits `a` as a proc-call candidate — a false positive.

**Correct Behavior:** The pre-pass must distinguish "pattern" positions from "body" positions in the switch body using an alternating state machine. When the current position is "pattern" and an LBRACE is found at `inner_depth`, the entire brace block (LBRACE, all interior tokens, matching RBRACE) is marked opaque in `skip_indices`.

The alternating model:

| Position | Token at `inner_depth` | Action |
|---|---|---|
| Pattern | `WORD` | Mark as skip; advance to body position |
| Pattern | `LBRACE` | Mark entire block as skip; advance to body position |
| Body | `WORD` (e.g. `-` fall-through) | Mark as skip; advance to pattern position |
| Body | `LBRACE` | Leave unmarked (real code); advance to pattern position |

**Implementation Requirement:**

In `src/chopper/parser/call_extractor_structural.py`, replace the `for`-loop in `mark_switch_pattern_words` with a `while`-loop that tracks `expecting_pattern: bool`. When `expecting_pattern is True` and an LBRACE at `inner_depth` is found, mark all tokens in the range `[j, rbrace_j]` inclusive as skip (using `mark_opaque_arg_braces` semantics). Toggle `expecting_pattern` after every consumed token pair.

**Why It Matters:** Brace-enclosed regex-style patterns are common in EDA Tcl for character-class routing (`{[A-Z]+}`, `{[0-9a-f]+}`) and glob-pattern dispatch. Without this fix, every such switch arm emits spurious TW-02 warnings for single-letter identifiers like `a`, `z`, `A`, `Z`.

**Tests:**
- `tests/unit/parser/test_call_extractor.py::TestSwitchBracePatterns::test_brace_pattern_char_class_not_a_call`
- `tests/unit/parser/test_call_extractor.py::TestSwitchBracePatterns::test_multiple_brace_patterns_suppressed`
- `tests/unit/parser/test_call_extractor.py::TestSwitchBracePatterns::test_mixed_word_and_brace_patterns`
- `tests/unit/parser/test_call_extractor.py::TestSwitchBracePatterns::test_body_code_inside_switch_arm_still_extracted`
- `tests/unit/parser/test_call_extractor.py::TestSwitchBracePatterns::test_fixture_classify_char`

**Fixture:** `tests/fixtures/edge_cases/parser_switch_brace_pattern.tcl`

---

### Pitfall P-48: Missing Standard Tcl Builtins Cause Spurious TW-02 Warnings

**THE TRAP:**

```tcl
proc parse_line {line} {
    lassign [split $line :] host port path   ;# TW-02: lassign not in domain proc set
    subst $template                          ;# TW-02: subst not in domain proc set
}
```

`TCL_BUILTINS` did not include `lassign`, `subst`, `apply`, `throw`, `lmap`, `lrepeat`, or `lreverse`. When any of these appeared as first-word commands in a proc body, `classify_call_candidate` did not suppress them (not in the builtin set, not EDA commands) and they were emitted as unresolved proc-call candidates. Every domain that used these commands received spurious TW-02 `unresolved-call` warnings, polluting diagnostic output.

**Correct Behavior:** All standard Tcl 8.5+ / 8.6+ built-in commands must be in `TCL_BUILTINS`. First-word occurrences of `lassign`, `subst`, `apply`, `throw`, `lmap`, `lrepeat`, and `lreverse` in proc bodies should produce zero TW-02 diagnostics.

**Implementation Requirement:**

In `src/chopper/parser/call_extractor_constants.py`, add to `TCL_BUILTINS`:

```python
"lassign",   # Tcl 8.5 — destructuring list assignment
"subst",     # Tcl core — variable/command substitution in a string
"apply",     # Tcl 8.5 — anonymous proc (lambda) application
"throw",     # Tcl 8.5 — structured error with options dict
"lmap",      # Tcl 8.6 — list map (transform each element)
"lrepeat",   # Tcl 8.5 — create a list by repeating an element
"lreverse",  # Tcl 8.5 — reverse a list
```

**Why It Matters:** `lassign` in particular is ubiquitous in modern EDA Tcl for destructuring complex parsed output (`lassign [split $path /] dir base ext`). Every file using it generated a TW-02 false positive. Users who investigated would be confused — `lassign` is not a user proc and does not belong in `procedures.include`.

**Tests:**
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_lassign_not_extracted_as_call`
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_subst_not_extracted_as_call`
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_apply_not_extracted_as_call`
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_throw_not_extracted_as_call`
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_lmap_not_extracted_as_call`
- `tests/unit/parser/test_call_extractor.py::TestMissingBuiltins::test_builtins_in_tcl_builtins_constant`

---


---

## 2. Compiler & Tracer Module

**TC-03 — Transitive Proc Tracing:** The center of the product. Requires correct static call extraction, conservative behavior for dynamic Tcl, cross-file proc mapping within the domain boundary based on the per-run proc index, and clear warnings when trace cannot prove correctness. The proc index contract is defined in R3 and must exist before F2 trimming or trace expansion runs.

**TC-08 — Override and Ordering Semantics:** Multiple selected features may touch the same proc or stage. Selected input order governs last-wins behavior for explicit `replace_step`/`replace_stage` conflicts; R1 governs include/exclude survival. Within one feature, action order is top-to-bottom and later actions see results of earlier ones.

### Pitfall P-08: Trace Expansion Must Be Deterministic

**THE TRAP:**
```python
# If proc index lookup returns multiple candidates:
candidates = [proc_a, proc_b]  # Which one do we trace?
# Result: non-deterministic output
```

**Correct Behavior:** Trace expansion resolves a proc call only when the deterministic namespace lookup contract produces exactly one canonical proc in the selected domain.

**Implementation Requirement:**
- Bare token `helper`: try `caller_namespace::helper`, then global `helper`
- Relative qualified token `pkg::helper`: try `caller_namespace::pkg::helper`, then global `pkg::helper`
- Absolute token `::pkg::helper`: try only `pkg::helper`
- If a candidate qualified name maps to multiple canonical procs, log WARNING `TW-01`
- If no candidate resolves inside the selected domain, log WARNING `TW-02`
- Dynamic or syntactically unresolvable call forms still log WARNING `TW-03`
- Do NOT auto-resolve ambiguous or cross-domain calls

**Why It Matters:** Non-deterministic trimming breaks reproducibility.

**Test:** Scenario: caller namespace `flow::setup` invokes `helper`; tracer must try `flow::setup::helper` before global `helper`. Scenario: two canonical procs match the same candidate qualified name; log `TW-01`.

---

### Pitfall P-09: Same-Layer Include Wins Over Exclude (and Later Layers Win Over Earlier Layers)

**THE TRAP:**
```json
{
  "base": { "procedures": { "include": [{"file": "utils.tcl", "procs": ["helper"]}] } },
  "feature": { "procedures": { "exclude": [{"file": "utils.tcl", "procs": ["helper"]}] } }
}
```

**Correct Behavior:** Under the R1 ordered overlay (later layer wins), the feature is the *later* layer in this example, so its `procedures.exclude` actually drops `helper`; the transition emits `VW-21 layer-shadowed`. Within a *single* layer, an explicit `procedures.include` for a proc and a `procedures.exclude` for the same proc still resolves include-wins (same-layer authoring rule, `VW-12`). Trace (P4) is reporting-only and never adds procs to the surviving set: traced callees are emitted in `dependency_graph.json` and `trim_report.json` for visibility but are not copied.

**Implementation Requirement:**
- Literal file paths in `files.include` are authoritative and always survive
- `files.exclude` applies only to files matched by wildcard `files.include` patterns
- Explicit `procedures.include` entries are authoritative and always survive
- `procedures.exclude` prunes procs inside `PROC_TRIM` files contributed by this layer, and — because R1 is now an **ordered overlay** — a later layer's `procedures.exclude` can also drop a proc that an earlier layer (base or a preceding feature) contributed. Such transitions emit `VW-21 layer-shadowed`. The retired `VW-18` / `VW-19` cross-source veto warnings no longer fire.
- PI+ (transitive trace set) is **reporting-only**: see [ARCHITECTURE.md](ARCHITECTURE.md) §5.4. A traced-only proc is never auto-included; if it is needed it must be named explicitly in `procedures.include`

**Why It Matters:** Within a single layer, explicit include must beat its sibling exclude (otherwise authors cannot say "keep this one named proc and exclude the rest"). Across layers, a later layer must be able to remove or replace what an earlier layer contributed (otherwise variant flows would have to split every removable item into its own feature). The two rules together are R1 ordered overlay.

**Test:** Scenario: base includes proc X, a later feature excludes proc X. Final output must omit proc X and emit `VW-21 layer-shadowed`. Scenario: a single feature lists proc X in both `procedures.include` and `procedures.exclude`; same-layer include wins, X survives, `VW-12` is emitted. Scenario: proc Y is only reachable via trace (called by an explicitly-included proc); a later feature excludes Y. Y was never going to be copied (trace is reporting-only), so the trimmed domain omits Y regardless and the PE entry is recorded with no extra diagnostic.

---

### Pitfall P-10: Feature Order Is Authoritative for Flow Actions

**THE TRAP:**
```python
features_cli = ["feature_b", "feature_a"]  # User specified
features_base = ["feature_a", "feature_b"]  # Base JSON reference order
# Which order do we apply?
```

**Correct Behavior:** CLI order (or project JSON order if no CLI override) is authoritative. Features are applied left-to-right in the specified order.

**Implementation Requirement:**
- CLI feature order completely replaces project JSON feature list
- Do NOT try to merge or re-sort
- Apply features in order: for each feature in order, apply all rules from that feature

**Why It Matters:** Determinism + reproducibility. Flow actions can be order-dependent.

**Test:** Scenario: Feature A creates stage X, Feature B modifies stage X with order ["A", "B"]. Reverse order to ["B", "A"] and verify different output (if flow actions can be order-dependent).

---

### Pitfall P-11: Glob Expansion Must Normalize Paths

**THE TRAP:**
```python
patterns = ["**/*.tcl", "sub/../file.tcl"]  # Unnormalized
# Result: file listed twice with different paths
```

**Correct Behavior:** Glob expansion results are normalized to a canonical form, deduplicated, and sorted.

**Implementation Requirement:**
- Use `pathlib.Path.glob()` for pattern expansion
- Normalize all results with `Path.resolve()` or similar
- Deduplicate results (set conversion)
- Sort results lexicographically before outputting

**Why It Matters:** Manifest must have canonical file lists for reproducibility.

**Test:** Fixture: `glob_normalizes_and_deduplicates` must produce sorted unique list.

---

### Pitfall P-12: Reject Absolute Paths and `..` Traversal

**THE TRAP:**
```json
{ "files": { "include": ["/absolute/path", "sub/../../../outside"] } }
```

**Correct Behavior:** Validation error. Paths must be relative, within domain, no `..` traversal.

**Implementation Requirement:**
- Check each path in JSON:
  - No leading `/`
  - No `..` segments (or reject if `..` would escape domain root)
  - Validate by resolving path and checking it stays within domain root

**Why It Matters:** Prevents accidental (or malicious) inclusion of files outside the domain.

**Test:** Schema validation must reject these patterns.

---


---

## 3. Trimmer Module

**TC-04 — Copy-and-Delete Correctness:** F2 depends on preserving top-level Tcl while deleting only unwanted proc definitions. Chopper deletes only recorded proc spans; text between surviving spans is preserved byte-for-byte. If a proc-trimmed file has no surviving procs and no non-comment top-level Tcl, it survives as a stub with `VW-08`. Malformed deletion breaks Tcl syntax or leaves dangling structure.

### Pitfall P-13: Backup-and-Rebuild Must Fail Cleanly and Recover Deterministically

**THE TRAP:**
```python
# WRONG: If crash between steps 1 and 2, domain is corrupted
os.rename(domain, domain_backup)  # Step 1
write_trimmed_output(domain)      # Step 2: CRASH here
# Result: domain/ doesn't exist, domain_backup/ exists, but trim is incomplete
```

**Correct Behavior:** Backup creation and direct rebuild transitions are simple, restartable, and deterministic.

**Implementation Requirement:**
- Backup creation: First trim creates sibling `domain_backup/` once and treats it as the recovery source on every later run.
- Rebuild: Write directly into the active `domain/` tree during P5. There is no staging tree and no final promotion step.
- Failure: If a write fails mid-run, leave the half-rebuilt `domain/` in place and keep `domain_backup/` untouched.
- Recovery: On re-run, detect the existing backup and rebuild from it cleanly without re-backing-up.

**Why It Matters:** Trim must be re-runnable without manual intervention.

**Test:** Scenario: Simulate crash during backup creation or mid-rebuild; verify re-run recovers cleanly from `domain_backup/`.

---


### Pitfall P-15: Proc Trimming Must Preserve Surrounding Context

**THE TRAP:**
```tcl
# Original file:
set x 1
proc remove_me {args} { return 42 }
set y 2

# WRONG trimmed output:
set x 1
set y 2
# (removes entire proc but leaves surrounding code)
```

**Correct Behavior:** Extract just the proc definition, preserve surrounding lines as-is.

**Implementation Requirement:**
- Source file is a list of lines
- For each proc to keep: extract lines `[start_line, end_line]` from source
- For each proc to remove: skip those lines
- Reassemble: lines not part of any proc + lines from kept procs (in source order)

**Why It Matters:** Top-level code, variable assignments, and comments outside procs must remain untouched.

**Test:** Fixture: `trim_procs_preserves_context` must produce valid output with surrounding code intact.

---

### Pitfall P-44: `FULL_COPY` Must Not Decode Opaque Files

**THE TRAP (bug report: GitHub #21):**
```python
# WRONG: every surviving file is treated as UTF-8 text
text = fs.read_text(backup_root / rel)
fs.write_text(domain_root / rel, text)
```

That works for ordinary Tcl and simple text files, but it explodes on domain artifacts such as `.sn.gz`, compressed reports, binary sidecars, and other opaque payloads that are legitimately included by F1. The immediate symptom is a `UnicodeDecodeError` during P5 `FULL_COPY`, after the rebuild has already started. Chopper then leaves a half-rebuilt `domain/` in place by design (P-13), so a bad full-copy path turns one file-handling bug into a visible mid-run failure.

**Correct Behavior:** `FULL_COPY` is an opaque, byte-preserving file-copy operation for **every** file type, including `.tcl`. Chopper must preserve source bytes exactly and carry the file forward without attempting to interpret encoding, normalize line endings, reformat indentation, or otherwise reserialize content. The P5c indentation-normalization pass applies only to files Chopper itself rewrote (`PROC_TRIM`) or synthesized (`GENERATED`). See also Pitfall **P-45** for the `FULL_COPY` indentation-normalization regression that motivated this scoping (issue #22).

**Implementation Requirement:**
- `FULL_COPY` must use a filesystem-level single-file copy operation from `<domain>_backup/` to `domain/`.
- For non-Tcl files, the copy must preserve file bytes exactly. No UTF-8 decode, no newline normalization, no "best effort" text fallback.
- The live filesystem adapter must preserve source mode bits on the copied file.
- `REMOVE` byte-accounting must come from metadata (`stat().size` or equivalent), not by reading file contents.
- `PROC_TRIM` is the only P5a path that may read file contents for proc-body deletion, and only for `.tcl` files selected for proc trimming.
- P5c may read and rewrite every emitted `PROC_TRIM` or `GENERATED` `.tcl` output for indentation normalization. It must not read or rewrite any `FULL_COPY` output. It must update `TrimReport.bytes_out` for `PROC_TRIM` `.tcl` outcomes so P6 compares against final normalized bytes; `FULL_COPY` byte counts are never re-stamped because the source bytes already match the on-disk output.

**Why It Matters:** F1 is intentionally file-type agnostic. Real EDA domains contain Tcl next to Perl, Python, gzip-compressed artifacts, scheduler payloads, reports, and tool-generated sidecars. If `FULL_COPY` assumes "surviving file == decodable text" for every extension, trims fail on legitimate inputs and the user gets a broken rebuild from an avoidable implementation mistake. Tcl readability is handled inside P5c, scoped to files Chopper itself produced (`PROC_TRIM`, `GENERATED`); see P-45 for the regression that introduced and then scoped this pass.

**Tests:**
- `tests/unit/adapters/test_fs_local.py::test_copy_file_preserves_opaque_bytes`
- `tests/unit/adapters/test_fs_memory.py::test_copy_file_copies_stored_content`
- `tests/unit/trimmer/test_file_writer_modes.py::test_full_copy_file_copies_binary_payload_without_text_decode`
- `tests/integration/test_cli_e2e.py::TestGlobFilesIncludeRegression::test_trim_full_copy_binary_file_survives_without_unicode_decode_error`

---

### Pitfall P-45: P5c Must Never Rewrite `FULL_COPY` Outputs

**THE TRAP (bug report: GitHub #22):**
```python
# WRONG: full-copy .tcl files are read off disk, reformatted, and rewritten
_NORMALIZED_TREATMENTS = frozenset({
    FileTreatment.FULL_COPY,
    FileTreatment.PROC_TRIM,
    FileTreatment.GENERATED,
})
```

When P5c was first introduced (0.8.4) it normalized indentation for **every** emitted `.tcl` file, including `FULL_COPY` outputs. That violates the F1 `FULL_COPY` contract: a full-copy file is supposed to land on disk byte-for-byte identical to the source. The 1.2.6 regression in `power/onepower/basic.tcl` was a textbook symptom — a base-included `.tcl` file with mixed tab/space indentation and a missing trailing `}` was reformatted **and** had a synthetic closing brace appended by the running brace counter, then the post-trim brace check (`VE-16`) fired against the *rewritten* file even though the proc set was untouched.

**Correct Behavior:** P5c reads and rewrites only files that Chopper itself produced — `PROC_TRIM` outputs (whose contents Chopper already changed when it deleted dropped procs) and `GENERATED` `.tcl` artifacts (whose contents Chopper authored from scratch). `FULL_COPY` outputs are never touched by P5c regardless of extension. If a `FULL_COPY` source already has a brace imbalance or odd indentation, that is a property of the input domain and surfaces as the same property in the output domain — Chopper does not mutate user-authored bytes silently to make them pretty.

**Implementation Requirement:**
- `_NORMALIZED_TREATMENTS` in `src/chopper/trimmer/indentation.py` must equal `frozenset({FileTreatment.PROC_TRIM, FileTreatment.GENERATED})`. Adding `FULL_COPY` reopens issue #22.
- `_with_updated_bytes` in P5c must update `TrimReport.bytes_out` only for `PROC_TRIM` outcomes. `FULL_COPY` byte counts are pinned at the source byte size during P5a and never re-stamped.
- The `rewritten_paths` tuple returned by `TclIndentationService.run` must contain only `PROC_TRIM` and `GENERATED` `.tcl` paths. P6 `validate_post` re-tokenizes exactly that set; `FULL_COPY` outputs are excluded from re-tokenization because they are byte-identical copies of the source.

**Why It Matters:** Domain owners list legacy Tcl files in `files.include` precisely because they want those files preserved as-is. Reformatting them silently — even cosmetically — destroys diff-ability against the original source, can introduce real bugs (the appended `}` in basic.tcl was syntactically wrong relative to the source), and turns a "kept file" decision into an unannounced rewrite. P5c is a readability pass for files Chopper *had* to produce; it is not a global Tcl beautifier.

**Tests:**
- `tests/unit/trimmer/test_indentation.py::test_service_formats_proc_trim_and_generated_but_not_full_copy_tcl`
- `tests/integration/test_runner_localfs_e2e.py::test_runner_localfs_live_trim_formats_proc_trim_and_generated_tcl_only`

---


---

## 4. Validator Module

**TC-07 — Validation Quality:** Validation must catch broken Tcl syntax, missing files, unjustifiable proc references, and F3 output pointing to trimmed-away content. Diagnostics must use stable IDs, severities, and actionable hints so CI, text reports, and future UIs all consume the same signal.

### Pitfall P-16: Cross-Validation of Proc References

**THE TRAP:**
```python
# Proc included in JSON but file doesn't exist:
{"file": "nonexistent.tcl", "procs": ["my_proc"]}
# WRONG: silently ignore
# CORRECT: emit ERROR diagnostic
```

**Correct Behavior:** Validate that every proc entry in JSON actually exists in the domain.

**Implementation Requirement:**
- For each proc in procedures.include:
  - Verify the source file exists in domain
  - Verify the proc is defined in that file
  - If not: emit ERROR with code "VAL-PROC-01"
- For procedures.exclude: same validation

**Why It Matters:** Typos in JSON go unnoticed otherwise; leads to silent logic errors.

**Test:** Scenario: JSON references `nonexistent.tcl::helper`. Validator must emit ERROR.

---

### Pitfall P-17: Trace Expansion Must Validate Proc Existence

**THE TRAP:**
```python
# Proc A calls Proc B, but Proc B doesn't exist:
# Tracer should emit WARNING, not crash
```

**Correct Behavior:** When tracing discovers a proc call that doesn't resolve:
- Log literal unresolved calls as WARNING `TW-02`
- Log dynamic or otherwise unmodelable call forms as WARNING `TW-03`
- Include location (file + line) in diagnostic
- Suggest owner review

**Implementation Requirement:**
- Trace expansion must surviv unresolved references gracefully
- Emit diagnostics, not exceptions
- Continue tracing other procs

**Why It Matters:** Dynamic code or external-domain references are expected; must not crash.

**Test:** Scenario: Proc calls external proc. Tracer logs WARNING, continues.

---


---

## 5. Audit & Diagnostics

### Pitfall P-18: All Diagnostics Must Include Location

**THE TRAP:**
```python
# WRONG:
diagnostic = Diagnostic(message="File not found")
# CORRECT:
diagnostic = Diagnostic(
    message="File not found",
    location="jsons/base.json:files.include[2]",  # or "fev_formality/utils.tcl:42"
    code="CONFIG-FILE-01"
)
```

**Implementation Requirement:**
- Every diagnostic must have a `location` field
- For JSON errors: `filename:path.to.field[index]`
- For parser errors: `filename:line_number:column` (1-indexed)
- For compiler errors: `canonical_name` + context

**Why It Matters:** Owner must be able to find and fix each error in source.

**Test:** All diagnostic types must carry location context.

---

### Pitfall P-19: Audit Artifacts Must Be Deterministic

**THE TRAP:**
```python
# WRONG: iterate over dict/set (order undefined in Python <3.7)
for key in diagnostics_dict.keys():  # Non-deterministic order
    output.write(json.dumps(key))
# Result: same input produces different output

# CORRECT: deterministic ordering
sorted_keys = sorted(diagnostics_dict.keys())
for key in sorted_keys:
    output.write(json.dumps(key))
```

**Implementation Requirement:**
- All serialized output (manifest.json, trace_report.json, etc.) must use sorted keys
- Use `json.dumps(..., sort_keys=True)`
- Preserve user-authored ordered collections in authored order (selected features, stages, stage steps, flow actions)
- Sort only inherently unordered or discovery-derived collections (inventories, normalized sets, diagnostics when no authored order exists)
- Same input always produces byte-for-byte identical output

**Why It Matters:** Reproducibility; allows comparison of two trim runs via checksums.

**Test:** Run trim twice with identical inputs; verify bit-identical audit artifacts.

---


---

## 6. Backup & Recovery

### Pitfall P-20: Backup Detection and Manual Recovery

**THE TRAP:**
```python
# WRONG: Always create a backup, even if one already exists
os.rename(domain, domain_backup)  # Overwrites any existing _backup!

# CORRECT: Detect backup, decide action
if domain_backup_exists():
    rebuild_from_backup()  # Re-trim scenario
else:
    os.rename(domain, domain_backup)  # First trim
```

**Implementation Requirement:**
- Before trim, check if `domain_backup/` exists
- If it exists: rebuild the trimmed domain from the backup (re-trim scenario)
- If it doesn't exist: create the backup by renaming `domain/` to `domain_backup/`
- Users can manually restore a domain by renaming `domain_backup/` back to `domain/` if desired
- `cleanup` removes the `domain_backup/` directory when the trim window is complete (requires `--confirm`)

**Why It Matters:** Enables re-trim without loss of work, and supports manual recovery if needed.

**Test:** Scenario 1: First trim creates backup and builds trimmed domain. Scenario 2: Re-run detects backup and rebuilds from it without duplicating. Scenario 3: User can manually rename backup to restore domain.

---


---

## 7. Configuration & Paths

**TC-10 — Boundary Discipline:** Chopper must never accidentally reach and trim outside the domain trim scope. Path validation is the primary enforcement mechanism.

### Pitfall P-21: Always Normalize Paths to POSIX Forward Slashes

**THE TRAP:**
```python
# Windows:
path = "sub\\file.tcl"  # Backslashes
manifest = {"file": "sub\\file.tcl"}  # Manifest has backslashes
# When comparing later on Windows: OK
# When checking out on Linux: manifest won't match; broken

# CORRECT:
path = PurePosixPath(path).as_posix()  # Always "sub/file.tcl"
manifest = {"file": "sub/file.tcl"}  # Portable
```

**Implementation Requirement:**
- All paths stored in JSON use forward slashes
- Internally use `pathlib.PurePosixPath` for domain-relative paths
- Use `pathlib.Path` for filesystem operations (OS-native)
- Convert between them explicitly at boundaries

**Why It Matters:** Artifacts must be portable across Windows/Linux/macOS.

**Test:** Cross-platform test: trim on Windows, verify JSON on Linux.

---

### Pitfall P-22: Config File Path Resolution

**THE TRAP:**
```python
# User supplies relative path in .chopper.config:
common_path = "global/snps/common"
# WRONG: resolve relative to current working directory (unstable)
# CORRECT: resolve relative to config file location
config_dir = Path(".chopper.config").parent
common_path = (config_dir / common_path).resolve()
```

**Implementation Requirement:**
- Relative paths in `.chopper.config` are resolved relative to the config file location
- Absolute paths are used as-is
- After resolution, path must exist or emit error

**Why It Matters:** Config file is more portable if paths are relative to config location.

**Test:** Config file in subdirectory; verify path resolution is correct.

---


---

## 8. CLI & Presentation

### Pitfall P-23: Dry-Run Must Not Modify Filesystem

**THE TRAP:**
```python
if args.dry_run:
    # WRONG: still create domain_backup
    os.rename(domain, domain_backup)
    # Then fail partway through
    # Result: domain is corrupt

# CORRECT: skip all filesystem writes
if args.dry_run:
    return compiled_manifest  # Return results without writing
```

**Implementation Requirement:**
- `--dry-run` must produce full compilation + manifest + diagnostics
- Must NOT create domain_backup or write any files to domain/
- Must output manifest.json to stdout or `--output` file instead

**Why It Matters:** Dry-run allows domain owners to preview trim without risk.

**Test:** Scenario: `trim --dry-run` on live domain. Verify no filesystem changes.

---

### Pitfall P-25: Project JSON Paths Resolve Relative to the Operational Domain Root

**THE TRAP:**
```python
# User runs Chopper from the domain root fev_formality/
# project.json lives at ../configs/project_abc.json
# contains: "base": "jsons/base.json"
#
# WRONG: resolve relative to project JSON file location
base_path = Path("../configs/") / "jsons/base.json"
# Result: ../configs/jsons/base.json (doesn't exist there)
#
# CORRECT: resolve relative to the operational domain root (RunConfig.domain_root)
base_path = ctx.config.domain_root / "jsons/base.json"
# Result: fev_formality/jsons/base.json (correct)
```

**Correct Behavior:** `base` and `features` paths inside a project JSON are resolved relative to the operational domain root recorded on `RunConfig.domain_root`, NOT relative to the project JSON file location. The domain root is computed by the CLI per ARCHITECTURE §5.1 priority: `--domain` (highest) → backup-cwd suffix-strip guard → `Path.cwd()`.

**Implementation Requirement:**
- CLI layer computes the operational domain root via `_resolve_domain_root` (priority above)
- CLI layer loads project JSON, extracts `base` and `features` fields
- Resolves all project-JSON-relative paths against `RunConfig.domain_root`
- Default expected curated JSON locations under the domain are `jsons/base.json` and `jsons/features/*.feature.json`
- The project JSON file itself can live anywhere (e.g., `configs/`, `projects/`, outside the repo)
- The project JSON `domain` field must match `domain_root.name` (case-insensitive `casefold()`); see VE-17
- After resolution, passes fully resolved `Path` objects into the `RunConfig` bound by `ChopperContext`
- Phase 1 validation (`VE-13 project-path-unresolvable`) catches unresolvable paths

**Why It Matters:** This is the #1 probable mistake for project JSON implementers. The path resolution convention is intentional — it keeps project JSONs portable.

**Test:** Run from `fev_formality/` with a project JSON in `../configs/` referencing `jsons/base.json`. Verify the path resolves to `fev_formality/jsons/base.json`.

---

### Pitfall P-26: `--project` Is Mutually Exclusive with `--base`/`--features`

**THE TRAP:**
```bash
# WRONG: user provides both
chopper trim --project p.json --base jsons/base.json
# What happens? Which base wins?
```

**Correct Behavior:** Reject immediately with exit code 2 and an actionable error message. Do not attempt to merge or guess.

**Implementation Requirement:**
- In argparse setup, create a mutually exclusive group for `--project` vs `--base`/`--features`
- If both are provided: fail with exit code 2 and a clear message like: `"--project is mutually exclusive with --base and --features. Use one mode or the other."`
- Validation check `VE-11 conflicting-cli-options` (exit code 2) covers this case

**Why It Matters:** Ambiguous input modes produce unpredictable behavior and break reproducibility.

**Test:** Scenario: `chopper trim --project p.json --base b.json` → exit code 2.

---

### Pitfall P-27: `--strict` Changes Exit Behavior

**THE TRAP:**
```python
# Without --strict: warnings are exit 0
# With --strict: warnings become errors → exit 1
# If implementer doesn't check strict flag: warnings silently pass in CI
```

**Correct Behavior:** When `--strict` is enabled (via CLI flag or `validation.strict = true` in `.chopper.config`), all WARNING-severity diagnostics are escalated to ERROR. This changes the final exit code from 0 to 1 if any warnings were emitted.

**Implementation Requirement:**
- After collecting all diagnostics, if `--strict` is active, re-classify any WARNING as ERROR
- Recalculate the exit code based on the escalated diagnostics
- `VW-01 file-in-both-include-lists` (and related soft-mismatch warnings) is the primary case: normally WARNING, escalated to ERROR under `--strict`

**Why It Matters:** CI pipelines rely on exit codes to gate merges. `--strict` ensures warnings do not silently pass.

**Test:** Scenario: trim with a `VW-01` overlap warning. Without `--strict`: exit 0. With `--strict`: exit 1.

---

### Pitfall P-28: `chopper cleanup` Requires `--confirm`

**THE TRAP:**
```bash
# WRONG: user forgets --confirm
chopper cleanup
# What happens? Silently deletes backup?
```

**Correct Behavior:** Refuse to run. Emit exit code 2 with message: `"cleanup requires --confirm to proceed. This action is irreversible."`

**Implementation Requirement:**
- `--confirm` is a required flag for cleanup (not optional with a default)
- Without `--confirm`: exit code 2, no filesystem changes
- With `--confirm`: proceed with backup removal
- The CLEANED state is terminal and irreversible

**Why It Matters:** Cleanup permanently deletes `domain_backup/`. There is no undo. The `--confirm` flag forces conscious intent.

**Test:** Scenario: `chopper cleanup` without `--confirm` → exit code 2, backup untouched.

---


---

## 9. Hook Files

**TC-05 — File Dependency Detection:** Chopper must correctly capture `source` and `iproc_source` references, including flags and hooks. Required vs optional references and `-use_hooks` behavior must follow R3 exactly and be reflected in diagnostics and manifests.

### Pitfall P-29: Hook Files from `-use_hooks` Are Discovery-Only

**THE TRAP:**
```tcl
# In main.tcl:
iproc_source -file setup.tcl -use_hooks
# Domain has pre_setup.tcl and post_setup.tcl

# WRONG assumption: Chopper will automatically include pre_setup.tcl and post_setup.tcl
# CORRECT: Chopper discovers them (reported in scan artifacts) but does NOT copy them
```

**Correct Behavior:** When Chopper encounters `iproc_source -file X -use_hooks`, it detects the corresponding `pre_X` and `post_X` hook files as candidates. These appear in `scan_report.json`, `file_inventory.json`, and `dependency_graph.json`. But they are **NOT** copied during trim unless the domain owner explicitly adds them to `files.include` in the selected JSON.

**Implementation Requirement:**
- During scan/analysis: record hook file candidates in the file dependency graph
- During trim compilation: hook files are treated like any other file — they survive only if they appear in `files.include`
- There is no `HOOK_AUTO` keep reason. Hook files use the normal `explicit-file` reason if included.
- Warn in scan output that discovered hook files require explicit inclusion

**Why It Matters:** The old hook-auto behavior was removed by design (see [ARCHITECTURE.md](ARCHITECTURE.md) Q12). Restoring it silently would re-bloat trimmed domains.

**Test:**
- Scenario: Domain has `setup.tcl` + `pre_setup.tcl` + `post_setup.tcl`. Base JSON includes only `setup.tcl` in `files.include`. After trim: `pre_setup.tcl` and `post_setup.tcl` must NOT appear in the trimmed domain.
- Scenario: Same domain, but base JSON adds `pre_setup.tcl` to `files.include`. After trim: `pre_setup.tcl` survives, `post_setup.tcl` does not.

---


---

## 10. Project JSON

### Pitfall P-30: Project Metadata Must Flow Through to Audit Artifacts

**THE TRAP:**
```python
# CLI loads project JSON, extracts base + features
# WRONG: discards project name, owner, notes before building RunConfig
config = RunConfig(
    domain_root=domain,
    backup_root=backup,
    audit_root=audit,
    # project_json, project_name, project_owner, release_branch, project_notes all missing!
)
# Result: audit artifacts have no record that --project was used
```

**Correct Behavior:** When `--project` is used, the CLI layer must populate ALL project-related fields on `RunConfig` (the engine-behavior record inside `ChopperContext`, per [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §1.6.1):
- `project_json` — path to the project JSON file
- `project_name` — from `project` field
- `project_owner` — from `owner` field
- `release_branch` — from `release_branch` field
- `project_notes` — from `notes` array

These fields flow through `ConfigService` → `CompiledManifest` and are written into `chopper_run.json` and `compiled_manifest.json` by `AuditService`.

**Implementation Requirement:**
- CLI layer: parse project JSON, populate all `RunConfig` project fields before constructing `ChopperContext`
- Service layer: pass project fields through to `LoadedConfig` and `CompiledManifest`
- Audit writer: serialize project fields into `chopper_run.json` and `compiled_manifest.json`
- When `--project` is NOT used: these fields are empty strings / None / empty tuples

**Why It Matters:** The audit trail must capture WHY a particular selection was made. Without project metadata, the audit trail shows WHAT was selected but not the project-level context.

**Test:** Trim with `--project`. Verify `chopper_run.json` contains `project_json_path`, `project_name`, `project_owner`, `release_branch`. Trim with `--base`/`--features`. Verify those fields are absent or null.

---

### Pitfall P-31: Project JSON Domain Must Match the Operational Domain Root

**THE TRAP:**
```bash
# User runs from sta_pt/
# Project JSON says: "domain": "fev_formality"
# CLI also passes --domain ./
# Which root wins?
```

**Correct Behavior:** The operational domain root is computed by the CLI per ARCHITECTURE §5.1 priority list: `--domain` (highest) → backup-cwd suffix-strip guard → `Path.cwd()`. The project JSON `domain` field is a consistency identifier and must match `domain_root.name` (case-insensitive). When `--domain` is provided, it is the source of truth — cwd is **not** consulted, and there is no separate "cwd does not match `--domain`" exit-2 gate. Mismatch between `domain_root.name` and the project's `domain` field is reported as `VE-17` (exit 1).

**Implementation Requirement:**
- Compute the operational domain root via the priority list and store it on `RunConfig.domain_root`
- Use `RunConfig.domain_root` (not `Path.cwd()`) as the verified domain root for project path resolution
- Require `project_json["domain"].casefold() == domain_root.name.casefold()` (→ VE-17 on miss)
- Do **not** validate `--domain` against `Path.cwd()` — `--domain` is authoritative on its own

**Why It Matters:** This freezes one path root for the whole run and avoids hidden path-resolution branches.

**Test:** 
- `cd fev_formality && chopper trim --project ../configs/p.json`: succeeds only if the project JSON says `"domain": "fev_formality"`
- `cd sta_pt && chopper trim --project ../configs/p.json`: exit code 2 if the project JSON says `"domain": "fev_formality"`
- `cd fev_formality && chopper trim --project ../configs/p.json --domain $(pwd)`: succeeds
- `cd fev_formality && chopper trim --project ../configs/p.json --domain ../sta_pt`: exit code 2 with a mismatch diagnostic

---


---

## 11. Testing Strategy

### Pitfall P-24: Edge Case Fixtures Must Be Tested Early

**THE TRAP:**
```
Stage 1: Implement parser, defer edge-case fixtures to later stages
Stage 2 or later: Add edge case tests
Result: Major bugs discovered after the compiler is already built on top of an untested parser, forcing cross-stage rework
```

**Implementation Requirement:**
- Implement parser and all fixtures together within Stage 1 — the Parser module is not complete until every fixture passes
- All 15+ fixture categories must pass before Stage 2 (Compiler) begins
- Property-based tests for invariants (span consistency, no overlaps, etc.) are part of Stage 1 acceptance

**Why It Matters:** Parser is the critical path; every later stage consumes its typed output (`list[ProcEntry]`). Failures here cascade into the compiler, trimmer, and validator.

**Test:** All fixtures from this doc §1.9 must pass before Stage 1 is declared complete.

---


---

## 12. Quick Reference: Common Mistakes by Module

| Module | Mistake | Prevention |
|--------|---------|-----------|
| **Parser** | Quotes treated as inert inside braced bodies (old, incorrect rule) | Apply Tcl Endekas rule 5: `"` opens a quoted word at any brace depth; track `quoted_bracket_depth` (P-01) |
| **Parser** | Quote-open detection that ignores boundary context can open phantom quoted words inside brace words and swallow the closing `}` (false `PE-02`) — e.g. `set q {"}`, `regexp {".*"} $line`, `string map {" " ""}` | Enforce rule-5 word-boundary whitelist (SOF/whitespace/`;`/`[`) and treat other prefixes as literal quote bytes; this subsumes the old single-byte `{` guard (P-01a) |
| **Parser** | Line continuation corrupts line numbers | Don't physically join lines (P-02) |
| **Parser** | Namespace context resets incorrectly | LIFO stack management (P-03) |
| **Parser** | Computed proc names not skipped | Log `PW-01`, skip proc (P-04) |
| **Parser** | Duplicate proc not flagged | Log `PE-01`, use last span (P-05) |
| **Parser** | Args nested defaults cause premature body detection | Track full brace depth through args word; body `{` only at original depth (P-32) |
| **Parser** | DPA block left as orphan after proc drop | Record `dpa_start_line`/`dpa_end_line`; drop atomically with proc (P-33) |
| **Parser** | Comment banner orphaned after proc drop | Record `comment_start_line`/`comment_end_line`; drop atomically with proc (P-34) |
| **Parser** | DPA proc name extracted as false call dependency | Extract first word only; Level 2c suppression filter (P-35) |
| **Parser** | `foreach_in_collection` not in control-flow keywords | Add to `CONTROL_FLOW_KEYWORDS`; push `CONTROL_FLOW` context (P-36) |
| **Parser** | `regexp`/`regsub`/`exec`/`glob` brace args walked as code | Pre-pass marks opaque `{…}` token ranges as skip; recurse into code-block braces (P-38) |
| **Parser** | `switch` pattern labels extracted as proc calls | Pre-pass marks odd-indexed body WORDs as skip (P-39) |
| **Parser** | DPA name parser concatenates option-list fragments | Take first whitespace-token after keyword; ignore option list entirely (P-40) |
| **Parser** | `\[` in a quoted string extracted as a proc-call candidate | Count preceding backslashes at match position; skip on odd count (P-46) |
| **Parser** | Brace-delimited switch pattern `{[a-z]+}` generates false call candidates | Alternating pattern/body state in `mark_switch_pattern_words`; mark brace-pattern blocks opaque (P-47) |
| **Parser** | `lassign`, `subst`, `apply`, `throw`, `lmap` etc. generate spurious TW-02 | Add missing Tcl 8.5+/8.6+ builtins to `TCL_BUILTINS` (P-48) |
| **Compiler/Validator** | Diagnostics serialise with `"file": null` | P4/P6 emit sites must pass `path=`; recover from canonical name where ProcEntry is absent (P-41) |
| **Compiler** | Glob-matched non-Tcl files silently absent from manifest | (1) Pass full surface paths (not Tcl-only `parsed_paths`) to `_extract_facts`; (2) Add `fi_glob_surviving` to `_collect_universe`; F1 is file-type agnostic (P-42) |
| **Trimmer** | Adjacent drop-ranges leave blank-line artifacts | Coalesce adjacent/overlapping ranges before deletion pass (P-37) |
| **Compiler** | Trace expansion is non-deterministic | Require exact match, not ambiguous (P-08) |
| **Compiler** | Excludes override includes | Remember: include wins (P-09) |
| **Compiler** | Glob results include duplicates | Normalize + deduplicate (P-11) |
| **Trimmer** | Crash leaves domain half-rebuilt | Backup-and-rebuild model with deterministic safe re-run from `domain_backup/` (P-13) |
| **Trimmer** | Lost work on re-trim | Detect existing backup and rebuild from it (P-20) |
| **Trimmer** | `FULL_COPY` decodes opaque files as text | Use filesystem-level opaque copy; reserve content reads to Tcl `PROC_TRIM` only (P-44) |
| **Trimmer** | P5c rewrites `FULL_COPY` `.tcl` and breaks the verbatim contract | Scope `_NORMALIZED_TREATMENTS` to `{PROC_TRIM, GENERATED}`; `FULL_COPY` `.tcl` outputs are byte-for-byte copies and must never reach the indentation pass (P-45) |
| **Validator** | Typos in JSON go unnoticed | Validate JSON references exist (P-16) |
| **Audit** | Diagnostics lack context | Include location in every diagnostic (P-18) |
| **Config** | Paths break on different OS | Always use forward slashes (P-21) |
| **CLI** | Dry-run modifies filesystem | Skip all writes when `--dry-run` (P-23) |
| **CLI** | Project JSON paths resolve wrong | Resolve relative to the current working directory / domain root, not the project file (P-25) |
| **CLI** | `--project` + `--base` both provided | Mutually exclusive — exit code 2 (P-26) |
| **CLI** | `--strict` not checked | Escalate warnings to errors, change exit code (P-27) |
| **CLI** | Cleanup runs without `--confirm` | Require `--confirm` — exit code 2 without it (P-28) |
| **Hooks** | Hook files auto-copied from `-use_hooks` | Discovery-only; must be in `files.include` (P-29) |
| **Project** | Project metadata lost in audit | Populate all `RunConfig` project fields (P-30) |
| **Project** | Domain mismatch with project JSON | Require current working directory consistency and reject mismatches (P-31) |

---


---

## 13. Standalone Risk Items

These technical challenges have no dedicated pitfall entries but remain important architectural constraints.

### TC-06: Non-Tcl Handling

Non-Tcl files are intentionally file-level only. Attempting to over-interpret non-Tcl files adds cost without strong product value.

### TC-09: Template Generation

Template-script generation is **not** a Chopper v1 feature and is not reserved in the schema. Previous drafts kept an `options.template_script` field with diagnostic `VE-18 template-script-path-escapes` as a reserved hook — that field and that diagnostic have been removed in line with the scope-lock policy (no reserved seams). If a future version wants template generation, it will be filed as `FD-12 template-script-generation` and re-introduced through the architecture-doc-first cascade. Domain-specific generation logic stays outside the Chopper core.

---


---

## Appendix A: Permanently Out of Scope

These items have been evaluated and **permanently excluded**. They will not be implemented in any version of Chopper. Do not plan, design, or prototype any of these.

| ID | Item | Rationale |
|---|---|---|
| OOS-01 | Non-Tcl subroutine-level trimming | Non-Tcl files (Perl, Python, shell) are file-level only by design. Subroutine-level parsing for non-Tcl languages is not a requirement. |
| OOS-02 | Computed proc name extraction | Procs with dynamic names (`proc ${prefix}_helper`) are skipped with `PW-01`. Heuristic resolution adds complexity with no practical value. |
| OOS-03 | Pipeline checkpointing | No domain exceeds 200 MB. Full restart from Phase 1 is acceptable. The `compiled_plan.json` resumption idea is unnecessary. |
| OOS-04 | Auto-draft JSON / scan mode | Scan mode was considered and explicitly removed. Chopper does not generate draft JSONs. Domain owners author JSONs manually; `--dry-run` is the authoring iteration feedback loop. |

---


---

## Appendix B: Deferred Work Items

These items have been considered and **deferred** from the v1 release. They are recorded so future authors know what was thought about and why it was not built. An FD-xx entry is **not a TODO** — many will stay deferred indefinitely. Adding any of these requires re-entering the architecture-doc-first cascade specified in `.github/instructions/project.instructions.md`.

### B.1 Parser Enhancements

### FD-01: Advanced Namespace Resolution

The following Tcl namespace features are out of scope and are never guessed. They emit `TW-03` (unresolvable call form) when encountered:

- `namespace import`
- Command path lookup (`namespace path`)
- `namespace unknown` handlers
- Runtime aliasing / `interp alias`
- Runtime redefinition order across sourced files

**Source:** this doc §6.3, `technical_docs/ARCHITECTURE.md` §4.6

---

### B.2 Compiler / Pipeline Enhancements

### FD-02: Cross-Domain Dependency Awareness

v1 treats domains as fully isolated. Cross-domain proc calls are logged as `TW-02` (unresolved) but never traced. A future version could optionally accept a multi-domain manifest for read-only cross-domain call validation (not trimming).

**Source:** `technical_docs/ARCHITECTURE.md` §2.2, Q1

### FD-14: Feature Replacement Semantics

**ADOPTED in 2.0.0-alpha.** Adopted as the design baseline. See [`technical_docs/ARCHITECTURE.md`](ARCHITECTURE.md) §4 (R1 ordered overlay). The original FD-14 proposal was the seed of the overlay model: features are now layered, not additive, and the last layer that mentions a file or proc wins. A feature can therefore add new content, remove base content, or replace base content with its own — exactly the use case this FD called out. The previous additive-only semantics with `VW-18` / `VW-19` cross-source vetoes are retired.

---

### B.3 CLI / UX Enhancements

### FD-03: Interactive Feature Selection TUI

Provide a terminal-based interactive UI for browsing available features, previewing their effects, and composing a project JSON.

**Deferred because:** CLI-first approach is correct today. The service-layer and renderer-adapter architecture (`technical_docs/ARCHITECTURE.md` §5.11) enables this without engine changes.

### FD-04: GUI Client

A machine-readable stdio wire protocol for a future GUI client is documented in `technical_docs/ARCHITECTURE.md` §5.11.3 and in [`FD-10`](#fd-10-machine-readable-cli-output). The wire-level JSON payload is conventionally called a "TrimRequest" envelope; on the Python side it deserializes into `RunConfig` + `PresentationConfig` consumed by `ChopperRunner.run(ctx) -> RunResult`. There is no Python class named `TrimRequest` — the engine boundary is `ChopperContext` in, `RunResult` out (see [`technical_docs/ENGINEERING.md`](ENGINEERING.md) §6). Progress events will be emitted as JSON lines on stderr. Not implemented here but architecturally enabled by the service-layer, serialization, and renderer-adapter contracts defined in §5.11.

GUI-relevant data surfaces (file selection, proc selection, dependency graph, trim stats, JSON viewing, diagnostics) are enumerated in §1.5.11.5. No additional data models or artifacts are needed — the current pipeline already produces everything a GUI would consume.

### FD-13: Host-Integrated GitHub Issue Attachment Upload

The Chopper Agent may package local evidence and create a GitHub issue body automatically, but v1 does not standardize binary attachment upload to the created issue. GitHub's attachment flow is host- and credential-dependent: browser UI upload works today, while CLI/API support for issue attachments varies by environment and is not exposed through a stable Chopper-owned contract.

If future users require truly end-to-end companion filing, this FD would define:

- which host transports are allowed (`gh`, browser automation, extension API, or none)
- how credentials are sourced and validated without expanding Chopper's runtime surface
- size and file-type limits for uploaded bundles
- failure behavior when issue creation succeeds but attachment upload does not

**Deferred because:** packaging plus issue-body creation solves the reproducibility problem today without forcing Chopper to own browser automation, token storage, or an unstable GitHub attachment API.

---

### B.4 Documentation Enhancements

### FD-05: Quick-Start Guide

Add a quick-start section to the architecture doc with a minimal end-to-end walkthrough.

**Source:** `technical_docs/ARCHITECTURE.md` §13.4, DF-01

### FD-06: Example Diagnostic Messages

Add concrete example error/warning messages to the architecture doc for every diagnostic code.

**Source:** `technical_docs/ARCHITECTURE.md` §13.4, DF-02

### FD-07: Terminology Glossary

Add a terminology note distinguishing "capability" (F1/F2/F3) from "feature JSON" (a JSON file that extends the base).

**Source:** `technical_docs/ARCHITECTURE.md` §13.4, DF-03

---


---

### FD-10: Machine-Readable CLI Output

v1's CLI emits human-readable table output only. A `--json` or `--jsonl` mode would emit `RunResult` (and progress events) as structured lines on stdout so downstream tooling (CI dashboards, a future GUI, ad-hoc scripts) can consume them without scraping tables.

Post-v1, this is ~50 lines of code in `cli/render.py` plus a test fixture — `RunResult` already serializes via `core/serialization.py` and `PresentationConfig` already has a rendering seam. The deferral is solely to keep v1's user surface minimal and let the table renderer bed in before committing to a machine-output contract.

**Deferred because:** v1 is a push-button tool for one operator on one domain; structured output solves a problem (programmatic consumption) that no v1 user has. Shipping it now would freeze the JSON shape before the core pipeline has proved itself.

**Source:** `DAY0_REVIEW.md` A1 (CLI flag inventory decision).

---



---

### FD-12: Template-Script Generation

Some domains may want Chopper to execute a domain-specific post-trim script that generates derived artifacts (lint reports, project-level `run.tcl` wrappers, tool-specific setup files). Earlier spec drafts carried an `options.template_script` schema field and a `VE-18` diagnostic for path-safety validation, with the intent that v1 would validate the path but not execute the script ("reserved seam").

Per the scope-lock policy in [`.github/instructions/project.instructions.md`](../.github/instructions/project.instructions.md), reserved seams with registered diagnostics are not allowed. The field and the diagnostic have been removed. If a future version wants template generation, it will file this FD-12 entry as the starting point and re-enter the architecture through the architecture-doc-first cascade: spec the execution contract (sandbox? arguments? failure mode?), then reintroduce the schema field and diagnostic in a new code slot.

**Deferred because:** domain owners today can run their generation scripts before or after `chopper trim` themselves. Baking an executor into Chopper commits the tool to a security surface (what paths are allowed? what exit-code policy?) that has no v1 caller demanding it.

**Source:** `DAY0_REVIEW.md` G2; scope-lock policy (`.github/instructions/project.instructions.md` §1).

---

### FD-15: Companion-File Sync for ERRGEN Config (`default_rules` pattern)

#### What

A silent post-trim behavior triggered when a file whose POSIX basename matches `default_rules.<sfx>.tcl` receives **PROC_TRIM treatment** — meaning the final compiled PI set (accounting for both `procedures.include` **and** `procedures.exclude` across all feature layers merged via R1 overlay) retains only a subset of its procs. After the trimmer drops procs from the rules file, Chopper also:

1. **Filters the companion CSV** — removes any row whose first comma-separated column (proc name, stripped) is not in the final surviving PI set. The line is deleted entirely; no blank placeholder is left. Original blank lines and `#`-comment lines in the file are kept unchanged.
2. **Prunes the companion milestone** — removes `change_config <ProcName> ...` lines where `<ProcName>` is not in the final surviving PI set. The line is deleted entirely; no blank placeholder is left.

No CLI flag. No schema field. No user-visible output beyond optional `VW-xx` warnings when a companion file is expected but absent. Triggered solely by the naming convention of the trimmed file.

#### Naming convention and file discovery

Given a trimmed file at `<dir>/default_rules.<sfx>.tcl`:

| Companion | Derived path | Required? |
|---|---|---|
| Config CSV | `<dir>/default_config.<sfx>.csv` | Warn `VW-xx companion-file-missing` if absent, then skip |
| Milestone Tcl | `<dir>/default_milestone.<sfx>.tcl` | Warn `VW-xx companion-file-missing` if absent, then skip |

Example for Formality (`<sfx>` = `fm`):
- Rules: `default_rules.fm.tcl` → CSV: `default_config.fm.csv`, Milestone: `default_milestone.fm.tcl`

Example for Conformal (`<sfx>` = `cfm`):
- Rules: `default_rules.cfm.tcl` → CSV: `default_config.cfm.csv`, Milestone: `default_milestone.cfm.tcl`

The suffix `<sfx>` is any single dot-separated token between `default_rules.` and `.tcl`. The pattern match is applied to the POSIX basename of every PROC_TRIM file in the domain; depth in the directory tree does not matter.

#### CSV modification algorithm

```
For each line in default_config.<sfx>.csv (in order):
  stripped = line.strip()
  if stripped == "" or stripped.startswith("#"):
    keep the line unchanged          # original blanks and comments survive
  else:
    col0 = stripped.split(",")[0].strip()
    if col0 in final_pi_proc_names:
      keep the line unchanged
    else:
      drop the line entirely         # no blank placeholder; the line is gone
Write the retained lines back, preserving original line endings.
```

#### Milestone modification algorithm

```
For each line in default_milestone.<sfx>.tcl (in order):
  m = re.match(r'^\s*change_config\s+(\w+)\b', line)
  if m:
    proc_name = m.group(1)
    if proc_name NOT in final_pi_proc_names:
      drop the line entirely         # no blank placeholder; the line is gone
    else:
      keep the line
  else:
    keep the line (comments, blanks, other Tcl statements, etc.)
Write the retained lines back, preserving original line endings.
```

Note: original blank lines and non-`change_config` statements are kept as-is. Only `change_config` lines that reference a proc absent from the final PI set are removed.

#### Trigger conditions

- The trimmed domain contains at least one file whose POSIX basename matches `default_rules.*.tcl`.
- That file's treatment in the `TrimReport` is `PROC_TRIM` (not `FULL_COPY`, not `REMOVE`).
- The **surviving proc set** used to filter companion files is the **final compiled PI set** from `CompiledManifest` for the `default_rules.<sfx>.tcl` file. This accounts for both `procedures.include` and `procedures.exclude` contributions from all merged feature layers (R1 ordered overlay) — not merely the raw `procedures.include` list of any individual JSON. Procs excluded via `procedures.exclude` are absent from PI and therefore removed from the companion files.
- The companion files (`default_config.<sfx>.csv`, `default_milestone.<sfx>.tcl`) are declared as `files.include` entries in the base or feature JSON, so they receive FULL_COPY treatment and are unconditionally present in the rebuilt domain. The companion-sync pass operates on those already-written full copies and overwrites them in-place.
- The companion-sync pass runs after P3 (compile) and P4 (BFS trace) have completed, so the final PI set is fully resolved before any filtering decisions are made.

#### Where in the pipeline

This runs at the end of **P5** (build output), after `TrimmerService` has written the rebuilt domain and the `TrimReport` is available, but before P6 (post-validate) and P7 (audit). The companion files (`default_config.*.csv` and `default_milestone.*.tcl`) have already been full-copied into the rebuilt domain at this point; this step overwrites them in-place with the filtered versions.

The feature is implemented as a post-process pass in `TrimmerService` or as a thin co-worker called from the trimmer's `run()` method — it does not alter the `TrimReport` or any `CompiledManifest` fields.

#### Diagnostics (assigned in 2.0.1)

| Code | Slug | Condition | Exit effect |
|---|---|---|---|
| `VW-24` | `companion-file-missing` | Expected `default_config.<sfx>.csv` or `default_milestone.<sfx>.tcl` not found in the rebuilt domain | Warning only; sync skipped for the missing file |
| `VI-04` | `companion-sync-applied` | Companion file was present and was successfully filtered | Informational |

#### What would change in the architecture doc if adopted

- ✅ **Adopted in 2.0.1.** `technical_docs/ARCHITECTURE.md` §5.5 (P5 build output) was extended with a P5d companion-file sync sub-step. `technical_docs/DIAGNOSTIC_CODES.md` gained `VW-24 companion-file-missing` and `VI-04 companion-sync-applied`. Implementation is in `src/chopper/trimmer/companion_sync.py`, called from `src/chopper/orchestrator/runner.py` after P5c.

#### Why deferred

- The naming convention (`default_rules` / `default_config` / `default_milestone`) is specific to the fev_formality and fev_conformal EDA tool families. No other domains use it. Encoding it in the core trimmer adds domain-specific knowledge to a domain-agnostic tool.
- The CSV format is informal (no schema): any deviation in column order or quoting would silently corrupt the file. A formal companion-file declaration in the JSON (e.g., `options.companion_config`) would be safer but requires schema changes.
- The milestone pruning relies on a regex match on `change_config` — if other Tcl commands follow the same pattern in the milestone, they would be incorrectly removed.
- A cleaner long-term approach (FD-15b, not filed) would let the domain author declare companion relationships in the base JSON (`files.companions: [{source: "default_rules.fm.tcl", csv: "default_config.fm.csv", milestone: "default_milestone.fm.tcl"}]`) and let Chopper apply a general-purpose sync. That design requires schema changes and a more robust CSV/Tcl parser.

**Source:** User request 2026-05-22; fev_formality domain analysis.

---

### B.5 Summary Table

| ID | Category | Item | Status |
|---|---|---|---|
| FD-01 | Parser | Advanced namespace resolution | Out of scope for v1 |
| FD-02 | Pipeline | Cross-domain dependency awareness | Out of scope for v1 |
| FD-14 | Pipeline | Feature replacement semantics | **ADOPTED in 2.0.0-alpha** — R1 ordered overlay (see ARCHITECTURE.md §4) |
| FD-03 | CLI/UX | Interactive feature selection TUI | Architecturally enabled, deferred |
| FD-04 | CLI/UX | GUI client via JSON-over-stdio | Architecturally enabled, deferred (§1.5.11) |
| FD-05 | Docs | Quick-start guide | Deferred until spec final |
| FD-06 | Docs | Example diagnostic messages | Deferred until spec final |
| FD-07 | Docs | Terminology glossary | Deferred until spec final |
| FD-09 | Performance | Benchmark harness and phase budgets | Deferred until core pipeline verified |
| FD-10 | CLI/UX | Machine-readable CLI output (`--json` / `--jsonl`) | Deferred; v1 is table-only |
| FD-11 | Platform | Multi-platform domain support (trim on Windows) | Deferred; v1 is Linux-only |
| FD-12 | Generator | Template-script generation (post-trim executor) | Deferred; scope-lock removed the reserved seam |
| FD-13 | CLI/UX | Host-integrated GitHub issue attachment upload | Deferred; issue creation may be automated, binary attachment upload is not |
| FD-15 | Trimmer | Companion-file sync for ERRGEN config (`default_rules` pattern) | **ADOPTED in 3.4.1** — P5d in `src/chopper/trimmer/companion_sync.py`; `VW-24`, `VI-04` |
