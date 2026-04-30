# Changelog

All notable changes to Chopper are recorded here.

## [Unreleased]

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
