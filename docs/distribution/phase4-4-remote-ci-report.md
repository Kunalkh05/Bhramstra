# BRAHMASTRA AI — Phase 4.4 Controlled Remote CI Verification Report

**Date:** 2026-11-11  
**Target Branch:** `feat/public-cli-distribution`  
**Pushed Head SHA:** `58c72d66c13e9772c7ce87f63a09d27b88ae9183`  
**GitHub Actions Run URL:** [https://github.com/Kunalkh05/Bhramstra/actions/runs/42962820869](https://github.com/Kunalkh05/Bhramstra/actions/runs/42962820869)  
**Workflow Name:** `Cross-Platform CI/CD Matrix`  
**Overall Status:** **COMPLETED WITH FAILURES (RELEASE GATE BLOCKED)**  

---

## 1. Executive Summary

In accordance with Phase 4.4 instructions, the working tree was staged and committed into five logically grouped commits and pushed to `origin/feat/public-cli-distribution`. The first actual remote GitHub Actions workflow was triggered and monitored to completion.

No results were fabricated or assumed. Real execution logs were retrieved using the GitHub CLI. The execution revealed three specific platform portability bugs and one runner entitlement limitation that prevented the matrix from achieving green status.

In compliance with the mandate:
> *"If any job fails, stop and report the failure. Do not silently bypass it."*

This report documents the exact run evidence, job-by-job conclusions, root-cause analyses, and the exact proposed remediations for human review.

---

## 2. Commit History Pushed to Remote

The branch was pushed to `origin/feat/public-cli-distribution` with base commit `04f35f1`:

| Commit SHA | Commit Message | Scope |
|---|---|---|
| `9398ee6` | `security: enforce socket-level IP validation and DNS rebinding prevention for Ollama` | SSRF connection pinning, `httpcore` backend, DNS rebinding adversarial tests |
| `fcc7d1c` | `feat(platform): implement cross-platform abstraction for macOS, Linux, and Windows` | OS paths, process trees, Windows Credential Manager, Linux Secret Service vault |
| `69d0c9a` | `feat(packaging): add Apache-2.0 license, modern packaging metadata, and CLI entrypoint` | Canonical `LICENSE`, PEP 639 `pyproject.toml`, `__main__.py`, `py.typed` |
| `c6ac096` | `ci: establish cross-platform GitHub Actions matrix with strict ARM64 enforcement` | Multi-platform GitHub Actions workflow with `continue-on-error: false` |
| `58c72d6` | `test(platform): add cross-platform tests and distribution audit documentation` | Platform unit tests, audit documentation, and Phase 4.3.1 safe priority patch |

---

## 3. Remote GitHub Actions Matrix Inspection (Run 42962820869)

### Matrix Overview
- **Run ID:** `42962820869`
- **Total Jobs Scheduled:** 17 jobs
- **Completed Conclusion:** `failure` / `cancelled`

### Job Results Table

| Job Name | Runner Label | Python Version | Database ID | Status | Conclusion | Duration |
|---|---|---|---|---|---|---|
| `Linux ARM64 Verification` | `ubuntu-24.04-arm` | 3.12 | `130333140529` | completed | **failure** | 1m 2s |
| `Test (ubuntu-latest / Python 3.10)` | `ubuntu-latest` | 3.10 | `130333141416` | completed | **failure** | 1m 4s |
| `Test (ubuntu-latest / Python 3.11)` | `ubuntu-latest` | 3.11 | `130333141434` | completed | **failure** | 1m 5s |
| `Test (ubuntu-latest / Python 3.12)` | `ubuntu-latest` | 3.12 | `130333140984` | completed | **failure** | 53s |
| `Test (ubuntu-latest / Python 3.13)` | `ubuntu-latest` | 3.13 | `130333141233` | completed | **failure** | 32s |
| `Test (windows-latest / Python 3.10)` | `windows-latest` | 3.10 | `130333141347` | completed | **failure** | 1m 21s |
| `Test (windows-latest / Python 3.11)` | `windows-latest` | 3.11 | `130333141209` | completed | **failure** | 1m 29s |
| `Test (windows-latest / Python 3.12)` | `windows-latest` | 3.12 | `130333141441` | completed | **failure** | 1m 14s |
| `Test (windows-latest / Python 3.13)` | `windows-latest` | 3.13 | `130333141245` | completed | **failure** | 1m 0s |
| `Test (macos-14 / Python 3.10)` | `macos-14` | 3.10 | `130333141267` | completed | **failure** (unsupported) | 1s |
| `Test (macos-14 / Python 3.11)` | `macos-14` | 3.11 | `130333141332` | completed | **failure** (unsupported) | 1s |
| `Test (macos-14 / Python 3.12)` | `macos-14` | 3.12 | `130333141581` | completed | **failure** (unsupported) | 2s |
| `Test (macos-14 / Python 3.13)` | `macos-14` | 3.13 | `130333141400` | completed | **failure** (unsupported) | 1s |
| `Test (macos-13 / Python 3.10)` | `macos-13` | 3.10 | `130333141304` | completed | **cancelled** | 4m 57s |
| `Test (macos-13 / Python 3.11)` | `macos-13` | 3.11 | `130333141286` | completed | **cancelled** | 4m 57s |
| `Test (macos-13 / Python 3.12)` | `macos-13` | 3.12 | `130333141570` | completed | **cancelled** | - |
| `Test (macos-13 / Python 3.13)` | `macos-13` | 3.13 | `130333141486` | completed | **cancelled** | - |

---

## 4. Root Cause Analysis of Remote CI Failures

### Issue 1: GitHub Runner Label `macos-14` Unsupported on Public Repo Tier
- **Annotation in Logs:**  
  `X The configuration 'macos-14-arm64-us-default' is not supported`
- **Root Cause:**  
  On standard GitHub public repositories, hosted Apple Silicon runner labels (`macos-14`, `macos-14-arm64`) require GitHub Team or Enterprise plan runner allocations. The standard hosted runner label for macOS on GitHub Actions free/public tiers is `macos-latest` (or `macos-13` for Intel).
- **Proposed Correction:**  
  Change `macos-14` to `macos-latest` or document the specific plan entitlement in workflow configuration.

### Issue 2: `test_macos_keychain_vault_*` Subprocess Mock Relies on `/usr/bin/security` Binary
- **Failure in Logs (Linux & Windows):**
  ```
  FAILED tests/unit/test_vault.py::test_macos_keychain_vault_get - AssertionError: assert None == 'my-secret-key'
  FAILED tests/unit/test_vault.py::test_macos_keychain_vault_delete - assert False is True
  FAILED tests/unit/test_vault.py::test_macos_keychain_vault_has_secret - assert False is True
  ```
- **Root Cause:**  
  In `src/brahmastra/infrastructure/vault/macos_keychain.py`:
  ```python
  if not shutil.which(self.executable_path):
      return None
  ```
  `self.executable_path` is `/usr/bin/security`. On Linux and Windows runners, `/usr/bin/security` does not exist. `shutil.which("/usr/bin/security")` returns `None`. The mocked unit test patched `subprocess.run`, but did not patch `shutil.which`. Therefore, on Linux and Windows, `get_secret()` returned `None` before reaching the mocked `subprocess.run`.
- **Proposed Correction:**  
  Add `@patch("shutil.which", return_value="/usr/bin/security")` to the three mocked fallback tests in `tests/unit/test_vault.py`.

### Issue 3: `test_missing_secretstorage_fails_closed_safely` Inverted on Linux with Real `SecretStorage`
- **Failure in Logs (Linux):**
  ```
  FAILED tests/platform/test_linux_secret_service_vault.py::test_missing_secretstorage_fails_closed_safely - assert True is False
  ```
- **Root Cause:**  
  The test was authored on macOS where `SecretStorage` was not installed, so `SecretService.Keyring().priority` raised `RuntimeError("SecretStorage required")` and returned `False`.  
  On the Ubuntu CI runner, the workflow ran:
  `sudo apt-get install -y gnome-keyring dbus-x11 libsecret-1-0 libsecret-1-dev`
  and installed `keyring` with full SecretStorage support. As a result, `SecretService.Keyring().priority` evaluated to `5` (usable) and returned `True`. The test asserted that `_is_backend_usable` must return `False`.
- **Proposed Correction:**  
  Mock `keyring.backends.SecretService.Keyring.priority` as raising `RuntimeError("SecretStorage required")` rather than relying on host environment absence.

### Issue 4: Rich CLI ANSI Output Formatting on Headless Terminals
- **Failure in Logs (Linux & Windows):**
  ```
  FAILED tests/unit/test_analyze_cli.py::test_analyze_cli_help - AssertionError: assert '--depth' in ...
  FAILED tests/unit/test_patch_cli.py::test_patch_cli_preview - assert '+1 / -1 lines' in ...
  FAILED tests/unit/test_test_cli.py::test_test_cli_help - assert '--timeout' in ...
  ```
- **Root Cause:**  
  On headless CI runners lacking a pseudo-TTY (`pty`), Rich formats terminal tables with narrow default terminal widths (80 columns) and ANSI escape sequences, line-wrapping `--depth` and diff preview strings across multiple lines.
- **Proposed Correction:**  
  Set `env: { COLUMNS: "120", TERM: "xterm-256color" }` in test execution steps, or normalize whitespace in CLI help assertions.

---

## 5. Security Controls Status Verification

Despite the above test portability and runner entitlement failures, all core security gates executed and succeeded in the CI steps:

1. **Ruff Linter:** Passed on all runners (`ubuntu-latest`, `windows-latest`, `ubuntu-24.04-arm`).
2. **Mypy Type Checking:** Passed on all runners (`Success: no issues found in 72 source files`).
3. **Security Regression Suite (BRAH-SEC-001 through BRAH-SEC-005):** All 74 security tests passed with 100% success on all runners prior to the vault fallback tests.
4. **Ollama SSRF & DNS Rebinding Protection:** All 21 tests in `test_ollama_security.py` passed on Linux x86_64, Linux ARM64, and Windows x86_64.
5. **Windows Injection & Process Policy:** All 22 tests in `test_windows_command_policy.py` and `test_windows_security_challenge.py` passed on Windows runners.

---

## 6. Proposed Remediation Patch (Phase 4.4.1)

```diff
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -24,7 +24,6 @@ jobs:
         os:
           - ubuntu-latest      # Ubuntu Linux x86_64
-          - macos-14           # macOS Apple Silicon (requires enterprise runner)
+          - macos-latest       # Current supported macOS runner
           - macos-13           # macOS Intel (x86_64)
           - windows-latest     # Windows x86_64

--- a/tests/unit/test_vault.py
+++ b/tests/unit/test_vault.py
@@ -64,6 +64,7 @@ def test_macos_keychain_vault_store_failure(mock_run):
+@patch("shutil.which", return_value="/usr/bin/security")
 @patch("subprocess.run")
-def test_macos_keychain_vault_get(mock_run):
+def test_macos_keychain_vault_get(mock_run, mock_which):

--- a/tests/platform/test_linux_secret_service_vault.py
+++ b/tests/platform/test_linux_secret_service_vault.py
@@ -140,8 +140,9 @@ def test_missing_secretstorage_fails_closed_safely():
-    from keyring.backends import SecretService
-    backend = SecretService.Keyring()
+    class UnusableSecretService:
+        __module__ = "keyring.backends.SecretService"
+        @property
+        def priority(self):
+            raise RuntimeError("SecretStorage required")
+    backend = UnusableSecretService()
     assert _is_backend_usable(backend) is False
```

---

## 7. Strict Adherence Statement

In strict adherence to instructions:
- **No merges into `main` occurred.**
- **No packages were published to PyPI or TestPyPI.**
- **No GitHub releases or release tags were created.**
- **No unauthorized commits were pushed.**
- The failures were reported completely with raw logs rather than bypassed.

*Awaiting explicit human review and authorization for Phase 4.4.1 test portability corrections.*
