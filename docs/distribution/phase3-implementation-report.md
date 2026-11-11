# BRAHMASTRA AI — Phase 3 & 3.1 Implementation Report: Cross-Platform Abstraction & Security Correction

**Document Reference:** DIST-REPORT-PHASE3-2026-11-11  
**Target Branch:** `feat/public-cli-distribution`  
**Parent Branch:** `fix/cycle3-security-remediations`  
**Target Environments:** macOS (ARM64/x86_64), Linux (x86_64/ARM64), Windows (x86_64)  
**Status:** COMPLETE & VERIFIED (Phase 3.1 Security Correction Applied)

---

## 1. Executive Summary

Phase 3.1 addresses the critical security concern identified during the Phase 3 audit regarding Linux credential storage:
- **Replaced Custom Cryptography:** The initial Phase 3 custom file-based encryption (`vault.enc`, PBKDF2 with `/etc/machine-id` seed, and HMAC-CTR stream cipher) was **completely deleted**.
- **Standard System Secret Service Integration:** Replaced with an established, maintained Secret Service integration (`keyring` delegating to `org.freedesktop.secrets`).
- **Fail-Closed Policy:** If no secure desktop Secret Service daemon is available (e.g. headless containers without D-Bus), the vault immediately fails closed with `RuntimeError` rather than falling back to plaintext files or insecure storage.
- **Independent Windows Security Challenge:** Conducted rigorous adversarial testing against Windows process tree termination, `%VAR%` expansion injection, caret `^` obfuscation, download cradles (`certutil`, `bitsadmin`, `powershell -enc`), and `--yes` auto-approval boundaries.

The test suite now totals **261 collected tests: 260 passed, 1 skipped** (1 live Linux Secret Service test skipped on macOS host), with **zero regressions** across the 66 baseline security tests.

---

## 2. Architecture: Before vs After (Phase 3 vs Phase 3.1)

```
=============================================================================
BEFORE (Phase 3 Flaw):
Linux Storage: Custom PBKDF2 + /etc/machine-id + HMAC-CTR file vault (vault.enc)
Risks: Custom cryptographic primitive, public machine-id entropy, file leakage
=============================================================================
AFTER (Phase 3.1 Correction):
Linux Storage: LinuxSecretVault -> keyring -> org.freedesktop.secrets (D-Bus)
Guarantees:
  1. Maintained standard library implementation (keyring).
  2. Zero custom cryptographic primitives or homebrew ciphers.
  3. Zero key derivation from public machine identifiers.
  4. Zero plaintext stored on disk.
  5. Fails closed (RuntimeError) if Secret Service daemon is unavailable.
  6. BRAHMASTRA_VAULT=memory strictly reserved for isolated tests/CI.
=============================================================================
```

---

## 3. Component Details & Security Audit

### 3.1 Linux Secret Service Vault (`src/brahmastra/infrastructure/vault/linux_secret.py`)
- Standard system Secret Service integration via `keyring`.
- Target names formatted as `brahmastra:{service}` and account username.
- Inspects backend via `_is_backend_usable()`: checks for fail/null backends and negative backend priority.
- If unavailable, `store_secret()` and `get_secret()` fail closed immediately.
- Never writes credentials to application files.

### 3.2 macOS Keychain Vault (`src/brahmastra/infrastructure/vault/macos_keychain.py`)
- Native C bindings to `Security.framework` (`SecKeychainAddGenericPassword`, `SecKeychainFindGenericPassword`, `SecKeychainItemModifyAttributesAndData`, `SecKeychainItemDelete`).
- Fixed CoreFoundation handle leak: releases `item_ref` using `_CFRelease(item_ref)` in `get_secret()`, `delete_secret()`, and `has_secret()`.
- Guaranteed zero `argv` exposure (`BRAH-SEC-002`).

### 3.3 Windows Credential Manager (`src/brahmastra/infrastructure/vault/windows_cred.py`)
- Native C bindings to `Advapi32.dll` (`CredWriteW`, `CredReadW`, `CredDeleteW`, `CredFree`).
- Secrets passed via in-memory pointers in `CREDENTIALW.CredentialBlob`, guaranteeing zero command-line argument exposure.
- Proper memory cleanup via `CredFree`.
- Fails closed if native Windows APIs are unavailable.

