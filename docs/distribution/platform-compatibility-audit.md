# BRAHMASTRA AI — Cross-Platform Compatibility Audit

**Document Reference:** DIST-AUDIT-2026-11-11  
**Project:** BRAHMASTRA AI (`brahmastra`)  
**Target Environments:**
- macOS: Apple Silicon (`arm64`) & Intel (`x86_64`)
- Linux: `x86_64` & `aarch64` / `arm64`
- Windows: `x86_64` (AMD64)
**Target Python Versions:** Python 3.10, 3.11, 3.12, 3.13  
**Status:** COMPLETE (Phase 1 Baseline Audit)

---

## 1. Executive Summary

BRAHMASTRA was developed and initially hardened on macOS Darwin (Apple Silicon ARM64). While its architectural layering cleanly separates domain logic, use cases, and interfaces, a comprehensive codebase audit reveals several platform-specific couplings, hardcoded path assumptions, and absent OS-native abstraction layers that currently block seamless public installation and execution across Linux and Windows.

This audit details all platform-dependent components, categorizes blockers by severity, and identifies the exact source lines requiring cross-platform adaptation.

---

## 2. Comprehensive Component Audit

### 2.1 Packaging & Metadata (`pyproject.toml`)
- **Build Backend:** Currently configured with `setuptools>=68.0.0` and `wheel`.
- **Package Layout:** `src/` layout with `[tool.setuptools.packages.find] where = ["src"]`. Correctly structured for modern packaging.
- **Entry Points:** `[project.scripts] brahmastra = "brahmastra.cli.app:main"`. Entrypoint function exists in `src/brahmastra/cli/app.py`.
- **Missing OS Classifiers:**
  - Has `"Operating System :: MacOS"` and `"Operating System :: POSIX :: Linux"`.
  - **MISSING:** `"Operating System :: Microsoft :: Windows"`, `"Operating System :: OS Independent"`.
- **Dependency Declarations:**
  - Base: `typer>=0.12.0`, `rich>=13.0.0`, `pydantic>=2.5.0`, `sqlalchemy>=2.0.0`, `httpx>=0.27.0`.
  - **GAP:** No secure OS credential vault library declared for Linux or Windows (e.g. `keyring>=24.0.0` or native `ctypes` bindings for SecretService/WinCred).
  - **GAP:** No package data rules for non-python assets if needed in future releases.

---

