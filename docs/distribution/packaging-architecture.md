# BRAHMASTRA AI — Packaging & Distribution Architecture

**Document Reference:** DIST-PKG-2026-11-11  
**Target Registry:** Python Package Index (PyPI) & TestPyPI  
**Package Name:** `brahmastra` (Fallback option: `brahmastra-ai` if name conflict occurs)  
**Distribution Type:** Pure Python Wheel (`py3-none-any.whl`) and Source Distribution (`sdist.tar.gz`)  
**Status:** PROPOSED (Phase 2 Design Specification)

---

## 1. Packaging Metadata Specification

### 1.1 Project Identity
- **Package Name:** `brahmastra`
- **Current Version:** `0.1.0` (SemVer 2.0)
- **Description:** `"Provider-independent AI orchestration platform and CLI coding assistant"`
- **License:** `Apache-2.0`
- **Requires-Python:** `>=3.10`
- **Authors:** BRAHMASTRA AI Team (`support@brahmastra.ai` / project repository)
- **URLs:**
  - Homepage: `https://github.com/Kunalkh05/Bhramstra`
  - Documentation: `https://github.com/Kunalkh05/Bhramstra#readme`
  - Repository: `https://github.com/Kunalkh05/Bhramstra.git`
  - Issues: `https://github.com/Kunalkh05/Bhramstra/issues`
  - Changelog: `https://github.com/Kunalkh05/Bhramstra/blob/main/CHANGELOG.md`

### 1.2 PyPI Classifiers
```toml
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: OS Independent",
    "Operating System :: MacOS",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: Build Tools",
    "Topic :: Software Development :: Quality Assurance",
    "Topic :: Security",
    "Topic :: Utilities",
]
```

---

## 2. Build Backend Evaluation

| Build Backend | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- |
| **`setuptools` (`setuptools.build_meta`)** | Default standard, already integrated, rock-solid stability, zero friction for legacy tools. | Slower build times, verbose configuration for complex plugins. | **Keep for v0.1.0** (Least disruptive; already working cleanly). |
| **`hatchling`** | Extremely clean metadata, deterministic builds, built-in environment management, fast. | Requires changing `[build-system]` and reconfiguring package discovery. | Consider for v0.2.0. |
| **`flit_core`** | Minimalist, very fast. | Lacks advanced package discovery and extension support. | Not recommended. |

**Decision:** Retain `setuptools>=68.0.0` with `build-backend = "setuptools.build_meta"` to preserve compatibility and prevent unintended build breakage across platforms.

---

## 3. Package Discovery & File Layout

- **Source Layout:** `src/` layout (Standard modern best practice).
  ```text
  src/
  └── brahmastra/
      ├── __init__.py
      ├── __main__.py
      ├── py.typed
      ├── cli/
      ├── application/
      ├── domain/
      └── infrastructure/
  ```
- **Configuration in `pyproject.toml`:**
  ```toml
  [tool.setuptools.packages.find]
  where = ["src"]
  include = ["brahmastra*"]
  namespaces = false

  [tool.setuptools.package-data]
  brahmastra = ["py.typed"]
  ```

---

## 4. Console Script Entry Points

### 4.1 CLI Command Wiring
```toml
[project.scripts]
brahmastra = "brahmastra.cli.app:main"
```

### 4.2 Python Direct Execution Support (`python -m brahmastra`)
Add `src/brahmastra/__main__.py`:
```python
from brahmastra.cli.app import main

if __name__ == "__main__":
    main()
```
This enables running `python -m brahmastra` in environments where script entrypoints are not on the user's `PATH`.

---

## 5. Dependency Management & Platform Groups

### 5.1 Core Runtime Dependencies
Essential dependencies required across all platforms:
```toml
dependencies = [
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pydantic>=2.5.0",
    "sqlalchemy>=2.0.0",
    "httpx>=0.27.0",
]
```

### 5.2 Secure Credential Storage Strategy
To eliminate the Linux and Windows credential loss defect without breaking macOS native security:
1. **Tier 1 (Zero-dependency OS Native):**
   - **macOS:** Native `Security.framework` C bindings via `ctypes` (already implemented and hardened in `BRAH-SEC-002`).
   - **Windows:** Native Windows Credential Manager (`win32cred`) via `ctypes` to `Advapi32.dll` (`CredWriteW`, `CredReadW`, `CredDeleteW`). Zero external dependencies required.
   - **Linux:** Freedesktop SecretService via DBus, or encrypted file vault using PBKDF2/Fernet with machine-bound master key.
2. **Tier 2 (Keyring Integration Option):**
   Add `keyring>=24.0.0` as an optional or platform-conditional dependency:
   ```toml
   [project.optional-dependencies]
   keyring = [
       "keyring>=24.0.0",
   ]
   ```

### 5.3 Optional & Development Dependency Groups
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "respx>=0.21.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "build>=1.2.0",
    "twine>=5.0.0",
]
test = [
    "pytest>=8.0.0",
    "respx>=0.21.0",
]
```

---

## 6. Installation & Upgrade User Workflows

### 6.1 Recommended Global Installation (`pipx` or `uv tool`)
```bash
# Recommended for CLI isolation (prevents dependency collision)
pipx install brahmastra

# Upgrade:
pipx upgrade brahmastra

# Or via uv:
uv tool install brahmastra
```

### 6.2 Standard Virtualenv Installation (`pip`)
```bash
pip install brahmastra
```

### 6.3 Post-Installation Verification
Upon first run or upgrade, the user can execute:
```bash
brahmastra doctor
```
This performs an immediate pre-flight check of the OS, architecture, database, vault, and local Ollama daemon.
