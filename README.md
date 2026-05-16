
<div align="center">


# 🔥 Chimera Gateway

### The Free, Secure, Multi-Source AI API Gateway

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen?style=for-the-badge&logo=pytest)](tests/)
[![Security](https://img.shields.io/badge/Security-AC--1%2FAC--2-red?style=for-the-badge&logo=shield)](docs/SECURITY.md)
[![Providers](https://img.shields.io/badge/Providers-15-purple?style=for-the-badge)](docs/PROVIDERS.md)
[![Coverage](https://img.shields.io/badge/Coverage-95%25-brightgreen?style=for-the-badge)](htmlcov/)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-ff69b4?style=for-the-badge)](CONTRIBUTING.md)

**One endpoint. 20+ providers. Zero vendor lock-in. Full security.**

[🚀 Quick Start](#-quick-start) · [📖 Docs](docs/) · [🛡️ Security](docs/SECURITY.md) · [🧪 Testing](tests/) · [🌐 Live Demo](#)

</div>

---

## ✨ What Is Chimera Gateway?

Chimera Gateway is a **production-grade, self-hosted AI API gateway** that routes your LLM requests across **15 free providers** with intelligent fallback, latency-aware routing, local Ollama support, and battle-tested security defences directly informed by the **"Your Agent Is Mine"** research paper (arXiv:2604.08407).

Drop in as a replacement for any OpenAI-compatible client — zero code changes required.

```bash
# Before (locked to one provider)
curl https://api.openai.com/v1/chat/completions ...

# After (21 providers, smart routing, full security)
curl http://localhost:8000/v1/chat/completions ...
```

---

## 🏗️ Architecture
```

                          ┌─────────────────────────────────────────────┐
                          │                Your Application            │
                          │     (OpenAI SDK · Claude SDK · curl ·      │
                          │               any HTTP client)             │
                          └──────────────────────────┬──────────────────┘
                                                     │
                          POST /v1/chat/completions or /v1/messages
                                                     │
                                                     ▼
          ┌─────────────────────────────────────────────────────────────────────┐
          │                      Chimera Gateway v8.2.0                        │
          │                                                                     │
          │   ┌───────────┐  ┌─────────┐  ┌───────────┐  ┌──────────┐          │
          │   │ Auth Gate │→ │  WAF    │→ │  Prompt   │→ │ Content  │          │
          │   │ (Bearer)  │  │         │  │  Shield   │  │ Policy   │          │
          │   └───────────┘  └─────────┘  └───────────┘  └──────────┘          │
          │                               │                                     │
          │   ┌─────────────────────────────────────────────────────────────┐   │
          │   │                 Intelligent Routing Engine                  │   │
          │   │      auto · fast · quality · balanced · reasoning           │   │
          │   │      + 21 provider circuit breakers & rate limiters        │   │
          │   └─────────────────────────────────────────────────────────────┘   │
          │                                                                     │
          │   ┌───────────┐  ┌───────────┐  ┌────────────────────┐            │
          │   │ Canaries  │  │   E2EE    │  │ Transparency Log   │            │
          │   │ (key leak)│  │ (AES-GCM) │  │  (SHA-256 audit)   │            │
          │   └───────────┘  └───────────┘  └────────────────────┘            │
          └──────────────────────────┬──────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Cloud    │   │    Local     │   │   Custom     │
            │ Providers  │   │   Ollama     │   │    BYOK      │
            │  (20 APIs) │   │  (offline)   │   │  (vLLM etc)  │
            └────────────┘   └──────────────┘   └──────────────┘

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

## 🤖 Claude Code / Anthropic SDK Support

Chimera natively supports the Anthropic API format via `/v1/messages` and `/v1/responses` — works directly with Claude Code, Claude SDK (Node/Python), and any Anthropic-compatible client.

### Quick Start — Claude SDK

```bash
# Set environment
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_AUTH_TOKEN="your_chimera_api_key"
```

```javascript
// Node.js — Claude SDK
import Anthropic from '@anthropic-ai/sdk';
const client = new Anthropic({ baseURL: process.env.ANTHROPIC_BASE_URL });
const msg = await client.messages.create({
  model: "auto:reasoning",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Explain quantum entanglement" }],
});
```

```python
# Python — Anthropic SDK
from anthropic import Anthropic
client = Anthropic(base_url="http://localhost:8000")
msg = client.messages.create(
    model="auto:reasoning",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Supported Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /v1/messages` | Messages API — non-streaming & streaming (SSE) |
| `POST /v1/messages/count_tokens` | Token counting for pre-flight checks |
| `POST /v1/responses` | Responses API format wrapper |

### Virtual Models with Anthropic

All virtual model aliases work with `/v1/messages`:

- `auto` / `auto:free` — Best non-reasoning model (fast by default)
- `auto:reasoning` / `auto:free:reasoning` — Best reasoning model
- `fast` / `quality` / `balanced` — Latency vs quality trade-offs

Model alias shortcuts: `sonnet` → `claude-sonnet-4-7`, `opus` → `claude-opus-4-5`, `haiku` → `claude-haiku-4-7`

### Model Name Rewriting for Claude Desktop

Claude Desktop (and Cowork) validates model names in Gateway mode — only names containing `claude`, `sonnet`, `opus`, `haiku`, or `anthropic` are accepted (see [GitHub #56990](https://github.com/anthropics/claude-code/issues/56990)). Chimera automatically rewrites free/third-party model names to the `opencode-zen/` prefix so they pass validation while routing to the correct backend:

| Client model name | Rewritten to |
|---|---|
| `minimax-m2.5-free` | `opencode-zen/minimax-m2.5-free` |
| `gemini-3-flash` | `opencode-zen/gemini-3-flash` |
| `glm-5` | `opencode-zen/glm-5` |
| `qwq-32b` | `opencode-zen/qwq-32b` |
| `gpt-oss-20b` | `opencode-zen/gpt-oss-20b` |

This applies to both `/v1/chat/completions` and `/v1/messages` endpoints. No client config change needed — just use the model name as-is.

### Direct Anthropic API

Set `ANTHROPIC_API_KEY` in `.env` to route directly to Anthropic for model names starting with `anthropic/`:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_TIMEOUT=120
```

### Anthropic Headers

These headers are forwarded through to the upstream provider:
- `anthropic-beta` — enables beta features
- `anthropic-version` — API version (e.g. `2023-06-01`)
- `anthropic-dangerous-direct-browser-access` — for direct browser clients

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
| 21 | **Anthropic (direct)** | ⚠️ Paid API | — | Vision · Tools · Thinking · Stream | `ANTHROPIC_API_KEY` |
| 22 | **Custom (BYOK)** | ✅ User-defined | ∞ | Vision · Tools · System · Stream | `CUSTOM_OPENAI_*` |

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

# Anthropic direct routing (optional — for claude-sonnet-4, claude-opus-4, etc.)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_TIMEOUT=120

# OpenCode Zen — free model gateway (minimax-m2.5-free, gemini-3-flash, glm-5, etc.)
# Also used for Claude Desktop model name rewriting (see README)
OPENCODE_ZEN_API_KEY=

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
