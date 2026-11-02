"""Front-end-neutral application layer.

Every front end (the CLI today; the future local browser GUI recorded in
``FD-04``) calls these use cases and renders their typed results. No
module here prints, raises :class:`SystemExit`, or reads ``argv``; input
failures surface as :class:`~chopper.app.errors.AppError`. See
``technical_docs/ARCHITECTURE.md`` Sec.5.11.2.

* :mod:`chopper.app.domain` -- domain resolution
* :mod:`chopper.app.catalog` -- base / project-config / feature discovery
* :mod:`chopper.app.session` -- recipe, context, run, projections, cleanup
* :mod:`chopper.app.trim_stats` -- post-trim statistics rows
"""
