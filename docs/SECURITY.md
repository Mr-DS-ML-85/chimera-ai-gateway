# 🛡️ Security Policy — Chimera Gateway

## Overview

Chimera Gateway is a multi-provider AI routing system that handles:
- External API keys (Groq, Google, OpenRouter, etc.)
- User prompts and responses
- Optional encrypted outputs (AES-256-GCM)
- Tool routing and provider fallback logic

Because it operates as a **network-facing AI gateway**, security is a first-class design goal.

---

## 🔐 Threat Model

We assume adversarial input from:

- Prompt injection attacks
- Malicious tool-call manipulation
- SSRF attempts via model outputs
- API key leakage attempts
- Encoded payload bypass (Base64, Unicode, nested JSON)
- Provider-side malicious responses

---

## 🧱 Core Security Layers

### 1. WAF (Web Application Firewall)
Location: `security/waf.py`

Blocks:
- SQL injection
- XSS payloads
- Command injection
- Path traversal (`../`)
- Encoded bypass attempts

---

### 2. Prompt Shield
Location: `security/prompt_shield.py`

Detects:
- Multi-shot prompt injection
- Role confusion attacks (system prompt leakage)
- Instruction override attempts

---

### 3. Content Policy Engine
Location: `security/content_policy.py`

Blocks:
- CSAM content
- Weapons of mass destruction instructions
- Self-harm content
- Illegal instruction generation (configurable)

---

### 4. SSRF Protection
Location: `security/ssrf.py`

Prevents:
- Internal network access (`localhost`, `169.254.x.x`)
- Metadata service attacks (`/latest/meta-data`)

---

### 5. Canary Token System
Location: `security/canary.py`

Detects:
- API key leakage in model outputs
- Secret exfiltration attempts
- Prompt-based data extraction

---

### 6. Replay Protection
Location: `security/nonce.py`

Prevents:
- Request replay attacks
- Duplicate payload execution

---

### 7. Output Guard
Location: `security/output_guard.py`

Validates:
- Tool call structure
- Response schema integrity
- Malicious JSON injection

---

## 🔑 API Key Handling

- Keys are **never logged in full**
- Keys are stored only in environment variables
- Optional masking is applied in debug logs
- Rotation is recommended every 30–90 days

---

## 🔒 Encryption (Optional E2EE)

Chimera supports optional response encryption:

- Algorithm: AES-256-GCM
- Key exchange: X25519
- Scope: per-request encryption

Enabled via:
```json
{
  "encrypt": true
}

```


# 🚨 Incident Response

## If a vulnerability is found:

- Do NOT open a public issue with exploit details
- Contact maintainer privately
### Provide:
- Payload (if any)
- Provider affected


## Logs or reproduction steps
## 🧪 Security Testing
```
Run full security suite:

pytest tests/ -m security -v

Fuzz testing:

python security/ultimate_fuzzer.py

```
# ⚠️ Known Limitations
- ### Regex-based WAF may produce rare false positives
- ### Provider-side responses are not fully controllable
- ### Some encoded injection variants may bypass initial filters (mitigated downstream)


# 🧠 Security Philosophy

### Chimera follows a defense-in-depth architecture:

### No single layer is trusted. Every layer validates the previous one.