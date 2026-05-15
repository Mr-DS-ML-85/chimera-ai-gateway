# 🔥 Chimera AI Gateway

**The free, secure, multi-source AI API gateway — 21 providers, one endpoint.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Security](https://img.shields.io/badge/Security-AC--1%2FAC--2-red?style=for-the-badge&logo=shield)](docs/SECURITY.md)
[![Providers](https://img.shields.io/badge/Providers-21-purple?style=for-the-badge)](docs/PROVIDERS.md)

**v8.2.0** · One endpoint · 21 providers · Virtual model routing · Claude Code compatible

---

## ✨ What Is Chimera Gateway?

Chimera Gateway is a **self-hosted AI API gateway** that routes LLM requests across **21 providers** with intelligent fallback, circuit breakers, and battle-tested security defences.

Use it as a drop-in replacement for any OpenAI-compatible client — zero code changes.

```bash
# Before (locked to one provider)
curl https://api.openai.com/v1/chat/completions ...

# After (21 providers, smart routing, full security)
curl http://localhost:8000/v1/chat/completions ...
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Application                        │
│        (OpenAI SDK · Claude SDK · curl · any HTTP client)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ POST /v1/chat/completions or /v1/messages
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Chimera Gateway v8.2.0                     │
│                                                             │
│  ┌───────────┐  ┌─────────┐  ┌───────────┐  ┌──────────┐  │
│  │ Auth Gate │→ │   WAF   │→ │  Prompt   │→ │ Content  │  │
│  │ (Bearer)  │  │         │  │  Shield   │  │  Policy  │  │
│  └───────────┘  └─────────┘  └───────────┘  └──────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Intelligent Routing Engine                   │  │
│  │   auto · fast · quality · balanced · reasoning       │  │
│  │   + 21 provider circuit breakers & rate limiters     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────┐  ┌───────────┐  ┌────────────────────┐     │
│  │ Canaries  │  │  E2EE     │  │ Transparency Log   │     │
│  │ (key leak)│  │(AES-GCM)  │  │  (SHA-256 audit)   │     │
│  └───────────┘  └───────────┘  └────────────────────┘     │
└──────────────────────────┬──────────────────────────────────┘
                           │
   ┌───────────────────────┼────────────────────────┐
   ▼                       ▼                        ▼
┌──────────┐        ┌──────────────┐         ┌──────────┐
│  Cloud   │        │    Local     │         │  Custom  │
│ Providers│        │   Ollama     │         │   BYOK   │
│(20 APIs) │        │ (offline)   │         │ (vLLM etc)
└──────────┘        └──────────────┘         └──────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Mr-DS-ML-85/chimera-ai-gateway.git
cd chimera-ai-gateway
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure

Edit `.env` — add at least one API key. **Pollinations.AI works with zero keys.**

```dotenv
# Minimum: one key (or nothing for Pollinations free)
GROQ_API_KEY=your_key_here
```

### 3. Run

```bash
# Development
DEV=1 python main.py

# Production
python main.py

# Health check
curl http://localhost:8000/v1/health
```

### 4. Try It

```bash
# OpenAI-compatible
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello!"}]}'

# Anthropic / Claude Code — /v1/messages
curl -X POST http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### 5. Docker

```bash
# Build & run
docker build -t chimera-gateway .
docker run -d --name chimera -p 8000:8000 --env-file .env chimera-gateway

# Docker Compose (Chimera + Ollama)
docker compose up -d
```

---

## 🎯 Virtual Models

Use these special model names for automatic intelligent routing:

- **`auto`** — Best free non-reasoning model (fast by default)
- **`auto:free`** — Free-tier only, non-reasoning
- **`auto:reasoning`** — Best free reasoning/math/code model
- **`auto:free:reasoning`** — Free-tier only, reasoning
- **`fast` / `fast:free`** — Prioritise latency
- **`quality` / `balanced`** — Prioritise output quality
- **`reasoning` / `reasoning:free`** — Reasoning models
- **`non-reasoning` / `non-reasoning:free`** — General-purpose models

Provider-prefixed variants also work: `groq/auto`, `openrouter/reasoning`, `ollama/fast`, etc.

---

## 🤖 Claude Code / Anthropic Support

Chimera natively supports the `/v1/messages` endpoint for Claude Code and Anthropic SDK clients.

```bash
# Claude SDK
const client = new Anthropic({ baseURL: "http://localhost:8000" });
const msg = await client.messages.create({
  model: "auto:reasoning",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Explain quantum entanglement" }],
});
```

```python
# Python Anthropic SDK
from anthropic import Anthropic
client = Anthropic(base_url="http://localhost:8000")
msg = client.messages.create(
    model="auto:reasoning",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)
```

---

## 🆓 Provider Matrix (21 Providers)

| # | Provider | Free Tier | RPM | Capabilities | Key Variable |
|---|----------|-----------|-----|--------------|--------------|
| 1 | **Groq** | ✅ No CC | 30 | Tools · System · Stream | `GROQ_API_KEY` |
| 2 | **Google AI Studio** | ✅ No CC | 15 | Vision · Tools · System · Stream | `GOOGLE_API_KEY` |
| 3 | **OpenRouter** | ✅ No CC | 20 | Vision · Tools · System · Stream | `OPENROUTER_API_KEY` |
| 4 | **Cloudflare Workers AI** | 10K neurons/day | 300 | System · Stream | `CF_ACCOUNT_ID` + `CF_API_TOKEN` |
| 5 | **GitHub Models** | ✅ 50 req/day | 5–15 | Tools · System · Stream | `GITHUB_TOKEN` |
| 6 | **NVIDIA NIM** | ⚠️ 1K credits | 40 | Tools · System · Stream | `NVIDIA_NIM_API_KEY` |
| 7 | **a4f.co** | ✅ No CC | 20 | System · Stream | `A4F_API_KEY` |
| 8 | **Cerebras** | ✅ No CC | 30 | Tools · System · Stream | `CEREBRAS_API_KEY` |
| 9 | **Pollinations.AI** | ✅ Zero-key | 10 | Vision · System | None needed |
| 10 | **Ollama (Local)** | ✅ Unlimited | ∞ | Vision · Tools · System · Stream | `OLLAMA_BASE_URL` |
| 11 | **HuggingFace** | ✅ No CC | 60 | System · Stream | `HUGGINGFACE_API_KEY` |
| 12 | **SambaNova** | ✅ No CC | 30 | System · Stream | `SAMBANOVA_API_KEY` |
| 13 | **Together AI** | $5 credit | 60 | Tools · System · Stream | `TOGETHER_API_KEY` |
| 14 | **LLM7.io** | ✅ Anonymous | 30 | Vision · System | `LLM7_API_KEY` |
| 15 | **Mistral AI** | ✅ Experiment | 2 | Vision · Tools · System · Stream | `MISTRAL_API_KEY` |
| 16 | **xAI / Grok** | ⚠️ Paid API | 60 | Vision · Tools · System · Stream | `XAI_API_KEY` |
| 17 | **DeepSeek** | ✅ Trial credits | 60 | Tools · System · Stream | `DEEPSEEK_API_KEY` |
| 18 | **Perplexity** | ❌ Paid API | 20 | System · Stream · Search | `PERPLEXITY_API_KEY` |
| 19 | **Fireworks AI** | $1 credit | 6,000 | Vision · Tools · System · Stream | `FIREWORKS_API_KEY` |
| 20 | **DeepInfra** | ✅ Trial credits | 12,000 | Tools · System · Stream | `DEEPINFRA_API_KEY` |
| 21 | **Custom (BYOK)** | ✅ User-defined | ∞ | Vision · Tools · System · Stream | `CUSTOM_OPENAI_*` |

See [docs/PROVIDERS.md](docs/PROVIDERS.md) for full provider details and model lists.

---

## 🛡️ Security Features

Built on the **"Your Agent Is Mine"** threat model (arXiv:2604.08407):

- **AC-1 Payload Injection** — Pattern + Base64 nested scan for injected code
- **AC-2 Secret Exfiltration** — Canary token detection for API key leaks
- **Prompt Shield** — Many-shot and encoding-bypass injection detection
- **Content Policy** — CSAM, WMD, self-harm block lists
- **WAF** — SQLi, XSS, CMDi, path traversal protection
- **PII Redaction** — Automatic sensitive data masking in logs
- **SSRF Guard** — No redirect following to internal resources
- **AES-256-GCM E2EE** — Optional per-request response encryption
- **HMAC Request Signing** — Request integrity verification
- **Transparency Log** — Append-only SHA-256 audit trail

See [docs/SECURITY.md](docs/SECURITY.md) for full details.

---

## ⚙️ Configuration

Key `.env` variables:

```dotenv
# Gateway
CHIMERA_API_KEY=your_master_key
ROUTE_BY=quality          # quality | latency | random

# Provider keys (add as needed)
GROQ_API_KEY=
GOOGLE_API_KEY=
OPENROUTER_API_KEY=
POLLINATIONS_API_KEY=    # optional — works without it
OLLAMA_BASE_URL=http://localhost:11434
CUSTOM_OPENAI_BASE_URL=  # your vLLM / ollama server

# Security
ENABLE_WAF=1
ENABLE_PII_REDACTION=1

# Runtime
PORT=8000
DEV=0                    # 1 for development
```

---

## 🗂️ Project Structure

```
chimera-ai-gateway/
├── main.py                    # Entry point (python main.py)
├── api/
│   ├── app.py                 # FastAPI app factory
│   ├── middleware.py           # CORS, request ID, client IP
│   └── routes/
│       ├── chat.py            # /v1/chat/completions + /v1/messages
│       ├── health.py          # /v1/health
│       ├── models.py          # /v1/models
│       ├── metrics.py         # /v1/metrics
│       ├── admin.py           # /v1/admin/* (keys, providers)
│       └── transparency.py    # /v1/transparency-log
├── providers/
│   ├── catalogue.py            # 21 provider definitions + live discovery
│   ├── router.py              # Intelligent routing engine
│   ├── virtual_routes.py      # Virtual model alias resolution
│   ├── circuit_breaker.py     # Per-provider health/failover
│   ├── rate_limiter.py        # Sliding-window RPM/RPD limits
│   └── auto_models.py         # Hourly live model refresh
├── security/
│   ├── waf.py                 # Web Application Firewall
│   ├── prompt_shield.py      # Injection detection
│   ├── canary.py              # API key exfil detection
│   ├── pii.py                 # PII redaction
│   └── ssrf.py                # SSRF protection
├── crypto/
│   └── e2ee.py                # AES-256-GCM E2EE
├── keys/
│   └── virtual_keys.py        # Scoped API key management
├── transparency/
│   └── log.py                 # SHA-256 audit log
└── docs/
    ├── API.md                 # Full API reference
    ├── PROVIDERS.md           # Detailed provider docs
    └── SECURITY.md            # Security architecture
```

> **Note:** This is a flat-package project. Run with `PYTHONPATH=. python main.py` or from the project root. Do NOT `pip install` the directory — it is not a published package.

---

## 🔧 Development

```bash
# Full test suite (mocked — no API calls)
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=html

# Specific test categories
pytest tests/ -v -m security     # security tests
pytest tests/ -v -m integration # integration tests

# Lint
ruff check .
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 🙏 Credits

- [cheahjs/free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources) — free provider catalogue
- ["Your Agent Is Mine"](https://arxiv.org/abs/2604.08407) (arXiv:2604.08407) — security threat model
- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- All 21 integrated AI providers