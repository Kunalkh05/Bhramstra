# BRAHMASTRA AI

> **A provider-independent AI orchestration platform and developer CLI assistant.**

BRAHMASTRA is built from first principles as a modular monolith designed to give developers total control over AI model routing, multi-account credential management, organization isolation, and repository-aware coding assistance.

---

## Key Pillars

1. **Provider Independence:** First-class support for cloud APIs (OpenRouter) and local runtimes (Ollama) behind a normalized provider contract.
2. **Credential Organization Management (COM):** Strict organization isolation. Secrets are kept in the OS credential vault (macOS Keychain), never in SQLite, configuration files, or logs.
3. **Cross-Architecture Mac Compatibility:** Fully tested and supported on macOS across both Apple Silicon (`arm64`) and Intel (`x86_64`) architectures.
4. **Explainable Routing:** Clear, constraint-based model selection without hidden black-box logic.
5. **Controlled Execution:** Untrusted model output; explicit approval required for file writes and shell execution.

---

## Quickstart

### Prerequisites
- macOS (Apple Silicon `arm64` or Intel `x86_64`) or Linux.
- Python 3.10 or higher (tested on Python 3.13).

### Installation (Development Mode)

```bash
# 1. Clone repository & navigate to directory
cd "/Users/kunalkhande/Project /Bhramstra"

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode with development tools
pip install -e ".[dev]"

# 4. Verify installation
brahmastra --help
brahmastra --version
brahmastra doctor
```

---

## Project Status

- **Current Milestone:** Milestone 1 (CLI Shell & System Diagnostics)
- **Roadmap:**
  - [x] Milestone 0: Baseline documentation, safety standards, and project hygiene.
  - [x] Milestone 1: Minimal CLI shell (`--help`, `--version`, `doctor`), automated tests.
  - [ ] Milestone 2: Organization CRUD and active profile switching.
  - [ ] Milestone 3: Vault abstraction and macOS Keychain integration.
  - [ ] Milestone 4: Credential lifecycle and organization-account assignments.
  - [ ] Milestone 5: Provider contract, OpenRouter & Ollama adapters.
  - [ ] Milestone 6: Model registry, health status, and usage tracking.
  - [ ] Milestone 7: Explainable routing engine.
  - [ ] Milestone 8: Read-only repository analysis.
  - [ ] Milestone 9: User-approved code changes and patch inspection.
  - [ ] Milestone 10: Sandboxed execution & bounded retries.
  - [ ] Milestone 11: Evaluation harness & benchmarks.
  - [ ] Milestone 12: Security hardening & production packaging.

---

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Concepts for Beginners](docs/concepts-for-beginners.md)
- [Security Model & Safeguards](docs/security.md)
- [Development Log](docs/development-log.md)
