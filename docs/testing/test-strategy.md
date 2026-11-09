# BRAHMASTRA AI: Comprehensive Testing Strategy & Quality Engineering Standard

> **Document Version:** 1.0.0  
> **Target System:** BRAHMASTRA AI CLI & Orchestration Engine  
> **Status:** Approved Architecture Standard  
> **Owner:** Quality Engineering & Core Architecture Team  

---

## 1. Executive Summary & Quality Principles

BRAHMASTRA is an enterprise-grade, provider-independent AI orchestration CLI and developer platform. Because BRAHMASTRA executes autonomous code generation, interfaces directly with operating system security rings (macOS Keychain), routes across external LLM APIs, and executes shell commands within developer workspaces, software defects carry high risks—ranging from credential leakage and system corruption to non-deterministic routing failures.

### Core Testing Tenets

1. **Hermetic by Default:** Zero reliance on live external network endpoints or active LLM accounts during unit, integration, and security test suites. Tests run identically on an isolated offline machine, CI runner, or developer laptop.
2. **Zero-Trust Security Verification:** Automated regression tests continually assert that plain-text secrets never touch SQLite storage, standard output streams, logs, or error traces.
3. **Determinism Over Probability:** Probabilistic LLM outputs are decoupled from orchestration logic via recorded golden contract fixtures and typed schema validations.
4. **Behavior-Driven Over Implementation-Tied:** Test suites validate behavior, invariants, domain boundaries, and system contracts rather than internal private method calls.
5. **Strict Environment Parity:** Dual-platform verification ensuring seamless behavior across macOS Apple Silicon (`arm64`), macOS Intel (`x86_64`), and Linux container environments.

```
                  ▲
                 / \
                /   \
               / CHAOS\       5% - Reliability, Chaos & Provider Fault Injection
              /--------\
             / SECURITY \    10% - Secret Leakage, Command Injection, Path Traversal
            /------------\
           / INTEGRATION  \  20% - SQLite + SQLAlchemy, Vault Adapters, CLI Runner
          /----------------\
         /      UNIT        \ 65% - Domain Models, Use Cases, Routing Policies
        /--------------------\
```

---

## 2. Test Pyramid & Execution Levels

The testing architecture is split into five distinct, decoupled layers, ensuring rapid developer feedback (<2s for unit tests) while providing exhaustive guarantees for security and fault tolerance.

### Summary Matrix of Test Levels

| Level | Primary Focus | Dependencies / Mocking | Execution Target | Typical Marker |
| :--- | :--- | :--- | :--- | :--- |
| **Unit** | Domain entities, pure validation, use case logic, routing calculations | In-memory fakes; zero network; zero disk IO (or isolated `tmp_path`) | < 3 seconds | `@pytest.mark.unit` |
| **Integration** | SQLAlchemy ORM queries, SQLite transactions, OS Keychain adapters, Typer CLI runs | Temporary SQLite databases; Fake / Isolated Vault; CliRunner | < 15 seconds | `@pytest.mark.integration` |
| **Security** | Zero-leakage assertions, command sanitization, path traversal defense, file sandbox boundaries | Log capture, AST scanners, filesystem isolation harnesses | < 10 seconds | `@pytest.mark.security` |
| **Contract & Network** | OpenRouter, Ollama, Anthropic/OpenAI API payload validation, error mapping | `respx` / `responses`, VCR-style golden JSON fixtures | < 10 seconds | `@pytest.mark.contract` |
| **Reliability & Chaos**| Timeouts, exponential backoff with jitter, HTTP 429/503 recovery, mid-flight credential revocation | Fault-injecting HTTP mock transports, simulated network delays | < 20 seconds | `@pytest.mark.chaos` |

---

### Level 1: Unit Testing (Domain Models, Use Cases, Routing Policies)

Unit tests exercise business rules in strict isolation from infrastructure drivers, presentation logic, or operating system state.

