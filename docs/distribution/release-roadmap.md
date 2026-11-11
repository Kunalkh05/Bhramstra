# BRAHMASTRA AI — Cross-Platform Release & Distribution Roadmap

**Document Reference:** DIST-ROADMAP-2026-11-11  
**Project:** BRAHMASTRA AI (`brahmastra`)  
**Target Matrix:** macOS (ARM64/x86_64), Linux (x86_64/ARM64), Windows (x86_64)  
**Distribution Channel:** PyPI / TestPyPI  
**Status:** PROPOSED (Phases 3, 4, 5 Architecture Plan)

---

## 1. Platform Abstraction Architecture (Phase 3 Design)

To preserve the hard-won security guarantees (BRAH-SEC-001 through BRAH-SEC-005) while running seamlessly across Linux, Windows, and macOS, four platform adapters are designed:

### 1.1 Secure Credential Storage Adapter (`VaultInterface`)
```
                     ┌───────────────────────────────┐
                     │        VaultInterface         │
                     │  (store, get, delete, has)    │
                     └───────────────┬───────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│ MacOSKeychain    │       │ WindowsCredVault │        │ LinuxSecretVault │
│ (Security.fwk    │       │ (Advapi32.dll    │        │ (SecretService   │
│  native C ctypes)│       │  CredWrite/Read) │        │  or Encrypted)   │
└──────────────────┘       └──────────────────┘        └──────────────────┘
```

1. **macOS (`MacOSKeychainVault`):**
   - Retain current native C bindings to `Security.framework` (`SecKeychainAddGenericPassword`, `SecKeychainFindGenericPassword`, `SecKeychainItemModifyAttributesAndData`, `SecKeychainItemDelete`).
   - Guarantees zero `argv` leakage (`BRAH-SEC-002`).
2. **Windows (`WindowsCredentialVault`):**
   - Implement via `ctypes` bindings to `Advapi32.dll` (`CredWriteW`, `CredReadW`, `CredDeleteW`, `CredFree`).
   - Zero external dependencies.
   - Credentials stored in official Windows Credential Manager under target prefix `brahmastra:<service>:<account>`.
   - In-memory UTF-16 byte pointer passing guarantees zero `argv` exposure.
3. **Linux (`LinuxSecretServiceVault`):**
   - Primary: Freedesktop SecretService API via DBus (`org.freedesktop.secrets`).
   - Headless / CI Fallback: File-based vault encrypted with AES-256-GCM / PBKDF2 using a machine-specific key salt (`/etc/machine-id` + user UID) with `chmod 0o600` permissions.
4. **Test / Hermetic (`InMemoryVault`):**
   - Activated strictly when `BRAHMASTRA_VAULT=memory` for isolated tests.

---

### 1.2 Storage & Configuration Path Adapter (`config.py`)
Replace hardcoded developer paths with standard multi-platform path resolution:
```python
def get_user_data_dir() -> Path:
    """Resolve OS-standard user data directory."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "brahmastra"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "brahmastra"
    else:
        # Linux / XDG
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        return Path(base) / "brahmastra"
```
- Workspace-local storage (`.brahmastra` in project root) is preferred when running inside a project.
- Global fallback defaults to `get_user_data_dir()`.
- Directory permissions enforced as `0o700` (POSIX) and read/write restricted to owner.

---

