# 🤝 Contributing to Chimera Gateway

Thank you for your interest in improving Chimera 🚀  
This project is built to be **modular, secure, and production-grade**, so contributions are highly welcome.

---

## 🧭 Project Philosophy

Before contributing, understand:

- Security > Features
- Reliability > Complexity
- Transparency > Magic
- Multi-provider resilience is core design

---

## 🏗️ Development Setup

### 1. Clone repository

```bash
git clone https://github.com/your-org/chimera-gateway.git
cd chimera-gateway

```

This guide outlines the standard procedures for contributing to and running **Chimera Gateway**. Please follow these steps to ensure system stability and security.

---


### 2. Create Virtual Environment

Set up a clean environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements-dev.txt

```

### 4. Run Locally

```bash
python main.py

```

---

## 🧪 Running Tests

We use `pytest` for our testing suite. Ensure all tests pass before submitting changes.

* **Full test suite:** `pytest tests/ -v`
* **Security tests:** `pytest tests/ -m security -v`
* **Integration tests:** `pytest tests/ -m integration -v`

---

## 🧱 Code Style Guidelines

* **Type Safety:** Use type hints everywhere.
* **Asynchronous I/O:** Prefer `async`/`await` for all I/O operations.
* **Modularity:** Keep functions small, focused, and testable.
* **Performance:** Avoid blocking operations in the request path.
* **Privacy:** Never log secrets, credentials, or raw API keys.

---

## 🔐 Security Rules (MANDATORY)

**Strictly adhere to the following to prevent vulnerabilities:**

* **Do NOT** disable WAF (Web Application Firewall) checks.
* **Do NOT** bypass prompt shield logic.
* **Do NOT** log full request payloads in production environments.
* **Do NOT** add external network calls without SSRF validation.
* **Do NOT** commit `.env` files to the repository.

---

## 🧩 Adding a New Provider

When integrating a new AI provider, follow these requirements:

1. **Catalogue Entry:** Add an entry in `providers/catalogue.py`.
2. **Definitions:** Define `base_url`, `models_path`, and `capabilities`.
3. **Validation:**
* Ensure rate limits are explicitly defined.
* Mark keyless support status correctly.
* Add comprehensive test coverage in `tests/test_providers.py`.



---

## 🧠 Adding Features

Before implementing a new feature, evaluate the following:

* Does this break provider abstraction?
* Does it affect routing stability?
* Does it introduce security risk?

> **Note:** If the answer to any of the above is **Yes**, you must implement the necessary safeguards first.

---

## 📦 Commit Convention

We follow structured commit messages to maintain a clean history:

| Prefix | Description | Example |
| --- | --- | --- |
| `feat:` | New features | `feat: add new routing strategy` |
| `fix:` | Bug fixes | `fix: resolve provider timeout bug` |
| `security:` | Security patches | `security: patch prompt injection bypass` |
| `refactor:` | Code improvements | `refactor: simplify router logic` |
| `test:` | Adding/updating tests | `test: add ollama integration tests` |

---

## 🔄 Pull Request Process

1. **Fork** the repository and create a **feature branch**.
2. **Add tests** for your changes.
3. **Run the full suite** to ensure no regressions.
4. **Submit PR** ensuring it includes:
* Passing CI/CD pipeline.
* No security regressions.
* A clear, concise description of changes.



---

## 🚨 Reporting Issues

* **Security Vulnerability:** Report privately via the designated security contact.
* **Bugs:** Open an issue with clear reproduction steps.
* **Feature Requests:** Describe the use case and intended benefit clearly.

---

## 🧠 Design Philosophy

Chimera is more than an API wrapper—it is a **routing intelligence layer** designed for multi-provider AI ecosystems. Every contribution should prioritize **resilience, observability, and provider neutrality.**

**🙏 Thank you for helping make AI systems more reliable and secure!**