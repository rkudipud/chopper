# Chopper — Tcl Parser Specification

> **Status:** Draft — Parser Engineering Baseline (Rev 7)  
> **Last Updated:** 2026-04-05  
> **Author:** Architecture review  
> **Implements:** AI-01 (Tcl parser / lexer prototype)

---

## 1. Purpose

This document specifies the tokenization, parsing, and indexing rules for Chopper's Tcl parser. The parser is the foundation of F2 (proc-level trimming) and transitive tracing. Every rule here is derived from the Tcl 8.6 Dodekalogue (the twelve rules that define Tcl syntax and semantics) and adapted for Chopper's static analysis context.

**Non-goal:** Chopper does not execute or interpret Tcl. It performs structural analysis only — finding proc boundaries, extracting namespace context, and identifying static call references.

---

## 2. Input Contract

| Property | Requirement |
|---|---|
| **Input unit** | One Tcl file at a time, identified by domain-relative path |
| **Encoding** | Attempt UTF-8 first; on decode failure, fall back to Latin-1 and log a WARNING diagnostic |
| **Line endings** | Normalize all line endings to `\n` on read (strip `\r`) |
| **Line indexing** | 1-indexed. Line 1 is the first line of the file |
| **Span convention** | Inclusive: `start_line=5, end_line=10` means lines 5, 6, 7, 8, 9, 10 |
| **Output** | A list of `ProcEntry` records (see §6) |
| **Diagnostics** | Emitted via optional `on_diagnostic: DiagnosticCollector` callback (see §8.4) |

### 2.1 Public Function Signature

```python
def parse_file(
    domain_path: Path,
    file_path: Path,
    on_diagnostic: DiagnosticCollector | None = None,
) -> list[ProcEntry]:
    """Parse a Tcl file and extract proc definitions.

    Args:
        domain_path: Absolute path to the domain root directory.
        file_path: Absolute path to the Tcl file to parse.
        on_diagnostic: Optional callback for emitting Diagnostic records
            (PARSER-DUP-01, PARSE-DYNA-01, PARSE-ENCODING-01, etc.).
            When None, diagnostics are silently discarded.

    Returns:
        List of ProcEntry records. May be empty (not an error).
    """
```

**Design rationale:** The parser is an internal utility module, not a top-level service endpoint. It returns `list[ProcEntry]` (not a result dataclass) because:
1. It is called by the compiler during Phase 2.4 — the compiler owns diagnostic aggregation.
2. The `DiagnosticCollector` callback pattern matches `ProgressSink.on_diagnostic`, allowing the compiler to bridge the two by passing `progress.on_diagnostic`.
3. Unit tests can call `parse_file()` with `on_diagnostic=None` for simplicity, or with a `list.append` callback to capture diagnostics.

---

## 3. Tokenization Rules

Chopper uses a simplified, brace-aware tokenizer that follows Tcl 8.6 Rules [1], [6], [9], and [10]. The tokenizer does NOT interpret variables, commands, or expressions — it only tracks structural delimiters.

### 3.1 Brace Matching (Tcl Rule 6)

Braces `{` and `}` define word boundaries in Tcl. Chopper must track brace depth accurately.

