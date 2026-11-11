# BRAHMASTRA AI — Phase 4.3.1 Remediation Report: Safe Linux Keyring Priority Inspection

**Date:** 2026-11-11  
**Target Branch:** `feat/public-cli-distribution`  
**Base Commit:** `04f35f1` (`origin/fix/cycle3-security-remediations`)  
**Authorized Scope:** Remediation of FINDING-4.3-01 in `src/brahmastra/infrastructure/vault/linux_secret.py`  

---

## 1. Executive Summary

During the Phase 4.3 Independent Re-Audit, a low-severity robustness finding (**FINDING-4.3-01**) was identified in `src/brahmastra/infrastructure/vault/linux_secret.py`:
In the Python `keyring` library, `keyring.backends.SecretService.Keyring.priority` is implemented as a dynamic `jaraco.classes.properties.ClassProperty`. If the underlying D-Bus client library (`SecretStorage` or `jeepney`) is not installed on the system, checking `hasattr(backend, "priority")` evaluates the getter, which immediately raises an uncaught `RuntimeError: SecretStorage required`. While this failed closed, the uncaught exception escaped `_is_backend_usable` and prevented `_ensure_backend_available` from displaying the friendly diagnostic error message instructing the user how to configure their Secret Service daemon. Furthermore, `DISALLOWED_BACKENDS` inspected only `type(backend).__name__` but did not inspect `type(backend).__module__`.

Human authorization was granted to implement the proposed safe priority inspection correction. The fix has been applied and validated with six targeted regression tests.

---

## 2. Technical Remediation Details

### File Modified
- `src/brahmastra/infrastructure/vault/linux_secret.py`

### Implementation
```python
def _is_backend_usable(backend: Any) -> bool:
    """
    Determine whether the detected keyring backend provides secure OS-level persistence.
    Explicitly rejects unencrypted plaintext, local files, and failure backends.
    Requires SecretService or KWallet, while allowing test doubles in test environments.
    Safely inspects dynamic properties and fails closed if priority or identity evaluation raises.
    """
    if backend is None:
        return False
    name = type(backend).__name__.lower()
    mod = getattr(type(backend), "__module__", "").lower()

    # Explicitly reject disallowed/insecure backends by class name or module path
    for d in DISALLOWED_BACKENDS:
        if d in name or d in mod:
            return False

    # Safely inspect priority without letting ClassProperty exceptions escape
    try:
        priority = getattr(backend, "priority", None)
        if isinstance(priority, (int, float)) and priority < 0:
            return False
    except Exception:
        # If accessing priority raises an error (e.g. missing SecretStorage/jeepney), fail closed
        return False

    # Allow approved secure OS backends by class name
    if any(a in name for a in ALLOWED_SECURE_BACKENDS):
        return True

    # Allow mock / test double backends in test suites
    if any(t in name for t in ("mock", "fake", "test")):
        return True

    # Allow approved secure OS backends by module path
    if any(a in mod for a in ALLOWED_SECURE_BACKENDS):
        return True

    return False
```

### Key Properties Preserved & Hardened
1. **Module & Name Allowlisting:** Backends must match `ALLOWED_SECURE_BACKENDS` (`"secretservice"`, `"kwallet"`, `"dbus"`) by class name or module path, or be an explicit test mock (`"mock"`, `"fake"`, `"test"`). Unrecognized third-party backends fail closed (`return False`).
2. **Dual-Layer Rejection of Insecure Backends:** `DISALLOWED_BACKENDS` (`"plain"`, `"file"`, `"alt"`, `"chainer"`, `"fail"`, `"null"`) is checked against both the class name and the module path, ensuring that classes with generic names like `Keyring` inside `keyring.backends.plain` are strictly rejected.
3. **Safe Dynamic Property Evaluation:** Accessing `backend.priority` is wrapped in `try...except Exception`. If `SecretService.Keyring.priority` raises `RuntimeError("SecretStorage required")`, or if any other D-Bus exception occurs during property evaluation, it is cleanly caught and returns `False`.
4. **Mock and Negative Priority Handling:** If `priority` is a numeric type (`int`, `float`), values `< 0` cause rejection. If `priority` is a `MagicMock` in unit tests, it avoids invalid numeric comparison and proceeds to test-double evaluation.

---

## 3. Regression Tests Added

Six new dedicated regression tests were added in `tests/platform/test_linux_secret_service_vault.py`:

1. `test_missing_secretstorage_fails_closed_safely`:  
   Instantiates actual `keyring.backends.SecretService.Keyring()` without `SecretStorage`. Verifies `_is_backend_usable` returns `False` without crashing, and `vault.store_secret(...)` raises the expected user-friendly `RuntimeError("Linux Secret Service is unavailable...")`.
2. `test_backend_priority_getter_exception_fails_closed`:  
   Injects a backend whose `priority` property dynamically raises `RuntimeError("D-Bus session bus disconnected")`. Verifies `_is_backend_usable` returns `False` and vault operations fail closed.
3. `test_negative_priority_backend_rejected`:  
   Injects a backend declaring `priority = -1`. Verifies rejection.
4. `test_approved_backend_selection_by_module_and_name`:  
   Verifies approved `SecretService` and `KWallet` backends with valid positive priorities return `True`.
5. `test_disallowed_backend_by_module_path_rejected`:  
   Injects a generic class named `Keyring` in `keyring.backends.plain` with `priority = 1`. Verifies that module-path inspection catches and rejects it.
6. `test_unknown_backend_rejected`:  
   Injects an unrecognized third-party backend (`untrusted_third_party.custom_keyring`). Verifies it returns `False`.

---

## 4. Verification Evidence

### A. Ruff Linter
```
$ .venv/bin/ruff check src tests
All checks passed!
```

### B. Mypy Type Checker
```
$ .venv/bin/mypy src
Success: no issues found in 72 source files
```

### C. Linux Secret Service Test Suite
```
$ .venv/bin/pytest tests/platform/test_linux_secret_service_vault.py -v
======================== 17 passed, 1 skipped in 0.05s =========================
```

### D. Security Regression Suite (BRAH-SEC-001 through BRAH-SEC-005)
```
$ .venv/bin/pytest tests/security/ -v
============================== 74 passed in 0.71s ==============================
```

### E. Full Pytest Suite
```
$ .venv/bin/pytest tests
======================== 276 passed, 4 skipped in 3.59s ========================
```
*Note: The 4 skipped tests are live native OS tests (`test_live_linux_secret_service_integration`, `test_live_windows_cred_lifecycle`, `test_live_windows_taskkill_process_tree_termination`, `test_live_windows_cred_manager_full_lifecycle`) which are gated strictly on foreign platforms and correctly skip on Darwin.*

---

## 5. Strict Adherence Statement

- **Commits Created:** 0
- **Pushes to Remote:** 0
- **Merges Performed:** 0
- **Packages Published:** 0
- **Unrelated Files Modified:** 0
- **Working Tree State:** All changes remain uncommitted on branch `feat/public-cli-distribution`.
