# BRAHMASTRA Command-Line Interface (CLI) User Experience Design

> **Document Version:** 1.0.0  
> **Status:** Approved Architecture Specification  
> **Target Platform:** macOS (Darwin `arm64` Apple Silicon & `x86_64` Intel), Linux  
> **Primary Technology Stack:** Python 3.10+, Typer, Click, Rich, Prompt Toolkit  

---

## 1. Executive Summary & Core Design Principles

BRAHMASTRA is an enterprise-grade, provider-independent AI orchestration platform and developer assistant. The command-line interface (CLI) is the primary window through which software engineers, DevOps leads, and security administrators interact with the system.

### Core Design Tenets

1. **Deterministic, Predictable Command Hierarchy:**  
   Every command follows strict subject-verb or domain-action patterns (`brahmastra <domain> <action> [options]`). Zero ambiguous global verbs.
2. **Security-First Ergonomics:**  
   API credentials never print to terminal screens, error logs, or bash histories. Destructive actions require explicit verification safeguards. Secret inputs are masked with zero-echo memory protections.
3. **Information Density without Visual Clutter:**  
   Leverage Rich terminals to present high-signal data: organized tabular outputs, clean column alignments, subtle borders, contextual glyphs, and distinct semantic color scales.
4. **Actionable Failure Diagnostics:**  
   No generic tracebacks in user terminals. Every error provides an explicit error classification code, a plain-English explanation, contextual metadata, and numbered copy-paste remediation commands.
5. **Universal Terminal Fidelity:**  
   Seamless rendering across modern terminal emulators (macOS Terminal, iTerm2, Alacritty, Warp, WezTerm) with graceful degradation to ANSI or raw plain-text when pipes, non-TTY streams, or `NO_COLOR=1` are detected.

---

## 2. Global CLI Conventions & Flags

### 2.1 Invocation Syntax
```bash
brahmastra [GLOBAL_OPTIONS] <COMMAND> [SUBCOMMAND] [ARGUMENTS...] [OPTIONS...]
```

### 2.2 Global Options
All global flags are parsed at the root level and propagate to subcommands:

| Flag | Short | Default | Description |
| :--- | :---: | :---: | :--- |
| `--org` | `-o` | Active Org | Override target organization workspace for this execution only |
| `--verbose` | `-v` | `False` | Enable detailed debug logs (API latency, routing scores, SQL traces) |
| `--quiet` | `-q` | `False` | Suppress non-essential output, banners, and spinners (show only results) |
| `--json` | `-j` | `False` | Emit pure, machine-readable JSON to stdout for scripting and CI pipelines |
| `--plain` | `-p` | `False` | Strip all ANSI escape sequences, colors, boxes, and emojis |
| `--no-input` | | `False` | Disable all interactive prompts; fail if required inputs are omitted |
| `--version` | `-V` | — | Display current BRAHMASTRA version, commit hash, and architecture |
| `--help` | `-h` | — | Render rich command manual and options overview |

### 2.3 Output Streams Separation
- **Standard Output (`stdout`, File Descriptor 1):**  
  Reserved exclusively for primary payload data: generated code, command output tables, JSON payloads, and chat streaming text.
- **Standard Error (`stderr`, File Descriptor 2):**  
  Used for diagnostic messages, status spinners, progress bars, security alerts, and error callouts. This guarantees that commands like `brahmastra models list --json > models.json` or `brahmastra analyze . > report.md` remain clean and pipe-friendly.

---

## 3. Complete Command Tree & Specification