**Rules:**
1. An unescaped `{` increments brace depth by 1.
2. An unescaped `}` decrements brace depth by 1.
3. A brace preceded by an odd number of consecutive backslashes is **escaped** and does NOT affect depth.
4. Inside braces, no substitutions occur (no `$`, `[...]`, or `"` processing) — braces are opaque containers.
5. The only exception inside braces: backslash-newline (`\` immediately before `\n`) is a line continuation at the parser level. This affects the **line count** but does NOT affect brace depth.
6. Nested braces must balance: `{ { } }` is valid (depth goes 0→1→2→1→0).

**Why this matters:** Proc bodies are brace-delimited. Incorrect brace tracking means incorrect proc boundaries.

### 3.2 Backslash Continuation (Tcl Rule 9)

A backslash `\` immediately before a newline character joins the next line.

**Rules:**
1. When `\` appears immediately before `\n`, the parser treats the next line as a continuation of the current line.
2. Continuation only occurs when the backslash count before `\n` is **odd**.
3. For brace-depth tracking, continuation does NOT change depth — it only affects line numbering.
4. For line counting purposes, each `\n` in the source (including inside continuations) increments the line counter.

**Implementation note:** Do NOT physically join lines. Track them as separate source lines but recognize that a `\` at end-of-line means the logical command continues.

### 3.3 Double Quotes (Tcl Rule 4)

Double-quoted strings `"..."` group content and allow substitutions only when Tcl is parsing a quote-delimited word.

**Rules for Chopper:**
1. When the current word began with `"`, braces inside that quoted word do NOT affect brace depth. `set x "text { more"` keeps the `{` as ordinary text within the quoted word.
2. The parser must track whether it is inside a double-quoted word so it does not falsely count braces while scanning proc names, argument words, or other non-braced words before a proc or `namespace eval` body opens.
3. A backslash before a `"` inside a quoted word escapes the quote (e.g. `\"`). The parser must explicitly check for this so it does not incorrectly exit the quoted context.
4. Double quotes are only special at the beginning of a word (after whitespace or at command start).
5. Inside a brace-delimited word, including a brace-delimited proc body, `"` has no structural meaning. Tcl Rule 6 applies: quotes are literal characters there, and unescaped `{` / `}` still participate in brace matching.

#### 3.3.1 Pre-Body Quote Rule (Outside Brace-Delimited Blocks)

While the parser is at brace_depth 0 and scanning the proc name or args specification before the proc body `{` opens:

- If a word begins with `"`, treat it as a quote-delimited word.
- Inside a quote-delimited word, braces do NOT affect `brace_depth`.
- Escaped quotes `\"` do not end the quoted word.
- The quote-delimited word ends at the next unescaped `"` that is not preceded by a backslash.

Example: `proc foo "arg1 {arg2}" { body }` — the `{` inside the quoted args does NOT increment brace_depth. The body `{` is found after the closing `"`.

#### 3.3.2 In-Body Rule (Inside Brace-Delimited Blocks)

Once the parser is inside a brace-delimited block (brace_depth > 0), including a proc body or `namespace eval` body:

- `"` has **NO structural meaning** — it is a literal character.
- The parser must **NOT** enter a quoted-string context.
- Unescaped `{` and `}` **still affect** brace_depth.
- `$`, `[`, `]` are inert for structural purposes (no substitution tracking).
- Only `\` before `\n` (line continuation) and `#` at command position (comments) have structural effects.

Example: `proc foo {} { set x "text { brace" }` — the `{` inside the quoted text IS a brace_depth event. This makes the proc body unbalanced (an extra `{` with no matching `}`), and Chopper must report an unbalanced-brace parse error.

**Mnemonic:** Outside braces, quotes suppress braces. Inside braces, nothing suppresses braces.

### 3.4 Comments (Tcl Rule 10)

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

### 3.5 Command Substitution (`[...]`) (Tcl Rule 7)

**Rules for Chopper:**
1. Square brackets `[` and `]` denote command substitution.
2. Inside brace-delimited blocks (including proc bodies), `[...]` is NOT executed but is still text.
3. For brace tracking purposes, brackets are irrelevant — only braces matter for proc boundary detection.
4. For **call extraction** (tracing), bracketed expressions like `[helper_proc arg1]` are parsed to extract the proc name (first token after `[`).

---

## 4. Proc Detection

### 4.1 Proc Definition Pattern

The standard Tcl proc definition is:

```
proc <name> <args> <body>
```

Where:
- `proc` is a literal keyword appearing as the first word of a command
- `<name>` is the proc's name (may be namespace-qualified)
- `<args>` is the argument list (typically brace-delimited)
- `<body>` is the proc body (always brace-delimited for Chopper's purposes)

### 4.2 Detection Algorithm

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

  3. If the line matches: ^\s*(namespace)\s+(eval)\s+(\S+)\s*\{
     Push (NAMESPACE_EVAL, current_brace_depth) onto context_stack
     Push the namespace name onto namespace_stack
     When brace_depth returns to entered_at_depth, pop both stacks

  4. If the line matches a control-flow keyword (if, for, foreach,
     while, switch, catch, eval) followed by a body `{`:
     Push (CONTROL_FLOW, current_brace_depth) onto context_stack
     When brace_depth returns to entered_at_depth, pop the stack
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

### 4.3 Proc Name Resolution

| Source Pattern | Resolved Name |
|---|---|
| `proc foo {args} {...}` at file root | `foo` |
| `proc ::ns::foo {args} {...}` at file root | `ns::foo` (strip leading `::`) |
| `proc foo {args} {...}` inside `namespace eval ns { ... }` | `ns::foo` |
| `proc foo {args} {...}` inside `namespace eval a { namespace eval b { ... } }` | `a::b::foo` |
| `proc ::abs::foo {args} {...}` inside `namespace eval ns { ... }` | `abs::foo` (absolute overrides namespace context) |
| `proc ${prefix}_foo {args} {...}` | **SKIP** — log WARNING (computed name, unresolvable) |

### 4.4 Where Procs Are Recognized

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

### 4.5 Namespace Eval Detection

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

#### 4.5.1 Namespace Stack Pop Timing — Worked Example

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

## 5. Call Extraction (For Tracing)

Call extraction identifies proc calls within a proc body for transitive dependency tracing.

### 5.1 What Chopper Extracts

From each proc body, Chopper extracts:

| Pattern | Example | Extracted |
|---|---|---|
| Direct proc call (first word of command) | `helper_proc arg1 arg2` | `helper_proc` |
| Bracketed proc call | `[helper_proc arg1]` | `helper_proc` |
| Namespace-qualified call | `::ns::helper arg1` | `ns::helper` |
| Call after semicolon | `set x 1; helper_proc` | `helper_proc` |
| Call inside control structures | `if {$cond} { helper_proc }` | `helper_proc` |

### 5.2 What Chopper Does NOT Extract

| Pattern | Example | Reason |
|---|---|---|
| Variable-based call | `$cmd arg1 arg2` | Dynamic dispatch — unresolvable |
| Eval-based call | `eval "helper_proc arg1"` | Eval content is a string — unresolvable |
| Uplevel-based call | `uplevel 1 helper_proc` | Caller context — unresolvable |
| String in quotes | `set x "helper_proc"` | Data, not a call |
| Interp alias | `interp alias {} foo {} bar` | Dynamic alias — unresolvable |
| Apply lambda | `apply {args { helper_proc }}` | Lambda body — too dynamic |

All unresolvable patterns produce structured diagnostics with reason codes.

### 5.3 Call Extraction Algorithm

```
For each line in proc body:
  1. Skip comment lines (# at command position)
  2. Identify command boundaries (newlines and semicolons, respecting braces and quotes).
     Semicolons inside brace-delimited blocks (depth > 0 relative to current context)
     and inside double-quoted strings do NOT create command boundaries.
  3. For each command:
     a. Extract the first word (the command name)
     b. If the first word is a known control structure (if, for, foreach, while, switch, catch):
        - Parse the body argument(s) recursively for commands.
          Recursion depth is bounded by brace nesting in the source file, which is finite.
          Implementations should use an iterative or stack-based approach to avoid
          Python stack overflow on deeply nested control structures.
     c. If the first word starts with `$` or contains `$`:
        - Log as dynamic dispatch, do not extract
     d. If the first word is a literal string matching [a-zA-Z_][a-zA-Z0-9_:]* :
        - Record as a candidate proc call
  4. For bracketed expressions [cmd ...]:
     a. Extract `cmd` as a candidate proc call
     b. Apply the same literal-check as step 3d
```

### 5.3.1 Deterministic Proc Name Resolution Contract

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
4. If more than one canonical proc matches the same candidate qualified name, emit `TRACE-AMBIG-01` and stop unresolved.
5. If no candidate qualified name resolves inside the selected domain, emit `TRACE-CROSS-DOMAIN-01` and stop unresolved.

**Out of scope for v1:**

- `namespace import`
- command path lookup
- `namespace unknown`
- runtime aliasing / `interp alias`
- runtime redefinition order across sourced files

These are not guessed. Dynamic or syntactically unresolvable call forms still emit `TRACE-UNRESOLV-01`.

### 5.4 Source/iproc_source Extraction

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

---

## 6. Output: Proc Index Entry

Each detected proc produces one `ProcEntry` record:

| Field | Type | Description |
|---|---|---|
| `canonical_name` | `str` | `relative/path.tcl::qualified_name` |
| `short_name` | `str` | Name as it would appear in JSON `procs` array |
| `qualified_name` | `str` | Namespace-qualified name with leading `::` stripped |
| `source_file` | `PurePosixPath` | Domain-relative Tcl file path |
| `start_line` | `int` | First line of proc definition (the `proc` keyword line) |
| `end_line` | `int` | Last line of proc definition (the closing `}` line) |
| `body_start_line` | `int` | Line immediately after the opening `{` of the proc body (see §4.2 step 2g) |
| `body_end_line` | `int` | Line immediately before the closing `}` of the proc body (see §4.2 step 2g) |
| `namespace_path` | `str` | Namespace context from enclosing `namespace eval` (empty string if at file root) |

### 6.1 Invariants

1. `start_line <= body_start_line <= body_end_line <= end_line`
2. `canonical_name` is unique within the proc index for one domain. Duplicate canonical names are an ERROR.
3. `short_name` is unique within the same source file. Duplicate short names in the same file are an ERROR.
4. If the same short name is defined twice in the same file, the **last definition wins** for index materialization so downstream tooling has one deterministic span to report, but Chopper emits an ERROR diagnostic and the file is invalid for trim/trace work until fixed.

### 6.2 Boundary Definitions for `body_start_line` / `body_end_line`

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

---

## 7. Edge Cases and Adversarial Inputs

### 7.1 Brace in Quoted Text Inside a Braced Proc Body

```tcl
proc problematic_proc {args} {
    set data "this has { an open brace"
    return $data
}
```

**Handling:** This input is structurally invalid Tcl. The proc body is itself a brace-delimited word, so the unescaped `{` inside the quoted text still increments brace depth under Tcl Rule 6. Chopper must report an unbalanced-brace parse error here rather than inventing a quote context inside the braced proc body.

### 7.2 Backslash Line Continuation

```tcl
proc split_definition \
    {arg1 arg2} \
    {
    return [list $arg1 $arg2]
}
```

**Handling:** The `proc` keyword, name, args, and body opening may span multiple lines via `\` continuation. The parser must handle this by recognizing continuation before parsing words.

### 7.3 Empty File

```tcl
# This file has no proc definitions
# Just comments and maybe some top-level code
set x 1
```

**Handling:** Returns an empty proc index for this file. This is not an error.

### 7.4 Proc with No Body Braces (Theoretical)

```tcl
proc foo args "return hello"
```

**Handling:** While Tcl allows a quoted body, this is extremely rare in practice. Chopper logs a WARNING and skips this proc. The parser only recognizes brace-delimited bodies.

### 7.5 Deeply Nested Namespace

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

### 7.6 Multiple Namespace Blocks

```tcl
namespace eval utils {
    proc helper_a {} { return "a" }
}

namespace eval utils {
    proc helper_b {} { return "b" }
}
```

**Handling:** Both procs are in namespace `utils`. This is standard Tcl — namespaces accumulate across multiple `namespace eval` blocks.

### 7.7 Mixed Encoding

```tcl
# -*- coding: latin-1 -*-
proc legacy_proc {} {
    # Comment with ü ö ä characters
    return "done"
}
```

**Handling:** UTF-8 decode fails; fall back to Latin-1 with a WARNING. Proc boundaries are still detected correctly because brace matching is byte-level.

### 7.8 Proc Inside If Block

```tcl
if {$feature_enabled} {
    proc conditional_proc {} {
        return "maybe"
    }
}
```

**Handling:** `conditional_proc` is NOT indexed. It is inside a conditional block, not at file top level or inside `namespace eval`. Debug-level log message notes the skip.

### 7.9 Computed Proc Name

```tcl
proc ${prefix}_handler {} {
    return "dynamic"
}
```

**Handling:** The proc name contains `$` — it is computed at runtime. Chopper logs a WARNING diagnostic and does NOT index this proc.

### 7.10 Duplicate Proc Definition

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

## 8. Parser Architecture

### 8.1 Two-Phase Design

The parser operates in two phases:

**Phase 1: Structure Detection**
- Input: file content as string
- Process: Track brace depth, identify `proc` and `namespace eval` boundaries
- Output: List of `ProcEntry` records with line spans

**Phase 2: Call Extraction** (used by tracer, not by proc index builder)
- Input: `ProcEntry` record (specifically, the body lines)
- Process: Extract candidate proc calls and file references from body text
- Output: List of call references and file references

### 8.2 State Machine

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

### 8.3 Performance Target

For a domain like power/ (~60 Tcl files, ~150+ procs), performance should be reasonable for interactive use. No strict timing constraints are imposed.

The parser is purely CPU-bound string processing. No external dependencies required.

> **Implementation note:** Prefer bulk string operations (`str.find()`, `str.index()`) to jump between braces, quotes, and newlines rather than iterating character-by-character. Measure against the 60-file synthetic domain from `tests/fixtures/gen_large_domain.py`.

### 8.4 Diagnostic Emission Contract

The parser does **not** return diagnostics in its return value. Instead, it emits them via the optional `on_diagnostic` callback (`DiagnosticCollector = Callable[[Diagnostic], None]`), defined in `core/protocols.py`.

**Parser diagnostic codes and their emission points:**

| Code | Severity | When Emitted |
|------|----------|--------------|
| `PARSER-DUP-01` | ERROR | After parsing a file, duplicate `short_name` detected within the same file (§6.3) |
| `PARSE-DYNA-01` | WARNING | During proc detection, computed/dynamic proc name encountered (§4.3) |
| `PARSE-ENCODING-01` | WARNING | During file read, UTF-8 decode failed, fell back to Latin-1 (§2) |
| `PARSE-UNBRACE-01` | ERROR | After parsing, brace depth did not return to 0 (unbalanced braces) |
| `PARSE-NOBODY-01` | WARNING | During proc detection, proc body could not be delimited |
| `PARSE-COMPNS-01` | WARNING | During namespace eval detection, computed namespace name encountered |

**Emission pattern:**
```python
# Inside parse_file():
if on_diagnostic is not None:
    on_diagnostic(Diagnostic(
        severity=Severity.ERROR,
        code="PARSER-DUP-01",
        message=f"Duplicate proc definition for '{short_name}' in '{rel_path}'",
        location=f"{rel_path}:{start_line}",
        hint="Remove one definition or rename the proc.",
        source=DiagnosticSource.PARSER,
    ))
```

**Caller integration (compiler):**
```python
# Compiler bridges ProgressSink to parser's DiagnosticCollector
entries = parse_file(domain, tcl_file, on_diagnostic=progress.on_diagnostic)
```

**Unit test isolation:**
```python
# Test without diagnostics (simple)
entries = parse_file(domain, file)

# Test with diagnostic capture
diags: list[Diagnostic] = []
entries = parse_file(domain, file, on_diagnostic=diags.append)
assert any(d.code == "PARSER-DUP-01" for d in diags)
```

---

## 9. Test Strategy

### 9.1 Fixture Categories

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

### 9.2 Property-Based Invariants

1. **Span consistency:** For every `ProcEntry`, all lines in `[start_line, end_line]` exist in the source file.
2. **Body subset:** `{body_start_line, body_end_line}` is a strict subset of `{start_line, end_line}`.
3. **No overlap:** No two `ProcEntry` spans overlap.
4. **Canonical uniqueness:** All `canonical_name` values are unique.
5. **Roundtrip:** Extracting proc spans from a file and re-joining them produces valid Tcl (brace balance preserved per proc).

---

## 10. References

| Source | Relevance |
|---|---|
| [Tcl 8.6 Dodekalogue](https://wiki.tcl-lang.org/page/Dodekalogue) | The twelve rules defining Tcl syntax |
| [Tcl proc manual](https://www.tcl-lang.org/man/tcl8.6/TclCmd/proc.htm) | `proc name args body` syntax |
| [Tcl namespace manual](https://www.tcl-lang.org/man/tcl8.6/TclCmd/namespace.htm) | `namespace eval` semantics |
| [BNF for Tcl](https://wiki.tcl-lang.org/page/BNF+for+Tcl) | Why Tcl has no formal BNF (context-sensitive language) |
| ARCHITECTURE.md §4.3 | Proc index contract and trace expansion algorithm |
| ARCHITECTURE.md §9 (TC-01, TC-02) | Technical challenges for proc boundary detection |

---

## 11. Revision History

| Date | Change |
|---|---|
| 2026-04-04 | **Rev 1:** Created parser spec from architecture review GAP-09. Covers tokenization (brace matching, continuations, quotes, comments), proc detection, namespace handling, call extraction, edge cases, and test strategy. Based on Tcl 8.6 Dodekalogue and official `proc`/`namespace` documentation. |
| 2026-04-05 | **Rev 2:** Aligned duplicate-proc semantics with the source architecture: duplicate short names in the same file are deterministic for indexing purposes but are ERRORs for trim/trace validation, not warnings. |
| 2026-04-05 | **Rev 3:** Corrected quote-handling guidance to match Tcl Rule 6. Quotes inside brace-delimited proc bodies are literal text and do not suppress brace matching; unescaped braces there are parse errors. |
| 2026-04-05 | **Rev 4:** Added a deterministic proc name resolution contract for trace expansion. Bare and relative qualified calls now resolve by caller namespace first, then global namespace, while absolute qualified calls resolve exactly. Ambiguous matches emit `TRACE-AMBIG-01`; unresolved literal calls emit `TRACE-CROSS-DOMAIN-01`; dynamic forms emit `TRACE-UNRESOLV-01`. |
| 2026-04-05 | **Rev 5:** Resolved pre-coding review blockers B-01 through B-04 and HIGH issues H-01, H-02, M-02. Replaced ambiguous "at this depth" detection rule with explicit context-type stack (`FILE_ROOT`, `NAMESPACE_EVAL`, `CONTROL_FLOW`, `PROC_BODY`). Operationally defined `body_start_line` / `body_end_line` boundaries with edge-case table (§6.2). Specified args-word skip algorithm ("scan forward to unescaped `{` at current depth"). Added namespace stack pop-timing worked example (§4.5.1). Separated quote handling into Pre-Body Rule (§3.3.1) and In-Body Rule (§3.3.2). Added call extraction scope statement to §4.4. Revised performance target from <1s to <2s primary. |
| 2026-04-05 | **Rev 6:** Added §6.3 (Duplicate Proc Validation Timing) and §5.3.1 cross-reference to ARCHITECTURE §4.3 trace resolution. Resolves E-02, E-11 from production review. |
| 2026-04-05 | **Rev 7:** Added §2.1 (Public Function Signature) and §8.4 (Diagnostic Emission Contract). Resolves parser return type ambiguity: `parse_file()` returns `list[ProcEntry]`, emits diagnostics via optional `on_diagnostic: DiagnosticCollector` callback. Aligns with `ProgressSink.on_diagnostic` pattern used by service layer. |

---

## Addendum A: Clarifications from Production Review

### A.1 Duplicate Proc Validation Timing (E-02)

`PARSER-DUP-01` is checked at the end of parsing **each source file**, not after all files in the domain are parsed. The check compares `short_name` values within a single file's proc index.

**Timing:** After the parser finishes processing all lines of a single file and has produced its list of `ProcEntry` records, scan for duplicate `short_name` values within that list.

**Error message format:**
```
PARSER-DUP-01 (ERROR): Duplicate proc definition for '<short_name>' in '<source_file>'
  First definition: line <first_start_line>
  Last definition:  line <last_start_line> (used for index)
  Hint: Remove one definition or rename the proc.
```

**Location field:** `<source_file>:<first_start_line>`

Cross-file `canonical_name` uniqueness is checked later during domain-wide proc index assembly. That is a separate check and uses a different diagnostic code if needed (implementation may merge into PARSER-DUP-01 with an extended message).

### A.2 Namespace Resolution Cross-Reference (E-11)

The parser captures `namespace_path` for each proc (e.g., `"a::b::c"`). During trace expansion (see ARCHITECTURE.md §4.3 step 5 and TECHNICAL_REQUIREMENTS.md §7.1.1 Phase 3), the tracer uses this namespace context to resolve proc calls deterministically via the namespace resolution contract defined in TCL_PARSER_SPEC.md §5.3.1.
