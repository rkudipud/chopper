# Changelog

All notable changes to Chopper are recorded here.

## [Unreleased]

### Fixed

- **`chopper trim` no longer drops file mode bits** on rebuilt files.
  Previously every file written into `<domain>/` (FULL_COPY or PROC_TRIM)
  came out with default-umask permissions because `Path.write_text`
  ignores the source's `st_mode`. Executable scripts (Tcl/Perl/csh/Python
  entry points, helper drivers, etc.) lost their `+x` bit on every trim,
  silently breaking flows that invoked them by execution. The trim
  writer now mirrors the source mode via `shutil.copymode` after each
  write.

- **`files_removed.txt` now reports the full physical-deletion set.**
  Previously the artifact only listed files whose manifest treatment was
  explicitly `REMOVE`, missing the much larger set of files chopper
  silently dropped via the documented "default is exclude" rule (i.e.
  files no `files.include` pattern matched). The audit bundle therefore
  contained no flat list of what actually disappeared from the rebuilt
  domain. The writer now computes the deletion set as
  `walk(<domain>_backup/) − manifest_kept_files`, which captures both
  explicit `REMOVE` decisions and default-exclude drops. When no backup
  exists (e.g. `validate`-only runs) the writer falls back to the prior
  REMOVE-only behaviour and the header line records which mode was used.

### Added

#### Task A — `files_removed.txt` audit artifact

Every `chopper trim` and `chopper trim --dry-run` run now writes a
`files_removed.txt` file into the `.chopper/` audit bundle alongside the
existing `trim_report.json`.

The file contains a flat, alphabetically sorted list of every domain-relative
path that is scheduled for removal (i.e. all files whose `CompiledManifest`
treatment is `REMOVE`), one path per line.  A header comment identifies the
file.  When no files are scheduled for removal the file contains only the
header.

This gives operators an immediate, machine-readable answer to *"which files
will disappear?"* without having to parse the full `trim_report.json`.

#### Task B — `files_kept.txt` audit artifact

Every `chopper trim` and `chopper trim --dry-run` run now writes a
`files_kept.txt` file into the `.chopper/` audit bundle.

The file contains a flat, alphabetically sorted list of every domain-relative
path that survives trimming (treatments `FULL_COPY`, `PROC_TRIM`, and
`GENERATED`), one path per line.  A header comment identifies the file.

This gives operators an immediate, machine-readable answer to *"which files
will remain?"* without having to parse the compiled manifest.

Both artifacts appear in the `artifacts_present` array of
`chopper_run.json` so downstream tooling can detect their presence
reliably.
