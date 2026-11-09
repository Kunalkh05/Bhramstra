# BRAHMASTRA AI — Evidence-Backed Risk Register

**Maintained by:** Agent 2 — Defensive Code Auditor  
**Date:** 2026-11-09  
**Status:** ACTIVE (Council Audited)

---

## 1. Summary of Identified Findings

| Finding ID | Severity | Category | Affected Component | File & Line Range | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **BRAH-SEC-001** | **HIGH** | Access Control / Isolation | Credential Lifecycle Use Cases | `application/use_cases/credential_use_cases.py` (L26-L450) | **VERIFIED_FIXED** |
| **BRAH-SEC-002** | **HIGH** | Credential Exposure | macOS Keychain Subprocess Invocation | `infrastructure/vault/macos_keychain.py` (L29-L40) | **ACCEPTED** |
| **BRAH-SEC-003** | **MEDIUM** | Information Disclosure | Shell Command Policy Engine | `domain/patch/command_policy.py` (L27-L40, L61) | **ACCEPTED** |
| **BRAH-SEC-004** | **MEDIUM** | Injection | Sandboxed Test Command Runner | `application/use_cases/execution_use_cases.py` (L30-L38) | **ACCEPTED** |
| **BRAH-SEC-005** | **LOW** | Network Security | Local Inference Daemon | `infrastructure/providers/ollama.py` (L24-L35) | **ACCEPTED** |

---

## 2. Detailed Vulnerability Records

### BRAH-SEC-001: Missing Organization Scoping on Credential Rotation, Revocation, and Removal
- **Severity:** HIGH  
- **Confidence:** CONFIRMED (100% reproducible)  
- **Affected Component:** `credential_use_cases.py` (Functions: `rotate_credential`, `revoke_credential`, `remove_credential`, `verify_credential`)
- **Exact Code Evidence:**
  [`src/brahmastra/application/use_cases/credential_use_cases.py#L308-L322`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L308-L322)
  ```python
  account = session.scalar(
      select(ProviderAccountModel).where(ProviderAccountModel.name == account_name)
  )
  cred = session.scalar(
      select(CredentialModel).where(
          CredentialModel.account_id == account.id,
          CredentialModel.label == label,
      )
  )
  ```
- **Trust Boundary:** Tenant isolation between logical organizations.
- **Preconditions:** Adversary knows or enumerates the `account_name` and credential `label` of another organization.
- **Expected Behavior:** `rotate_credential`, `revoke_credential`, and `remove_credential` must require an explicit `org_name` argument (or active org) and verify that `OrganizationAssignmentModel` links that account to the active organization.
- **Actual Behavior:** Queries filter purely by `ProviderAccountModel.name` without joining `OrganizationAssignmentModel`. Any caller can mutate, revoke, or delete credentials belonging to any other organization.
- **Impact:** Cross-tenant denial of service and credential hijacking.
- **Resolution:** RESOLVED & VERIFIED. Added `_verify_account_organization_scoping` checks to `add_credential`, `verify_credential`, `rotate_credential`, `revoke_credential`, and `remove_credential`. Added `--org` parameter across all CLI key management commands. Full regression suite in `tests/security/test_tenant_isolation_security.py` passes 5/5.

---

### BRAH-SEC-002: Secret Exposure via Process Table Command-Line Arguments (`-w <secret>`)
- **Severity:** HIGH  
- **Confidence:** CONFIRMED (100% reproducible)  
- **Affected Component:** `MacOSKeychainVault.store_secret`
- **Exact Code Evidence:**
  [`src/brahmastra/infrastructure/vault/macos_keychain.py#L29-L37`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L29-L37)
  ```python
  cmd = [
      self.executable_path,
      "add-generic-password",
      "-a", account,
      "-s", service,
      "-w", secret,
      "-U",
  ]
  res = subprocess.run(cmd, capture_output=True, text=True)
  ```
- **Trust Boundary:** Host process boundary between BRAHMASTRA and other local unprivileged processes.
- **Preconditions:** Any process on macOS running under the same user UID executing `ps -ef`, `pgrep -a security`, or calling `sysdiagnose`.
- **Expected Behavior:** Secrets must be passed via standard input pipes or directly via C in-memory APIs (`Security.framework`), never appearing in process `argv`.
- **Actual Behavior:** The raw plaintext secret is passed as the `-w` argument to `/usr/bin/security`.
- **Impact:** Immediate plaintext credential compromise on multi-process host environments.

---

### BRAH-SEC-003: Sensitive File Disclosure via Unrestricted `cat` in Command Whitelist
- **Severity:** MEDIUM  
- **Confidence:** CONFIRMED (100% reproducible)  
- **Affected Component:** `CommandPolicyEngine.SAFE_COMMAND_PREFIXES`
- **Exact Code Evidence:**
  [`src/brahmastra/domain/patch/command_policy.py#L27-L40`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/domain/patch/command_policy.py#L27-L40)
  ```python
  SAFE_COMMAND_PREFIXES: List[str] = [
      "ls", "git status", ..., "cat", ...
  ]
  ```
- **Trust Boundary:** Tool execution approval gate.
- **Preconditions:** Command string begins with `cat` (e.g., `cat .env`, `cat ~/.ssh/id_rsa`, `cat .brahmastra/brahmastra.db`).
- **Expected Behavior:** Commands targeting protected configuration, private keys, or system password databases must be flagged as `MODERATE` or `DANGEROUS` and require explicit interactive confirmation.
- **Actual Behavior:** Any command starting with `cat` and lacking shell redirection operators is categorized as `SAFE_READ` and can be auto-executed under `--yes`.
- **Impact:** Exfiltration of local secrets and SSH keys by automated workflows.

---

### BRAH-SEC-004: Arbitrary Pytest Flag & Option Injection in Test Subprocess Runner
- **Severity:** MEDIUM  
- **Confidence:** CONFIRMED (100% reproducible)  
- **Affected Component:** `execution_use_cases.run_project_tests`
- **Exact Code Evidence:**
  [`src/brahmastra/application/use_cases/execution_use_cases.py#L30-L36`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/execution_use_cases.py#L30-L36)
  ```python
  cmd = [sys.executable, "-m", "pytest", "-v"]
  if target:
      cmd.append(target)
  ```
- **Trust Boundary:** Sandboxed test execution boundary.
- **Preconditions:** Target argument begins with a dash `-` (e.g., `brahmastra test "--override-ini=addopts=-s"`).
- **Expected Behavior:** Target argument must be validated to ensure it is a safe file path or module path, not a flag starting with `-`.
- **Actual Behavior:** Arbitrary flags are passed directly to `pytest`, allowing modification of test runner runtime hooks and configuration.
- **Impact:** Subversion of test execution controls and sandbox circumvention.

---

### BRAH-SEC-005: Unauthenticated Local Inference Daemon Probe
- **Severity:** LOW / INFORMATIONAL  
- **Confidence:** CONFIRMED  
- **Affected Component:** `OllamaAdapter`
- **Exact Code Evidence:** [`src/brahmastra/infrastructure/providers/ollama.py#L24-L35`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L24-L35)
- **Description:** Default endpoint `http://127.0.0.1:11434` does not enforce bearer tokens. Local processes on loopback can query Ollama daemon directly.