### 2.2 Storage & Configuration Paths (`src/brahmastra/infrastructure/config.py`)
- **CRITICAL DEFECT — Hardcoded User Directory:**
  [`src/brahmastra/infrastructure/config.py:11`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/config.py#L11):
  ```python
  DEFAULT_STATIC_PROJECT_DIR = Path("/Users/kunalkhande/Project /Bhramstra")
  ```
  - **Impact:** If `brahmastra` is run in an empty directory outside a git repository or project without `BRAHMASTRA_HOME`, it attempts to write to `/Users/kunalkhande/Project /Bhramstra/.brahmastra`. On Linux, Windows, or any other user's machine, this directory does not exist and throws `PermissionError` or `FileNotFoundError`.
- **Global Configuration Strategy Missing:**
  - Standalone CLIs require a standard user configuration root:
    - **Linux:** XDG specification (`$XDG_DATA_HOME/brahmastra` or `~/.local/share/brahmastra`, with fallback to `~/.brahmastra`).
    - **macOS:** `~/Library/Application Support/brahmastra` or `~/.brahmastra`.
    - **Windows:** `%LOCALAPPDATA%\brahmastra` or `%USERPROFILE%\.brahmastra`.
- **Filesystem Permissions:**
  - Linux/macOS require `chmod 0o700` on `.brahmastra` directory and `chmod 0o600` on `state.json` and `brahmastra.db`.
  - On Windows, POSIX chmod modes are largely ignored. Windows requires proper inheritance or ACL settings to protect credentials.

---

### 2.3 Secure Credential Storage (`src/brahmastra/infrastructure/vault/`)
- **Current macOS Implementation:**
  [`src/brahmastra/infrastructure/vault/macos_keychain.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py):
  - Uses direct `ctypes` to `/System/Library/Frameworks/Security.framework/Security` and `CoreFoundation.framework`.
  - Fully compliant with `BRAH-SEC-002` (zero argv exposure).
  - Compatible with macOS Apple Silicon (`arm64`) and macOS Intel (`x86_64`).
- **CRITICAL GAP — Non-Darwin Fallback:**
  [`src/brahmastra/infrastructure/vault/factory.py:42-45`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/factory.py#L42-L45):
  ```python
  # Non-macOS fallback default
  if _default_memory_vault is None:
      _default_memory_vault = InMemoryVault()
  return _default_memory_vault
  ```
  - **Impact on Linux & Windows:** When users run `brahmastra key add` on Linux or Windows, credentials are stored in `InMemoryVault()`. As soon as the CLI process exits, **all API keys are wiped**. The CLI is completely non-functional for persistent credential management on Linux and Windows.
- **Legacy macOS CLI `/usr/bin/security` in Subprocess:**
  - `MacOSKeychainVault.get_secret`, `has_secret`, and `delete_secret` still contain fallback subprocess branches invoking `/usr/bin/security`. On Linux/Windows, `/usr/bin/security` does not exist (`FileNotFoundError`).

---

### 2.4 Subprocess Execution & Process Isolation (`src/brahmastra/domain/execution/test_runner.py`)
- **POSIX-Specific Process Group Isolation:**
  [`src/brahmastra/domain/execution/test_runner.py:89-114`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/domain/execution/test_runner.py#L89-L114):
  - Uses `preexec_fn=os.setsid` and `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`.
  - Protected with `if hasattr(os, "setsid")` and `if hasattr(os, "killpg")`.
  - **Windows Limitation:** On Windows, `os.setsid` and `os.killpg` do not exist. When timeouts occur, `proc.kill()` is called. Under Windows, `proc.kill()` only terminates the root parent process, leaving child processes (e.g. pytest worker sub-processes) orphaned in the background. Windows requires `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` and Windows Job Objects or `taskkill /F /T /PID <pid>` for complete process tree cleanup.
- **Environment Sanitization:**
  - `PRESERVED_SYSTEM_ENV` includes `SYSTEMROOT` and `COMSPEC`, which properly allows Windows Python subprocesses to initialize system DLLs.

---

### 2.5 Shell Command Security Policy (`src/brahmastra/domain/patch/command_policy.py`)
- **POSIX Shell Quoting Bias:**
  - Uses `shlex.split(cleaned_cmd)` which defaults to POSIX mode (`posix=True`).
  - On Windows, file paths use backslashes `\` (e.g. `src\brahmastra\app.py`). Under POSIX `shlex`, `\` is parsed as an escape character, mutilating Windows paths into `srcbrahmastraapp.py`.
- **Command Allowlist & Danger Patterns:**
  - `SAFE_EXECUTABLES: {"ls", "pwd", "whoami", "which", "pytest", "brahmastra"}`
    - On Windows `cmd.exe`: `dir`, `where` are standard inspection commands, but are currently rejected as `MODERATE`.
  - `DANGEROUS_PATTERNS`:
    - Flags Unix tools: `rm -rf`, `sudo`, `mkfs`, `fdisk`, `dd`.
    - **Missing Windows destructive patterns:** `del /s /q`, `rmdir /s /q`, `format`, `reg delete`, `certutil -urlcache`.

---

### 2.6 Local AI Engine Compatibility (`src/brahmastra/infrastructure/providers/ollama.py`)
- **Daemon Connectivity:**
  - Connects over loopback HTTP (`http://localhost:11434`, `http://127.0.0.1:11434`).
  - Standard socket and HTTP operations are fully portable across Linux, Windows, and macOS.
  - SSRF protections (IP canonicalization, DNS pre-resolution, private/link-local filtering) use standard Python libraries (`socket`, `ipaddress`, `urllib.parse`) and function identically on all platforms.
- **System Diagnostics (`doctor` command):**
  [`src/brahmastra/cli/commands/doctor.py:51-53`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/doctor.py#L51-L53):
  - Flags Windows with a yellow `[yellow]WARN[/yellow]` stating `Windows (Darwin/Linux recommended)`.
  - For official cross-platform distribution, Windows must be treated as a first-class supported OS with `[green]PASS[/green]`.

---

### 2.7 SQLite Persistence (`src/brahmastra/infrastructure/database/session.py`)
- **PRAGMA WAL Mode:**
  [`src/brahmastra/infrastructure/database/session.py:24`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/database/session.py#L24):
  - SQLite WAL (`PRAGMA journal_mode=WAL;`) requires shared memory (`.shm` and `.wal` companion files).
  - Functions cleanly on local Windows NTFS, macOS APFS, and Linux ext4/btrfs.
  - Caveat: Network drives (CIFS/NFS) on Windows/Linux do not support SQLite WAL mode; local user directory storage avoids this.

---

## 3. Platform Compatibility Matrix Summary

| Platform | Arch | Python | Packaging | Config / Storage | Vault Storage | Process Isolation | Shell Policy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **macOS** | ARM64 | 3.10 - 3.13 | Supported | Needs Fix (hardcoded path) | Fully Native (`Security.framework`) | Native POSIX (`setsid`) | Native POSIX |
| **macOS** | x86_64 | 3.10 - 3.13 | Supported | Needs Fix (hardcoded path) | Fully Native (`Security.framework`) | Native POSIX (`setsid`) | Native POSIX |
| **Linux** | x86_64 | 3.10 - 3.13 | Supported | Needs Fix (hardcoded path) | **BROKEN** (In-Memory wipe) | Native POSIX (`setsid`) | Native POSIX |
| **Linux** | ARM64 | 3.10 - 3.13 | Supported | Needs Fix (hardcoded path) | **BROKEN** (In-Memory wipe) | Native POSIX (`setsid`) | Native POSIX |
| **Windows** | x86_64 | 3.10 - 3.13 | Needs Meta | Needs Fix (hardcoded path) | **BROKEN** (In-Memory wipe) | **PARTIAL** (Orphan processes) | **DEFECT** (`\` escape in shlex) |

---

## 4. Priority Remediation Plan for Cross-Platform Release

1. **P0: Fix Hardcoded Static Path** — Remove `DEFAULT_STATIC_PROJECT_DIR = Path("/Users/kunalkhande/Project /Bhramstra")` and adopt XDG/OS-standard user application data paths.
2. **P0: Implement Cross-Platform Vault** — Provide secure persistent storage for Linux (Freedesktop SecretService / libsecret or encrypted file vault) and Windows (Windows Credential Manager / `win32cred`).
3. **P1: Cross-Platform Shell & Path Parsing** — Ensure `shlex.split` respects Windows backslashes and add Windows-equivalent safe/dangerous command patterns.
4. **P1: Windows Process Tree Termination** — Ensure subprocess timeout terminates Windows process trees without leaking orphan processes.
5. **P1: Packaging & Metadata Updates** — Update `pyproject.toml` classifiers, dependencies, and build specs for PyPI publication.
