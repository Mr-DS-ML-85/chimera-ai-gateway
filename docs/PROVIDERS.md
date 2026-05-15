# 🛰️ Providers — Chimera Gateway

> **Last updated for Chimera Gateway v8.2.0 — 22 providers**

---

## Overview

Chimera Gateway ships with **22 configured AI provider integrations** covering free-tier, trial-credit, and BYOK endpoints. Providers are automatically discovered on startup and refreshed hourly via each provider's native `/models` endpoint.

Providers are sorted by default **quality** priority (lower number = higher priority). You can override the routing strategy via `ROUTE_BY=quality|latency|random`.

---

## Provider Catalogue

### 1. Groq

| Field | Value |
|---|---|
| **Base URL** | `https://api.groq.com/openai/v1` |
| **Auth** | API key required |
| **RPM / RPD** | 30 / 14,400 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 1 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `GROQ_API_KEY` |

**Models:** `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `llama-4-scout`, `llama-4-maverick`, `deepseek-r1-distill-70b`, `qwen-3-32b`

---

### 2. Google AI Studio

| Field | Value |
|---|---|
| **Base URL** | `https://generativelanguage.googleapis.com/v1beta/openai` |
| **Auth** | API key required |
| **RPM / RPD** | 15 / 1,500 |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 2 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `GOOGLE_API_KEY` |

**Models:** `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`

---

### 3. OpenRouter

| Field | Value |
|---|---|
| **Base URL** | `https://openrouter.ai/api/v1` |
| **Auth** | API key required |
| **RPM / RPD** | 20 / 200 |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 3 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `OPENROUTER_API_KEY` |

**Models (free):** `meta-llama/llama-4-scout:free`, `google/gemma-3-27b-it:free`, `mistralai/mistral-small-3.1-24b:free`, `deepseek/deepseek-r1:free`, `deepseek/deepseek-r1-zero:free`

---

### 4. Cloudflare Workers AI

| Field | Value |
|---|---|
| **Base URL** | `https://api.cloudflare.com/client/v4/accounts/{id}/ai/run` |
| **Auth** | Account ID + API token |
| **RPM** | 300 |
| **Capabilities** | System prompts, Streaming |
| **Priority** | 4 |
| **Free tier** | 10K neurons/day |
| **Key vars** | `CF_ACCOUNT_ID`, `CF_API_TOKEN` |

**Models:** `@cf/meta/llama-3.1-8b-instruct-fp8`, `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b`

---

### 5. GitHub Models

| Field | Value |
|---|---|
| **Base URL** | `https://models.inference.ai.azure.com` |
| **Auth** | GitHub PAT |
| **RPM / RPD** | 5–15 / 50–150 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 5 |
| **Free tier** | ✅ 50 req/day (varies) |
| **Key var** | `GITHUB_TOKEN` |

**Models:** `Llama-3.3-70B-Instruct`, `gpt-4o-mini`, `DeepSeek-R1`, `o1-mini`

---

### 6. NVIDIA NIM

| Field | Value |
|---|---|
| **Base URL** | `https://integrate.api.nvidia.com/v1` |
| **Auth** | API key required |
| **RPM** | 40 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 6 |
| **Free tier** | ⚠️ 1,000 credits (one-time) |
| **Key var** | `NVIDIA_NIM_API_KEY` |

**Models:** `meta/llama-3.3-70b-instruct`, `nvidia/llama-3.1-nemotron-ultra-253b`, `deepseek-ai/deepseek-r1`

---

### 7. a4f.co

| Field | Value |
|---|---|
| **Base URL** | `https://api.a4f.co/v1` |
| **Auth** | API key required |
| **RPM / RPD** | 20 / 200 |
| **Capabilities** | System prompts, Streaming |
| **Priority** | 7 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `A4F_API_KEY` |

---

### 8. Cerebras

| Field | Value |
|---|---|
| **Base URL** | `https://api.cerebras.ai/v1` |
| **Auth** | API key required |
| **RPM / RPD / TPD** | 30 / 14,400 / 1M |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 2 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `CEREBRAS_API_KEY` |

**Models:** `llama3.1-8b`, `qwen-3-235b-a22b-instruct`

---

### 9. Pollinations.AI