### 1.3 Shell Execution & Policy Adapter (`command_policy.py`)
1. **Windows Path Separator Handling:**
   - Detect OS via `sys.platform == "win32"`.
   - On Windows, use Windows-aware path tokenization (`shlex.split(..., posix=False)`) to prevent backslashes (`\`) from being stripped as POSIX escape characters.
2. **Windows Command Allowlist & Danger Patterns:**
   - Add safe Windows inspection executables: `dir`, `where.exe`, `where`.
   - Add destructive Windows patterns to `DANGEROUS_PATTERNS`:
     - `\bdel\s+(/[sS]\s+|/[qQ]\s+)*`
     - `\b(rmdir|rd)\s+(/[sS]\s+|/[qQ]\s+)*`
     - `\bformat\s+[A-Za-z]:`
     - `\b(reg\s+delete|certutil\s+-urlcache)`

---

### 1.4 Process Group Isolation Adapter (`test_runner.py`)
1. **POSIX (macOS / Linux):**
   - Retain `preexec_fn=os.setsid` and `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`.
2. **Windows:**
   - Use `subprocess.Popen(..., creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)`.
   - On timeout, invoke `taskkill /F /T /PID {proc.pid}` via standard library to recursively terminate the entire Windows process subtree, avoiding orphaned processes.

---

## 2. CI/CD Architecture (Phase 4 Design)

### 2.1 Multi-OS Test Matrix
A comprehensive GitHub Actions workflow testing across 5 distinct platform/runner targets:

```yaml
name: CI Matrix

on:
  push:
    branches: [main, feat/*, fix/*]
  pull_request:
    branches: [main]

jobs:
  test:
    name: ${{ matrix.os }} - Python ${{ matrix.python-version }} (${{ matrix.arch }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          # macOS Apple Silicon (ARM64)
          - os: macos-14
            python-version: "3.11"
            arch: arm64
          - os: macos-14
            python-version: "3.12"
            arch: arm64
          # macOS Intel (x86_64)
          - os: macos-13
            python-version: "3.11"
            arch: x86_64
          # Linux x86_64
          - os: ubuntu-latest
            python-version: "3.10"
            arch: x86_64
          - os: ubuntu-latest
            python-version: "3.11"
            arch: x86_64
          - os: ubuntu-latest
            python-version: "3.12"
            arch: x86_64
          - os: ubuntu-latest
            python-version: "3.13"
            arch: x86_64
          # Windows x86_64
          - os: windows-latest
            python-version: "3.11"
            arch: x64
          - os: windows-latest
            python-version: "3.12"
            arch: x64

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Code formatting & Linting (ruff)
        run: |
          ruff check src/ tests/

      - name: Execute Full Test Suite & Security Regression Tests
        run: |
          pytest -v --tb=short

      - name: Build Wheel & Sdist
        run: |
          python -m pip install build twine
          python -m build
          twine check dist/*

      - name: Smoke Test CLI Installation
        run: |
          python -m pip install dist/*.whl
          brahmastra --version
          brahmastra doctor
```

---

## 3. PyPI Release Workflow (Phase 5 Design)

### 3.1 Security-First Publishing with PyPI Trusted Publishing (OIDC)
- **Zero Static Tokens:** No long-lived API tokens stored in GitHub repository secrets.
- **GitHub Actions OIDC:** Authentication directly with PyPI via `pypa/gh-action-pypa-publisher@release/v1` through OpenID Connect.
- **Environment Gating:** Deployment bound to a protected `pypi` environment in GitHub requiring manual release approval.

### 3.2 Two-Stage Deployment Pipeline:
1. **Stage 1: TestPyPI Deployment:**
   - Triggered on tag `v*-rc*` or workflow dispatch.
   - Validates that package uploads, dependencies resolve, and `pip install --index-url https://test.pypi.org/simple/ brahmastra` installs and runs cleanly on clean VMs.
2. **Stage 2: Production PyPI Release:**
   - Triggered on official semantic version tag `v[0-9]+.[0-9]+.[0-9]+` (e.g. `v0.1.0`).
   - Requires manual reviewer approval in GitHub Environment.
   - Publishes `.whl` and `.tar.gz` to PyPI.
   - Automatically drafts GitHub Release with auto-generated release notes, changelog, and SHA-256 checksums.

---

## 4. Execution Plan (Post-Approval)

| Phase | Milestone | Scope | Validation Gate |
| :---: | :--- | :--- | :--- |
| **Phase 3.1** | Config & Path Portability | Remove hardcoded paths; implement `get_user_data_dir()` for Linux/macOS/Windows | Tests pass on macOS, Linux paths validated |
| **Phase 3.2** | Windows Native Vault | Implement `WindowsCredentialVault` via `Advapi32.dll` ctypes | Unit tests with mock Advapi32; fail-closed checks |
| **Phase 3.3** | Linux Secret Storage | Implement `LinuxSecretServiceVault` / Encrypted vault | Unit tests with mock DBus/SecretService |
| **Phase 3.4** | Shell & Process Portability | Windows `shlex` fix, dangerous Windows patterns, Windows process tree termination | Command policy and test runner tests pass |
| **Phase 4** | CI Workflow Automation | Create `.github/workflows/ci.yml` matrix (macOS, Linux, Windows) | Green runs across all 5 OS runner matrix targets |
| **Phase 5** | Packaging & PyPI Prep | Update `pyproject.toml`, add `py.typed`, verify `twine check` | Local wheel build & installation smoke test |
