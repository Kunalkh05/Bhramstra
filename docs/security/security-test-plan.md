# BRAHMASTRA AI — Council Security Test Plan

**Author:** Agent 5 — Test & Reliability Engineer  
**Date:** 2026-11-09  
**Status:** PROPOSED

---

## 1. Test Strategy Overview

All security tests must be:
1. **Deterministic:** No flaky sleep timers or external dependencies.
2. **Hermetic:** Run completely offline without internet or paid API calls.
3. **Failing-Before / Passing-After:** Explicitly verify vulnerability before applying fixes, and confirm resolution after.

---

## 2. Security Test Matrix

| Finding ID | Test Function Name | Test Suite File | Expected Behavior |
| :--- | :--- | :--- | :--- |
| **BRAH-SEC-001** | `test_cross_tenant_credential_rotation_blocked` | `tests/security/test_tenant_isolation_security.py` | Raises `PermissionError` when non-assigned organization rotates credential |
| **BRAH-SEC-001** | `test_cross_tenant_credential_revocation_blocked` | `tests/security/test_tenant_isolation_security.py` | Raises `PermissionError` when non-assigned organization revokes credential |
| **BRAH-SEC-002** | `test_keychain_vault_zero_argv_leakage` | `tests/security/test_vault_security.py` | Verifies secrets are never formatted into subprocess argv |
| **BRAH-SEC-003** | `test_command_policy_blocks_sensitive_cat` | `tests/security/test_command_policy_security.py` | Verifies `cat .env` is classified as `DANGEROUS` |
| **BRAH-SEC-004** | `test_test_runner_blocks_flag_injection` | `tests/security/test_execution_security.py` | Verifies `target="--flag"` raises `ValueError` |

---

## 3. Regression Safeguards

Following remediation, the full 106-test existing suite must continue to pass with a 100% pass rate.
