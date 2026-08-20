# Real-world tokenizer test fixture captured from Intel Caliber domain
# (intel_caliber/run_caliber.tcl). The patterns below previously produced
# a spurious PE-02 unbalanced-braces error in chopper before the
# Dodekalogue rule-5 opener-prefix tightening landed.
#
# Tcl reference: Dodekalogue rule 6 (brace word) -- contents of `{...}`
# are LITERAL bytes; `"` inside a brace word is just a byte, never a
# quoted-word opener. The lexer-level rule that makes this work is
# rule 5: a `"` only opens a quoted word when it appears at a real word
# boundary (after whitespace, `;`, `[`, or start-of-input). After the
# closing `"` of a prior quoted pair, another `"` cannot open.
#
# Each pattern below is valid Tcl (verified with `info complete`) and
# must tokenize without errors.

proc demo_string_map {filtered_rules} {
    # intel_caliber:run_caliber.tcl:418 - multi-quote-pair braced data word.
    # Two empty/space-only quoted strings inside one `{...}` argument.
    set search_keywords [string map {" " ""} [join $filtered_rules ", "]]
    set string_rule_candidates [string map {" " ""} [join $filtered_rules ", "]]
}

proc demo_regexp_two_quoted_groups {line} {
    # Two adjacent quoted regex fragments inside a single braced word.
    if {[regexp {".*" ".*"} $line]} {
        return 1
    }
    return 0
}

proc demo_string_map_newline_pair {text} {
    # Common normalization idiom: collapse newlines into spaces.
    return [string map {"\n" " " "\t" " "} $text]
}

proc demo_literal_brace_in_quoted_with_escapes {var2preserve} {
    # intel_caliber:run_caliber.tcl:304 - escaped braces inside a quoted
    # word that itself contains command substitutions. Backslash-braces
    # are literal bytes; the surrounding `"..."` is a single quoted
    # WORD. No structural braces are emitted from this line.
    set str ""
    append str "array set $var2preserve \{[array get $var2preserve]\}\n"
    return $str
}

proc demo_list_literal_with_quotes {} {
    # List literal with multiple quoted elements as braced data.
    set pairs {"a" "b" "c" "d"}
    foreach p $pairs {
        puts $p
    }
}

proc demo_dict_like_braced {} {
    # Dict-style data word with quoted keys and values.
    set d {"key1" "val1" "key2" "val2"}
    return [llength $d]
}
