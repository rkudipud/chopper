# Changelog

All notable changes to Chopper are recorded here.

## [0.5.3] — 2026-05-01

### Added

- **`files_kept.txt` and `files_removed.txt` now record JSON provenance per
  file.** Both audit artifacts have always listed the surviving / removed
  domain-relative paths, but earlier releases only emitted a flat sorted
  path list — useful for `wc -l`, useless for answering "*which* JSON
  pulled this file in?". Each line is now tab-separated as
  `<path>\t<provenance>`:
  - In `files_kept.txt`, `<provenance>` is a comma-separated list of
    `<source_key>:<json_field>` tags (from
    `CompiledManifest.provenance[<path>].input_sources`) identifying every
    authoring intent that kept the file. Files with no provenance entry
    fall back to `-`.
  - In `files_removed.txt`, `<provenance>` is `vetoed-by:<src1>,<src2>,...`
    when the file was named by an authoring intent that was vetoed
    cross-source (`FileProvenance.vetoed_entries`), or `default-exclude`
    when no JSON named the file at all.

  The header comment in each file documents the format. Output remains
  alphabetically sorted by path so existing `diff`/`grep` regression
  scripts that operate on path columns (`cut -f1`) continue to work.

### Documentation

- Architecture Doc §3.7 (dry-run output list) updated to specify the new
  per-line format for both artifacts.