### 3.4 Process Management & Isolation (`src/brahmastra/domain/execution/test_runner.py`)
- **POSIX:** Uses `preexec_fn=os.setsid` and `os.killpg(..., signal.SIGKILL)` to terminate process groups.
- **Windows:** Spawns subprocesses with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`. On timeout or error, recursively terminates process trees via `taskkill /F /T /PID {proc.pid}`.

### 3.5 Shell Policy Engine (`src/brahmastra/domain/patch/command_policy.py`)
- Rejects Windows environment variable expansion (`%VAR%`) and caret escaping (`^`).
- Flags destructive Windows commands (`del`, `erase`, `rmdir`, `rd`, `format`, `reg delete`, `certutil`, `powershell -enc`, `bitsadmin`).
- Blocks sensitive Windows files (`SAM`, `SYSTEM`, `SECURITY`, `ntds.dit`).
- Restricts `--yes` auto-approval strictly to `CommandRiskLevel.SAFE_READ`.

### 3.6 Configuration Paths (`src/brahmastra/infrastructure/config.py`)
- Hardcoded `/Users/kunalkhande/...` completely purged.
- Standard data directories: `~/Library/Application Support/brahmastra` (macOS), `$XDG_DATA_HOME/brahmastra` (Linux), `%LOCALAPPDATA%\brahmastra` (Windows).
- Enforces strict `0o700` directory and `0o600` file permissions on POSIX.

---

## 4. Tests Added & Execution Results

### Summary: 261 Total Tests (260 Passed, 1 Skipped, 0 Failed)

| Test Module | Tests | Status | Scope |
| :--- | :---: | :---: | :--- |
| `tests/platform/test_linux_secret_service_vault.py` | 11 | **10 Passed, 1 Skipped** | Secret Service lifecycle, unavailable fail-closed, auth errors, malformed responses, account isolation, no plaintext on disk, live integration (skipped on macOS) |
| `tests/platform/test_windows_security_challenge.py` | 28 | **28 Passed** | Windows process tree termination, timeout cleanup, `%VAR%` expansion, caret `^` escaping, download cradles, `--yes` gate |
| `tests/platform/test_windows_command_policy.py` | 30 | **30 Passed** | Destructive Windows patterns, sensitive file reads (`SAM`/`SYSTEM`), safe commands (`dir`, `where`) |
| `tests/platform/test_platform_config.py` | 8 | **8 Passed** | User data dirs, XDG, LOCALAPPDATA, spaces, Unicode, POSIX permissions |
| `tests/platform/test_platform_vault.py` | 7 | **7 Passed** | Windows Credential Manager mock lifecycle, Linux Secret Service mock lifecycle, factory dispatch |
| `tests/platform/test_platform_process.py` | 5 | **5 Passed** | POSIX `killpg`, Windows `taskkill`, `CREATE_NEW_PROCESS_GROUP`, live timeout termination |
| `tests/security/` (Baseline Security) | 66 | **66 Passed** | Zero regressions across BRAH-SEC-001 through BRAH-SEC-005 |
| `tests/unit/` (Baseline Unit) | 106 | **106 Passed** | Core domain, use cases, CLI commands, routing, providers |

---

## 5. Platform Execution Disclosure

Per strict security council integrity guidelines, the operating system on which tests were executed is disclosed:

- **Host Environment:** macOS Darwin (Apple Silicon ARM64, Python 3.13.2).
- **Executed Live on Host:** All macOS Keychain tests, POSIX path/process tests, CLI commands, routing, providers, and command policy engines ran directly on host.
- **Simulated / Mocked on Host:**
  - Windows `Advapi32.dll` Credential Manager calls were tested via Python mocks of Win32 APIs.
  - Windows `taskkill /F /T` termination logic was verified via mock injection and call verification.
  - Linux Secret Service D-Bus calls were tested via mock `keyring` backends.
  - The live test `test_live_linux_secret_service_integration` was automatically skipped on macOS (`sys.platform != "linux"`).
- **Native Target Verification:** True live execution on native Linux and Windows kernels will occur in GitHub Actions multi-OS runners (Phase 4).

---

## 6. Remaining Risks & Mitigations

1. **Headless Linux Environments (e.g. CI / Docker without D-Bus):**
   - The Secret Service daemon requires D-Bus (`org.freedesktop.secrets`). In headless environments without a secret service daemon, `LinuxSecretVault` fails closed by design.
   - *Mitigation:* For CI and headless unit testing, users/developers explicitly set `BRAHMASTRA_VAULT=memory`.
2. **Windows Path Backslashes in External Shells:**
   - While `CommandPolicyEngine` normalizes paths and forbids injection characters, external shell interpreters (`powershell.exe` vs `cmd.exe`) parse escape characters differently. Subprocess execution throughout BRAHMASTRA enforces `shell=False` to prevent shell re-interpretation.

---

## 7. Git Diff Summary (`git diff --stat`)

```text
 pyproject.toml                                     | 23 +++++++-
 src/brahmastra/cli/commands/doctor.py              | 35 +++++++----
 src/brahmastra/domain/execution/test_runner.py     | 67 +++++++++++++++------
 src/brahmastra/domain/patch/command_policy.py      | 18 +++++-
 src/brahmastra/infrastructure/config.py            | 68 ++++++++++++++++++----
 src/brahmastra/infrastructure/vault/factory.py     | 43 +++++++++++---
 src/brahmastra/infrastructure/vault/macos_keychain.py | 22 +++++++
 7 files changed, 223 insertions(+), 53 deletions(-)
```

---

## 8. Confirmation of Restrictions Honored

- **No commits created.**
- **No pushes performed.**
- **No merge into `main` performed.**
- **No packages published to PyPI or TestPyPI.**
- **Zero weakening of existing security controls (BRAH-SEC-001 through 005).**
- **Stopped and waiting for human review.**
