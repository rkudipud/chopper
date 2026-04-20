# Chopper v2

**Chopper v2** is a Python CLI tool that surgically trims VLSI EDA tool domains via JSON feature selection. It executes a 7-phase compilation pipeline to automatically remove unwanted files, Tcl procedures, and code paths while preserving correctness and auditability.

## Quick Links

- **[AGENTS.md](AGENTS.md)** — AI agent instructions, architecture overview, design principles
- **[docs/chopper_description.md](docs/chopper_description.md)** — Single source of truth: product behavior, 7-phase pipeline, R1 merge rules, requirements
- **[docs/CLI_HELP_TEXT_REFERENCE.md](docs/CLI_HELP_TEXT_REFERENCE.md)** — Complete CLI subcommand reference
- **[docs/DIAGNOSTIC_CODES.md](docs/DIAGNOSTIC_CODES.md)** — Authoritative diagnostic code registry
- **[Makefile](Makefile)** — Build, test, lint commands

---

## Development Setup

**Important Note:** tcsh is the PRIMARY shell for this system. bash/zsh are NOT available. Use `setup.csh` for Unix/Linux/macOS.

### Quick Start (Choose Your Platform)

| Platform | Command |
|----------|---------|
| **Unix/Linux/macOS (tcsh)** | `source setup.csh` |
| **Windows (PowerShell)** | `. .\setup.ps1` |
| **Windows (cmd.exe)** | `setup.bat` |

This creates `.venv`, activates it, and installs dev dependencies.

### Platform-Specific Setup Scripts

The following setup scripts are platform and shell agnostic:

| Platform | Shell | Script | Status |
|----------|-------|--------|--------|
| **Unix/Linux/macOS** | tcsh, csh | `setup.csh` | **PRIMARY** |
| **Unix/Linux/macOS** | bash, zsh, sh | `setup.sh` | Fallback (bash/zsh not available) |
| **Windows** | PowerShell 5.1+ | `setup.ps1` | Standard |
| **Windows** | cmd.exe | `setup.bat` | Standard |

---

## Setup Instructions

### **Unix/Linux/macOS (tcsh) — PRIMARY**

```tcsh
cd /path/to/chopper_v2
source setup.csh
```

**To auto-activate on every terminal launch:**

```tcsh
echo "source /path/to/chopper_v2/setup.csh" >> ~/.tcshrc
source ~/.tcshrc
```

---

### **Unix/Linux/macOS (bash/zsh) — Fallback Only**

**Note:** bash/zsh are NOT available on this system. Use tcsh (setup.csh) instead.

If bash/zsh are available:

```bash
cd /path/to/chopper_v2
source setup.sh
```

**To auto-activate on every terminal launch:**

```bash
# For bash:
echo "source /path/to/chopper_v2/setup.sh" >> ~/.bashrc
source ~/.bashrc

# For zsh:
echo "source /path/to/chopper_v2/setup.sh" >> ~/.zshrc
source ~/.zshrc
```

---

### **Windows (PowerShell 5.1+)**

```powershell
cd C:\path\to\chopper_v2
. .\setup.ps1
```

**To auto-activate on every PowerShell launch:**

1. Check your profile location:
   ```powershell
   echo $PROFILE
   ```

2. Add the setup script:
   ```powershell
   Add-Content -Path $PROFILE -Value ". 'C:\path\to\chopper_v2\setup.ps1'"
   ```

3. Restart PowerShell:
   ```powershell
   . $PROFILE
   ```

**Optional: Skip proxy configuration**

```powershell
. .\setup.ps1 -NoProxy
```

---

### **Windows (cmd.exe / Command Prompt)**

```cmd
cd C:\path\to\chopper_v2
setup.bat
```

**To auto-activate on every cmd launch:**

**Option 1: Create a shortcut**
1. Right-click desktop → **New** → **Shortcut**
2. Target: `%comspec% /k "cd /d C:\path\to\chopper_v2 && setup.bat"`
3. Start in: `C:\path\to\chopper_v2`

**Option 2: Windows Startup folder**
1. Create `activate_chopper.bat`:
   ```batch
   @echo off
   cd /d C:\path\to\chopper_v2
   setup.bat
   cmd /k
   ```
2. Move to: `C:\Users\[YourUsername]\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

---

## VS Code Setup

Open the workspace file for VS Code auto-configuration:

```powershell
code chopper_v2.code-workspace
```

This automatically configures:
- ✅ Python interpreter from `.venv`
- ✅ Linting (Ruff) and formatting (auto-format on save)
- ✅ pytest runner (Ctrl+Shift+D)
- ✅ Tasks: `make check`, `make ci`, `make test`

---

## Essential Commands

```bash
make install-dev    # Install dev dependencies (pytest, ruff, mypy)
make check          # Fast gate: lint + format-check + type-check + unit tests
make ci             # Full CI: all code quality + all test suites
make test           # Run all tests (unit, integration, golden, property)
make lint           # Ruff linter
make format         # Auto-format with Ruff
make type-check     # mypy static type check
```

**Coverage Requirement:** Minimum 78% line coverage (parser: 85%, compiler: 80%, trimmer: 80%)

---

## Verifying Your Setup

After running setup:

```bash
# Check Python version (should show .venv prefix)
python --version