```text
brahmastra
├── doctor                     [System diagnostics, hardware, vault, network health]
├── org                        [Organization workspace isolation & profiles]
│   ├── add                    [Register a new organization profile]
│   ├── list                   [List registered organizations & active selection]
│   ├── switch                 [Set active organization workspace]
│   ├── current                [Display active organization details]
│   └── show                   [Inspect organization metadata, quotas, policies]
├── provider                   [AI model provider connectors]
│   ├── add                    [Register provider (openrouter, anthropic, ollama, custom)]
│   ├── list                   [List registered providers and connection health]
│   ├── test                   [Validate endpoint latency, auth, and handshake]
│   └── remove                 [Deregister provider connector]
├── key                        [Secure credential management backed by OS Keychain]
│   ├── add                    [Store API key into OS vault with org scoping]
│   ├── list                   [List key aliases, providers, statuses (no raw secrets)]
│   ├── test                   [Perform live test auth request with stored key]
│   ├── rotate                 [Replace active key with new secret seamlessly]
│   ├── revoke                 [Mark key inactive and disable routing usage]
│   └── remove                 [Permanently purge key from vault and database]
├── models                     [Catalog discovery, capabilities & routing registry]
│   ├── list                   [List active models, context windows, cost/token]
│   ├── search                 [Filter models by capability, provider, pricing]
│   └── inspect                [Deep-dive model schema, benchmarks, token constraints]
├── usage                      [Token consumption, cost accounting & budget metrics]
│   ├── summary                [High-level spend, request volume, token usage]
│   └── breakdown              [Segmented spend by org, provider, model, or timeframe]
├── chat                       [Interactive AI development REPL]
├── run                        [Autonomous code execution & agentic task loop]
└── analyze                    [Repository architecture, security & model readiness]
```

---

### 3.1 `brahmastra doctor`

#### Purpose
Executes comprehensive pre-flight diagnostics across local system architecture, OS Keychain availability, database integrity, network connectivity to AI gateways, and required developer tooling.

#### Syntax
```bash
brahmastra doctor [OPTIONS]
```

#### Options
- `--fix`: Automatically attempt remediation for fixable issues (e.g., creating storage directories, repairing database file permissions).
- `--deep`: Run live network round-trip latency checks to registered providers.

#### Sample Terminal Output
```text
BRAHMASTRA System Health Check
Evaluating environment, OS, architecture, and system capabilities...

┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category   ┃ Component           ┃ Status ┃ Details                                ┃
┣━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Runtime    ┃ Python Version      ┃  PASS  ┃ Python 3.11.8 (>= 3.10 required)       ┃
┃ Platform   ┃ Operating System    ┃  PASS  ┃ macOS 14.4.1 (Darwin 23.4.0)           ┃
┃ Hardware   ┃ CPU Architecture    ┃  PASS  ┃ Apple Silicon / ARM64 (arm64)          ┃
┃ Storage    ┃ State Directory     ┃  PASS  ┃ ~/.brahmastra (rw-r--r--)              ┃
┃ Database   ┃ SQLite Metadata     ┃  PASS  ┃ SQLite 3.43.2 (WAL mode enabled)       ┃
┃ Vault      ┃ macOS Keychain      ┃  PASS  ┃ Security framework responsive          ┃
┃ Tools      ┃ Git CLI             ┃  PASS  ┃ git version 2.44.0                     ┃
┃ Tools      ┃ Ripgrep             ┃  PASS  ┃ rg 14.1.0                              ┃
┃ Network    ┃ OpenRouter API      ┃  PASS  ┃ 42ms round-trip latency                ┃
┃ Network    ┃ Local Ollama        ┃  WARN  ┃ Service unreachable at localhost:11434 ┃
┗━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Summary: 9 checks passed, 1 warning, 0 failures. System ready for operation.
```

---

### 3.2 `brahmastra org`

#### Purpose
Enforces tenant isolation, workspace credential scoping, project routing policies, and spend quotas.

#### Subcommands

##### 1. `brahmastra org add <NAME>`
- **Syntax:** `brahmastra org add <name> [--desc <description>] [--default]`
- **Description:** Creates a new isolated organization workspace.
- **Example:**
  ```bash
  $ brahmastra org add enterprise-core --desc "Core infrastructure squad"
  ✓ Created organization 'enterprise-core' (ID: org_01j7b3x89v9q...)
  Set as current active organization.
  ```