#### 1. Domain Models & Value Objects
- **Validation Rules:** Assert that Pydantic models validate constraints (e.g., organization naming rules, credential metadata, model pricing ranges, context window parameters).
- **Immutability & Transitions:** Verify that domain status transitions (e.g., active vs. inactive orgs, credential expiration flags) enforce legal state machines.

```python
# tests/unit/domain/test_organization_rules.py
import pytest
from pydantic import ValidationError
from brahmastra.domain.organizations.models import OrganizationCreate

@pytest.mark.unit
def test_organization_name_disallows_illegal_characters():
    """Verify that org slugs only permit alphanumeric and hyphens/underscores."""
    with pytest.raises(ValidationError):
        OrganizationCreate(name="invalid/name with spaces")

    valid = OrganizationCreate(name="finance-ai-2026")
    assert valid.name == "finance-ai-2026"
```

#### 2. Application Use Cases
- **Dependency Inversion in Tests:** Use cases receive abstract repository and vault interfaces. Tests supply lightweight in-memory implementations.
- **Workflow Orchestration:** Verify correct transaction sequencing: creating orgs, activating orgs, recording audit events.

```python
# tests/unit/application/test_org_orchestration.py
import pytest
from brahmastra.application.use_cases.org_use_cases import create_organization
from brahmastra.domain.organizations.models import OrganizationCreate

@pytest.mark.unit
def test_first_created_organization_is_automatically_active(test_engine):
    """Business rule: The first created organization must automatically be active."""
    org = create_organization(
        OrganizationCreate(name="default-org", description="Default"),
        engine=test_engine,
    )
    assert org.is_active is True
```

#### 3. Routing Engine & Policy Tests
The routing engine (`brahmastra.domain.routing`) maps coding tasks to models and provider accounts using configurable heuristics (cost, latency, context window, capabilities, fallback priority).
- **Deterministic Routing:** Test that routing decisions match configured rules for specific task requirements (e.g., `code-completion` vs. `deep-architectural-reasoning`).
- **Account Failover:** Verify that when a primary account is throttled or degraded, the router picks the next compliant active account.
- **Explainability Contract:** Test that every routing decision returns a structured `RoutingExplanation` documenting why model $M$ and account $A$ were selected over alternatives.

```python
# tests/unit/domain/routing/test_router.py
import pytest
from brahmastra.domain.routing.models import TaskRequirement, RouteContext
from brahmastra.domain.routing.engine import ModelRouter

@pytest.mark.unit
def test_router_selects_cheapest_model_satisfying_context_window():
    router = ModelRouter()
    context = RouteContext(
        task=TaskRequirement(min_context_tokens=32000, requires_code_specialization=True),
        budget_priority="cost_efficient"
    )
    decision = router.resolve(context)
    assert decision.selected_model.context_window >= 32000
    assert decision.explanation.reason_code == "BEST_COST_FOR_CONTEXT"
```

---

### Level 2: Integration Testing (SQLAlchemy + SQLite, Vault Adapters, CLI Runner)

Integration tests verify that modular boundaries mesh correctly with actual SQLite persistence, file storage, OS Keychain APIs, and the Typer CLI runtime.

#### 1. SQLAlchemy + SQLite Persistence
- **Schema Lifecycle:** Verify that `Base.metadata.create_all()` and Alembic migrations execute cleanly against a raw SQLite instance without table locks or foreign-key violations.
- **Concurrency & WAL Mode:** Verify that concurrent read and write operations do not produce `sqlite3.OperationalError: database is locked` under standard connection pooling.
- **State File Isolation:** Ensure `BRAHMASTRA_HOME` can be redirected to a temporary path, leaving no residual files in `~/.brahmastra`.

```python
# tests/integration/database/test_sqlite_lifecycle.py
import pytest
from sqlalchemy import select
from brahmastra.infrastructure.database.models import OrganizationModel

@pytest.mark.integration
def test_sqlite_transaction_rollback_on_conflict(db_session):
    """Assert database rollback preserves consistency upon conflict."""
    org1 = OrganizationModel(name="ops-team", slug="ops-team")
    db_session.add(org1)
    db_session.commit()

    # Attempt duplicate insert
    dup = OrganizationModel(name="ops-team", slug="ops-team")
    db_session.add(dup)
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()

    result = db_session.execute(select(OrganizationModel)).scalars().all()
    assert len(result) == 1
```

