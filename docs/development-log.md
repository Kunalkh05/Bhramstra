# BRAHMASTRA AI — Development Log

This document records chronological progress, architectural decisions, commands executed, test results, and planned next steps across all milestones.

---

## [2026-11-09] — Milestone 0 & Milestone 1: Baseline Setup & CLI Shell

### Objectives
1. Inspect repository and establish safety baseline.
2. Configure Git version control, secret-safe `.gitignore`, and `pyproject.toml`.
3. Author foundational documentation (`README.md`, `docs/architecture.md`, `docs/concepts-for-beginners.md`, `docs/security.md`, `docs/development-log.md`).
4. Implement minimal CLI application with `--version`, `--help`, and `doctor` commands with macOS (ARM64/x86_64) diagnostic checks.
5. Create automated test suite for CLI commands and verify 100% pass rate.

### Actions Taken
- Initialized Git repository on `main` branch.
- Created `.gitignore` covering Python cache, virtual environments, OS files, and secret patterns (`.env`, `*.db`, `*.key`).
- Defined packaging via `pyproject.toml` with `typer`, `rich`, and `pydantic`.
- Authored baseline architectural and security documentation.
- Built `brahmastra.cli` package with:
  - `brahmastra --version`
  - `brahmastra --help`
  - `brahmastra doctor` (checking Python version, Darwin OS, architecture ARM64/x86_64, directory permissions).
- Implemented unit tests using Typer's `CliRunner`.

### Native Apple Silicon (M1 ARM64) Configuration & Test Results
- Resolved execution environment to native Apple Silicon (`arm64`):
  - Extracted native `arm64` architecture binary via `lipo` from universal Python 3.13 install.
  - Installed native Apple Silicon wheels (`pydantic_core-2.50.4-cp313-cp313-macosx_11_0_arm64.whl`).
- Command run: `.venv/bin/brahmastra doctor`
  - `CPU Architecture`: **PASS - Apple Silicon / ARM64 (arm64)**
  - All 6 diagnostic categories PASS.
- Test Suite: `.venv/bin/pytest tests/unit/test_cli.py`
  - Result: **5 passed in 0.08s (100% pass rate, native ARM execution)**.

### Known Limitations
- Milestone 1 provides the CLI framework and diagnostics only. Organization management, vault storage, and AI provider integration will be introduced in subsequent milestones.

### Next Step
- Milestone 2: Organization CRUD and active profile switching (Completed below).

---

## [2026-11-09] — Milestone 2: Organization CRUD & Active Profile Switching

### Objectives
1. Configure storage path to `/Users/kunalkhande/Project /Bhramstra/.brahmastra`.
2. Add `sqlalchemy>=2.0.0` and configure SQLite persistence.
3. Build domain models (`Organization`, `OrganizationCreate`) with input validation.
4. Implement application use cases (`create_organization`, `list_organizations`, `get_organization`, `get_active_organization`, `switch_active_organization`).
5. Build CLI commands:
   - `brahmastra org add <name> [--desc <text>]`
   - `brahmastra org list`
   - `brahmastra org current`
   - `brahmastra org switch <name>`
   - `brahmastra org show <name>`
6. Implement comprehensive unit tests (use cases & CLI commands) with zero warnings.
7. Connect and push repository to public GitHub at `https://github.com/Kunalkh05/Bhramstra`.

### Actions Taken
- Integrated `sqlalchemy` ORM with timezone-aware datetime columns and isolated session management.
- Implemented state tracking in `.brahmastra/state.json` with fallback resolution.
- Added Rich formatting tables for listing and inspecting organizations.
- Added strict organization name validation (alphanumeric with underscores and hyphens, 2-64 characters).
- Enforced unique organization names at both database and use case levels.

### Test Results
- Command run: `.venv/bin/pytest`
- Result: **14 passed in 0.48s (100% pass rate, 0 warnings)**
  - `tests/unit/test_cli.py`: 5 passed
  - `tests/unit/test_org_cli.py`: 4 passed
  - `tests/unit/test_org_use_cases.py`: 5 passed
- Live verification:
  - Created `personal` and `company` organizations.
  - Successfully listed, inspected, and switched active profile.
  - Verified `brahmastra doctor` validates `/Users/kunalkhande/Project /Bhramstra/.brahmastra`.

### Known Limitations
- Credentials, vault references, and provider account assignments will be attached to organizations in Milestones 3 and 4.

