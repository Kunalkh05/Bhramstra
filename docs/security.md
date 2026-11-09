# BRAHMASTRA Security Architecture & Policy

Security is a foundational design requirement for BRAHMASTRA, not an afterthought.

---

## 1. Zero Plaintext Secrets Rule

- **No Secrets in Source Code or Git:**
  - Strict `.gitignore` prevents configuration and environment files from ever being staged.
- **No Secrets in Database:**
  - SQLite database stores strictly metadata and *vault references*. Plaintext API keys or tokens are forbidden from being inserted into relational tables.
- **OS Vault Abstraction:**
  - On macOS, secrets are kept in the OS Keychain using the `security` framework or standard vault APIs.
  - Test suites utilize an isolated in-memory fake vault; tests never read from or write to the developer's real macOS Keychain.
- **No Secrets in CLI Arguments or Command Line History:**
  - Sensitive inputs (API tokens) are accepted only via masked interactive prompts or standard input redirection, never as `--key <secret>` CLI flags.
- **Redaction in Logs and Output:**
  - Exceptions, traces, and terminal logs must scrub sensitive keys before display.

---

## 2. Organization Isolation

- **Explicit Assignment:**
  - A provider account is only accessible to an organization if explicitly assigned by the user.
- **Zero Cross-Talk:**
  - Context, credentials, and usage records cannot cross organization boundaries. Requests executed under Org `Company` can never tap into Org `Personal` credentials or history.

---

## 3. Untrusted Code and Execution Control

- **Model Output is Untrusted:**
  - Models frequently generate inaccurate or dangerous code and shell commands.
- **Explicit Approval Required:**
  - No autonomous filesystem writes or shell command executions are allowed without explicit user confirmation.
- **Path Traversal Protection:**
  - File operations must validate canonical paths to ensure they reside strictly within the designated project root.

---

## 4. Mac Architecture Security Considerations

- Works natively on macOS (`arm64` and `x86_64`).
- Avoids arbitrary binary downloads; relies on standard audited Python packages and OS-provided tools.