| Field | Value |
|---|---|
| **Base URL** | `https://gen.pollinations.ai` |
| **Auth** | **None — fully free** |
| **RPM** | 10 |
| **Capabilities** | Vision, System prompts |
| **Priority** | 8 |
| **Free tier** | ✅ Zero-key, no signup |
| **Key var** | `POLLINATIONS_API_KEY` (optional) |

**Models:** `openai`, `mistral`, `llama`, `gemini`, `deepseek-reasoner`

> Pollinations.AI is the recommended fallback for fully anonymous / zero-key usage.

---

### 10. Ollama (Local)

| Field | Value |
|---|---|
| **Base URL** | `http://localhost:11434` (configurable) |
| **Auth** | None |
| **RPM / RPD / TPD** | ∞ |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 99 |
| **Free tier** | ✅ Unlimited (local hardware) |
| **Key var** | `OLLAMA_BASE_URL` |

**Environment-configurable model lists:**
- `OLLAMA_NR_MODELS` — comma-separated non-reasoning models
- `OLLAMA_R_MODELS` — comma-separated reasoning models

---

### 11. Custom OpenAI-Compatible Endpoint (BYOK)

| Field | Value |
|---|---|
| **Base URL** | User-defined |
| **Auth** | Optional |
| **RPM / RPD / TPD** | Configurable |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | Configurable (default 0) |
| **Key vars** | `CUSTOM_OPENAI_BASE_URL`, `CUSTOM_OPENAI_API_KEY` |

**Environment-configurable model lists:**
- `CUSTOM_OPENAI_MODELS_NR`
- `CUSTOM_OPENAI_MODELS_R`

---

### 12. HuggingFace Inference API

| Field | Value |
|---|---|
| **Base URL** | `https://api-inference.huggingface.co/v1` |
| **Auth** | HF token required |
| **RPM** | 60 |
| **Capabilities** | System prompts, Streaming |
| **Priority** | 6 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `HUGGINGFACE_API_KEY` |

---

### 13. SambaNova

| Field | Value |
|---|---|
| **Base URL** | `https://api.sambanova.ai/v1` |
| **Auth** | API key required |
| **RPM** | 30 |
| **Capabilities** | System prompts, Streaming |
| **Priority** | 2 |
| **Free tier** | ✅ No credit card required |
| **Key var** | `SAMBANOVA_API_KEY` |

**Models:** `Meta-Llama-3.3-70B-Instruct`, `DeepSeek-R1-Distill-Llama-70B`, `QwQ-32B`

---

### 14. Together AI

| Field | Value |
|---|---|
| **Base URL** | `https://api.together.xyz/v1` |
| **Auth** | API key required |
| **RPM** | 60 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 5 |
| **Free tier** | $5 credit on signup |
| **Key var** | `TOGETHER_API_KEY` |

**Models:** `meta-llama/Llama-3.3-70B-Instruct-Turbo`, `deepseek-ai/DeepSeek-R1`, `Qwen/QwQ-32B-Preview`

---

### 15. LLM7.io

| Field | Value |
|---|---|
| **Base URL** | `https://api.llm7.io/v1` |
| **Auth** | API key required |
| **RPM** | 30 |
| **Capabilities** | Vision, System prompts |
| **Priority** | 7 |
| **Free tier** | ✅ Anonymous tier available |
| **Key var** | `LLM7_API_KEY` |

**Models:** `gpt-4o-mini-2024-07-18`, `deepseek-r1-0528`

---

### 16. Mistral AI

| Field | Value |
|---|---|
| **Base URL** | `https://api.mistral.ai/v1` |
| **Auth** | API key required |
| **RPM / TPD** | 2 / 1B |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 3 |
| **Free tier** | ✅ Experiment tier |
| **Key var** | `MISTRAL_API_KEY` |

**Models:** `mistral-large-latest`, `mistral-small-latest`, `codestral-latest`, `magistral-medium-latest`

---

### 17. xAI / Grok

| Field | Value |
|---|---|
| **Base URL** | `https://api.x.ai/v1` |
| **Auth** | API key required |
| **RPM** | 60 |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 4 |
| **Free tier** | ⚠️ Limited app / paid API |
| **Key var** | `XAI_API_KEY` |

**Models:** `grok-3-beta`, `grok-3-mini-beta`

---

### 18. DeepSeek

