# BRAHMASTRA AI — Phase 4.1: Independent Pre-Release Gate Audit

**Document Reference:** SEC-AUDIT-PHASE4-1-RELEASE-GATE  
**Date:** 2026-11-11  
**Project:** BRAHMASTRA AI (`brahmastra`)  
**Target Release:** 0.1.0  
**Audit Role:** Independent Pre-Release Security & Packaging Gate Auditor  
**Audit Branch:** `feat/public-cli-distribution`  
**Base Commit:** `04f35f1` (`origin/fix/cycle3-security-remediations`)  
**Audit Verdict:** **NO-GO (RELEASE GATE BLOCKED)**  

---

## Executive Summary

An adversarial, evidence-grounded independent audit was conducted on BRAHMASTRA AI to determine release readiness for public distribution on PyPI and GitHub.

The previous Phase 4 report claimed cross-platform verification across macOS, Linux, and Windows. This audit examined the underlying codebase, test suites, packaging artifacts, and actual continuous integration history.

**Critical Findings Summary:**
1. **Zero GitHub Actions Execution:** The repository has **never executed any workflow on GitHub Actions** (`gh run list` reports `no runs found`). `.github/workflows/ci.yml` is an uncommitted, untracked local file.
2. **False Live Linux Integration Test:** In [`tests/platform/test_linux_secret_service_vault.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_linux_secret_service_vault.py#L205-L207), `test_live_linux_secret_service_integration` catches `RuntimeError` and asserts success when the Secret Service backend is unavailable, reporting a false "PASS" in environments where live D-Bus communication never occurred.
3. **Missing Legal LICENSE File:** No `LICENSE` or `LICENSE.txt` file exists anywhere in the repository, despite `pyproject.toml` declaring `license = { text = "Apache-2.0" }`.
4. **DNS Rebinding / TOCTOU SSRF in Ollama Adapter:** [`OllamaAdapter`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L82) resolves and checks IP addresses only during `__init__`. When `httpx.post()` executes later, the underlying HTTP client performs its own independent DNS resolution, exposing the adapter to DNS rebinding attacks against cloud metadata endpoints.
5. **Non-Blocking ARM64 Enforcement:** The `ubuntu-24.04-arm` CI job in [`.github/workflows/ci.yml`](file:///Users/kunalkhande/Project%20/Bhramstra/.github/workflows/ci.yml#L118) is configured with `continue-on-error: true`, allowing ARM64 Linux build or test failures to produce an overall green CI status.

---

## 1. Actual GitHub Actions CI Execution Audit

Inspection of the remote GitHub repository (`https://github.com/Kunalkh05/Bhramstra.git`) via the GitHub CLI (`gh`) and Git telemetry revealed:

| Evidence Metric | Value / Observation | Verification Status |
| :--- | :--- | :---: |
| **Workflow Run URLs** | **NONE** | **UNVERIFIED** |
| **Tested Remote Commit SHA** | **NONE** | **UNVERIFIED** |
| **Active Remote Workflows** | **`no workflows found`** | **CONFIRMED** |
| **Historical Remote Runs** | **`no runs found`** | **CONFIRMED** |
| **Local `.github` State** | Untracked directory (`.github/workflows/ci.yml`) | **CONFIRMED** |
| **Remote Branch Status** | `feat/public-cli-distribution` has **never been pushed to origin** | **CONFIRMED** |

> [!CAUTION]
> The workflow has **NEVER RUN ON GITHUB ACTIONS**. Any runtime timings or platform metrics reported in earlier distribution summaries reflected local machine execution on a single Darwin host or synthetic estimates. Not a single job has executed on a GitHub-hosted runner.

---

## 2. ARM64 Release Enforcement Audit

Inspection of [`.github/workflows/ci.yml`](file:///Users/kunalkhande/Project%20/Bhramstra/.github/workflows/ci.yml#L115-L119):

```yaml
  linux-arm64-check:
    name: Linux ARM64 Verification
    runs-on: ubuntu-24.04-arm
    continue-on-error: true
```

### Audit Assessment:
- **`continue-on-error: true` is enabled:** If the ARM64 job fails, times out, segfaults, or fails package validation, the GitHub Actions check status remains green.
- **Matrix Exclusion:** Linux ARM64 is excluded from the primary `test-matrix` job (`strategy.matrix.os` specifies only `ubuntu-latest`, which is `x86_64`).
- **Release Mandate Violation:** The distribution mandate declared Linux ARM64 as a supported public distribution target. Allowing an essential release architecture to fail without failing the release pipeline is unacceptable.

### Proposed Workflow Modification (Presented for Authorization):
```yaml
# In .github/workflows/ci.yml:
# Move ARM64 into a blocking job or primary matrix:
  linux-arm64-check:
    name: Linux ARM64 Verification
    runs-on: ubuntu-24.04-arm
    continue-on-error: false  # BLOCKING: ARM64 failure must fail the build
```

---

## 3. Linux Secret Service CI Audit

Inspection of [`.github/workflows/ci.yml`](file:///Users/kunalkhande/Project%20/Bhramstra/.github/workflows/ci.yml#L69-L71), [`src/brahmastra/infrastructure/vault/linux_secret.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/linux_secret.py), and [`tests/platform/test_linux_secret_service_vault.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_linux_secret_service_vault.py):

### Finding 3.1: Fictitious Test Success in Live Integration Test (CRITICAL)
In [`tests/platform/test_linux_secret_service_vault.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_linux_secret_service_vault.py#L199-L207):
```python
    vault = LinuxSecretVault()
    try:
        ref = vault.store_secret("brahmastra-test", "test-user", "live-linux-secret")
        assert ref.startswith("vault:")
        assert vault.get_secret("brahmastra-test", "test-user") == "live-linux-secret"
        vault.delete_secret("brahmastra-test", "test-user")
    except RuntimeError as exc:
        # Expected on headless Linux CI containers lacking D-Bus Secret Service
        assert "Secret Service" in str(exc)
```
- **Vulnerability:** When the Secret Service daemon is unavailable, `store_secret` raises `RuntimeError`. The test catches this exception and asserts `"Secret Service" in str(exc)`, **marking the test as PASSED**.
- **Impact:** A broken or non-existent Secret Service configuration in CI will report 100% test pass rates without ever executing a single real D-Bus secret operation.

### Finding 3.2: Daemon Environment Masking in CI Workflow (HIGH)
In [`.github/workflows/ci.yml`](file:///Users/kunalkhande/Project%20/Bhramstra/.github/workflows/ci.yml#L70):
```yaml
run: |
  dbus-run-session -- sh -c "echo '' | gnome-keyring-daemon --unlock --components=secrets || true; pytest tests"
```
- **Vulnerability 1 (`|| true`):** Silently suppresses `gnome-keyring-daemon` startup errors.
- **Vulnerability 2 (Missing `eval`):** `gnome-keyring-daemon --unlock` outputs shell variable assignments to stdout (e.g., `GNOME_KEYRING_CONTROL=...`). Without `eval $(echo '' | gnome-keyring-daemon --unlock --components=secrets)`, the environment variables are not exported to subsequent commands in the shell.

### Finding 3.3: Incomplete Plaintext Backend Rejection (MEDIUM)
In [`src/brahmastra/infrastructure/vault/linux_secret.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/linux_secret.py#L14-L28):
```python
def _is_backend_usable(backend) -> bool:
    if backend is None:
        return False
    name = type(backend).__name__.lower()
    if "fail" in name or "null" in name:
        return False
...
```
- **Vulnerability:** If third-party packages or environment configurations register `keyrings.alt.file.PlaintextKeyring`, its class name is `PlaintextKeyring`. It does not contain `"fail"` or `"null"`, so `_is_backend_usable()` permits it, violating the zero-plaintext-fallback requirement.

---

## 4. Windows and macOS Native Tests Audit

### 4.1 Windows Subprocess Cleanup & Process Grouping
- **Mocked vs Native:** In [`tests/platform/test_windows_security_challenge.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_windows_security_challenge.py#L21-L58), tests for `taskkill /F /T` and timeout termination rely on `unittest.mock.patch("subprocess.run")` and `unittest.mock.patch("subprocess.Popen")`.
- **Live Verification Status:** **UNVERIFIED ON NATIVE WINDOWS**. While `test_live_timeout_terminates_child_process` in [`tests/platform/test_platform_process.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_platform_process.py#L83) executed on Darwin, real `taskkill` process tree termination has never run on a genuine Windows machine.

### 4.2 Windows Credential Manager
- **Interface & Mocked Lifecycle:** [`tests/platform/test_platform_vault.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_platform_vault.py#L36-L63) thoroughly verifies mock `Advapi32.dll` pointers and fail-closed semantics.
- **Live Native Lifecycle:** [`test_live_windows_cred_lifecycle`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_platform_vault.py#L125) was added with `@pytest.mark.skipif(sys.platform != "win32")`. On the current Darwin host, it correctly skipped. It remains **UNVERIFIED ON NATIVE WINDOWS** until executed in CI.

### 4.3 macOS Keychain
- **Native Execution Evidence:** [`test_live_macos_keychain_lifecycle`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/platform/test_platform_vault.py#L155) executed directly on the Darwin host environment and PASSED.
- **Resource Management:** Memory handles (`item_ref`) are released via `_CFRelease(item_ref)` in [`src/brahmastra/infrastructure/vault/macos_keychain.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L187).
- **Log Exposure:** Live tests use ephemeral test keys and do not print secrets to stdout/stderr.

---

## 5. Package Identity, Metadata, and Installation Audit

| Packaging Field | Declared Setting | Audit Assessment |
| :--- | :--- | :---: |
| **Package Name** | `brahmastra` | PASS |
| **Package Version** | `0.1.0` | PASS |
| **CLI Script** | `brahmastra = brahmastra.cli.app:main` | PASS |
| **License Declaration** | `license = { text = "Apache-2.0" }` | **WARNING (Deprecated syntax)** |
| **LICENSE File** | **NONE** | **CRITICAL DEFECT (Missing file)** |
| **README Inclusion** | `README.md` (2,827 bytes) | PASS |
| **Requires-Python** | `>=3.10` | PASS |
| **Wheel Completeness** | Bundles all vault implementations & `py.typed` | PASS |
| **Twine Check** | `dist/*.whl` & `dist/*.tar.gz` | PASS |
| **Fresh venv Install** | `pip install dist/*.whl` -> `brahmastra doctor` | PASS (on macOS) |

> [!CRITICAL]
> The absence of an actual `LICENSE` file in the root directory is a critical release defect. An Apache-2.0 distribution must include the Apache-2.0 license text file in the repository root and sdist manifest.

---

## 6. Security Council Regression Audit (BRAH-SEC-001 through 005)

### 6.1 BRAH-SEC-001: Multi-Tenant Credential & Organization Isolation
- **Status:** **VERIFIED PROTECTED**.
- **Audit:** [`tests/security/test_tenant_isolation_security.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/security/test_tenant_isolation_security.py) (14/14 passed).
- Unscoped callers cannot enumerate or access credentials for attached accounts. [`evaluation_use_cases.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/evaluation_use_cases.py#L49-L75) strictly checks `OrganizationAssignmentModel.organization_id == org.id`.

### 6.2 BRAH-SEC-002: Native macOS Keychain Zero Argv Exposure
- **Status:** **VERIFIED PROTECTED**.
- **Audit:** [`tests/security/test_keychain_security.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/security/test_keychain_security.py) (2/2 passed).
- [`MacOSKeychainVault.store_secret`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/vault/macos_keychain.py#L151) fails closed if native C bindings are unavailable; zero `security add-generic-password` fallback.

### 6.3 BRAH-SEC-003: Command Policy Engine & `--yes` Gate Enforcement
- **Status:** **VERIFIED PROTECTED**.
- **Audit:** [`tests/security/test_command_policy_security.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/security/test_command_policy_security.py) (30/30 passed).
- Dangerous commands, shell metacharacters (`$`, `\n`, `|`, `&`, `%`, `^`), and sensitive file disclosure paths are blocked. In [`patch.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/cli/commands/patch.py#L76), `--yes` cannot auto-approve dangerous commands.

### 6.4 BRAH-SEC-004: Pytest Runner Execution Security
- **Status:** **VERIFIED PROTECTED**.
- **Audit:** [`tests/security/test_execution_security.py`](file:///Users/kunalkhande/Project%20/Bhramstra/tests/security/test_execution_security.py) (2/2 passed).
- Flag injection (`-o`, `--override-ini`) is blocked; path traversal outside `cwd` is prevented, and `--` argument boundaries are enforced in [`execution_use_cases.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/application/use_cases/execution_use_cases.py#L42).

### 6.5 BRAH-SEC-005: Ollama SSRF, DNS Rebinding & TOCTOU (HIGH RISK)
- **Status:** **DEFECT IDENTIFIED**.
- **Audit:** In [`src/brahmastra/infrastructure/providers/ollama.py`](file:///Users/kunalkhande/Project%20/Bhramstra/src/brahmastra/infrastructure/providers/ollama.py#L80-L128), IP validation correctly evaluates loopbacks, cloud metadata (169.254.169.254, fd00:ec2::254), private ranges, and decimal/hex IP encodings.
- **TOCTOU / DNS Rebinding Flaw:**
  1. `OllamaAdapter.__init__` validates the host IP via `socket.getaddrinfo()`.
  2. `OllamaAdapter.generate()` connects to `url = f"{self.endpoint}/api/chat"` via `httpx.post()`.
  3. `httpx` performs its own DNS lookup at request time. An attacker using a DNS service with a short TTL (0s) can point a domain to a safe IP during `__init__`, and rebind it to `169.254.169.254` at request time.
- **Proposed Correction:** Connect to the validated IP address directly or enforce a custom `httpx` transport/resolver that pins the connection to the validated socket address.

---

## 7. Risk Classification Matrix

| Risk ID | Severity | Category | Description | File & Line Reference |
| :--- | :---: | :---: | :--- | :--- |
| **RISK-01** | **CRITICAL** | CI / Release | GitHub Actions workflows have never run on GitHub; zero remote test evidence. | `.github/workflows/ci.yml:1` |
| **RISK-02** | **CRITICAL** | Security / Test | Live Linux Secret Service integration test catches failure and falsely reports pass. | `tests/platform/test_linux_secret_service_vault.py:205-207` |
| **RISK-03** | **CRITICAL** | Packaging / Legal | No `LICENSE` file exists in repository root or package distribution. | Repository root |
| **RISK-04** | **HIGH** | Security (SSRF) | DNS rebinding / TOCTOU SSRF window in `OllamaAdapter` HTTP requests. | `src/brahmastra/infrastructure/providers/ollama.py:168` |
| **RISK-05** | **HIGH** | CI / Platform | ARM64 Linux CI job has `continue-on-error: true`, permitting silent release failures. | `.github/workflows/ci.yml:118` |
| **RISK-06** | **HIGH** | Security / Vault | `_is_backend_usable` does not explicitly reject plaintext file keyrings. | `src/brahmastra/infrastructure/vault/linux_secret.py:19` |
| **RISK-07** | **MEDIUM** | CI / Linux | `|| true` and missing `eval $(...)` in headless `gnome-keyring-daemon` startup. | `.github/workflows/ci.yml:70` |
| **RISK-08** | **MEDIUM** | Platform | Windows Credential Manager and `taskkill` tests rely entirely on mocks. | `tests/platform/test_windows_security_challenge.py:28` |
| **RISK-09** | **LOW** | Packaging | Deprecated `project.license` table syntax triggers build warnings. | `pyproject.toml:11` |

---

## 8. Remediation Plan Prior to Release Gate Re-evaluation

Before granting a release authorization:

1. **Add `LICENSE` File:** Create the standard `LICENSE` file (Apache-2.0 text) in repository root. Update `pyproject.toml` to `license = "Apache-2.0"`.
2. **Fix `test_live_linux_secret_service_integration`:** Remove the `except RuntimeError` mask. If Secret Service is required for live integration, it must genuinely succeed or fail the test.
3. **Fix Linux CI D-Bus Session:** Update the CI workflow to properly export keyring daemon environment variables:
   ```bash
   dbus-run-session -- sh -c 'eval $(gnome-keyring-daemon --start --components=secrets) && pytest tests'
   ```
4. **Fix Plaintext Keyring Rejection:** In `_is_backend_usable`, reject any backend whose name contains `"plain"`.
5. **Mitigate DNS Rebinding in Ollama:** In `OllamaAdapter`, pin HTTP requests to the validated IP address or use an `httpx` HTTP transport with custom DNS resolution.
6. **Enforce Blocking ARM64 in CI:** Set `continue-on-error: false` on the ARM64 job.
7. **Execute Remote CI on GitHub:** Commit approved remediations to `feat/public-cli-distribution`, push the branch, and verify actual execution on GitHub Actions runners across macOS, Linux, and Windows.

---

## 9. Final Release Gate Verdict

# Verdict: **NO-GO (RELEASE GATE BLOCKED)**

**Justification:**
BRAHMASTRA AI cannot be approved for public release in its current state. The absence of a `LICENSE` file, the lack of any actual GitHub Actions execution, the false-pass behavior in Linux Secret Service live tests, non-blocking ARM64 verification, and the DNS rebinding TOCTOU window must be remediated before any public distribution.

---
*Report generated pursuant to Phase 4.1 Independent Pre-Release Gate Audit protocol.*