#### 2. Vault Adapter Integration
- **Abstract Contract Compliance:** Verify that both `KeychainVaultAdapter` (macOS) and `InMemoryFakeVaultAdapter` fulfill the identical abstract protocol `VaultProtocol`.
- **Reference Integrity:** Ensure the database stores strictly the canonical reference URI (e.g., `brahmastra:org:dev:anthropic:key`) while the vault securely holds the raw secret token.

#### 3. CLI Runner Tests (Typer + Rich)
- **CliRunner Execution:** Invoke subcommands using `typer.testing.CliRunner`.
- **Exit Codes & Outputs:** Assert clean exit code 0 on success, exit code 1 or 2 on validation/operational failure.
- **Rich Terminal Formatting:** Assert that ANSI colors, panels, and Rich tables render gracefully and can be stripped or evaluated using `--json` flags.

```python
# tests/integration/cli/test_doctor_command.py
import pytest
from brahmastra.cli.app import app

@pytest.mark.integration
def test_doctor_command_succeeds_in_clean_environment(cli_runner, tmp_brahmastra_home):
    result = cli_runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "BRAHMASTRA System Health Check" in result.output
    assert "SQLite Database" in result.output
```

---

### Level 3: Security Testing (Secret Leakage, Command Injection, Path Traversal)

Security tests form a mandatory quality gate. Any violation fails the pipeline immediately.

```
                      +-----------------------------+
                      |   Security Test Harness    |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+------------------+       +-------------------+       +-------------------+
|  Secret Leakage  |       | Command Injection |       |  Path Traversal   |
|     Scanner      |       |     Defenses      |       |    Guardrails     |
+------------------+       +-------------------+       +-------------------+
| Logs, stdout, DB |       | Shell metachars,  |       | `..`, symlinks,   |
| traces & errors  |       | pipe concatenation|       | absolute paths    |
+------------------+       +-------------------+       +-------------------+
```

#### 1. Secret Leakage Assertions
- **Log Stream Inspection:** Use pytest `caplog` to capture all log records emitted during execution and assert that raw API keys (e.g., `sk-or-v1-...`, `sk-ant-...`) never appear in logs.
- **Database Content Scanning:** Run automated sweeps against all columns of SQLite tables verifying zero matches against known secret patterns or regexes.
- **Error Trace Sanitization:** Provoke API errors and unhandled exceptions; assert that stack traces and error messages presented to the user contain only masked secrets (`sk-or-***...***`).

```python
# tests/security/test_secret_leakage.py
import re
import pytest
from brahmastra.cli.app import app

RAW_SECRET_PATTERN = re.compile(r"sk-[a-zA-Z0-9_\-]{20,}")

@pytest.mark.security
def test_api_key_never_leaked_in_cli_output_or_logs(cli_runner, caplog, fake_vault):
    fake_vault.store_secret("brahmastra:dev:openrouter", "sk-or-v1-super-secret-token-999")
    
    result = cli_runner.invoke(app, ["key", "list"])
    
    # Assert neither stdout nor caplog contains the raw token
    assert "sk-or-v1-super-secret-token-999" not in result.output
    for record in caplog.records:
        assert "sk-or-v1-super-secret-token-999" not in record.message
```

#### 2. Command Injection Protection
- **Untrusted Model Output:** LLMs may suggest malicious shell commands (e.g., `git status; rm -rf /`, `cat $(whoami)`).
- **Execution Sanitizer Validation:** Test that all command execution passes through an explicit command tokenizer and argument vector parser without invoking shell interpolation (`shell=False` in Python subprocess execution).
- **Metacharacter Shielding:** Verify that attempts to pass `;`, `|`, `&&`, `$()`, or backticks are either safely quoted as single arguments or blocked by the command policy validator.

