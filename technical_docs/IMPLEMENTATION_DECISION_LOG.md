# Implementation Decision Log

Tracking log for non-obvious implementation decisions, detours, and spec clarifications encountered during the Chopper buildout. Each entry records **what** was decided, **why**, and **where** the outcome lives so future readers can reconstruct the reasoning without rereading the full conversation history.

Entries are keyed `D-<stage>-<nn>` where `<stage>` tracks the roadmap checkpoint (`0`, `1a`, `1b`, …). Within a stage, numbering starts at `01`. Entries are **append-only**; if a decision is reversed, file a new entry that references the old one — never edit the old one in place.

Scope of this document:

- **In scope.** Design decisions that diverged from an obvious reading of the spec, mid-implementation algorithm replacements, spec clarifications absorbed into the code, and hiccups where a first attempt had to be rolled back.
- **Out of scope.** Line-level code edits, routine bug fixes caught by `make check`, and any content the spec docs already fully cover. If the decision is fully expressible as "we followed the spec", it does not belong here.

---

## Stage 1b — Tokenizer

### D-1b-01: LBRACE records depth *before* increment; RBRACE records depth *after* decrement

**Context.** A consumer of `Token.brace_depth` needs to know "what depth am I at?" intuitively for both opens and closes. The tokenizer had two equally valid choices: record the depth at the token's position (LBRACE=0, RBRACE=0 for `{}`) or record the depth after the token's effect.

**Decision.** LBRACE records the depth *before* the brace increments it; RBRACE records the depth *after* the brace decrements it. Both end up as the depth of the *enclosing* scope in which the brace sits, which reads correctly for `token.brace_depth == 0` checks on either kind.

**Rationale.** Downstream consumers (NamespaceTracker, proc extractor) test "is this brace at top level?" via `brace_depth == 0`, which should be true for both the opening `{` of a top-level proc and the matching `}`. The spec (§3.1) does not dictate which convention to use — it says only that "depth increments on `{` and decrements on `}`".

**Outcome.** Documented in `Token.brace_depth` docstring at [src/chopper/parser/tokenizer.py](../src/chopper/parser/tokenizer.py). Unit-tested in `TestBraces::test_empty_braces` at [tests/unit/parser/test_tokenizer.py](../tests/unit/parser/test_tokenizer.py).

### D-1b-02: Four devil's-advocate hardening tests — spec-compliant `;` + `#` inside braces

**Context.** A mid-stage review raised the claim that `;` followed by `#` inside a brace-delimited data block would swallow the closing `}` as part of the comment, which would be a spec-violating bug.

**Decision.** The behaviour is **by design** per §3.0 state table + §3.4 rule 3 + §3.3.2. Brace-delimited bodies **are** Tcl scripts (the spec says so explicitly for `proc` bodies, and there is no syntactic distinction between a proc body and any other brace-delimited script). A `;` at any depth terminates the current command and re-establishes command position; a subsequent `#` at command position starts a comment that scans to the next unescaped newline.

**Rationale.** The spec endorses this behaviour via the worked example in §3.3.2 ("`set x { a ; # comment\n }` — the `#` activates a comment inside the brace"). Changing it would have required a spec edit; the spec was correct.

**Outcome.** Added 4 hardening tests to [tests/unit/parser/test_tokenizer.py](../tests/unit/parser/test_tokenizer.py) (`test_semicolon_inside_braces_still_emits_token`, `test_comment_after_semicolon_inside_braces_activates`, `test_dangling_backslash_at_eof`, `test_escaped_open_brace_in_word_stays_word`) to document the spec-compliant behaviour and prevent a future "fix" from regressing it.

---

## Stage 1c — NamespaceTracker

### D-1c-01: Sticky control-flow flag — persists until command terminator

**Context.** Control-flow commands routinely take multiple brace-delimited words on a single command: `if {cond} {body}`, `foreach v {list} {body}`, `while {cond} {body}`. The initial implementation classified only the **first** brace after a control-flow keyword as `CONTROL_FLOW` and reverted to default (`OTHER`) for subsequent braces in the same command, which caused the body brace of `if {cond} {body}` to land as `OTHER` and allow spurious proc recognition inside the `if` body.

**Decision.** Introduce a sticky `_in_control_flow_command` boolean on `NamespaceTracker`. Set it on any control-flow-keyword WORD at command position. Clear it on the next `NEWLINE`, `SEMICOLON`, or `COMMENT`. Every `LBRACE` while the flag is true produces a `CONTROL_FLOW` frame, regardless of how many brace words the command contains.

**Rationale.** The spec's §4.2 table lists `if`/`foreach`/`while`/`switch`/`catch`/`eval`/`for` as commands whose body braces push `CONTROL_FLOW`. The spec does not prescribe mechanism — only outcome. Sticky flag is the simplest mechanism that produces the right outcome for all variants.

**Outcome.** `_in_control_flow_command` field on [src/chopper/parser/namespace_tracker.py](../src/chopper/parser/namespace_tracker.py). Tested parametrically in `TestControlFlow::test_control_flow_keyword_pushes_context` at [tests/unit/parser/test_namespace_tracker.py](../tests/unit/parser/test_namespace_tracker.py).