##### 2. `brahmastra org list`
- **Syntax:** `brahmastra org list`
- **Description:** Lists all registered workspaces, showing the currently active organization with an indicator badge.
- **Sample Output:**
  ```text
  ┏━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
  ┃ Active ┃ Name            ┃ Description                 ┃ Created At       ┃
  ┣━━━━━━━━╋━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━┫
  ┃  ✓ *   ┃ enterprise-core ┃ Core infrastructure squad   ┃ 2026-11-09 11:42 ┃
  ┃        ┃ personal-dev    ┃ Experimental side projects  ┃ 2026-11-08 09:15 ┃
  ┃        ┃ client-alpha    ┃ Client engagement sandbox   ┃ 2026-11-01 14:20 ┃
  ┗━━━━━━━━┻━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━┛
  ```

##### 3. `brahmastra org switch <NAME>`
- **Syntax:** `brahmastra org switch <name>`
- **Description:** Changes the active organization context for subsequent commands.
- **Example:**
  ```bash
  $ brahmastra org switch personal-dev
  Switched active organization to 'personal-dev'.
  ```

##### 4. `brahmastra org current`
- **Syntax:** `brahmastra org current`
- **Description:** Displays the name, ID, active provider count, and monthly spend for the active organization.

##### 5. `brahmastra org show <NAME>`
- **Syntax:** `brahmastra org show <name>`
- **Description:** Displays in-depth configuration, credential mappings, spend limits, and model routing policies for the specified workspace.

---

### 3.3 `brahmastra provider`

#### Purpose
Configures upstream model endpoints, API targets, inference gateways, and connection parameters.

#### Subcommands

##### 1. `brahmastra provider add`
- **Syntax:** `brahmastra provider add <name> --type <type> [--base-url <url>] [--org <org>]`
- **Supported Types:** `openrouter`, `anthropic`, `openai`, `ollama`, `vllm`, `custom`
- **Example:**
  ```bash
  $ brahmastra provider add openrouter-prod --type openrouter
  ✓ Registered provider 'openrouter-prod' (Type: openrouter)
  ℹ Run 'brahmastra key add --provider openrouter-prod' to attach credentials.
  ```

##### 2. `brahmastra provider list`
- **Syntax:** `brahmastra provider list [--org <org>]`
- **Sample Output:**
  ```text
  ┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
  ┃ Name            ┃ Type       ┃ Base URL                  ┃ Keys     ┃ Status ┃
  ┣━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━┫
  ┃ openrouter-prod ┃ openrouter ┃ https://openrouter.ai/api ┃ 1 active ┃ Online ┃
  ┃ local-ollama    ┃ ollama     ┃ http://localhost:11434    ┃ None     ┃ Online ┃
  ┃ anthropic-corp  ┃ anthropic  ┃ https://api.anthropic.com ┃ 1 active ┃ Online ┃
  ┗━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━┛
  ```

##### 3. `brahmastra provider test <NAME>`
- **Syntax:** `brahmastra provider test <name>`
- **Description:** Dispatches a minimal handshake query to test auth validity, network transit latency, and model availability.
- **Example:**
  ```bash
  $ brahmastra provider test openrouter-prod
  ⠋ Connecting to provider openrouter-prod...
  ✓ Handshake successful: HTTP 200 OK
  Latency: 48ms | Authenticated Identity: org_ent_prod | Available Models: 248
  ```

##### 4. `brahmastra provider remove <NAME>`
- **Syntax:** `brahmastra provider remove <name> [--force]`
- **Description:** Removes the provider connector after confirming associated keys are safely unlinked or revoked.

---

### 3.4 `brahmastra key`

#### Purpose
Secure lifecycle management of LLM API keys. Keys are **never** stored in the SQLite database or plaintext configuration files; raw secrets are committed exclusively to the macOS Keychain (or Linux Secret Service) with isolated vault keys.

#### Subcommands

##### 1. `brahmastra key add`
- **Syntax:** `brahmastra key add --provider <provider> [--alias <alias>] [--org <org>]`
- **Interactive Security Flow:**
  Prompts for the secret with masked terminal input (no character echoing). Checks entropy and format before writing to the OS vault.