```python
# tests/security/test_command_sanitization.py
import pytest
from brahmastra.verification.sandbox import CommandSanitizer, SecurityViolationError

@pytest.mark.security
@pytest.mark.parametrize("malicious_command", [
    "git status; cat /etc/passwd",
    "ls && rm -rf ~",
    "python3 -c 'import os; os.system(\"id\")'",
    "`touch pwned`",
    "cat $(echo /etc/shadow)"
])
def test_command_sanitizer_blocks_unauthorized_shell_chaining(malicious_command):
    sanitizer = CommandSanitizer()
    with pytest.raises(SecurityViolationError):
        sanitizer.validate_or_reject(malicious_command)
```

#### 3. Path Traversal Defenses
- **Workspace Jail Verification:** Code generation, file editing, and diff application tools must operate strictly within the target repository directory.
- **Directory Traversal Vectors:** Test vectors including `../../`, absolute paths outside workspace (`/etc/hosts`, `~/.ssh/id_rsa`), and directory symlink escapes.
- **Realpath Canonicalization:** Assert that paths are canonicalized using `os.path.realpath` before permissions checks.

```python
# tests/security/test_path_traversal.py
import pytest
from pathlib import Path
from brahmastra.verification.filesystem import WorkspaceBoundary

@pytest.mark.security
def test_workspace_boundary_rejects_parent_directory_escape(tmp_path):
    workspace = tmp_path / "project_root"
    workspace.mkdir()
    boundary = WorkspaceBoundary(root_path=workspace)

    with pytest.raises(PermissionError, match="outside workspace"):
        boundary.resolve_safe_path("../../../etc/passwd")

    with pytest.raises(PermissionError, match="outside workspace"):
        boundary.resolve_safe_path("/var/log/system.log")
```

---

### Level 4: Network & Provider Mocking (Hermetic Tests & Golden Contracts)

BRAHMASTRA orchestrates across external providers (OpenRouter, Ollama, Anthropic). No automated test should make live external HTTP requests.

#### 1. Hermetic Mocking with `respx` / `pytest-mock`
- **Zero Real Traffic:** The pytest environment enforces a strict network block (`socket.socket` connection block) during test runs. Any unmocked external network attempt fails the test instantly.
- **Async & Streaming Mocking:** OpenRouter client uses Server-Sent Events (SSE) streaming. Tests mock chunked HTTP responses using simulated generator streams.

```python
# tests/contract/test_openrouter_streaming.py
import pytest
import respx
import httpx
from brahmastra.infrastructure.providers.openrouter import OpenRouterClient

@pytest.mark.contract
@respx.mock
async def test_openrouter_streaming_chunks_parsed_correctly():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"def hello():\\n"}}]}\n\ndata: {"choices":[{"delta":{"content":"    return True"}}]}\n\ndata: [DONE]\n\n',
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = OpenRouterClient(api_key="mock-key")
    tokens = []
    async for chunk in client.stream_completion(model="anthropic/claude-3.5-sonnet", prompt="hi"):
        tokens.append(chunk)

    assert "".join(tokens) == "def hello():\n    return True"
```

#### 2. Golden Contract Fixtures & Schema Drift
- **Recorded Fixtures:** Golden JSON fixtures recorded from standard provider responses are stored in `tests/fixtures/providers/`.
- **Pydantic Validation:** When providers update response structures, contract tests parse recorded fixtures through domain model parsers to detect API schema drift early.

```
tests/fixtures/providers/
├── openrouter/
│   ├── completion_200.json
│   ├── error_rate_limited_429.json
│   └── error_invalid_key_401.json
├── ollama/
│   ├── tags_200.json
│   └── generate_streaming.jsonl
└── anthropic/
    └── message_200.json
```

---

### Level 5: Reliability & Chaos Testing (Fault Injection & Recovery)

Distributed LLM APIs suffer from intermittent network cuts, heavy latency, rate limits, and server-side overload. Chaos tests simulate these failures to guarantee graceful degradation.