### D-1c-02: Computed-namespace body is `OTHER`, not `NAMESPACE_EVAL`, and does not push onto the namespace stack

**Context.** §4.5 rule 7 mandates that `namespace eval $var { ... }` emits `PW-04` and does not parse the body for procs. The body frame's kind was initially set to `NAMESPACE_EVAL` with a synthetic namespace name, which caused nested `namespace eval` statements inside it to be qualified against a computed parent, producing nonsense qualified names.

**Decision.** Push `ContextKind.OTHER` for the body frame (not `NAMESPACE_EVAL`), and do **not** push anything onto the namespace stack. `can_define_proc()` returns `False` for `OTHER`, which is exactly what the spec requires.

**Rationale.** "Do not parse the body for procs" is stronger than "procs do not get the computed-name prefix". Using `OTHER` closes the whole scope to proc recognition, consistent with the spec's intent.

**Outcome.** Implemented in `_check_namespace_eval` at [src/chopper/parser/namespace_tracker.py](../src/chopper/parser/namespace_tracker.py). Tested in `TestNamespaceEval::test_computed_namespace_name_emits_diagnostic` and `test_computed_namespace_with_brackets` at [tests/unit/parser/test_namespace_tracker.py](../tests/unit/parser/test_namespace_tracker.py).

---

## Stage 1d — ProcExtractor

### D-1d-01: Early PW-01 guard *before* running layout scan

**Context.** For `proc ${prefix}_foo {} { body }`, the initial implementation let `_scan_proc_layout` run — which tried to classify `${prefix}_foo` as the name word, `{}` as the args word, and the next quoted/plain word as a non-brace body. The result was `PW-03 non-brace-body` on a proc that should have produced `PW-01 computed-proc-name`.

**Decision.** Add `_peek_name_token` helper that returns the name WORD following `proc`. Before calling `_scan_proc_layout`, check the peeked name with `_is_computed_name`. If computed, emit `PW-01` immediately, advance past the `proc` keyword, and skip layout scanning for this definition.

**Rationale.** The spec (§4.3) is clear that computed names drop the proc from the index with `PW-01`; the layout-level fallback (`PW-03`) is for a genuinely malformed body shape. Distinguishing at the right level means the diagnostic the user sees reflects the real problem.

**Outcome.** `_peek_name_token` helper + guard in `extract_procs` main loop at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py). Tested in `TestDiagnostics::test_computed_proc_name_pw01` and `test_computed_proc_name_with_bracket` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

### D-1d-02: Duplicate detection keeps LAST definition; emits one PE-01 at the last line

**Context.** §6.3 invariant 4 says "two procs with the same short_name in one file → emit `PE-01`; the last definition wins in the index". Implementation needed to decide (a) how many diagnostics to emit per duplicate group, (b) which line number to attach, and (c) which entry survives.

**Decision.** One `PE-01` per duplicate *group* (not per occurrence). The diagnostic's `line_no` is the **last** definition's `start_line` — the one that survives in the index, so the user is pointed at the authoritative entry. The detail string records both the first and last line numbers for disambiguation.

**Rationale.** Multi-emission (one per duplicate) would produce `N-1` diagnostics for `N` duplicates — noise. Attaching the first line's number would point at the dead entry. Attaching the last ties the diagnostic to the row that actually made it into the final parse result.

**Outcome.** `_deduplicate_short_names` at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py). Tested in `TestDiagnostics::test_duplicate_proc_pe01` and `TestProcEntryInvariants::test_dedupe_diag_unique_per_short` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

### D-1d-03: DPA blank-line window is source-relative, not namespace-aware

**Context.** §4.6 permits up to 3 blank lines between a `proc` close and its `define_proc_attributes` block. A mid-stage test failed because a DPA placed **after** the closing `}` of the enclosing namespace was not associated with its proc — the `}` line broke the 3-blank-line window.

**Decision.** Do **not** make the DPA scan namespace-aware. The 3-blank-line window is measured in source-order lines; any non-blank non-DPA line (including a namespace-closing `}`) breaks the association. Relocate problematic DPA blocks inside the enclosing namespace block.

**Rationale.** The spec (§4.6) specifies "up to 3 blank lines" — it does not list "namespace close brace" as a permitted interruption. Making the parser namespace-aware here would let DPAs attach across namespace boundaries, which is not what the spec says. The correct fix is authoring the DPA inside the namespace block, and that is how the test fixture is now structured.

**Outcome.** Test fixture updated to place DPA inside the namespace block. `_scan_dpa` at [src/chopper/parser/proc_extractor.py](../src/chopper/parser/proc_extractor.py) unchanged (simple line-based scan). Tested in `TestDPA::test_dpa_matches_namespaced_proc` at [tests/unit/parser/test_proc_extractor.py](../tests/unit/parser/test_proc_extractor.py).

---

## Stage 1e — CallExtractor

### D-1e-01: Flat token walk replaces depth-based "skip to command boundary"

