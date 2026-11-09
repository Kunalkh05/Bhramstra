# BRAHMASTRA — Concepts for Beginners

Welcome! If you are learning software engineering and AI systems, this guide breaks down every technical concept and jargon term used across BRAHMASTRA.

---

## 1. Core Terminology Explained Simply

### Organization (Org)
- **What it is:** A workspace or boundary representing who owns a task. For example: `Personal`, `Work-AcmeCorp`, `College-Project`.
- **Why it matters:** You don't want your personal side project's AI usage to get billed to your employer, or your company's proprietary code to be sent through your personal unvetted accounts. Organizations prevent accidental cross-contamination.

### Provider
- **What it is:** A company or engine that runs AI models. 
- **Examples:** OpenRouter (cloud API aggregating multiple models), Ollama (local software that runs models right on your Mac laptop).

### Provider Account
- **What it is:** A specific account or registration with a provider.
- **Example:** You might have two OpenRouter accounts: one with high tier quota for production work, and one free account for quick experiments.

### Credential
- **What it is:** The actual secret key or token (e.g. `sk-or-v1-abc...`) used to prove identity to a provider account.
- **Lifecycle:** A credential can be added, tested, rotated (replaced with a new one), revoked, or permanently removed.

### Vault Reference
- **What it is:** A harmless label or pointer that refers to where a secret is stored, without containing the secret itself.
- **Analogy:** Think of a coat check ticket at a theater. The ticket is just a numbered plastic tag (`#42`), not the coat itself. If someone steals ticket `#42`, but doesn't have access to the coat room vault, they have nothing. In BRAHMASTRA, the SQLite database stores only the ticket (`vault:openrouter:acc1`), while macOS Keychain securely locks away the actual key.

### Normalized Provider Interface
- **What it is:** A single standard contract that all AI backends must follow.
- **Analogy:** A standard wall outlet. Whether you plug in a lamp or a laptop charger, the two-prong plug fits into the wall socket. Similarly, BRAHMASTRA defines a single `generate(request)` method. Whether the AI model is running on a cloud server across the ocean (OpenRouter) or locally on your Mac's GPU/M-series chip (Ollama), the application talks to them using the exact same code.

### Doctor Command
- **What it is:** A diagnostic command (`brahmastra doctor`) that inspects your local environment and reports if anything is broken, missing, or misconfigured.

---

## 2. macOS Architectures: ARM64 vs x86_64

- **ARM64 (Apple Silicon):** Newer Apple computers powered by M1, M2, M3, or M4 chips. They use the ARM instruction set, which is known for high energy efficiency and powerful Neural Engine hardware.
- **x86_64 (Intel):** Traditional processor architecture used on older Macs and many PC servers.
- **Why it matters for BRAHMASTRA:** Our code and CLI tools must work seamlessly on both chip architectures without requiring complicated compilation steps.