- **Example:**
  ```bash
  $ brahmastra key add --provider openrouter-prod --alias main-key
  Enter API Secret Key: [input hidden]
  Confirm API Secret Key: [input hidden]
  ⠋ Validating credential with upstream provider...
  ✓ Authenticated successfully with OpenRouter.
  ✓ Key securely stored in OS Keychain under alias 'main-key'.
  Key ID: key_01j7b9p42... | Prefix: sk-or-v1-8f4a... (last 4: 9b2d)
  ```

##### 2. `brahmastra key list`
- **Syntax:** `brahmastra key list [--org <org>]`
- **Security Rule:** Never displays raw secrets. Displays only vault ID, alias, provider, truncated key fingerprint (`...9b2d`), lifecycle state, and expiration/created timestamps.
- **Sample Output:**
  ```text
  ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
  ┃ Alias     ┃ Provider        ┃ Fingerprint      ┃ State      ┃ Created          ┃
  ┣━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━┫
  ┃ main-key  ┃ openrouter-prod ┃ sk-or-...9b2d    ┃ Active     ┃ 2026-11-09 11:50 ┃
  ┃ backup    ┃ openrouter-prod ┃ sk-or-...11ac    ┃ Inactive   ┃ 2026-10-15 08:30 ┃
  ┃ claude-35 ┃ anthropic-corp  ┃ sk-ant-...38ef   ┃ Active     ┃ 2026-11-01 14:10 ┃
  ┗━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━┛
  ```

##### 3. `brahmastra key test <ALIAS_OR_ID>`
- **Syntax:** `brahmastra key test <alias>`
- **Description:** Verifies credential validity by querying upstream provider user/quota API.

##### 4. `brahmastra key rotate <ALIAS_OR_ID>`
- **Syntax:** `brahmastra key rotate <alias>`
- **Description:** Prompts for a replacement secret, verifies the new secret upstream, updates the OS Keychain entry atomically, marks the prior key superseded, and retains audit logs without downtime.

##### 5. `brahmastra key revoke <ALIAS_OR_ID>`
- **Syntax:** `brahmastra key revoke <alias> [--yes]`
- **Description:** Sets key status to `REVOKED`. The routing engine immediately ceases dispatching traffic to this key. Requires interactive confirmation unless `--yes` is specified.

##### 6. `brahmastra key remove <ALIAS_OR_ID>`
- **Syntax:** `brahmastra key remove <alias> [--force]`
- **Description:** Permanently deletes secret from macOS Keychain and purges vault reference from the local metadata database.

---

### 3.5 `brahmastra models`

#### Purpose
Inspect available models, capabilities (reasoning, tool-calling, vision), context window limits, pricing per million tokens, and routing scores.

#### Subcommands

##### 1. `brahmastra models list`
- **Syntax:** `brahmastra models list [--provider <provider>] [--capability <cap>] [--sort <price|context|score>]`
- **Sample Output:**
  ```text
  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
  ┃ Model ID                       ┃ Provider    ┃ Context ┃ Input $/M    ┃ Output $/M    ┃
  ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━┫
  ┃ anthropic/claude-3.5-sonnet    ┃ openrouter  ┃ 200,000 ┃ $3.00        ┃ $15.00        ┃
  ┃ openai/gpt-4o                  ┃ openrouter  ┃ 128,000 ┃ $2.50        ┃ $10.00        ┃
  ┃ qwen/qwen-2.5-coder-32b-instruct┃ local-ollama┃ 32,768  ┃ $0.00 (free) ┃ $0.00 (free)  ┃
  ┃ deepseek/deepseek-coder        ┃ openrouter  ┃ 64,000  ┃ $0.14        ┃ $0.28         ┃
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┛
  ```

##### 2. `brahmastra models search <QUERY>`
- **Syntax:** `brahmastra models search <query> [--max-price-input <float>]`
- **Description:** Performs full-text and capability search over indexed models (e.g., `brahmastra models search "coder 32b"`).

##### 3. `brahmastra models inspect <MODEL_ID>`
- **Syntax:** `brahmastra models inspect <model_id>`
- **Description:** Emits a rich formatted spec card detailing parameter counts, tokenizer characteristics, max completion tokens, function calling support, and historical latency benchmarks.

---

### 3.6 `brahmastra usage`

