# BRAHMASTRA Security Council (BSC) — Decision Log (Cycle 2)

**Council Session:** BSC-2026-11-11-02
**Convened:** 2026-11-11
**Trigger:** Independent Post-Remediation Verification Report Disproves Complete Fix Claims
**Operating Principles:**
1. Zero source-code changes prior to explicit human approval.
2. Debate findings; never debate away empirical evidence.
3. Every finding must have a reproducible exploit and failing regression test prior to fix.
4. No reliance on tests passing alone as proof of security.

---

## 1. Council Attendance & Specialist Roster

| Role | Agent ID | Core Responsibility |
| :--- | :--- | :--- |
| **Security Orchestrator** | Agent 0 | Council facilitation, phase transitions, consensus aggregation |
| **Threat Model Analyst** | Agent 1 | Trust boundaries, STRIDE modeling, authorization boundaries |
| **Defensive Code Auditor** | Agent 2 | Static code analysis, C bindings, AST, SQLAlchemy session scoping |
| **Red-Team Agent** | Agent 3 | PoC weaponization, filter evasion, shell parsing bypasses |
| **Remediation Architect** | Agent 4 | Minimal, coherent, non-breaking architectural patch design |
| **Test Engineer** | Agent 5 | Hermetic test design, regression suites, edge-case coverage |
| **Independent Verification Agent** | Agent 6 | Adversarial validation, skepticism of previous claims |

---

## 2. Round 1 — Challenge the Proposals

