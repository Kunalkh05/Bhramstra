# BRAHMASTRA Security Council — Decision Log

## Session: Council Initial Formation & Scope Baseline
**Date:** 2026-11-09  
**Facilitator:** Agent 0 (Security Orchestrator)

---

### ADR-BSC-001: Round 0 Scope & Architecture Assumptions

To enable unblocked, high-precision security analysis without delay, the Council establishes the following baseline operational assumptions grounded in the codebase inspection:

1. **Deployment Architecture:**
   - **Baseline:** Single-developer workstation CLI operating on macOS Darwin (Apple Silicon ARM64 / Intel x86_64).
   - **Multi-Tenancy:** Logical multi-tenant organization scoping stored locally in SQLite (`.brahmastra/brahmastra.db`). The CLI is not currently exposed as a multi-user network daemon.
   - **Risk if Assumption Differs:** If multi-user remote shared servers are supported, local filesystem permissions and SQLite file locking must be hardened against cross-UID access.

2. **Shell Command Execution:**
   - **Baseline:** Controlled via `CommandPolicyEngine`. Safe read-only commands (`ls`, `git status`, `pytest`) can be executed. High-risk commands (`rm -rf`, `sudo`, `dd`) require explicit manual user override and cannot be auto-approved even under `--yes`. Interactive confirmation prompt is the default.
   - **Risk if Assumption Differs:** If autonomous unbounded shell access is expected, sandbox isolation must be upgraded to container/chroot boundaries.

3. **Credential Storage & Sharing:**
   - **Baseline:** Credentials are stored exclusively in the macOS Keychain (`/usr/bin/security`) or in-memory vault. SQLite stores only metadata (`vault_key_id`, label, status). Credentials cannot be shared across organizations unless explicitly linked via `OrganizationAssignmentModel`.
   - **Risk if Assumption Differs:** Sharing credentials across organizations without explicit linkage creates cross-tenant information disclosure.

4. **Filesystem Boundaries:**
   - **Baseline:** Modifying files outside the workspace root is blocked via `DiffEngine.validate_safe_path`. Modification of `.git/`, `.brahmastra/`, `.env`, and database files is strictly forbidden.
   - **Risk if Assumption Differs:** Path traversal could overwrite host files or tamper with internal state.

5. **Data Transmission to AI Providers:**
   - **Baseline:** User prompts and task context are dispatched to configured providers (OpenRouter for cloud inference, Ollama for local offline inference). Local inference sends zero external network traffic.
   - **Risk if Assumption Differs:** Prompt leakage or secret exposure to third-party model providers if prompts contain credentials.

---

### Record of Proceedings

- **2026-11-09 15:28:** Council convened by user request. Task board initialized. Round 0 assumptions formulated. Launching independent Round 1 investigations across Threat Modeling, Defensive Code Auditing, and Red Team Attack Scenarios.