#### Purpose
Audits LLM usage, input/output token counts, and cost telemetry per organization, project, or model.

#### Subcommands

##### 1. `brahmastra usage summary`
- **Syntax:** `brahmastra usage summary [--days <int>] [--org <org>]`
- **Sample Output:**
  ```text
  Usage Summary for Organization: 'enterprise-core' (Last 30 Days)

  Total Spend: $14.28 / $100.00 Budget Limit [=====>----------------] 14.3%
  Total Requests: 1,842 requests
  Total Tokens: 8,492,100 tokens (Input: 6,810,200 | Output: 1,681,900)
  Average Request Latency: 640ms
  ```

##### 2. `brahmastra usage breakdown`
- **Syntax:** `brahmastra usage breakdown --by <org|model|provider|day> [--since <date>]`
- **Sample Output:**
  ```text
  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━┓
  ┃ Model                       ┃ Requests  ┃ Input Tokens ┃ Output Tokens ┃ Cost    ┃
  ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━╋━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━┫
  ┃ anthropic/claude-3.5-sonnet ┃ 1,120     ┃ 4,200,100    ┃ 1,104,200     ┃ $12.60  ┃
  ┃ openai/gpt-4o-mini          ┃ 612       ┃ 2,110,000    ┃ 482,000       ┃ $1.42   ┃
  ┃ deepseek/deepseek-coder     ┃ 110       ┃ 500,100      ┃ 95,700        ┃ $0.26   ┃
  ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━╋━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━╋━━━━━━━━━┫
  ┃ Total                       ┃ 1,842     ┃ 6,810,200    ┃ 1,681,900     ┃ $14.28  ┃
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━┻━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━┻━━━━━━━━━┛
  ```

---

### 3.7 `brahmastra chat`

#### Purpose
Starts a stateful, interactive AI coding session with live syntax highlighting, streaming token rendering, repository context awareness, and slash command integration.

#### Syntax
```bash
brahmastra chat [OPTIONS]
```

#### Options
- `--model`, `-m`: Target model ID (default: org default or auto-routed)
- `--provider`: Target provider override
- `--temp`: Temperature setting (0.0 - 1.0, default: 0.2)
- `--system-prompt`: Custom system instructions file path

#### REPL Slash Commands
Inside the chat REPL, users control session context with leading slash commands:
- `/help` — Display list of available chat commands
- `/model [id]` — Display or switch the active model on the fly
- `/context [files...]` — Add files or directory AST trees into conversation memory
- `/diff` — Preview model's proposed code modifications as unified diffs
- `/apply` — Apply proposed changes to disk with user sign-off
- `/clear` — Clear current conversation context and start fresh
- `/tokens` — Display token consumption and running cost for this session
- `/exit` or `Ctrl+D` — Terminate chat session gracefully

---

### 3.8 `brahmastra run <TASK>`

#### Purpose
Autonomous agentic coding loop: inspects repository, generates execution plan, creates/edits files, runs verification tests, and loops until tests pass or user intervention is requested.

#### Syntax
```bash
brahmastra run <task_description> [OPTIONS]
```

#### Options
- `--path`, `-p`: Root directory of codebase (default: current directory `.`)
- `--model`, `-m`: Model override for agent task
- `--max-iterations`: Max agent action steps before pausing for confirmation (default: 10)
- `--auto-approve`: Execute non-destructive actions without prompt (caution: shell commands still require policy check)
- `--dry-run`: Output plan and proposed file diffs without modifying filesystem

#### Step Execution Flow & Visual States
```text
$ brahmastra run "Add Prometheus metrics endpoint to HTTP router"

⠋ Phase 1: Analyzing repository structure and AST...
✓ Located router in src/network/router.py
✓ Located dependencies in pyproject.toml

⠋ Phase 2: Generating execution plan...
Plan:
  1. Add 'prometheus-client' to pyproject.toml dependencies
  2. Implement /metrics route handler in src/network/router.py
  3. Write unit test in tests/test_metrics.py
  4. Run pytest test suite

[Prompt] Proceed with Step 1: Modify pyproject.toml? [Y/n/diff] diff
[Shows Rich syntax highlighted diff]
[Prompt] Approve diff? [Y/n] y
✓ Step 1 complete.

⠋ Step 4: Running verification suite 'pytest tests/test_metrics.py'...
✓ Tests passed: 3 passed in 0.42s
Task completed successfully in 4 steps. Total spend: $0.041.
```