### Finding 1: BRAH-SEC-001 (Cross-Tenant Credential Scoping Bypass)
- **Root Cause Analysis (Defensive Code Auditor):**
  In [`src/brahmastra/application/use_cases/credential_use_cases.py#L42-L53`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/credential_use_cases.py#L42-L53), `_verify_account_organization_scoping` falls back to `target_org = None` when no active organization is set in `config.json`. If `not target_org`, the function executes `return`. An early `return` grants universal unauthenticated access to mutate, rotate, revoke, or delete credentials on any provider account assigned to any organization.
- **Challenge to Proposed Fix (Red-Team Agent):**
  Proposal A in the report suggests checking if `account` has assignments, and raising an error if `target_org is None`.
  *Challenge:* What if an account is assigned to MULTIPLE organizations (`OrganizationAssignmentModel`)? If Org A and Org B share an account, can Org B revoke Org A's credential label?
  *Challenge 2:* What about `list_credentials` and `list_provider_accounts`? Both currently allow `org_name=None` to dump every tenant's metadata. If `list_credentials` allows `org_name=None`, information disclosure remains unmitigated.
- **Threat Model Evaluation (Threat Model Analyst):**
  The trust boundary is strictly tenant-to-tenant. An unassigned provider account (created during local development without an org) should only be accessible if explicitly designed for global scope, but any account with ANY organization binding MUST require an explicit or active tenant context that matches an assignment.
- **Smallest Robust Architectural Fix (Remediation Architect):**
  1. In `_verify_account_organization_scoping`:
     If `target_org` is `None`: Query `OrganizationAssignmentModel` for `account.id`. If any assignment exists, raise `PermissionError(f"Account '{account.name}' is assigned to an organization. Active organization context or explicit --org is required.")`.
     If `target_org` is provided or active: Verify that `OrganizationAssignmentModel` links `account.id` to `org.id`. If not, raise `PermissionError`.
  2. In `list_credentials`:
     If `org_name is None`: Check `get_active_org_name()`. If an active org exists, filter by it. If no active org exists and multiple orgs exist, do not return credentials assigned to organizations; only return unassigned credentials.
- **Regression Tests (Test Engineer):**
  - Exploit test: `rotate_credential` on an org-assigned account with `org_name=None` and active org `None` must raise `PermissionError`.
  - Exploit test: `list_credentials` with `org_name=None` and active org `None` must not leak credentials of org-assigned accounts.
  - Operation tests: verify, revoke, remove on org-assigned accounts without org context must all raise `PermissionError`.

---

### Finding 2: BRAH-SEC-002 (Insecure macOS Keychain Fallback)
- **Root Cause Analysis (Defensive Code Auditor):**
  In [`src/brahmastra/infrastructure/vault/macos_keychain.py#L139-L151`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L139-L151), the fallback block invokes `subprocess.run([self.executable_path, "add-generic-password", "-w", secret, ...])`. If `use_native=False` or `Security.framework` dynamic linking fails, the plaintext password is placed into `sys.argv`.
- **Challenge to Proposed Fix (Red-Team Agent):**
  Why is the fallback present at all? `security` CLI on macOS *never* allowed passing `-w` without `argv` unless reading from `/dev/tty` (which hangs in automation). Retaining the fallback creates a downgrade attack vector: an attacker manipulating library search paths (`DYLD_LIBRARY_PATH`) or causing `_init_native_bindings` to fail forces BRAHMASTRA into the vulnerable subprocess branch.
- **Architectural Fix (Remediation Architect):**
  **Fail Closed.** On macOS (`sys.platform == "darwin"`), `Security.framework` is a standard system library present in `/System/Library/Frameworks/Security.framework/Security` on all supported OS releases. If native C bindings fail to load on macOS, raise `RuntimeError("Failed to initialize native macOS Security.framework. Insecure plaintext subprocess invocation is prohibited.")`.
  For non-Darwin platforms (e.g. Linux CI without Keychain), users must use `InMemoryVault` or an encrypted vault backend, rather than an insecure CLI stub.
  Also, add `CFRelease` / `SecKeychainItemFreeContent` handling for `item_ref` to ensure CoreFoundation memory hygiene.
- **Regression Tests (Test Engineer):**
  - Verify that initializing `MacOSKeychainVault(use_native=False)` and attempting `store_secret` raises `RuntimeError` rather than calling `subprocess.run` with `-w`.

---

### Finding 3: BRAH-SEC-003 (Shell Quoting, Symlink & `--yes` Approval Bypass)
- **Root Cause Analysis (Defensive Code Auditor):**
  The command policy engine in `src/brahmastra/domain/patch/command_policy.py` relies on naive regex over raw string `command.strip()`. Shell quote syntax (`.e""nv`, `""`, `''`, `\`), parameter expansions, and filesystem symlinks bypass the lexical regex. Furthermore, `prompt_command_approval` in `patch.py` treats `--yes` as blanket authorization for all `MODERATE` commands.
- **Challenge to Proposed Fix (Red-Team Agent):**
  Regex filtering on shell commands is mathematically incomplete. Attackers can use:
  1. Internal quoting: `cat .e""nv`
  2. Environment variables: `F=.env; cat $F`
  3. Base64 / Hex decoding: `cat $(echo LmVudg== | base64 -d)`
  4. Symlinks: `ln -s .env safe.txt && cat safe.txt`
  5. Other read binaries: `head`, `tail`, `less`, `more`, `nl`, `fold`, `awk`, `python`, `perl`, `ruby`.
  If `--yes` automatically approves anything that is `MODERATE`, then ANY command not flagged as `DANGEROUS` will silently exfiltrate secrets!
- **Architectural Fix (Remediation Architect & Defensive Auditor):**
  A defense-in-depth model across three layers:
  1. **Shell Token Normalization & Parsing:**
     Use `shlex.split` (with POSIX mode) to extract actual command tokens and arguments rather than relying on raw string prefixes.
  2. **Filesystem Path & Symlink Resolution:**
     Inspect all file arguments passed to file-reading commands (`cat`, `head`, `tail`, `less`, `more`, `nl`, `sed`, `awk`, `grep`). Resolve arguments to canonical absolute paths (`Path(arg).resolve()`) and check if the canonical target resolves to sensitive files (`.env`, `.git/config`, `id_rsa`, `.ssh`, `.aws`, `/etc/shadow`, etc.).
  3. **Approval Policy Hardening:**
     In [`src/brahmastra/cli/commands/patch.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/patch.py), `--yes` (auto-approve) MUST NOT auto-approve file-inspection commands or any command with unresolved targets. `--yes` should ONLY auto-approve `SAFE_READ` commands (`git status`, `git diff`, `pytest -v`, `pwd`). `MODERATE` commands must still prompt interactively unless an explicit dangerous override `--allow-moderate` or interactive prompt is supplied.
- **Regression Tests (Test Engineer):**
  - Test `cat .e""nv` -> flagged as `DANGEROUS`.
  - Test symlink to `.env` (`cat link_to_env`) -> resolves to `.env` and flagged as `DANGEROUS`.
  - Test `patch.py` approval: `--yes` fails to execute `cat .e""nv` or symlink.

---

### Finding 4: BRAH-SEC-005 (Ollama Local Daemon & SSRF Investigation)
- **Root Cause Analysis (Threat Model Analyst & Red-Team Agent):**
  `OllamaAdapter` takes an arbitrary `endpoint` string and dispatches HTTP requests via `httpx`. While the default is `http://localhost:11434`, an adversary with write access to the database or config can set `endpoint="http://169.254.169.254"` (AWS/GCP metadata service) or internal LAN endpoints (`http://192.168.1.1:80/admin`). When BRAHMASTRA performs health checks or model generation, it will send HTTP POST/GET requests to the target, creating a Server-Side Request Forgery (SSRF) vulnerability.
- **Architectural Fix (Remediation Architect):**
  1. Add strict URL scheme validation (`http` or `https` only).
  2. For local provider mode, restrict endpoints to loopback interfaces (`localhost`, `127.0.0.1`, `::1`).
  3. If remote endpoints are permitted, block link-local metadata addresses (`169.254.169.254`, `metadata.google.internal`) and private loopback bypasses.
  4. Document the local loopback boundary clearly in threat model documentation.
- **Regression Tests (Test Engineer):**
  - Test invalid endpoint scheme (`file:///etc/passwd`, `gopher://`) -> rejected with `ValueError`.
  - Test cloud metadata IP (`http://169.254.169.254`) -> rejected with `ValueError: Cloud metadata endpoints are forbidden`.

---

## 3. Round 2 — Cross-Examination & Adjudication

### Red-Team vs Remediation Architect
- **Red-Team:** "If we use `shlex.split`, what happens when a command contains shell pipelines or compound statements like `ls && cat .env`?"
- **Architect:** "In `CommandPolicyEngine.evaluate`, compound operators (`&&`, `;`, `|`) are already rejected from `SAFE_READ`. However, we will also split compound commands on `&&`, `;`, `||`, and `|` and evaluate each command segment independently. If ANY segment is `DANGEROUS`, the entire command is `DANGEROUS`."
- **Adjudication:** Adopt compound command segment splitting.

### Defensive Code Auditor vs Threat Model Analyst
- **Auditor:** "What happens if a developer creates a test account without assigning it to any organization during local unit testing?"
- **Analyst:** "An account with ZERO entries in `OrganizationAssignmentModel` is explicitly an unassigned local account. However, once an account has AT LEAST ONE organization assignment, it belongs to that tenant domain and MUST NOT be accessed without an active organization matching one of its assignments."
- **Adjudication:** Adopt: `if has_assignments and target_org is None: raise PermissionError`. If the account has no assignments at all, permit local unscoped testing.

### Test Engineer vs Independent Verifier
- **Engineer:** "We need hermetic tests for symlinks that clean up temporary directories."
- **Verifier:** "All tests must verify both the use-case layer AND the CLI entry points (`key.py` and `patch.py`). We must not mark any finding fixed without verifying both layers."
- **Adjudication:** Adopt end-to-end tests covering both domain use-cases and CLI invocation.

---

## 4. Consensus & Decision Summary

The Council unanimously agrees on the four remediation designs:
1. **`BRAH-SEC-001`**: Reject access to org-assigned accounts when `target_org is None`. Filter `list_credentials` to active org or unassigned accounts.
2. **`BRAH-SEC-002`**: Eliminate the plaintext `-w <secret>` subprocess fallback in `macos_keychain.py`. Fail closed on macOS.
3. **`BRAH-SEC-003`**: Shell token normalization, segment evaluation, canonical symlink/path resolution, and `--yes` gate restriction.
4. **`BRAH-SEC-005`**: Restrict Ollama endpoints to valid HTTP/HTTPS URLs and block cloud metadata addresses (`169.254.169.254`).

**Zero source-code files will be modified until explicit human approval is received.**
