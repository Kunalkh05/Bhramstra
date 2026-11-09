# BRAHMASTRA Architecture Overview

## 1. Architectural Philosophy: The Modular Monolith

BRAHMASTRA is deliberately designed as a **modular monolith**. 

### Why not Microservices?
- Microservices add network serialization overhead, distributed failure modes, complex deployments, and operational headaches that are unnecessary for a CLI developer tool.
- A modular monolith enforces strict boundaries between layers using Python modules, interfaces, and typing, keeping the system clean, testable, and maintainable without distributed complexity.

---

## 2. Target Package Structure

The codebase is organized into cleanly separated layers:

```text
src/brahmastra/
  cli/                     # Typer CLI application, CLI presentation (Rich tables/prompts)
    app.py                 # Main CLI entrypoint
    commands/              # Subcommands (doctor, org, provider, key, chat, etc.)
  application/             # Orchestrates business workflows (Use Cases)
    use_cases/             # Coordinate domain entities and infrastructure
  domain/                  # Pure business rules, domain entities, and abstractions
    organizations/         # Organization workspaces and access boundaries
    credentials/           # Credential metadata, lifecycle states, assignments
    providers/             # Provider interface contracts (generate, list_models, health_check)
    models/                # Model capabilities, context windows, pricing metadata
    routing/               # Explainable model and account routing engine
    tasks/                 # Coding tasks, diffs, approvals
  infrastructure/          # Concrete implementations of external systems
    database/              # SQLite metadata storage via SQLAlchemy
    vault/                 # OS Keychain integration (macOS) & In-memory fake vault
    providers/             # OpenRouter client adapter, Ollama client adapter
  agents/                  # Assistant logic, repository inspection, code generation
  verification/            # Sandboxing, test runners, execution validation
  evaluation/              # Fixed benchmarks and model scoring
  observability/           # Usage accounting, structured logs, audit trails
tests/
  unit/                    # Fast isolated tests (mocked dependencies)
  integration/             # Multi-component interaction tests
  security/                # Vault isolation, leak prevention, command sanitization
```

---

## 3. Strict Architectural Rules

1. **Clean Dependency Inversion:**
   - The `domain/` layer has zero dependencies on CLI rendering (Rich/Typer) or external network SDKs.
   - External adapters in `infrastructure/` implement interfaces defined in `domain/`.
2. **Secrets Never Touch the Database:**
   - The database stores only non-secret *vault references* (e.g. `vault_key = "brahmastra:org-1:account-openrouter-prod"`).
   - Raw secrets are stored solely in the operating system vault (macOS Keychain) via an abstracted vault interface.
3. **Multi-Architecture macOS Support:**
   - BRAHMASTRA runs natively on macOS Apple Silicon (`arm64`) as well as Intel (`x86_64`).
   - We avoid brittle compiled dependencies and use native macOS system APIs.
4. **Untrusted Model Outputs:**
   - Output from LLMs is strictly treated as untrusted user input.
   - Shell commands and file modifications require explicit user authorization before execution.