---

### 3.9 `brahmastra analyze <PATH>`

#### Purpose
Performs static analysis, architectural mapping, dependency graph construction, and evaluates codebase readiness for LLM context ingestion.

#### Syntax
```bash
brahmastra analyze [PATH] [OPTIONS]
```

#### Options
- `--depth`: Maximum directory traversal depth (default: 5)
- `--security`: Perform credential leak detection and unsafe pattern scan
- `--export`: Path to write markdown/json analysis report

#### Sample Output
```text
Codebase Analysis: /Users/kunalkhande/Project/Bhramstra
Total Files: 84 | Lines of Code: 12,410 | Primary Language: Python (94.2%)

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric            ┃ Value   ┃ Assessment                             ┃
┣━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Architecture Style┃ Modular ┃ Clean layer separation (Domain/App/Infra)┃
┃ Token Footprint   ┃ 68.4k   ┃ Fits within 128k context window        ┃
┃ Secret Scan       ┃ Clean   ┃ 0 hardcoded keys detected              ┃
┃ Test Coverage     ┃ 88.5%   ┃ Robust test harness                    ┃
┗━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
✓ Repository is fully indexed and ready for agent tasks.
```

---

## 4. Visual Design Guidelines & Rich Formatting Specifications

BRAHMASTRA enforces strict terminal styling rules via Python's `rich` library to deliver consistency across all commands.

### 4.1 Color Palette & Semantic Meaning

| Semantic Role | Hex / ANSI Style | Rich Token | Usage |
| :--- | :--- | :--- | :--- |
| **Primary Brand** | `#00E5FF` (Cyan) | `[bold cyan]` | CLI Title, Command headers, primary IDs |
| **Accent / Focus** | `#7C4DFF` (Purple) | `[bold magenta]` | Active organization badges, highlights |
| **Success** | `#00E676` (Green) | `[bold green]` | Checkmarks `✓`, PASS status, additions `+` |
| **Warning** | `#FFD600` (Amber) | `[bold yellow]` | WARN status, non-critical degraded modes |
| **Danger / Error** | `#FF1744` (Crimson)| `[bold red]` | FAIL status, exceptions, deletions `-` |
| **Subdued / Dim** | `#9E9E9E` (Grey) | `[dim]` | Timestamps, file paths, fingerprints |

### 4.2 Rich Table Formatting Rules
- **Box Style:** Tables must use `rich.box.ROUNDED` for smooth, modern curved corners.
- **Headers:** Styled in `bold cyan` with centered or left-aligned labels.
- **Lines:** Horizontal lines between rows (`show_lines=True`) only when row content contains multi-line text; otherwise, use clean row separation with alternating styles if tables exceed 15 rows.
- **Empty States:** When a table has no items, do not render an empty box. Render a friendly yellow callout explaining how to create or seed items.

### 4.3 Status Spinners & Progress Bars
- **Spinners:** Use `dots` spinner for fast tasks (< 2 seconds):
  ```python
  with console.status("[bold cyan]Querying OpenRouter catalog...", spinner="dots"):
      ...
  ```
- **Progress Bars:** For multi-step tasks (model downloads, file indexing), use `rich.progress.Progress` configured with:
  1. `SpinnerColumn()`
  2. `TextColumn("[progress.description]{task.description}")`
  3. `BarColumn(bar_width=40, style="dim", complete_style="bold cyan")`
  4. `TaskProgressColumn()`
  5. `TimeRemainingColumn()`

### 4.4 Alert Callouts / Admonition Panels
Informational and error banners must be rendered as `rich.panel.Panel` elements:

