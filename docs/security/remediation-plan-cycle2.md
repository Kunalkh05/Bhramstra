# BRAHMASTRA Security Council — Remediation Plan (Cycle 2)

**Document Reference:** SEC-PLAN-CYC2-2026-11-11
**Status:** PROPOSED — PENDING DEVELOPER APPROVAL
**Scope:** Remediations for findings `BRAH-SEC-001`, `BRAH-SEC-002`, `BRAH-SEC-003`, and `BRAH-SEC-005`.

---

## 1. Finding 1: Seal Cross-Tenant Scoping (`BRAH-SEC-001`)

### 1.1 Root Cause
In `src/brahmastra/application/use_cases/credential_use_cases.py`:
`_verify_account_organization_scoping` returns early (`return`) if `target_org is None`. If an account belongs to an organization, an unauthenticated or unscoped caller can mutate or delete credentials without any authorization check.

### 1.2 Target Files & Lines
- [`src/brahmastra/application/use_cases/credential_use_cases.py#L32-L72`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L32-L72)
- [`src/brahmastra/application/use_cases/credential_use_cases.py#L265-L308`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L265-L308)

### 1.3 Minimal Coherent Remediation
1. Modify `_verify_account_organization_scoping`:
   ```python
   def _verify_account_organization_scoping(
       session,
       account: ProviderAccountModel,
       org_name: Optional[str] = None,
   ) -> None:
       target_org = org_name
       if not target_org:
           active = get_active_org_name()
           if active:
               active_org_record = session.scalar(
                   select(OrganizationModel).where(OrganizationModel.name == active)
               )
               if active_org_record:
                   target_org = active

       if not target_org:
           # Check if this account is bound to any organizations
           has_assignments = session.scalar(
               select(OrganizationAssignmentModel).where(
                   OrganizationAssignmentModel.account_id == account.id
               )
           )
           if has_assignments:
               raise PermissionError(
                   f"Account '{account.name}' is assigned to an organization. "
                   "An active organization context or explicit --org is required."
               )
           return  # Unassigned local test account

       org = session.scalar(
           select(OrganizationModel).where(OrganizationModel.name == target_org)
       )
       if not org:
           raise ValueError(f"Organization '{target_org}' not found.")

       assignment = session.scalar(
           select(OrganizationAssignmentModel).where(
               OrganizationAssignmentModel.account_id == account.id,
               OrganizationAssignmentModel.organization_id == org.id,
           )
       )
       if not assignment:
           raise PermissionError(
               f"Account '{account.name}' is not assigned to organization '{target_org}'."
           )
   ```
2. Update `list_credentials`:
   If `org_name` is None and `get_active_org_name()` is None, only return credentials for accounts that have **no** organization assignments.

### 1.4 Failing Regression Tests to Write First
- `test_unscoped_caller_cannot_rotate_org_credential`
- `test_unscoped_caller_cannot_revoke_org_credential`
- `test_unscoped_caller_cannot_remove_org_credential`
- `test_unscoped_list_credentials_does_not_leak_org_credentials`

---

## 2. Finding 2: Eliminate Insecure Keychain Fallback (`BRAH-SEC-002`)

### 2.1 Root Cause
In `src/brahmastra/infrastructure/vault/macos_keychain.py`:
Lines 139-151 contain an insecure subprocess invocation (`subprocess.run([..., "-w", secret, ...])`). If native `Security.framework` bindings fail or `use_native=False` is set, the secret is leaked to the process table (`argv`).

### 2.2 Target Files & Lines
- [`src/brahmastra/infrastructure/vault/macos_keychain.py#L135-L154`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L135-L154)

### 2.3 Minimal Coherent Remediation
1. Fail closed on macOS: If `self.use_native` is False or `self._sec` is None on `darwin`, raise:
   ```python
   raise RuntimeError(
       "Native macOS Security.framework C-level bindings are unavailable. "
       "Plaintext command-line argument fallback is disabled for security."
   )
   ```
2. Add `CFRelease` / memory cleanup for `item_ref` to ensure CoreFoundation object reference count hygiene.

### 2.4 Failing Regression Tests to Write First
- `test_keychain_vault_fails_closed_when_native_bindings_unavailable`: Asserts that `MacOSKeychainVault(use_native=False).store_secret(...)` raises `RuntimeError` and never executes `subprocess.run`.

