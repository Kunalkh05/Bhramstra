# BRAHMASTRA Security Council (BSC) — Task Board

**Council Chair / Orchestrator:** Agent 0 (Antigravity)  
**Execution Mode:** Subagent / Specialist Parallel & Sequential Workflow  
**Operating Principle:** Debate findings; never debate away evidence. No source-code changes without human approval.

---

## 1. Specialist Task Matrix

| Role | Agent Identifier | Assigned Task | Target Deliverable | Status | Last Update | Blockers / Notes |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **Agent 0: Chair / Orchestrator** | `main` | Council coordination, deduplication, challenge facilitation | `security-council-board.md`, `decision-log.md` | **ACTIVE** | 2026-11-09 15:28 | None |
| **Agent 1: Threat Model Analyst** | `threat_analyst` | STRIDE analysis, trust boundaries, entry points | [`docs/security/threat-model.md`](threat-model.md) | **ACTIVE** | 2026-11-09 15:28 | Round 0 baseline assumptions |
| **Agent 2: Defensive Code Auditor** | `code_auditor` | Static code audit, credential paths, permissions, SQLite | [`docs/security/risk-register.md`](risk-register.md) | **ACTIVE** | 2026-11-09 15:28 | None |
| **Agent 3: Red-Team / Attacker** | `red_team` | Safe local PoCs: injection, path traversal, shell bypass | [`docs/security/red-team-scenarios.md`](red-team-scenarios.md) | **ACTIVE** | 2026-11-09 15:28 | None |
| **Agent 4: Remediation Architect** | `remediation_architect` | Root-cause analysis, minimal fix plans, migration | [`docs/security/remediation-proposals.md`](remediation-proposals.md) | **PENDING** | 2026-11-09 15:28 | Awaiting Round 1-2 findings |
| **Agent 5: Test & Reliability Engineer** | `test_engineer` | Hermetic security tests, failure injection, regressions | [`docs/security/security-test-plan.md`](security-test-plan.md) | **PENDING** | 2026-11-09 15:28 | Awaiting remediation proposals |
| **Agent 6: Independent Verifier** | `verifier` | Post-fix verification, bypass checks, residual risk | [`docs/security/security-audit-report.md`](security-audit-report.md) | **PENDING** | 2026-11-09 15:28 | Awaiting approved fixes |

---

## 2. Review Phase Tracking

- [x] **Round 0: Scope & Scope Alignment** — Baseline architecture assumptions recorded.
- [x] **Round 1: Independent Analysis** — Threat modelling, Code audit, Red team PoCs.
- [x] **Round 2: Cross-Examination Challenge** — Structured interrogation of Critical & High findings.
- [x] **Round 3: Disagreement Resolution** — Evidence-based adjudication.
- [x] **Round 4: Remediation Proposals** — Minimal patch plans formulated.
- [x] **Round 5: Human Approval Gate** — Explicit user review prior to code changes (APPROVED by user).
- [x] **Round 6: Controlled Implementation & Verification (Cycle 1)** — One finding at a time.
  - [x] `BRAH-SEC-001` (Cross-Tenant Credential Scoping): **PARTIALLY_FIXED** (Cycle 1).
  - [x] `BRAH-SEC-003` (Sensitive File Disclosure via Command Policy Whitelist): **PARTIALLY_FIXED** (Cycle 1).
  - [x] `BRAH-SEC-004` (Pytest Flag & Option Injection): **VERIFIED_FIXED** (2/2 tests passing).
  - [x] `BRAH-SEC-002` (Plaintext Password in Keychain CLI `-w` Argument): **PARTIALLY_FIXED** (Cycle 1).
- [x] **Round 7: Post-Audit Sign-Off & Verification (Cycle 1)** — Independent verification disproved 100% fix claim.

---

## 3. Remediation Cycle 2 (Independent Re-Audit & Hardening)

- [x] **Independent Re-Audit & Challenge**: Produced `security/post-remediation-independent-report.md`.
- [x] **Cross-Examination**: 7-role Security Council adversarial challenge documented in `docs/security/decision-log-cycle2.md`.
- [x] **Human Approval Gate**: Council presented `docs/security/remediation-plan-cycle2.md` and received explicit human approval.
- [x] **Cycle 2 Implementation & Verification**:
  - [x] `BRAH-SEC-001`: Unscoped credential operations block org credentials; `list_credentials` filters org credentials when unscoped. 12/12 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-002`: Insecure argv fallback completely removed; fail-closed `RuntimeError` on missing native bindings. 2/2 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-003`: Normalized quote stripping, symlink canonical resolution, extended secret patterns, `--yes` restricted solely to `SAFE_READ`. 17/17 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-004`: Pytest target flag injection verified fixed. 2/2 tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-005`: SSRF & Link-Local cloud metadata IP blocklist implemented. 11/11 security regression tests passing. **VERIFIED_FIXED**.
- [x] **Full Regression Suite**: 150/150 tests passing (0 failures, 0 regressions across all unit and security tests).

---

## 4. Remediation Cycle 3 (Adversarial Bypass Hardening & Release Verification)

- [x] **Cycle 2 Release Gate Blocked**: Independent auditor uncovered command substitutions/prefix matching in BRAH-SEC-003, cross-tenant account hijacking in BRAH-SEC-001, and integer/hex/DNS SSRF in BRAH-SEC-005 (`docs/security/cycle2-release-review.md`).
- [x] **Dedicated Remediation Branch**: Switched to `fix/cycle3-security-remediations`.
- [x] **Cycle 3 Threat Modeling & Remediation Plan**: Formulated in `docs/security/remediation-plan-cycle3.md` and approved.
- [x] **Cycle 3 Implementation (Test-Driven, Pre-Fail Verification)**:
  - [x] `BRAH-SEC-003`: Exact token allowlist (`SAFE_EXECUTABLES`), git subcommand allowlist (`SAFE_GIT_SUBCOMMANDS`), shell metacharacter blocking (`[\$`\n\r><|&;(){}\!]`), working directory boundary check, `--yes` auto-approval restricted exclusively to `SAFE_READ`. 30/30 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-001`: Single-tenant ownership enforcement in `assign_account_to_organization` (cross-tenant attachment raises `PermissionError`); scoped `list_provider_accounts` returns only org accounts; unscoped `list_provider_accounts` filters out all assigned accounts. 14/14 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-005`: Raw host integer/hex validation (`int(raw_host, 0)`), DNS pre-resolution via `socket.getaddrinfo`, IPv4-mapped IPv6 normalization, rejection of private RFC 1918, link-local, AWS IMDS IPv6, wildcard DNS (`nip.io`), strict loopback restriction (`127.0.0.0/8`, `::1`), `follow_redirects=False` on all HTTP clients. 18/18 security regression tests passing. **VERIFIED_FIXED**.
  - [x] `BRAH-SEC-002` & `BRAH-SEC-004`: Maintained 100% protection with zero regressions.
- [x] **Full Regression Suite**: 172/172 tests passing in 3.50s (0 failures, 66 dedicated security tests passing).
- [x] **Independent Verification**: Separate autonomous verification agent completed adversarial testing and signed off in `docs/security/cycle3-independent-verification.md`. **VERIFIED_FIXED** across all 5 findings; **RELEASE GO**.