```python
from rich.panel import Panel

# Security Alert Panel Example:
panel = Panel(
    "[bold red]WARNING: Uncommitted Changes Detected[/bold red]\n"
    "Running this task will overwrite 3 unstaged files in your working tree.\n"
    "[dim]Commit your changes or use --stash to avoid data loss.[/dim]",
    title="[bold red]SECURITY GATE[/bold red]",
    border_style="red",
    box=box.ROUNDED,
)
```

### 4.5 Diff Syntax Highlighting
Unified diffs generated during code modification tasks must use `rich.syntax.Syntax`:
```python
from rich.syntax import Syntax

diff_content = """--- src/network/router.py
+++ src/network/router.py
@@ -12,4 +12,6 @@
 def create_router():
+    from prometheus_client import make_wsgi_app
+    app.mount("/metrics", make_wsgi_app())
"""
syntax = Syntax(diff_content, "diff", theme="monokai", line_numbers=True)
console.print(syntax)
```

---

## 5. Interactive Secure Prompts & TUI Guardrails

### 5.1 Masked Secret Input
When collecting sensitive material (API tokens, private keys, passwords), the CLI must never echo characters or record the value into shell histories:

```python
from rich.prompt import Prompt

# Secure non-echoing secret entry:
api_key = Prompt.ask("[bold cyan]Enter API Key[/bold cyan]", password=True)
```
- **Memory Hygiene:** Secret strings must be wiped from temporary variables immediately after persistence into the OS Keychain vault adapter.
- **Confirmation:** When provisioning new keys interactively, prompt twice to avoid typographical errors.

### 5.2 Destructive Action Confirmations
Destructive commands (`key revoke`, `key remove`, `provider remove`, `org delete`) require defensive confirmation dialogues:

```python
from rich.prompt import Confirm

# Standard confirmation:
if not Confirm.ask(f"[bold yellow]Revoke key '{alias}' permanently?[/bold yellow]", default=False):
    console.print("[dim]Action cancelled.[/dim]")
    raise typer.Exit(code=0)
```

