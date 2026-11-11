# BRAHMASTRA AI — Remediation Plan (Cycle 3)

**Document Reference:** SEC-PLAN-CYCLE3
**Status:** APPROVED FOR IMPLEMENTATION
**Author:** Remediation Architect & Security Council
**Branch:** `fix/cycle3-security-remediations`
**Date:** 2026-11-11

---

## 1. Scope of Remediations

| Priority | Finding ID | Component | File |
| :---: | :--- | :--- | :--- |
| **P0** | **BRAH-SEC-003** | Command Policy Engine & Patch CLI Gating | `src/brahmastra/domain/patch/command_policy.py`, `src/brahmastra/cli/commands/patch.py` |
| **P1** | **BRAH-SEC-001** | Account Ownership & Scoped Listing | `src/brahmastra/application/use_cases/credential_use_cases.py` |
| **P1** | **BRAH-SEC-005** | SSRF & Canonical IP Network Validation | `src/brahmastra/infrastructure/providers/ollama.py` |

---

## 2. Detailed Technical Specifications

### P0: BRAH-SEC-003 — Command Policy Engine
1. **Shell Metacharacter Rejection for `SAFE_READ`:**
   - Any command containing `$`, ``` ` ```, `\n`, `\r`, `>`, `<`, `|`, `&`, `;`, `(`, `)`, `{`, `}`, `!` is disqualified from `SAFE_READ` and classified as `DANGEROUS` (or `MODERATE`).
2. **Exact Executable Token Allowlist:**
   - Parse tokens with `shlex.split`. If parsing raises `ValueError`, return `DANGEROUS`.
   - First token must exactly match allowed executables: `{"ls", "git", "pwd", "whoami", "python", "pytest"}`.
   - Substring matches (e.g. `lsof`) are blocked from `SAFE_READ`.
3. **Subcommand Validation for `git`:**
   - If executable is `git`, second token must be in `{"status", "diff", "log", "branch"}`.
4. **Path & Symlink Boundary Checks:**
   - Positional arguments are inspected, canonicalized with `(working_dir / arg).resolve()`.
   - Ensure target matches neither sensitive file patterns nor escapes the repository root.

### P1: BRAH-SEC-001 — Tenant Authorization & Account Attachment
1. **Single-Tenant Ownership Rule:**
   - In `assign_account_to_organization`:
     - Query existing assignments for `account.id`.
     - If an assignment exists to another organization (`existing.organization_id != target_org.id`), raise `PermissionError(f"Account '{account.name}' is already assigned to an organization. Cross-tenant reassignment is forbidden.")`.
2. **Authorized Scoping on `list_provider_accounts`:**
   - Resolve `target_org = org_name or get_active_org_name()`.
   - If `target_org`: filter accounts assigned to `target_org`.
   - If no org context: filter only unassigned accounts via `outerjoin(OrganizationAssignmentModel).where(OrganizationAssignmentModel.id.is_(None))`.

### P1: BRAH-SEC-005 — SSRF & IP Canonicalization
1. **URL & Network Validation:**
   - Parse with `urllib.parse.urlsplit`. Validate scheme is `http` or `https`.
   - Resolve host with `socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)`.
   - Parse each resolved IP with `ipaddress.ip_address`.
   - If IPv4-mapped IPv6, inspect underlying IPv4 address.
   - Reject:
     - `ip.is_link_local` (169.254.0.0/16, fe80::/10).
     - `ip.is_private` (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7).
     - `ip.is_multicast`, `ip.is_reserved`, `ip.is_unspecified`.
     - AWS IPv6 metadata (`fd00:ec2::254`).
   - Allow:
     - Loopback (`127.0.0.1`, `::1`, `localhost`) for local Ollama daemon.
2. **Redirect Protection:**
   - Enforce `follow_redirects=False` in `httpx.Client`.

---

## 3. Execution Verification Plan
For each vulnerability:
1. Write failing regression test in `tests/security/`.
2. Run test to verify it fails before implementation.
3. Apply implementation fix.
4. Verify regression test passes.
5. Run full test suite with zero regressions.
