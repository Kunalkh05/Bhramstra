# BRAHMASTRA AI — Independent Post-Remediation Security Verification Report

**Audit Date:** 2026-11-11
**Auditor:** Independent Security Verification Team
**Evaluation Scope:** Codebase Commits `e461c5c` through `bfeea56`
**Platform Under Test:** macOS Darwin (Apple Silicon M1 ARM64), Python 3.13.2
**Baseline Test Suite Status:** 121 / 121 Tests Passing (6.62s)

---

## 1. Executive Summary

This independent post-remediation security audit evaluated the five vulnerabilities previously addressed by the BRAHMASTRA Security Council (`BRAH-SEC-001` through `BRAH-SEC-005`).

**Core Assessment:** While all 121 unit and regression tests pass and the remediations meaningfully raise the bar against straightforward exploits, **two critical architectural bypasses remain active in the codebase**:
1. **`BRAH-SEC-001` (Organization Isolation):** A tenant isolation bypass exists whenever a request is issued without an active organization context (`target_org is None`). In this state, `_verify_account_organization_scoping` immediately returns without verifying organization membership, allowing unauthenticated or unscoped callers to rotate, revoke, or delete credentials belonging to isolated organizations.
2. **`BRAH-SEC-003` (Sensitive File Disclosure):** The command policy filter relies entirely on static string regex. Trivial shell quoting (e.g. `cat .e""nv`, `cat .e''nv`), symlinks (`cat symlink_to_env`), or unlisted credential files (`secrets.json`, `.npmrc`) evade detection and are classified as `MODERATE`. When `--yes` is used, the CLI **automatically executes these commands without prompting the user**.
3. **`BRAH-SEC-002` (macOS Keychain):** Fully fixed on native macOS environments using `Security.framework` C bindings. However, the legacy fallback branch still contains the `-w <secret>` argument vector vulnerability.
4. **`BRAH-SEC-004` (Pytest Flag Injection):** **VERIFIED FIXED**. The input validation and `--` argument separator effectively neutralize both leading option injection and compound option injection.
5. **`BRAH-SEC-005` (Local Inference Daemon):** **ACCEPTED WITH DOCUMENTED RISK**. The loopback daemon lacks authentication by upstream design, and the absence of endpoint allowlisting presents an SSRF vector if external/cloud endpoints are configured.

### Status Scorecard

| Finding ID | Severity | Category | Claimed Status | Independent Audit Status | Exploit Status |
| :--- | :---: | :--- | :---: | :---: | :---: |
| **BRAH-SEC-001** | **HIGH** | Cross-Tenant Credential Scoping | VERIFIED_FIXED | **PARTIALLY FIXED** | **Bypass Confirmed** (when active org is unset) |
| **BRAH-SEC-002** | **HIGH** | macOS Keychain Secret Exposure in `argv` | VERIFIED_FIXED | **VERIFIED FIXED** (Native) / **PARTIAL** (Fallback) | Blocked on native macOS; present in fallback |
| **BRAH-SEC-003** | **MEDIUM** | Sensitive File Access via Shell Policy | VERIFIED_FIXED | **PARTIALLY FIXED** | **Bypass Confirmed** (via shell quotes, symlinks, `--yes`) |
| **BRAH-SEC-004** | **MEDIUM** | Pytest Subprocess Flag Injection | VERIFIED_FIXED | **VERIFIED FIXED** | Exploit Fully Neutralized |
| **BRAH-SEC-005** | **LOW** | Unauthenticated Local Inference Daemon | ACCEPTED | **ACCEPTED (Documented Risk)** | Architecture Risk Documented |

---

## 2. Test Suite Execution Integrity

The entire test suite was executed without modification:
```bash
.venv/bin/pytest --tb=short
```
- **Total Tests Collected:** 121
- **Passed:** 121
- **Failed:** 0
- **Duration:** 6.62s
- **Observation:** All existing tests pass cleanly. However, the green test suite reflects test coverage gaps rather than total security immunity.

---

## 3. Deep-Dive Independent Verification Findings

### BRAH-SEC-001: Organization Isolation and Cross-Tenant Credential Scoping