For ultra-high-risk operations (such as purging an entire organization's metadata and credentials):
- Require the user to type the exact target name:
  ```text
  This operation is IRREVERSIBLE. To confirm deletion, type 'personal-dev':
  > personal-dev
  ✓ Organization 'personal-dev' and associated vault credentials purged.
  ```
- Support non-interactive CI automation with `--force` or `--yes` flags.

### 5.3 Interactive Multi-Select
For choosing between discovered models or organizations when no argument is supplied:
- Implement cursor-driven selection using `prompt_toolkit` or numbered choice lists if running in constrained terminals.

---

## 6. Error UX, Diagnostics & Failure Remediation

Unclear errors drive developer frustration. BRAHMASTRA standardizes all error output into a consistent, actionable format.

### 6.1 Standard Error Architecture
Every error emitted to `stderr` must include:
1. **Error Header & Code:** A distinct, documented machine-readable identifier (e.g. `ERR_VAULT_KEY_NOT_FOUND`).
2. **Context:** The specific organization, provider, or file involved.
3. **Root Cause:** Plain-English explanation of why the failure occurred.
4. **Actionable Remediation:** Step-by-step shell commands the user can run immediately to resolve the issue.

### 6.2 Visual Error Callout Example
```text
╭─────────────────────────────── ERROR [ERR_KEY_EXPIRED] ──────────────────────────────╮
│                                                                                      │
│ Upstream authentication rejected key for provider 'openrouter-prod'.                  │
│                                                                                      │
│ Context:                                                                             │
│   • Organization: enterprise-core                                                    │
│   • Provider: openrouter-prod                                                        │
│   • Key Fingerprint: sk-or-...9b2d                                                   │
│   • Upstream HTTP Status: 401 Unauthorized (Invalid API Key)                         │
│                                                                                      │
│ Remediation Steps:                                                                   │
│   1. Generate a new API key in your OpenRouter console (https://openrouter.ai/keys) │
│   2. Rotate the key in your local vault:                                             │
│      $ brahmastra key rotate main-key                                                │
│   3. Validate connection health:                                                     │
│      $ brahmastra key test main-key                                                  │
│                                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────╯
```

### 6.3 Standardized Error Code Taxonomy

| Error Code | Exit Code | Description | Typical Cause |
| :--- | :---: | :--- | :--- |
| `ERR_ENV_PREREQUISITE` | `1` | System requirement missing | Python < 3.10, missing Git, unsupported OS |
| `ERR_CLI_USAGE` | `2` | Invalid syntax or missing option | Bad flag, unknown command argument |
| `ERR_VAULT_ACCESS` | `3` | OS Keychain failure | Keychain locked, permission denied |
| `ERR_KEY_NOT_FOUND` | `3` | No key attached to provider | User has not run `brahmastra key add` |
| `ERR_AUTH_FAILED` | `3` | Upstream provider rejected auth | Revoked, expired, or malformed API token |
| `ERR_PROVIDER_TIMEOUT` | `4` | Network timeout reaching provider | Offline network, upstream gateway outage |
| `ERR_PROVIDER_RATE_LIMIT`| `4` | 429 Too Many Requests | Upstream quota exhausted |
| `ERR_POLICY_VIOLATION` | `5` | Security / sandbox gate rejected action | Unapproved shell execution, path escape |
| `ERR_USER_ABORT` | `130` | User cancelled operation | `Ctrl+C` / SIGINT pressed during prompt |

---

## 7. Shell Completion & Terminal Compatibility

### 7.1 Automatic Shell Completion Installation
BRAHMASTRA includes native tab-completion generation for commands, subcommands, and flags across modern shells.

#### Installation Commands
```bash
# Zsh completion setup:
$ brahmastra --install-completion zsh
✓ Zsh completions installed to ~/.zfunc/_brahmastra
ℹ Add 'fpath=(~/.zfunc $fpath); autoload -Uz compinit; compinit' to ~/.zshrc

# Bash completion setup:
$ brahmastra --install-completion bash
✓ Bash completions installed to ~/.bash_completion.d/brahmastra

# Fish completion setup:
$ brahmastra --install-completion fish
✓ Fish completions installed to ~/.config/fish/completions/brahmastra.fish
```

### 7.2 Terminal Emulator Matrix & Optimization

| Terminal Emulator | Platform | Truecolor Support | Protocol Features | Degradation Strategy |
| :--- | :--- | :---: | :--- | :--- |
| **iTerm2** | macOS | Full (24-bit) | Proprietary escapes, inline badges | Full Rich UI, rounded boxes, icons |
| **macOS Terminal.app** | macOS | Basic (256-color) | Standard ANSI | 256-color palette fallback |
| **Alacritty** | Cross-platform | Full (24-bit) | Fast GPU, UTF-8 glyphs | Full Rich UI, system bell on complete |
| **Warp** | macOS/Linux | Full (24-bit) | Modern command blocks | Clean block boundaries, no duplicate prompts |
| **VS Code Terminal** | Cross-platform | Full (24-bit) | Integrated links, clicks | Filepaths formatted as clickable `file://` |
| **Dumb / Non-TTY** | Headless / CI | None | Raw ASCII | Plain text, no ANSI escapes, no spinners |

### 7.3 Accessibility & Environment Variables
- `NO_COLOR`: When set to any value (e.g. `NO_COLOR=1`), all color formatting is disabled immediately in accordance with `no-color.org` standards.
- `FORCE_COLOR`: Forces color rendering even when stdout is redirected to a pipe.
- `BRAHMASTRA_PLAIN`: Equivalent to passing `--plain` globally.
- `TERM=dumb`: Disables progress bars, spinners, and box characters, falling back to clean line-by-line log output.

---

## 8. Verification & Test Plan for CLI UX

To maintain high usability, all CLI commands undergo automated contract tests in `tests/cli/`:
1. **Snapshot Testing:** Verify output strings, formatting, and table columns match expected golden master outputs.
2. **Exit Code Assertions:** Ensure errors strictly return their designated code (e.g., auth failure returns exit code `3`).
3. **No Secret Leakage Assertion:** Unit tests inspect stdout/stderr logs to verify secrets never appear in terminal output.
4. **Pipe Compatibility Test:** Test `brahmastra <cmd> --json | jq .` across all commands to ensure zero contamination of stdout.
