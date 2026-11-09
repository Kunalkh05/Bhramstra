# BRAHMASTRA AI — Council Remediation Proposals

**Author:** Agent 4 — Remediation Architect  
**Date:** 2026-11-09  
**Status:** PROPOSED — AWAITING HUMAN APPROVAL  
**Rule:** Developer approval is required before applying any source-code modification.

---

## Proposal 1: Fix Cross-Tenant Credential Scoping (`BRAH-SEC-001`)

### 1. Root Cause
`rotate_credential`, `revoke_credential`, `remove_credential`, and `verify_credential` in `credential_use_cases.py` query `ProviderAccountModel` by `account_name` alone without verifying whether the active organization has an `OrganizationAssignmentModel` linking it to the target account.

### 2. Minimal Remediation
1. Add `org_name: Optional[str] = None` parameter to:
   - `rotate_credential`
   - `revoke_credential`
   - `remove_credential`
   - `verify_credential`
2. Default `org_name` to `get_active_org_name()`.
3. In each function, query `OrganizationModel` and assert that an `OrganizationAssignmentModel` exists for `(account.id, org.id)`. If missing, raise:
   ```python
   raise PermissionError(f"Account '{account_name}' is not assigned to organization '{target_org}'.")
   ```
4. Update CLI commands in `key.py` to pass the active organization context.

### 3. Files to Modify
- `src/brahmastra/application/use_cases/credential_use_cases.py`
- `src/brahmastra/cli/commands/key.py`

### 4. Acceptance Criteria
- Calling `rotate_credential` or `revoke_credential` on an account assigned to Org A from Org B raises `PermissionError`.
- Existing tests for Org A remain 100% passing.

---

## Proposal 2: Remove Sensitive `cat` from Safe Shell Whitelist (`BRAH-SEC-003`)

### 1. Root Cause
`CommandPolicyEngine.SAFE_COMMAND_PREFIXES` includes `cat`. Any command beginning with `cat` (such as `cat .env` or `cat ~/.ssh/id_rsa`) is classified as `SAFE_READ` and can execute without interactive confirmation under `--yes`.

### 2. Minimal Remediation
1. Remove `cat` from `SAFE_COMMAND_PREFIXES`.
2. Inspect commands for sensitive file targets (`.env`, `.key`, `.db`, `id_rsa`, `id_ed25519`, `credentials`, `shadow`) and escalate them directly to `DANGEROUS`.

### 3. Files to Modify
- `src/brahmastra/domain/patch/command_policy.py`

### 4. Acceptance Criteria
- `CommandPolicyEngine.evaluate("cat .env")` returns `CommandRiskLevel.DANGEROUS`.
- `CommandPolicyEngine.evaluate("ls -la")` remains `SAFE_READ`.

---

## Proposal 3: Validate Test Target Paths to Block Pytest Flag Injection (`BRAH-SEC-004`)

### 1. Root Cause
`run_project_tests` appends `target` directly to the `pytest` command invocation array without checking for leading dashes `-`.

### 2. Minimal Remediation
In `run_project_tests`:
```python
if target:
    cleaned = target.strip()
    if cleaned.startswith("-"):
        raise ValueError(f"Invalid test target '{target}': Flag injection is forbidden.")
    cmd.append(cleaned)
```

### 3. Files to Modify
- `src/brahmastra/application/use_cases/execution_use_cases.py`

### 4. Acceptance Criteria
- Passing `target="--override-ini=..."` raises `ValueError`.
- Passing valid paths (`tests/unit/test_cli.py`) executes cleanly.

---

## Proposal 4: In-Memory / C-Level Keychain API Migration (`BRAH-SEC-002`)

### 1. Root Cause
`/usr/bin/security add-generic-password -w <secret>` passes the password in `argv`.

### 2. Minimal Remediation
1. In `MacOSKeychainVault`, implement native `ctypes` bindings to macOS `Security.framework` (`SecKeychainAddGenericPassword` / `SecKeychainFindGenericPassword`) to pass secret data directly through memory pointers without invoking external subprocesses.
2. Maintain in-memory vault caching.

### 3. Files to Modify
- `src/brahmastra/infrastructure/vault/macos_keychain.py`

### 4. Acceptance Criteria
- Storing secrets no longer spawns `/usr/bin/security` with `-w <secret>` in `argv`.
- Tested on macOS Apple Silicon M1 (arm64).