#### 1. Provider Timeout Handling
- **Socket Drop Simulation:** Test client behavior when a provider establishes a connection but stalls data transfer mid-stream.
- **Configurable Deadlines:** Assert that the client terminates after `timeout_seconds`, emits a structured warning, and initiates fallback to the secondary provider.

#### 2. HTTP 429 Rate-Limit Backoff with Full Jitter
- **Backoff Mechanics:** Verify that encountering an HTTP 429 response status code triggers exponential backoff adhering to:
  $$T_{\text{sleep}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
- **Retry-After Header Adherence:** Verify that if the provider sends a `Retry-After: 3` header, the client honors the exact duration without aggressive re-polling.
- **Terminal Exhaustion:** Verify that exceeding `max_retries` throws a clean `ProviderRateLimitExceededError` instead of an unhandled crash.

#### 3. Mid-Flight Credential Invalidation
- **Scenario:** The user revokes an API key in their provider dashboard while BRAHMASTRA is in the middle of a multi-step task.
- **Recovery:** Assert that upon receiving HTTP 401 Unauthorized, the engine marks the cached credential state as `INVALIDATED`, attempts failover to an alternative credential for the same provider/model, and prompts the user cleanly if no backup exists.

```python
# tests/chaos/test_rate_limit_backoff.py
import pytest
import respx
import httpx
from brahmastra.infrastructure.providers.openrouter import OpenRouterClient
from brahmastra.domain.exceptions import ProviderRateLimitExceededError

@pytest.mark.chaos
@respx.mock
async def test_client_exponential_backoff_and_terminal_failure(monkeypatch):
    # Mock sleep to run instantly in tests
    slept = []
    monkeypatch.setattr("asyncio.sleep", lambda s: slept.append(s))

    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "2"})
    )

    client = OpenRouterClient(api_key="mock-key", max_retries=3)
    with pytest.raises(ProviderRateLimitExceededError):
        await client.complete(model="mock-model", prompt="test")

    assert route.call_count == 4  # 1 initial + 3 retries
    assert len(slept) == 3
```

---

## 3. Tooling, Standards & Pytest Configuration

### Configuration (`pyproject.toml`)

Pytest is configured natively within `pyproject.toml` with strict warnings, explicit markers, and standardized test paths:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
python_classes = ["Test*"]
addopts = [
    "-v",
    "--strict-markers",
    "--strict-config",
    "--tb=short",
    "-ra",
    "--cov=brahmastra",
    "--cov-report=term-missing:skip-covered",
    "--cov-report=xml:coverage.xml",
    "--cov-report=html:htmlcov"
]
markers = [
    "unit: Fast, isolated domain and application tests without external IO.",
    "integration: Multi-component integration tests (SQLite, Vault, CLI).",
    "security: Zero-leakage, path-traversal, and command injection tests.",
    "contract: Provider API contracts and mock schema adherence tests.",
    "chaos: Network disruption, backoff, and fault-injection scenarios.",
    "slow: Tests taking > 2 seconds to complete (skipped in fast iteration)."
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:pkg_resources.*",
    "ignore::ResourceWarning"
]
```

---

### Fixture Architecture & Hierarchy

Fixtures are organized hierarchically across `conftest.py` files to maximize reuse while strictly isolating state.

```
tests/
├── conftest.py                   # Root global fixtures (cli_runner, leak_detector, tmp_env)
├── unit/
│   └── conftest.py               # In-memory mock repositories and fake services
├── integration/
│   └── conftest.py               # SQLite in-memory engine, Session factories, test workspace
├── security/
│   └── conftest.py               # Security probes, secret generators, AST audit tools
└── chaos/
    └── conftest.py               # Fault injection proxies and timing interceptors
```

#### Root Fixtures (`tests/conftest.py`) Standard:

```python
"""
Global root test fixtures for BRAHMASTRA AI.
"""
import os
import pytest
from pathlib import Path
from typer.testing import CliRunner
from brahmastra.infrastructure.vault.fake import InMemoryFakeVault

@pytest.fixture(scope="session")
def cli_runner() -> CliRunner:
    """Provide a thread-safe, isolated Typer CLI runner."""
    return CliRunner(mix_stderr=False)

@pytest.fixture
def tmp_brahmastra_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect BRAHMASTRA_HOME to a guaranteed clean temporary directory."""
    home_dir = tmp_path / ".brahmastra"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BRAHMASTRA_HOME", str(home_dir))
    return home_dir

@pytest.fixture
def fake_vault() -> InMemoryFakeVault:
    """Provide a hermetic in-memory vault adapter."""
    vault = InMemoryFakeVault()
    return vault

@pytest.fixture(autouse=True)
def prevent_unmocked_live_network(monkeypatch: pytest.MonkeyPatch):
    """Safety guard: Intercept raw socket connections to prevent external calls."""
    import socket
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0]
        # Permit localhost connections for SQLite / local testing
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)
        raise RuntimeError(f"Hermeticity Breach: Unmocked network call attempted to {address}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
```

---

## 4. Mocking Standards: macOS Keychain vs. In-Memory Fake Vault

A critical architectural pillar of BRAHMASTRA is that secrets are stored strictly in the host OS vault (macOS Keychain in production), while SQLite only stores references.

### The Mocking Protocol

```
                        +--------------------+
                        |   <<interface>>    |
                        |   VaultProtocol    |
                        +---------+----------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
+-----------------------+                   +-----------------------+
|  KeychainVaultAdapter |                   |  InMemoryFakeVault   |
+-----------------------+                   +-----------------------+
| Production (macOS)    |                   | Unit & CI Pipeline    |
| Calls `security` CLI  |                   | Pure Python dict      |
| or PyObjC SecurityKit |                   | Zero system mutation  |
+-----------------------+                   +-----------------------+
```

### 1. The Contract: `VaultProtocol`
Both implementations adhere strictly to the same protocol:

```python
from typing import Protocol, Optional

class VaultProtocol(Protocol):
    def store_secret(self, key: str, value: str) -> None: ...
    def retrieve_secret(self, key: str) -> Optional[str]: ...
    def delete_secret(self, key: str) -> bool: ...
```

### 2. When to Use What
- **Unit & Normal CI Tests:** Always inject `InMemoryFakeVault`. It has zero dependencies on macOS, requires zero OS Keychain permissions prompts, executes in microseconds, and isolates data per test function.
- **Keychain Integration Tests:** Kept under `@pytest.mark.integration` and guarded with `@pytest.mark.skipif(sys.platform != "darwin", reason="Requires macOS")`.
- **macOS System Mocking:** When testing the `KeychainVaultAdapter` itself without mutating the engineer's real personal Keychain:
  - We use `pytest-mock` to intercept `subprocess.run` calls to `/usr/bin/security`.
  - Alternatively, create a temporary, isolated keychain via `security create-keychain -p password test.keychain` during dedicated macOS integration runners.

```python
# tests/unit/infrastructure/vault/test_keychain_adapter.py
import sys
import pytest
from brahmastra.infrastructure.vault.keychain import KeychainVaultAdapter

@pytest.mark.unit
def test_keychain_adapter_calls_security_binary(mocker):
    """Verify Keychain adapter builds correct macOS CLI invocation."""
    mock_sub = mocker.patch("subprocess.run")
    mock_sub.return_value.returncode = 0
    mock_sub.return_value.stdout = b"my-secret-token\n"

    adapter = KeychainVaultAdapter(service_name="brahmastra-test")
    secret = adapter.retrieve_secret("brahmastra:dev:anthropic")

    assert secret == "my-secret-token"
    mock_sub.assert_called_once()
    args = mock_sub.call_args[0][0]
    assert "/usr/bin/security" in args
    assert "find-generic-password" in args
```

---

## 5. Coverage Thresholds & CI Pipeline Gates

Quality is enforced through non-negotiable coverage thresholds and CI gates.

### 1. Coverage Targets

| Module / Layer | Minimum Line Coverage | Minimum Branch Coverage | Enforcement Action |
| :--- | :--- | :--- | :--- |
| **`domain/`** | **95%** | **90%** | Pipeline Fails |
| **`infrastructure/vault/`** | **100%** | **100%** | Pipeline Fails |
| **`verification/` (Sandbox)** | **100%** | **95%** | Pipeline Fails |
| **`application/use_cases/`** | **90%** | **85%** | Pipeline Fails |
| **`cli/`** | **85%** | **80%** | Pipeline Fails |
| **Entire Project Average** | **90%** | **85%** | PR Blocked |

---

### 2. CI Pipeline Gates Workflow

Every commit and pull request must execute through the following automated quality pipeline:

```
[ Developer Git Push ]
         |
         v
+-----------------------------------------------------------+
| Stage 1: Fast Static Quality Gate (< 30s)                 |
|  - Ruff (Linting & Code Formatting)                       |
|  - Mypy (Strict Type Checking, disallow-any-generics)     |
|  - Bandit / Pip-Audit (Dependency & Code Vulnerabilities) |
+-----------------------------------------------------------+
         |
         v (Success)
+-----------------------------------------------------------+
| Stage 2: Unit & Security Suites (< 60s)                   |
|  - pytest -m "unit or security"                           |
|  - Assert Zero-Leakage & Sandbox Integrity                |
|  - Verify 100% Coverage on Vault & Sandbox Modules        |
+-----------------------------------------------------------+
         |
         v (Success)
+-----------------------------------------------------------+
| Stage 3: Integration & Contract Suites (< 90s)            |
|  - pytest -m "integration or contract or chaos"           |
|  - SQLite Concurrency & Typer CLI Verification            |
|  - respx Mocked Provider Contract Assertions              |
+-----------------------------------------------------------+
         |
         v (Success)
+-----------------------------------------------------------+
| Stage 4: Matrix Compatibility Check                       |
|  - macOS Apple Silicon (arm64) Runner                     |
|  - macOS Intel (x86_64) Runner                            |
|  - Ubuntu 22.04 LTS Container (Headless CLI verification) |
+-----------------------------------------------------------+
         |
         v (All Passed)
[ Merge Permitted to Main ]
```

---

### 3. Sample GitHub Actions CI Pipeline Specification

```yaml
name: BRAHMASTRA Quality Gate

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  static-checks:
    name: Lint & Static Typing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install Dependencies
        run: pip install -e ".[dev]"
      - name: Run Ruff Linter
        run: ruff check src tests
      - name: Run Mypy Strict
        run: mypy --strict src

  matrix-test:
    name: Test Suite (${{ matrix.os }} - Py ${{ matrix.python-version }})
    needs: static-checks
    strategy:
      fail-fast: false
      matrix:
        os: [macos-14, macos-13, ubuntu-latest] # macos-14 is M1/arm64, macos-13 is Intel
        python-version: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"
      - name: Install Dependencies
        run: pip install -e ".[dev]"
      - name: Run Full Test Suite with Coverage
        run: |
          pytest --cov=brahmastra \
                 --cov-report=xml \
                 --cov-fail-under=90
      - name: Upload Coverage to Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ matrix.os }}-py${{ matrix.python-version }}
          path: coverage.xml
```

---

## 6. Implementation Plan & Developer Checklist

Before any feature PR is submitted to BRAHMASTRA AI, authors must verify against this standard:

- [ ] **Unit Tests Written:** Every new domain entity or use case has corresponding unit tests using in-memory fakes.
- [ ] **Security Scanned:** If the feature touches secrets, tokens, or paths, secret-leakage tests and path traversal tests are included.
- [ ] **No Live Network:** Verify that no tests attempt external DNS resolution or socket calls (`prevent_unmocked_live_network` fixture must pass).
- [ ] **Markers Applied:** Tests are explicitly decorated with `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.security`, `@pytest.mark.contract`, or `@pytest.mark.chaos`.
- [ ] **Coverage Met:** Layer-specific coverage rules are satisfied (e.g. 95% on domain models, 100% on security modules).
- [ ] **CLI Cleanliness:** CLI subcommands are tested via `CliRunner` validating clean exit codes and non-crashing output.
