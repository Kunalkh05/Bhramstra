# BRAHMASTRA AI — Evidence-Backed Risk Register

**Maintained by:** Agent 2 — Defensive Code Auditor  
**Date:** 2026-11-09  
**Status:** ACTIVE (Council Audited)

---

## 1. Summary of Identified Findings

| Finding ID | Severity | Category | Affected Component | File & Line Range | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **BRAH-SEC-001** | **HIGH** | Access Control / Isolation | Credential Lifecycle Use Cases | `application/use_cases/credential_use_cases.py` (L26-L450) | **VERIFIED_FIXED** |
| **BRAH-SEC-002** | **HIGH** | Credential Exposure | macOS Keychain Subprocess Invocation | `infrastructure/vault/macos_keychain.py` (L15-L250) | **VERIFIED_FIXED** |
| **BRAH-SEC-003** | **MEDIUM** | Information Disclosure | Shell Command Policy Engine | `domain/patch/command_policy.py` (L17-L70) | **VERIFIED_FIXED** |
| **BRAH-SEC-004** | **MEDIUM** | Injection | Sandboxed Test Command Runner | `application/use_cases/execution_use_cases.py` (L26-L45) | **VERIFIED_FIXED** |
| **BRAH-SEC-005** | **LOW** | Network Security | Local Inference Daemon | `infrastructure/providers/ollama.py` (L24-L50) | **VERIFIED_FIXED** |

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
- **Resolution:** RESOLVED & INDEPENDENTLY VERIFIED (Cycle 2 & Cycle 3).
  - Cycle 2: Added strict unscoped context protection: if `target_org is None` and an account has active assignments, operations fail-closed with `PermissionError`. In `list_credentials`, unscoped queries filter out org-assigned accounts via outer join, preventing cross-tenant enumeration.
  - Cycle 3: Hardened `assign_account_to_organization` to enforce single-tenant ownership; attempting to attach an account already assigned to another organization raises `PermissionError`. Hardened `list_provider_accounts` so scoped queries return only tenant accounts, and unscoped queries filter out all assigned accounts (`OrganizationAssignmentModel.id.is_(None)`).
  - Regression test suite expanded to 14 tests in `tests/security/test_tenant_isolation_security.py` covering all operations under unscoped and cross-tenant callers. 14/14 passing.

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
- **Resolution:** RESOLVED & INDEPENDENTLY VERIFIED (Cycle 2).
  - Completely purged insecure `subprocess.run` argv fallback (`-w <secret>`).
  - Implemented fail-closed semantics: raises `RuntimeError` immediately if native `Security.framework` C bindings are unavailable or initialization fails.
  - Hardened memory cleanup via `_CFRelease`.
  - Tested with 2/2 security regression tests in `tests/security/test_keychain_security.py` and 7/7 vault unit tests passing.

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
- **Resolution:** RESOLVED & INDEPENDENTLY VERIFIED (Cycle 2 & Cycle 3).
  - Cycle 2: Normalized shell quoting and escape characters before pattern matching; added `shlex.split` token inspection with symlink resolution (`Path.resolve()`); expanded sensitive targets list; restricted CLI `--yes` auto-approval strictly to `CommandRiskLevel.SAFE_READ`.
  - Cycle 3: Replaced fragile substring/startswith matching with exact token allowlist (`SAFE_EXECUTABLES: {"git", "pytest", "python", "python3", "ls", "echo", "pwd", "tree", "wc", "head", "tail", "cat"}`). For `git`, enforced strict `SAFE_GIT_SUBCOMMANDS`. Blocked command substitution (`$()`, ``` `` ```), newlines (`\n`, `\r`), input redirection (`<`), pipes, backgrounding, and compound metacharacters (`UNSAFE_SHELL_METACHARS = r"[\$`\n\r><|&;(){}\!]"`).
  - 30/30 security regression tests in `tests/security/test_command_policy_security.py` passing.

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
- **Resolution:** RESOLVED & VERIFIED. Validated that `target` cannot begin with `-` (blocking flag/option injection) and validated that target path does not escape the working directory via path traversal. Prepended `--` before positional targets in `pytest` invocation. 2/2 regression tests in `tests/security/test_execution_security.py` passing.

---

### BRAH-SEC-005: Local Inference Daemon SSRF & Unauthenticated Metadata Probing
- **Severity:** LOW / INFORMATIONAL  
- **Confidence:** CONFIRMED  
- **Affected Component:** `OllamaAdapter`
- **Exact Code Evidence:** [`src/brahmastra/infrastructure/providers/ollama.py#L24-L50`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L24-L50)
- **Description:** Ollama base URL configuration allowed arbitrary URL schemes and link-local cloud metadata addresses (`169.254.169.254`, `metadata.google.internal`), introducing potential SSRF risk in cloud-hosted multi-tenant developer environments.
- **Resolution:** RESOLVED & INDEPENDENTLY VERIFIED (Cycle 2 & Cycle 3).
  - Cycle 2: Enforced strict URI scheme allowlist (`http`, `https`); blocked cloud provider instance metadata service addresses (`169.254.169.254`, `metadata.google.internal`).
  - Cycle 3: Hardened IP canonicalization and validation. Parsed raw host via `int(raw_host, 0)` to intercept integer and hex IP encodings; resolved hostnames via `socket.getaddrinfo`; unwrapped IPv4-mapped IPv6 addresses (`ip.ipv4_mapped`); blocked private networks (RFC 1918), link-local (`169.254.0.0/16`, `fe80::/10`), AWS IMDS IPv6 (`fd00:ec2::254`), wildcard DNS (`nip.io`), multicast, and reserved addresses; restricted target strictly to loopback (`127.0.0.0/8`, `::1`); disabled HTTP redirects (`follow_redirects=False`) across all httpx clients.
  - Added 18 hermetic security regression tests in `tests/security/test_ollama_security.py`. 18/18 passing.