---

## 3. Finding 3: Harden Command Policy & Execution Gate (`BRAH-SEC-003`)

### 3.1 Root Cause
In `src/brahmastra/domain/patch/command_policy.py` & `src/brahmastra/cli/commands/patch.py`:
1. Static regex matching is bypassed by shell quoting (`cat .e""nv`), variables, and symlinks.
2. In `patch.py`, `--yes` auto-approves all `MODERATE` commands without checking if they read files.

### 3.2 Target Files & Lines
- [`src/brahmastra/domain/patch/command_policy.py#L27-L75`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/domain/patch/command_policy.py#L27-L75)
- [`src/brahmastra/cli/commands/patch.py#L51-L85`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/patch.py#L51-L85)

### 3.3 Minimal Coherent Remediation
1. **Shell Normalization:**
   Before regex matching, normalize command strings by stripping internal quotes and escape characters.
2. **Compound Command Splitting:**
   Split compound commands on `;`, `&&`, `||`, and `|` and evaluate each segment. If any segment is `DANGEROUS`, the command is `DANGEROUS`.
3. **Filesystem Path & Symlink Resolution:**
   For file-reading tools (`cat`, `head`, `tail`, `more`, `less`, `nl`), parse the file argument using `shlex.split`, resolve its canonical path via `Path(arg).resolve()`, and verify that the target path does not point to sensitive filenames (`.env`, `.git/config`, `id_rsa`, `.ssh`, `.aws`, `/etc/shadow`, `secrets.json`, `.npmrc`).
4. **Approval Gate Restriction:**
   In `prompt_command_approval`, restrict `--yes` so that it **only** auto-approves `CommandRiskLevel.SAFE_READ`. For `MODERATE` commands, require explicit human confirmation or a dedicated `--allow-moderate` flag.

### 3.4 Failing Regression Tests to Write First
- `test_shell_quote_obfuscation_flagged_dangerous`: `cat .e""nv`, `cat .e''nv`, `cat .e\nv`.
- `test_symlink_to_env_flagged_dangerous`: `cat symlink_to_env`.
- `test_patch_cli_yes_flag_does_not_auto_approve_moderate_or_file_reads`.

---

## 4. Finding 4: Ollama Endpoint Validation & SSRF Prevention (`BRAH-SEC-005`)

### 4.1 Root Cause
In `src/brahmastra/infrastructure/providers/ollama.py`:
`OllamaAdapter` takes an arbitrary `endpoint` URL without scheme or host validation, allowing requests to cloud metadata endpoints (`169.254.169.254`) or internal private IP networks.

### 4.2 Target Files & Lines
- [`src/brahmastra/infrastructure/providers/ollama.py#L25-L38`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L25-L38)

### 4.3 Minimal Coherent Remediation
Validate `endpoint` during initialization:
1. Ensure scheme is `http` or `https`.
2. Block known cloud metadata IP addresses (`169.254.169.254`, `metadata.google.internal`).
3. For default/local usage, allow loopback addresses (`localhost`, `127.0.0.1`, `::1`).
4. If non-loopback endpoints are specified, require explicit scheme and reject cloud metadata addresses with `ValueError("Cloud metadata endpoints are forbidden (SSRF prevention).")`.

### 4.4 Failing Regression Tests to Write First
- `test_ollama_invalid_scheme_rejected`: `file:///etc/passwd`, `gopher://evil.com`.
- `test_ollama_cloud_metadata_endpoint_rejected`: `http://169.254.169.254/latest/meta-data`.

---

## 5. Sequence of Implementation After Approval

1. **Step 1:** Implement failing tests and fix for **`BRAH-SEC-001`** (Organization Scoping Guard). Verify with pytest.
2. **Step 2:** Implement failing tests and fix for **`BRAH-SEC-002`** (Keychain Fail-Closed). Verify with pytest.
3. **Step 3:** Implement failing tests and fix for **`BRAH-SEC-003`** (Shell Normalization, Symlinks & Approval Gate). Verify with pytest.
4. **Step 4:** Implement failing tests and fix for **`BRAH-SEC-005`** (Ollama Endpoint Validation & SSRF Guard). Verify with pytest.
5. **Step 5:** Run full test suite (121+ tests).
6. **Step 6:** Inspect Git diff and present results for approval before committing.