### Next Step
- Milestone 3: Vault abstraction and macOS Keychain integration (Completed below).

---

## [2026-11-09] — Milestone 3: Vault Abstraction & macOS Keychain Implementation

### Objectives
1. Define abstract `VaultInterface` contract for zero-plaintext secret storage.
2. Implement `MacOSKeychainVault` utilizing macOS's native `/usr/bin/security` CLI.
3. Implement `InMemoryVault` fake vault for isolated, fast test execution.
4. Provide `get_vault()` factory supporting runtime backend selection (`BRAHMASTRA_VAULT`).
5. Write unit tests for all vault backends and verify 100% pass rate.

### Actions Taken
- Implemented `src/brahmastra/domain/vault/interface.py` with `store_secret`, `get_secret`, `delete_secret`, and `has_secret`.
- Implemented `src/brahmastra/infrastructure/vault/macos_keychain.py` ensuring secrets are securely passed and `-w` flag is avoided during presence probes to prevent leakage.
- Implemented `src/brahmastra/infrastructure/vault/memory_vault.py` with non-persistent dictionary storage.
- Added 9 unit tests with mocked subprocess calls to test keychain commands without mutating the developer's personal macOS Keychain.

### Test Results
- Command run: `.venv/bin/pytest`
- Result: **23 passed in 0.43s (100% pass rate, 0 warnings)**

### Known Limitations
- Milestone 4 will connect this vault abstraction to database credential records and organization assignments (`brahmastra key` and `brahmastra provider` commands).

### Next Step
- Milestone 4: Credential lifecycle and organization-account assignment (Completed below).

---

## [2026-11-09] — Milestone 4: Credential Lifecycle & Organization-Account Assignment

### Objectives
1. Implement database schemas for `ProviderAccountModel`, `OrganizationAssignmentModel`, and `CredentialModel`.
2. Guarantee that SQLite stores strictly metadata and non-secret vault references (`vault_ref`), never raw API keys.
3. Enforce organization boundary isolation: organizations can only list and access provider accounts explicitly assigned to them.
4. Implement secure CLI commands:
   - `brahmastra provider add <type> <name> [--endpoint <url>] [--desc <desc>] [--assign-org <org>]`
   - `brahmastra provider list [--org <org>]`
   - `brahmastra provider test <account>`
   - `brahmastra key add <account> <label> [--secret-stdin]` (masked input, non-echoing prompt)
   - `brahmastra key list [--account <name>] [--org <name>]`
   - `brahmastra key test <label> --account <name>`
   - `brahmastra key rotate <label> --account <name>`
   - `brahmastra key revoke <label> --account <name>`
   - `brahmastra key remove <label> --account <name>`
5. Add unit and CLI integration tests; verify 100% pass rate.

### Actions Taken
- Created `src/brahmastra/domain/credentials/models.py` with `mask_secret()` helper and validated Pydantic models.
- Implemented `ProviderAccountModel`, `OrganizationAssignmentModel`, and `CredentialModel` in `src/brahmastra/infrastructure/database/models.py`.
- Developed application use cases in `src/brahmastra/application/use_cases/credential_use_cases.py` enforcing organization isolation.
- Created Typer CLI subcommands in `provider.py` and `key.py` with masked prompts and Rich tables.
- Implemented singleton caching in `factory.py` for `InMemoryVault`.

### Test Results
- Command run: `.venv/bin/pytest`
- Result: **27 passed in 0.50s (100% pass rate, 0 warnings)**
  - `tests/unit/test_cli.py`: 5 passed
  - `tests/unit/test_org_cli.py`: 4 passed
  - `tests/unit/test_org_use_cases.py`: 5 passed
  - `tests/unit/test_vault.py`: 9 passed
  - `tests/unit/test_credential_use_cases.py`: 2 passed
  - `tests/unit/test_provider_key_cli.py`: 2 passed
- Live verification:
  - Registered `openrouter-main` and `ollama-local` assigned to `company`.
  - Stored credential `prod-key` securely via standard input redirection.
  - Tested credential accessibility in OS Vault (`status=ACTIVE, health=HEALTHY`).

### Known Limitations
- Milestone 5 will introduce the normalized provider interface and live adapters for OpenRouter and Ollama.

### Next Step
- Milestone 5: Provider interface plus OpenRouter and Ollama adapters.
