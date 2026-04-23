# 🤝 Contributing to Chopper

![Audience](https://img.shields.io/badge/audience-contributors-8a3ffc)
![Gate](https://img.shields.io/badge/gate-make%20check%20%7C%20make%20ci-0a7a3d)

This guide covers the practical workflow for contributing code or documentation to Chopper. Product overview, user setup, and the documentation map stay in [README.md](README.md); this file is only for contributor-specific guidance.

## 📖 Before You Start

Read the documents that define the behavior you are changing:

| Path | Purpose |
| --- | --- |
| [doc/TECHNICAL_GUIDE.md](doc/TECHNICAL_GUIDE.md) | High-level system design for integrators and contributors |
| [technical_docs/chopper_description.md](technical_docs/chopper_description.md) | Authoritative product behavior and pipeline contract |
| [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md) | Diagnostic registry |
| [technical_docs/ARCHITECTURE_PLAN.md](technical_docs/ARCHITECTURE_PLAN.md) | Architecture details and implementation boundaries |

> [!IMPORTANT]
> If your change affects CLI behavior, JSON structure, diagnostics, or generated artifacts, update the corresponding docs in the **same** pull request.

## 🛠️ Setup

Use one of the repository bootstrap scripts, then run the local quality gates before you open a pull request:

| Platform | Command |
| --- | --- |
| Windows PowerShell | `. .\setup.ps1` |
| Windows cmd.exe | `setup.bat` |
| Unix tcsh/csh | `source setup.csh` |
| Unix bash/zsh/sh | `source setup.sh` |

The scripts create `.venv`, activate it, and install the development dependencies.

Standard local checks:

```text
make check
make ci
make test
```

> [!NOTE]
> If `make` is not available on your platform, use the matching tools and tasks defined in [pyproject.toml](pyproject.toml) and the VS Code workspace.

## 🔒 Working Rules

These are the constraints that matter most during day-to-day implementation:

1. Keep the public command surface to `validate`, `trim`, and `cleanup`.
2. Preserve the layered structure: `cli -> orchestrator -> services -> core`.
3. Keep cross-service sharing in `src/chopper/core/`; avoid direct service-to-service imports.
4. Route service I/O through the configured filesystem and diagnostic abstractions rather than ad hoc direct access.
5. Register new diagnostic codes in [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md) before using them.
6. Update user-facing and engineering docs together when behavior changes.

> [!WARNING]
> For the full scope lock and rejected decisions, see [technical_docs/chopper_description.md](technical_docs/chopper_description.md) and [technical_docs/ARCHITECTURE_PLAN.md](technical_docs/ARCHITECTURE_PLAN.md). Adding features, stubs, or reserved seams outside the spec is a violation.

## 🔄 Typical Workflow

1. Create or update tests close to the affected module.
2. Implement the smallest change that satisfies the documented behavior.
3. Run a focused check for the touched area.
4. Run the standard repo gates before opening a pull request.

Focused command examples:

```text
make check
make ci
make test
pytest tests/unit/<package>/ -v
```

## 🗒️ Design Notes

- Chopper uses `json_kit/schemas/` as the runtime schema source.
- The CLI entry point is `chopper`, defined in [pyproject.toml](pyproject.toml).
- `trim --dry-run` produces trim-side reports without rebuilding domain content.
- `cleanup` is a direct filesystem operation and requires `--confirm`.

## ✅ Pull Request Checklist

- [ ] Tests or validation checks were run for the touched area.
- [ ] `make check` passes locally, or equivalent checks were run if `make` is unavailable.
- [ ] New diagnostics, if any, are registered in [technical_docs/DIAGNOSTIC_CODES.md](technical_docs/DIAGNOSTIC_CODES.md).
- [ ] User-facing docs were updated when command behavior or outputs changed.
- [ ] Engineering docs were updated when architectural behavior or contracts changed.
- [ ] No out-of-scope features were introduced implicitly through helper code, comments, or stubs.

> [!TIP]
> If you are adding a substantial feature or changing behavior across modules, read the relevant technical docs first and keep the documentation cascade in the same pull request.