**Context.** The first implementation of `extract_body_refs` consumed tokens per-command: at a command-position WORD, classify the first word, scan remaining tokens in the command for embedded `[call]` patterns, then *skip forward to the next command boundary* (NEWLINE/SEMICOLON at the same brace depth as the command's first word). Control-flow body contents were dropped: `if {cond} {helper_proc}` at depth 1 caused `_skip_to_command_boundary` to fast-forward from the `if` keyword past its `NEWLINE` at depth 1 — sailing over `helper_proc` at depth 2.

**Decision.** Delete `_skip_to_command_boundary` and `_scan_bracket_calls_in_command`. Walk every WORD token in the body range one at a time. For command-position WORDs, classify the first word. For every WORD (command-position or not, suppressed or not), regex-scan the value for embedded `[<name>` bracket calls. The tokenizer's `at_command_position` flag naturally re-establishes itself at every brace-depth transition, so body-internal command-position tokens are visited without any explicit recursion.

**Rationale.** §5.3 step 3d says "recurse into control-structure body"; the spec endorses iterative / stack-based implementations explicitly ("Implementations should use an iterative or stack-based approach to avoid Python stack overflow on deeply nested control structures"). The flat walk *is* the iterative form — and it has the additional benefit of eliminating the depth-matching bug class that led here. The uniform bracket scan on all WORD tokens handles §5.3 step 4 (bracket sub-calls) and §5.5 Level 3 exception (real `[call]` inside a log-proc string argument) with a single rule.

**Outcome.** Rewritten `extract_body_refs` at [src/chopper/parser/call_extractor.py](../src/chopper/parser/call_extractor.py). §5.3 algorithm block in [technical_docs/TCL_PARSER_SPEC.md](TCL_PARSER_SPEC.md) rewritten to match (with an explicit note that control-flow recursion is not needed). Tested in `TestControlFlowBodies` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py).

### D-1e-02: Suppression check is identifier-only; structural suppression leans on `TCL_BUILTINS` and `at_command_position`

**Context.** The `_should_suppress_first_word` helper initially took the token list and its index and implemented a command-structure check for each of §5.5 Levels 2b–2g (`set PROC x`, `info exists x`, `define_proc_attributes x`, etc.). This duplicated logic the tokenizer and classifier already provided.

**Decision.** Shrink `_should_suppress_first_word(first_word: str) -> bool` to pure identifier tests. It handles only the two classes that are **not** covered by other mechanisms: EDA log-proc names (`LOG_PROC_NAMES`) and EDA app-var commands (`set_app_var` / `get_app_var`, which are not in `TCL_BUILTINS`). Every other §5.5 level is satisfied structurally:

- Level 2a (comment lines) — tokenizer never emits COMMENT at command position in a WORD stream.
- Levels 2b, 2e — variable refs and arg-list positions are not at command position.
- Levels 2c, 2f, 2g — `define_proc_attributes`, `set`, `info` are in `TCL_BUILTINS`; `_classify_call_candidate` rejects them. Their arguments are not at command position.
- Level 2d (`set_app_var` / `get_app_var`) — explicit identifier check.
- Level 3 (log-proc string args) — explicit identifier check (the log proc itself is suppressed; the uniform bracket scan still picks up embedded real `[call]` inside string args).
- Level 4 (print labels) — labels are not at command position; structurally handled.

**Rationale.** Duplicating the structural check adds code that needs unit tests for every §5.5 level and creates two sources of truth. Leaning on the tokenizer's `at_command_position` flag plus `TCL_BUILTINS` membership is simpler and satisfies every spec-required suppression.

**Outcome.** `_should_suppress_first_word` at [src/chopper/parser/call_extractor.py](../src/chopper/parser/call_extractor.py) now ~5 lines. Suppression matrix is tested in `TestSuppression` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py); every §5.5 level has at least one test case.

### D-1e-03: `source` / `iproc_source` consume their argument indices to prevent double-count

**Context.** After the flat-walk restructure, `source common/helpers.tcl` correctly produced a `source_refs` entry — but the path token `common/helpers.tcl`, as an ordinary WORD, was also picked up by the free bracket scan pass (no `[` in it, but the token was considered), and in pathological cases (e.g. `iproc_source -file [derive_path]`) the bracket scan would extract `derive_path` as a call candidate.

**Decision.** `_extract_source_path_with_indices` returns not just the path string but a `set[int]` of token indices consumed by the source command (the keyword is left alone; the flag tokens and the path token are all marked consumed). The caller unions these into a `consumed` set and skips those tokens in the free bracket-scan pass.

**Rationale.** `source` is explicitly a file dependency, not a proc call (§5.4). Its argument tokens must not leak into `calls` under any shape — neither as literal text nor via embedded bracket expansion.

**Outcome.** `_extract_source_path_with_indices` + `consumed` set in `extract_body_refs` at [src/chopper/parser/call_extractor.py](../src/chopper/parser/call_extractor.py). Tested in `TestSourceRefs::test_source_not_a_call_edge` and `test_source_dynamic_path_dropped` at [tests/unit/parser/test_call_extractor.py](../tests/unit/parser/test_call_extractor.py).

---