# Check pip
pip --version

# Check Chopper CLI
chopper --help

# Run tests
pytest
```

Expected output:
- Python 3.8+ with `(.venv)` in your prompt
- pip from `.venv` directory
- Chopper CLI help text
- Pytest discovers and runs tests

---

## Development Workflow

```bash
# 1. Open a terminal (venv auto-activates if configured)
# 2. Make changes to src/chopper/

# 3. Run tests
make check    # Fast pre-commit gate
make ci       # Full CI before pushing

# 4. Commit and push
git add .
git commit -m "your message"
git push
```

---

## Troubleshooting

### Venv not activating in new terminals

**Solution:** Add the setup script to your shell's startup file:

**tcsh (PRIMARY):**
```tcsh
echo "source /path/to/chopper_v2/setup.csh" >> ~/.tcshrc
source ~/.tcshrc
```

**bash/zsh:**
```bash
echo "source /path/to/chopper_v2/setup.sh" >> ~/.bashrc
source ~/.bashrc
```

**PowerShell:**
```powershell
Add-Content -Path $PROFILE -Value ". 'C:\path\to\chopper_v2\setup.ps1'"
. $PROFILE
```

---

### `ModuleNotFoundError` for pytest or chopper

**Solution:** Ensure venv is activated:
```bash
# Check if venv is active (should show .venv path)
which python    # Unix/Linux/macOS
Get-Command python  # PowerShell
```

If not active, re-run setup:
```bash
source setup.csh    # tcsh (PRIMARY)
source setup.sh     # bash/zsh
. setup.ps1         # PowerShell
setup.bat           # cmd.exe
```

---

### PowerShell execution policy error

**Solution:** Allow scripts temporarily:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
. .\setup.ps1
```

---

### Proxy issues (internal networks)

**Solution:** Setup auto-configures Intel proxy. If issues persist:

```bash
# Clear proxy settings
pip config unset global.proxy
pip config unset global.trusted-host
```

**PowerShell:** Skip proxy configuration with `-NoProxy`:
```powershell
. .\setup.ps1 -NoProxy
```

---

### Virtual environment broken

**Solution:** Recreate `.venv`:
```bash
# Unix/Linux/macOS
rm -rf .venv
source setup.csh    # tcsh

# Windows
rmdir /s .venv
. .\setup.ps1       # PowerShell
```

---

## Platform Summary

| Feature | tcsh (PRIMARY) | bash/zsh | Windows |
|---------|----------------|----------|---------|
| **Status** | ✓ Primary | ✗ Fallback | ✓ Standard |
| **Auto-activation** | Via ~/.tcshrc | Via ~/.bashrc/.zshrc | Via PowerShell profile or shortcut |
| **Proxy config** | Automatic | Automatic | Automatic or `-NoProxy` |
| **Recommended** | **Use this** | Only if available | PowerShell 5.1+ |

---

## Architecture Overview

The codebase executes a **7-phase pipeline**:

```
F1 (Parse JSON)  →  F2 (Parse Tcl)  →  F3 (Merge & Trace)  →  F4 (Flow Actions) 
   ↓
F5 (Run File Gen)  →  F6 (Validate Post)  →  F7 (Write & Audit)
```

**Core Modules** in `src/chopper/`:

| Module | Responsibility | Phase |
|--------|-----------------|-------|
| **parser/** | Tcl static analysis; tokenize, extract procs, track namespaces | F2 |
| **compiler/** | Merge JSON, trace proc dependencies (breadth-first), apply selections | F3–F4 |
| **trimmer/** | Delete marked files/procs, rewrite Tcl | F5 |
| **validator/** | Pre- and post-trim validation (schema, structure, dangling refs) | F1, F6 |
| **config/** | JSON/TOML schema loading and validation | F1 |
| **cli/** | Command-line interface layer | User layer |
| **core/** | Shared models, errors, diagnostics, protocols, serialization | All |
| **audit/** | Backup, restore, audit trail artifacts | F7 |
| **generators/** | Run file generation | F5 |

For full details, see [AGENTS.md](AGENTS.md) and [docs/chopper_description.md](docs/chopper_description.md).

---

## Additional Resources

- **[Makefile](Makefile)** — Build and test commands
- **[docs/chopper_description.md](docs/chopper_description.md)** — Single source of truth: product behavior, 7-phase pipeline, R1 merge rules, requirements
- **[docs/CLI_HELP_TEXT_REFERENCE.md](docs/CLI_HELP_TEXT_REFERENCE.md)** — Complete CLI subcommand reference
- **[docs/TCL_PARSER_SPEC.md](docs/TCL_PARSER_SPEC.md)** — Tcl parser engineering baseline
- **[docs/RISKS_AND_PITFALLS.md](docs/RISKS_AND_PITFALLS.md)** — Technical risks and implementation pitfalls
- **[docs/DIAGNOSTIC_CODES.md](docs/DIAGNOSTIC_CODES.md)** — Authoritative diagnostic code registry
- **[tests/TESTING_STRATEGY.md](tests/TESTING_STRATEGY.md)** — Testing framework overview
- **[AGENTS.md](AGENTS.md)** — AI agent instructions for the codebase

---

**Last Updated:** April 2026  
**Status:** Platform-agnostic setup for all major shells and OS combinations