# BRAHMASTRA AI — Comprehensive Threat Model (STRIDE)

**Document Version:** 1.0  
**Author:** Agent 1 — Threat Model Analyst (BRAHMASTRA Security Council)  
**Date:** 2026-11-09  
**Status:** ACCEPTED (Council Review)

---

## 1. System Overview & Trust Architecture

BRAHMASTRA AI is a developer CLI orchestration platform enabling local and cloud AI inference, repository static analysis, autonomous patching, and sandboxed test verification on macOS (Apple Silicon M1/Darwin) and Linux.

```
                      TRUST BOUNDARY 0: Host User & Terminal
                                        │
                    ┌───────────────────▼───────────────────┐
                    │      BRAHMASTRA CLI Process (Python)  │
                    │   • Typer / Rich UI Engine            │
                    │   • LogSanitizer (Regex Scrubbing)    │
                    └───────┬───────────────────────────┬───┘
                            │                           │
  TRUST BOUNDARY 1: Local Storage                       │ TRUST BOUNDARY 2: OS Vault
  ┌─────────────────────────▼───────────────┐           │ ┌─────────────────────────▼───────────────┐
  │ SQLite (.brahmastra/brahmastra.db)      │           │ │ macOS Keychain (Security.framework)     │
  │ • Organizations & Profiles              │           │ │ • Encrypted API Keys & Passwords        │
  │ • Provider Accounts & Assignments       │           │ │ • Service: brahmastra:<provider>        │
  │ • Token Accounting (cost_micro_usd)     │           │ │ • Zero plaintext keys stored in DB      │
  └─────────────────────────────────────────┘           │ └─────────────────────────────────────────┘
                            │                           │
                            └──────────────┬────────────┘
                                           │
  TRUST BOUNDARY 3: Execution Sandbox      │ TRUST BOUNDARY 4: Network Inference
  ┌─────────────────────────▼───────────┐  │ ┌─────────────────────────▼───────────┐
  │ Isolated Subprocess (os.setsid)     │  │ │ OpenRouter (Cloud HTTPS) /          │
  │ • Stripped Env (No Secrets)         │  │ │ Ollama (127.0.0.1:11434 Local daemon│
  │ • Wall-Clock Timeout (SIGKILL)      │  │ │ • Prompt token transmission         │
  │ • Bounded Retries (max <= 3)        │  │ │ • Model generation responses        │
  └─────────────────────────────────────┘  │ └─────────────────────────────────────┘
```

---

## 2. Assets & Security Boundaries

| Asset ID | Asset Name | Sensitivity | Storage Location | Protection Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **AST-01** | Provider API Keys & Master Tokens | **CRITICAL** | macOS Keychain (`/usr/bin/security`) | OS-level encryption, ephemeral RAM access |
| **AST-02** | Organization Separation Boundaries | **HIGH** | SQLite `OrganizationAssignmentModel` | Explicit foreign-key tenant scoping |
| **AST-03** | Local Source Code Repository | **HIGH** | Host Filesystem (`CWD`) | Canonical path validation, read-only analysis |
| **AST-04** | Execution Environment / Host Shell | **CRITICAL** | Host OS Kernel / Shell | `CommandPolicyEngine` approval gates |
| **AST-05** | Financial & Usage Records | **MEDIUM** | SQLite `UsageRecordModel` | Micro-USD integer accounting (`cost_micro_usd`) |

---

## 3. STRIDE Threat Analysis

### 3.1 Spoofing (Identity & Tenant Spoofing)
- **Threat-S1: Cross-Tenant Account Manipulation**
  - *Description:* An adversary operating in Organization B supplies the name of a Provider Account belonging to Organization A in credential management commands (`rotate`, `revoke`, `remove`).
  - *Vulnerability ID:* `BRAH-SEC-001`
  - *Risk:* Unauthorized account modification or denial of service across organizations.

### 3.2 Tampering (Filesystem & Database Integrity)
- **Threat-T1: Path Traversal Symlink Escape**
  - *Description:* AI model or attacker-crafted patch contains symlinks pointing outside the project root to overwrite critical system files (`/etc/hosts`, `~/.zshrc`).
  - *Mitigation in Place:* `DiffEngine.validate_safe_path` resolves canonical paths against project root and verifies `Path.relative_to(root)`.
- **Threat-T2: Internal State Tampering**
  - *Description:* Patch targets internal databases (`.brahmastra/brahmastra.db`) or Git internals (`.git/config`).
  - *Mitigation in Place:* Restricted directory and extension blocklists.

### 3.3 Repudiation (Audit & Accounting)
- **Threat-R1: Model Usage Falsification**
  - *Description:* Untrusted response metrics falsify token counts or prices.
  - *Mitigation in Place:* Exact integer micro-USD pricing calculations with immutable request audit records in SQLite.

### 3.4 Information Disclosure (Credential & Data Leakage)
- **Threat-I1: Command-Line Argument Snooping (`ps aux`)**
  - *Description:* Invoking `/usr/bin/security add-generic-password -w <secret>` passes raw secrets as command arguments, exposing them in process tables to unprivileged users on the host.
  - *Vulnerability ID:* `BRAH-SEC-002`
  - *Risk:* Immediate credential compromise by co-located processes.
- **Threat-I2: Arbitrary File Read via Whitelisted Shell Commands**
  - *Description:* `CommandPolicyEngine` whitelists `cat` as `SAFE_READ`, allowing `cat .env` or `cat ~/.ssh/id_rsa` to bypass interactive approval gates under `--yes`.
  - *Vulnerability ID:* `BRAH-SEC-003`

### 3.5 Denial of Service (Execution & Resource Exhaustion)
- **Threat-D1: Subprocess Deadlocks & Infinite Loops**
  - *Description:* Malicious or buggy tests run infinite loops or hang on network connections.
  - *Mitigation in Place:* `ControlledTestRunner` enforces POSIX process group timeouts and kills runaway trees with `SIGKILL`.

### 3.6 Elevation of Privilege (Command Injection)
- **Threat-E1: Pytest Flag & Config Injection**
  - *Description:* Injecting command flags (`--override-ini`, `--import-mode`) into `brahmastra test <target>` alters test runner behavior or executes arbitrary Python hooks.
  - *Vulnerability ID:* `BRAH-SEC-004`
