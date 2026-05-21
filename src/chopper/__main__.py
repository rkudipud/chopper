"""Module entry point so ``python -m chopper`` runs the CLI.

This lets contributors use Chopper directly from a source checkout — with
``PYTHONPATH`` pointing at ``<repo>/src`` — without installing the package.
The setup scripts (`setup.csh`, `setup.ps1`, `setup.sh`, `setup.bat`) configure
that ``PYTHONPATH`` and alias ``chopper`` to ``python -m chopper`` so the
ergonomic command surface is identical to the installed console script.
"""

from __future__ import annotations

from chopper.cli.main import main

raise SystemExit(main())