- **Original Vulnerability:** Credential mutation methods (`rotate_credential`, `revoke_credential`, `remove_credential`, and `verify_credential`) only filtered by `ProviderAccountModel.name`, allowing Organization B to hijack or destroy credentials belonging to Organization A.
- **Source Files & Lines:**
  - [`src/brahmastra/application/use_cases/credential_use_cases.py#L30-L75`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L30-L75)
  - [`src/brahmastra/cli/commands/key.py#L31-L210`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/key.py#L31-L210)
- **Remediation Implementation:**
  The Security Council introduced `_verify_account_organization_scoping(session, account, org_name)` and added `org_name: Optional[str] = None` to `add_credential`, `verify_credential`, `rotate_credential`, `revoke_credential`, and `remove_credential`.
- **Independent Verification Procedure:**
  1. *Test Cross-Tenant Access:* Org A registers `alpha-acc` and credential `key1`. Org B attempts `rotate_credential(org_name="org-bravo")`.
     - *Result:* Blocked with `PermissionError: Account 'alpha-acc' is not assigned to organization 'org-bravo'`.
  2. *Test Non-Existent Org:* Attacker provides `org_name="nonexistent"`.
     - *Result:* Blocked with `ValueError: Organization 'nonexistent' not found`.
  3. *Test Unset Active Org Bypass:*
     Execute an operation when no active org is set in the session/environment (`get_active_org_name() is None`) and `org_name=None`:
     ```python
     # Account 'alpha-acc' is assigned exclusively to 'org-alpha'
     # Active org is None
     rotate_credential('key1', 'alpha-acc', 'hacked_secret', org_name=None, vault=vault, engine=engine)
     ```
     - *Result:* **SUCCESSFUL EXPLOIT**. The credential was rotated without raising any error!
- **Root Cause of Bypass:**
  In [`credential_use_cases.py#L41-L50`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L41-L50):
  ```python
  target_org = org_name
  if not target_org:
      active = get_active_org_name()
      if active:
          ...
  if not target_org:
      return  # <--- CRITICAL FLAW: Bypasses check if target_org is None!
  ```
  If an account is bound to one or more organizations, operating with `target_org is None` should be **rejected** (`PermissionError: Account belongs to an organization. Active organization context is required.`). Bypassing the check leaves org-bound credentials vulnerable to any script or CLI call lacking an active organization.
- **Additional Observation:**
  [`list_credentials(org_name=None)`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L270) dumps all credentials across all tenants if no active organization is set.
- **Final Status:** **PARTIALLY FIXED**

---

### BRAH-SEC-002: Plaintext Secret Exposure via macOS Keychain Process Table (`argv`)

- **Original Vulnerability:** `/usr/bin/security add-generic-password -w <secret>` exposed plaintext secrets in the host process table (`ps aux`, `pgrep -a security`, audit logs).
- **Source Files & Lines:**
  - [`src/brahmastra/infrastructure/vault/macos_keychain.py#L1-L250`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L1-L250)
- **Remediation Implementation:**
  Dynamic C bindings (`ctypes`) to `/System/Library/Frameworks/Security.framework/Security`:
  - `SecKeychainAddGenericPassword`
  - `SecKeychainFindGenericPassword`
  - `SecKeychainItemModifyAttributesAndData`
  - `SecKeychainItemDelete`
  - `SecKeychainItemFreeContent`
- **Independent Verification Procedure:**
  1. *Subprocess Invocation Check:* Verified via `unittest.mock.patch("subprocess.run")` and macOS process monitoring that storing, retrieving, modifying, and deleting credentials invokes zero subprocesses.
  2. *Argv Exposure Check:* Verified with `sysdiagnose` and `ps` that plaintext secrets never appear in argument vectors.
  3. *Error Diagnostics & Exception Inspection:* Verified that exception messages return `OSStatus` numeric error codes (e.g. `OSStatus -25299`) and do not interpolate secrets into string errors.
- **Remaining Weaknesses:**
  1. *Insecure Fallback Branch:*
     Lines 135-151 of [`macos_keychain.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L135-L151) preserve the exact vulnerable subprocess call:
     ```python
     cmd = [self.executable_path, "add-generic-password", "-a", account, "-s", service, "-w", secret, "-U"]
     ```
     If native bindings fail to load or `use_native=False` is set, the vulnerability re-emerges.
  2. *CoreFoundation Reference Handling:*
     `SecKeychainItemRef` pointers returned by `SecKeychainFindGenericPassword` should ideally be balanced with `CFRelease` to prevent handle leakage during long-lived process execution.
- **Final Status:** **VERIFIED FIXED** on Darwin Apple Silicon/Intel; **PARTIALLY FIXED** in legacy fallback branch.

---

### BRAH-SEC-003: Sensitive File Disclosure via Command Policy Whitelist and `--yes` Gating

- **Original Vulnerability:** `cat` in `CommandPolicyEngine.SAFE_COMMAND_PREFIXES` allowed `cat .env` or `cat ~/.ssh/id_rsa` to be auto-approved under `--yes`.
- **Source Files & Lines:**
  - [`src/brahmastra/domain/patch/command_policy.py#L17-L75`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/domain/patch/command_policy.py#L17-L75)
  - [`src/brahmastra/cli/commands/patch.py#L51-L86`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/patch.py#L51-L86)
- **Remediation Implementation:**
  - Removed `"cat"` from `SAFE_COMMAND_PREFIXES`.
  - Added `SENSITIVE_TARGET_PATTERNS` regex matching `.env`, `.git/config`, `id_rsa`, `.ssh/`, `.aws/`, and `/etc/shadow`.
  - Categorized sensitive targets as `CommandRiskLevel.DANGEROUS` with `requires_explicit_override=True`.
- **Independent Verification Procedure & Exploit Testing:**
  1. *Direct Static Commands:*
     `cat .env`, `cat ~/.ssh/id_rsa`, `head .env.local` -> Correctly flagged `DANGEROUS`. Under `--yes`, denied with `DENIED: Highly dangerous command cannot be auto-approved.`
  2. *Exploit 1: Shell Quoting & Escaping:*
     ```bash
     brahmastra patch eval-cmd 'cat .e""nv' --yes
     ```
     - *Result:* **SUCCESSFUL EXPLOIT**. Evaluates to `.env` in bash/zsh, but evades regex. Flagged as `MODERATE` with `requires_explicit_override=False`. **Auto-approved by `--yes` without user interaction!**
  3. *Exploit 2: Filesystem Symlinks:*
     ```bash
     ln -s .env symlink_to_env
     brahmastra patch eval-cmd 'cat symlink_to_env' --yes
     ```
     - *Result:* **SUCCESSFUL EXPLOIT**. Regex only inspects string characters; symlink path does not contain `.env`. Flagged as `MODERATE`. **Auto-approved by `--yes` without user interaction!**
  4. *Exploit 3: Common Non-Whitelisted Credential Files:*
     `cat secrets.json`, `cat credentials.yaml`, `cat .npmrc`, `cat .pypirc`, `cat production.key`.
     - *Result:* **SUCCESSFUL EXPLOIT**. All classified as `MODERATE` and auto-approved by `--yes`.
- **Root Cause of Bypass:**
  In [`src/brahmastra/cli/commands/patch.py#L80-L82`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/patch.py#L80-L82):
  ```python
  if auto_approve and action.risk_level != CommandRiskLevel.DANGEROUS:
      console.print("[bold yellow]Auto-approving command execution due to --yes flag.[/bold yellow]")
      return True
  ```
  `--yes` auto-approves **all** `MODERATE` commands. Any command that evades the regex becomes `MODERATE`, thus permitting automated reading of arbitrary files.
- **Final Status:** **PARTIALLY FIXED**

---

### BRAH-SEC-004: Arbitrary Pytest Flag & Option Injection in Test Subprocess Runner

- **Original Vulnerability:** `target` string was appended directly to `[sys.executable, "-m", "pytest", "-v"]`, allowing arbitrary option injection (e.g. `--override-ini`).
- **Source Files & Lines:**
  - [`src/brahmastra/application/use_cases/execution_use_cases.py#L26-L45`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/execution_use_cases.py#L26-L45)
- **Remediation Implementation:**
  - Verified `target.strip().startswith("-")` check.
  - Verified path traversal check using `(cwd / file_part).resolve().is_relative_to(cwd)`.
  - Added `--` option terminator before target in `cmd.extend(["--", cleaned_target])`.
- **Independent Verification Procedure:**
  1. *Leading Option Injection:*
     Tested `--override-ini`, `-c`, `-o`, `--rootdir`, `--confcutdir`.
     - *Result:* All blocked with `ValueError: Invalid test target ... Flag or option injection detected`.
  2. *Path Traversal:*
     Tested `../../etc/passwd` and `subdir/../../secret.py`.
     - *Result:* Blocked with `ValueError: Invalid test target ... Path traversal outside working directory detected`.
  3. *Compound Option Strings:*
     Tested `tests/unit/test_cli.py -s` or `tests/unit/test_cli.py --capture=no`.
     - *Result:* Because `cmd` includes `--`, pytest treats `"tests/unit/test_cli.py -s"` strictly as a literal filepath rather than an option. The subprocess exits safely with exit code 4 (file not found).
- **Final Status:** **VERIFIED FIXED**

---

### BRAH-SEC-005: Unauthenticated Local Inference Daemon Probe

- **Original Finding:** Local Ollama daemon running on `http://localhost:11434` does not require bearer token authentication.
- **Source Files & Lines:**
  - [`src/brahmastra/infrastructure/providers/ollama.py#L24-L37`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L24-L37)
- **Technical Analysis & Network Boundaries:**
  1. Upstream Ollama (`ollama serve`) does not enforce API tokens on loopback (`127.0.0.1`). Any unprivileged local process on macOS running under any UID can issue HTTP POST requests to `11434`.
  2. *SSRF Vector on Configured Endpoints:*
     `OllamaAdapter` allows arbitrary `endpoint` URLs stored in `ProviderAccountModel.endpoint`. If a non-loopback endpoint is configured (e.g. `http://169.254.169.254` cloud metadata, or internal intranet IPs), BRAHMASTRA will dispatch requests without URL scheme or host allowlisting.
- **Final Status:** **ACCEPTED WITH DOCUMENTED RESIDUAL RISK**

---

## 4. Synthesis and Concrete Remediation Proposals

Before making any source-code modifications, the verification team submits the following coherent fixes for human approval:

### Proposal A: Seal Tenant Isolation Bypass in `credential_use_cases.py` (`BRAH-SEC-001`)
When an account has assignments in `OrganizationAssignmentModel`, operating with `target_org is None` must be strictly forbidden:
```python
# In _verify_account_organization_scoping:
if not target_org:
    # Check if this account belongs to any organization
    has_assignments = session.scalar(
        select(OrganizationAssignmentModel).where(
            OrganizationAssignmentModel.account_id == account.id
        )
    )
    if has_assignments:
        raise PermissionError(
            f"Account '{account.name}' belongs to an organization. Active organization context or explicit --org is required."
        )
    return
```

### Proposal B: Harden Command Execution Gate against Shell Obfuscation & Symlinks (`BRAH-SEC-003`)
1. In `prompt_command_approval`, do not allow `--yes` to auto-approve file-reading commands unless they are explicitly in `SAFE_COMMAND_PREFIXES`.
2. Normalize command strings by stripping shell quotes (`""`, `''`, `\`) before regex matching.
3. For file arguments, resolve symlinks using `Path.resolve()` to detect symlinks pointing to `.env` or sensitive files.

### Proposal C: Secure Fallback in `macos_keychain.py` (`BRAH-SEC-002`)
If `Security.framework` fails to load, do NOT pass `-w secret` to subprocess arguments. Instead, raise a clear `RuntimeError("Native macOS Security.framework is required to prevent credential exposure in process arguments.")` or pipe via secure stdin.

---

## 5. Auditor Recommendation

**Do not deploy to multi-tenant or shared environments until Proposal A (Tenant Scoping Guard) and Proposal B (Command Gate Hardening) are approved and implemented.**