| Field | Value |
|---|---|
| **Base URL** | `https://api.deepseek.com` |
| **Auth** | API key required |
| **RPM** | 60 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 2 |
| **Free tier** | ✅ Trial credits (no CC) |
| **Key var** | `DEEPSEEK_API_KEY` |

**Models:** `deepseek-chat`, `deepseek-v4-flash`, `deepseek-reasoner`, `deepseek-v4-pro`

---

### 19. Perplexity

| Field | Value |
|---|---|
| **Base URL** | `https://api.perplexity.ai` |
| **Auth** | API key required |
| **RPM** | 20 |
| **Capabilities** | System prompts, Streaming, Search |
| **Priority** | 5 |
| **Free tier** | ❌ Paid API ($5 for Pro) |
| **Key var** | `PERPLEXITY_API_KEY` |

**Models:** `sonar`, `sonar-pro`, `sonar-reasoning`, `sonar-deep-research`

---

### 20. Fireworks AI

| Field | Value |
|---|---|
| **Base URL** | `https://api.fireworks.ai/inference/v1` |
| **Auth** | API key required |
| **RPM / TPD** | 6,000 / 2.5B |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 4 |
| **Free tier** | ✅ $1 credit on signup |
| **Key var** | `FIREWORKS_API_KEY` |

**Models:** `accounts/fireworks/models/llama-v3p3-70b-instruct`, `accounts/fireworks/models/deepseek-r1-0528`

---

### 21. DeepInfra

| Field | Value |
|---|---|
| **Base URL** | `https://api.deepinfra.com/v1/openai` |
| **Auth** | API key required |
| **RPM** | 12,000 |
| **Capabilities** | Tools, System prompts, Streaming |
| **Priority** | 4 |
| **Free tier** | ✅ Trial credits |
| **Key var** | `DEEPINFRA_API_KEY` |

**Models:** `meta-llama/Llama-3.3-70B-Instruct-Turbo`, `deepseek-ai/DeepSeek-R1`, `Qwen/QwQ-32B`

---

### 22. MiniMax

| Field | Value |
|---|---|
| **Base URL** | `https://api.minimax.chat/v1` |
| **Auth** | API key required |
| **RPM** | 60 |
| **Capabilities** | Vision, Tools, System prompts, Streaming |
| **Priority** | 3 |
| **Note** | ⚠️ No Base64 inline images — image URLs only |
| **Key var** | `MINIMAX_API_KEY` |

**Models:** `MiniMax-Text-01`, `MiniMax-Text-01-Turbo`

---

## Keyless Providers (No API Key Required)

| Provider | Base URL | Notes |
|---|---|---|
| **Pollinations.AI** | `https://gen.pollinations.ai` | Best zero-key option |
| **Ollama** | `http://localhost:11434` | Local; no internet needed |
| **a4f.co** | `https://api.a4f.co/v1` | Limited anonymous tier |
| **LLM7.io** | `https://api.llm7.io/v1` | Anonymous tier available |

---

## Adding a New Provider

To add a new provider, edit `providers/catalogue.py`:

```python
{
    "name":       "myprovider",
    "base_url":   "https://api.myprovider.ai/v1",
    "api_key":    MYPROVIDER_API_KEY,
    "keyless":    False,
    "chat_path":  "/chat/completions",
    "models_path": "/models",
    "extra_headers": {},
    "rpm_limit":  30,
    "rpd_limit":  0,
    "tpd_limit":  0,
    "timeout":    _env_float("MYPROVIDER_TIMEOUT", 60),
    "priority":   5,
    "enabled":    True,
    "capabilities": [
        ProviderCaps.TOOLS,
        ProviderCaps.SYSTEM,
        ProviderCaps.STREAMING,
    ],
    "non_reasoning_models": [
        "my-model-1",
        "my-model-2",
    ],
    "reasoning_models": [
        "my-reasoning-model",
    ],
},
```

Then add the key variable and import to `core/config.py` and `.env.example`.

---

## Circuit Breaker & Rate Limiting

Each provider has its own **circuit breaker** and **rate limiter** defined in:
- `providers/circuit_breaker.py` — failure threshold, reset timeout
- `providers/rate_limiter.py` — sliding-window RPM/RPD enforcement

When a provider's circuit opens, Chimera automatically routes to the next-best provider.