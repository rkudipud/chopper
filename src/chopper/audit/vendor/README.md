# Vendored: cloc

This directory contains a vendored copy of [cloc](https://github.com/AlDanial/cloc)
by Al Danial.

* `cloc.pl` -- the cloc script (v2.09 at vendor time).
* `LICENSE` -- GNU General Public License v2.0.

## License notice

`cloc` is distributed under the **GNU GPL v2.0**. The rest of chopper is
distributed under **Apache License 2.0** (see top-level `LICENSE`).

Vendoring `cloc.pl` into this tree means:

* Anyone redistributing chopper together with this `vendor/` directory
  must comply with GPL-2 for the cloc portion.
* Chopper's own code is **not** relicensed by this inclusion -- only
  the contents of this `vendor/` subdirectory are GPL-2.
* `chopper.audit.cloc_backend` invokes `cloc.pl` as a subprocess (no
  source-level linking), which the FSF has historically considered a
  weak coupling. Even so, redistributors should treat this directory
  as GPL-2.

If GPL-2 distribution is a problem for your downstream use case, delete
this directory and chopper will silently fall back to its pure-Python
SLOC counter (`chopper.audit.sloc._count_*`).
