"""
Provider catalogue with live model auto-detection.

Every provider entry has:
  - static fallback lists (non_reasoning_models / reasoning_models)
  - a models_path that is hit on startup and hourly to discover live models

Call refresh_all(http_client) from your lifespan to populate DISCOVERED.
Use effective_models(provider, bucket) everywhere instead of reading
the static lists directly.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

import httpx

from chimera.core.config import (
    A4F_API_KEY,
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    CEREBRAS_API_KEY,
    CF_ACCOUNT_ID,
    CF_API_TOKEN,
    CUSTOM_OPENAI_API_KEY,
    CUSTOM_OPENAI_BASE_URL,
    CUSTOM_OPENAI_MODELS_NR,
    CUSTOM_OPENAI_MODELS_R,
    DEEPINFRA_API_KEY,
    DEEPSEEK_API_KEY,
    FIREWORKS_API_KEY,
    GITHUB_TOKEN,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    HUGGINGFACE_API_KEY,
    LLM7_API_KEY,
    MINIMAX_API_KEY,
    MISTRAL_API_KEY,
    MODEL_REFRESH_INTERVAL_SECS,
    NVIDIA_NIM_API_KEY,
    OLLAMA_BASE_URL,
    OPENROUTER_API_KEY,
    PERPLEXITY_API_KEY,
    POLLINATIONS_API_KEY,
    SAMBANOVA_API_KEY,
    TOGETHER_API_KEY,
    XAI_API_KEY,
    _env_float,
    _env_int,
    _env_list,
)
from chimera.core.logging_setup import logger
from chimera.providers.capabilities import ProviderCaps

# ---------------------------------------------------------------------------
# Static catalogue
# ---------------------------------------------------------------------------
PROVIDER_CATALOGUE: List[Dict[str, Any]] = [

    # 1. Groq
    {
        "name":       "groq",
        "base_url":   "https://api.groq.com/openai/v1",
        "api_key":    GROQ_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  30,
        "rpd_limit":  14400,
        "tpd_limit":  0,
        "timeout":    _env_float("GROQ_TIMEOUT", 30),
        "priority":   1,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        "reasoning_models": [
            "deepseek-r1-distill-70b",
            "qwen-3-32b",
        ],
    },

    # 2. Google AI Studio
    {
        "name":       "google",
        "base_url":   "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key":    GOOGLE_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  15,
        "rpd_limit":  1500,
        "tpd_limit":  0,
        "timeout":    _env_float("GOOGLE_TIMEOUT", 60),
        "priority":   2,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
        ],
        "reasoning_models": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ],
    },

    # 3. OpenRouter
    {
        "name":       "openrouter",
        "base_url":   "https://openrouter.ai/api/v1",
        "api_key":    OPENROUTER_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/chimera-gateway",
            "X-Title":      "Chimera Gateway",
        },
        "rpm_limit":  20,
        "rpd_limit":  200,
        "tpd_limit":  0,
        "timeout":    _env_float("OPENROUTER_TIMEOUT", 60),
        "priority":   3,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-haiku",
            "google/gemini-2.0-flash",
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/devstral",
            "deepseek/deepseek-v3-0324",
            "nvidia/llama-3.3-nemotron-70b-instruct",
            "qwen/qwen3-32b",
        ],
        "reasoning_models": [
            "deepseek/deepseek-r1-0528",
            "deepseek/deepseek-r1",
            "anthropic/claude-sonnet-4",
            "google/gemini-2.5-flash",
            "qwen/qwq-32b",
            "mistralai/mistral-small",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ],
    },

    # 4. Cloudflare Workers AI
    {
        "name":       "cloudflare",
        "base_url":   "https://api.cloudflare.com/client/v4",
        "api_key":    CF_API_TOKEN,
        "keyless":    False,
        "chat_path":  f"/accounts/{CF_ACCOUNT_ID}/ai/run",
        "models_path": f"/accounts/{CF_ACCOUNT_ID}/ai/models/search",
        "extra_headers": {},
        "rpm_limit":  300,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("CF_TIMEOUT", 30),
        "priority":   4,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "@cf/meta/llama-3.1-8b-instruct-fp8",
            "@cf/meta/llama-3.2-11b-vision-instruct",
        ],
        "reasoning_models": [
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
            "@cf/qwen/qwq-32b",
        ],
    },

    # 5. GitHub Models
    {
        "name":       "github",
        "base_url":   "https://models.inference.ai.azure.com",
        "api_key":    GITHUB_TOKEN,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  5,
        "rpd_limit":  50,
        "tpd_limit":  0,
        "timeout":    _env_float("GITHUB_TIMEOUT", 60),
        "priority":   5,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "Llama-3.3-70B-Instruct",
            "gpt-4o-mini",
        ],
        "reasoning_models": [
            "DeepSeek-R1",
            "o1-mini",
        ],
    },

    # 6. NVIDIA NIM
    {
        "name":       "nvidia",
        "base_url":   "https://integrate.api.nvidia.com/v1",
        "api_key":    NVIDIA_NIM_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  40,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("NVIDIA_TIMEOUT", 60),
        "priority":   6,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "mistralai/mistral-7b-instruct-v0.3",
        ],
        "reasoning_models": [
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "deepseek-ai/deepseek-r1",
        ],
    },

    # 7. a4f.co
    {
        "name":       "a4f",
        "base_url":   "https://api.a4f.co/v1",
        "api_key":    A4F_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  20,
        "rpd_limit":  200,
        "tpd_limit":  0,
        "timeout":    _env_float("A4F_TIMEOUT", 60),
        "priority":   7,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "provider-3/gpt-4o-mini",
            "provider-5/llama-3.3-70b",
        ],
        "reasoning_models": [
            "provider-6/deepseek-r1",
        ],
    },

    # 8. Cerebras
    {
        "name":       "cerebras",
        "base_url":   "https://api.cerebras.ai/v1",
        "api_key":    CEREBRAS_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  30,
        "rpd_limit":  14400,
        "tpd_limit":  1_000_000,
        "timeout":    _env_float("CEREBRAS_TIMEOUT", 30),
        "priority":   2,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "llama3.1-8b",
            "qwen-3-235b-a22b-instruct-2507",
        ],
        "reasoning_models": [
            "llama3.1-8b",
            "qwen-3-235b-a22b-instruct-2507",
        ],
    },

    # 9. Pollinations.AI  (keyless)
    {
        "name":       "pollinations",
        "base_url":   "https://gen.pollinations.ai",
        "api_key":    POLLINATIONS_API_KEY,
        "keyless":    True,
        "chat_path":  "/v1/chat/completions",
        "models_path": "/v1/models",
        "extra_headers": {},
        "rpm_limit":  10,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("POLLINATIONS_TIMEOUT", 60),
        "priority":   8,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.SYSTEM,
        ],
        "non_reasoning_models": [
            "openai",
            "mistral",
            "llama",
            "gemini",
        ],
        "reasoning_models": [
            "deepseek-reasoner",
        ],
    },

    # 10. Ollama  (local, keyless)
    {
        "name":       "ollama",
        "base_url":   OLLAMA_BASE_URL,
        "api_key":    "",
        "keyless":    True,
        "chat_path":  "/v1/chat/completions",
        "models_path": "/api/tags",          # Ollama native endpoint
        "extra_headers": {},
        "rpm_limit":  0,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("OLLAMA_TIMEOUT", 120),
        "priority":   99,
        "enabled":    bool(OLLAMA_BASE_URL and OLLAMA_BASE_URL not in ("http://localhost:11434", "http://127.0.0.1:11434")),  # Only enable if custom URL configured
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": _env_list(
            "OLLAMA_NR_MODELS",
            "llama3.2,llama3.2:3b,mistral,phi4,gemma3:12b,qwen2.5:7b,deepseek-r1:7b",
        ),
        "reasoning_models": _env_list(
            "OLLAMA_R_MODELS",
            "deepseek-r1,deepseek-r1:14b,deepseek-r1:32b,qwq,phi4-reasoning",
        ),
    },

    # 11. Custom OpenAI-compatible endpoint
    {
        "name":       "custom",
        "base_url":   CUSTOM_OPENAI_BASE_URL,
        "api_key":    CUSTOM_OPENAI_API_KEY,
        "keyless":    not bool(CUSTOM_OPENAI_API_KEY),
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  _env_int("CUSTOM_OPENAI_RPM", 0),
        "rpd_limit":  _env_int("CUSTOM_OPENAI_RPD", 0),
        "tpd_limit":  _env_int("CUSTOM_OPENAI_TPD", 0),
        "timeout":    _env_float("CUSTOM_OPENAI_TIMEOUT", 120),
        "priority":   _env_int("CUSTOM_OPENAI_PRIORITY", 0),
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
            ProviderCaps.VISION,
        ],
        "non_reasoning_models": CUSTOM_OPENAI_MODELS_NR,
        "reasoning_models":     CUSTOM_OPENAI_MODELS_R,
    },

    # 12. HuggingFace Serverless Inference
    {
        "name":       "huggingface",
        "base_url":   "https://api-inference.huggingface.co/v1",
        "api_key":    HUGGINGFACE_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("HF_TIMEOUT", 60),
        "priority":   6,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
        ],
        "reasoning_models": [
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "meta-llama/Llama-3.3-70B-Instruct",
        ],
    },

    # 13. SambaNova
    {
        "name":       "sambanova",
        "base_url":   "https://api.sambanova.ai/v1",
        "api_key":    SAMBANOVA_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  30,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("SAMBANOVA_TIMEOUT", 30),
        "priority":   2,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
        ],
        "reasoning_models": [
            "DeepSeek-R1-Distill-Llama-70B",
            "QwQ-32B",
        ],
    },

    # 14. Together AI
    {
        "name":       "together",
        "base_url":   "https://api.together.xyz/v1",
        "api_key":    TOGETHER_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("TOGETHER_TIMEOUT", 60),
        "priority":   5,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ],
        "reasoning_models": [
            "deepseek-ai/DeepSeek-R1",
            "Qwen/QwQ-32B-Preview",
        ],
    },

    # 15. LLM7.io  (requires free token from token.llm7.io for higher rate limits)
    {
        "name":       "llm7",
        "base_url":   "https://api.llm7.io/v1",
        "api_key":    LLM7_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  30,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("LLM7_TIMEOUT", 60),
        "priority":   7,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.SYSTEM,
        ],
        "non_reasoning_models": [
            "gpt-4o-mini-2024-07-18",
            "gemini-2.5-flash-lite",
            "qwen2.5-coder-32b-instruct",
        ],
        "reasoning_models": [
            "deepseek-r1-0528",
        ],
    },

    # 16. Mistral AI
    {
        "name":       "mistral",
        "base_url":   "https://api.mistral.ai/v1",
        "api_key":    MISTRAL_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  2,
        "rpd_limit":  0,
        "tpd_limit":  1_000_000_000,
        "timeout":    _env_float("MISTRAL_TIMEOUT", 60),
        "priority":   3,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "codestral-latest",
            "mistral-nemo",
        ],
        "reasoning_models": [
            "magistral-medium-latest",
            "magistral-small-latest",
        ],
    },

    # 17. xAI / Grok
    {
        "name":       "xai",
        "base_url":   "https://api.x.ai/v1",
        "api_key":    XAI_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("XAI_TIMEOUT", 60),
        "priority":   4,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "grok-3-beta",
        ],
        "reasoning_models": [
            "grok-3-mini-beta",
        ],
    },

    # 18. DeepSeek
    {
        "name":       "deepseek",
        "base_url":   "https://api.deepseek.com",
        "api_key":    DEEPSEEK_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("DEEPSEEK_TIMEOUT", 60),
        "priority":   2,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "deepseek-chat",
            "deepseek-v4-flash",
        ],
        "reasoning_models": [
            "deepseek-reasoner",
            "deepseek-v4-pro",
        ],
    },

    # 19. Perplexity
    {
        "name":       "perplexity",
        "base_url":   "https://api.perplexity.ai",
        "api_key":    PERPLEXITY_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  20,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("PERPLEXITY_TIMEOUT", 60),
        "priority":   5,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
            ProviderCaps.SEARCH,
        ],
        "non_reasoning_models": [
            "sonar",
            "sonar-pro",
            "r1-1776",
        ],
        "reasoning_models": [
            "sonar-reasoning",
            "sonar-reasoning-pro",
            "sonar-deep-research",
        ],
    },

    # 20. Fireworks AI
    {
        "name":       "fireworks",
        "base_url":   "https://api.fireworks.ai/inference/v1",
        "api_key":    FIREWORKS_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("FIREWORKS_TIMEOUT", 60),
        "priority":   4,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/qwen2p5-72b-instruct",
        ],
        "reasoning_models": [
            "accounts/fireworks/models/deepseek-r1-0528",
            "accounts/fireworks/models/qwen3-235b-a22b",
        ],
    },

    # 21. DeepInfra
    {
        "name":       "deepinfra",
        "base_url":   "https://api.deepinfra.com/v1/openai",
        "api_key":    DEEPINFRA_API_KEY,
        "keyless":    False,
        "chat_path":  "/chat/completions",
        "models_path": "/models",
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("DEEPINFRA_TIMEOUT", 60),
        "priority":   4,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct",
        ],
        "reasoning_models": [
            "deepseek-ai/DeepSeek-R1",
            "Qwen/QwQ-32B",
        ],
    },

    # 22. MiniMax — supports text, image_url, video_url ONLY.
    #     Base64 inline images are NOT supported (HTTP 400).
    #     audio_url also unsupported. Routers must strip unsupported content.
    {
        "name":       "minimax",
        "base_url":   "https://api.minimax.chat/v1",
        "api_key":    MINIMAX_API_KEY,
        "keyless":    False,
        "chat_path":  "/text/chatcompletion_v2",
        "models_path": "/v1/text/models",   # MiniMax model list endpoint
        "extra_headers": {},
        "rpm_limit":  60,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("MINIMAX_TIMEOUT", 60),
        "priority":   3,
        "enabled":    True,
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "MiniMax-Text-01",
            "MiniMax-Text-01-Turbo",
        ],
        "reasoning_models": [
            "MiniMax-Text-01",
            "MiniMax-Text-01-Turbo",
        ],
    },

    # 23. Anthropic (direct — only enabled when ANTHROPIC_API_KEY is set)
    {
        "name":       "anthropic",
        "base_url":   ANTHROPIC_BASE_URL or "https://api.anthropic.com",
        "api_key":    ANTHROPIC_API_KEY,
        "keyless":    False,
        "chat_path":  "/v1/messages",
        "models_path": "/v1/models",
        "extra_headers": {
            "anthropic-version": "2023-06-01",
        },
        "rpm_limit":  50,
        "rpd_limit":  0,
        "tpd_limit":  0,
        "timeout":    _env_float("ANTHROPIC_TIMEOUT", 120),
        "priority":   0,  # highest priority when configured
        "enabled":    bool(ANTHROPIC_API_KEY),  # only enabled if key is set
        "capabilities": [
            ProviderCaps.VISION,
            ProviderCaps.TOOLS,
            ProviderCaps.SYSTEM,
            ProviderCaps.STREAMING,
        ],
        "non_reasoning_models": [
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20241022",
            "claude-3-7-sonnet-20250514",
            "claude-sonnet-4-7-20250514",
            "claude-opus-4-7-20250514",
        ],
        "reasoning_models": [
            "claude-sonnet-4-7-20250514",
            "claude-opus-4-7-20250514",
        ],
    },
]

# Drop entries with no base_url (unconfigured custom / ollama pointing nowhere)
PROVIDER_CATALOGUE = [
    p for p in PROVIDER_CATALOGUE if p.get("base_url", "").strip()
]

# Runtime enable/disable — mutated by admin API at runtime
PROVIDER_ENABLED: Dict[str, bool] = {
    p["name"]: p.get("enabled", True) for p in PROVIDER_CATALOGUE
}


# ---------------------------------------------------------------------------
# Model classification
# ---------------------------------------------------------------------------

# In catalogue.py — replace _REASONING_RE only:
_REASONING_RE = re.compile(
    r"\b(?:r1|qwq|o1|o3|think|reason|reasoner|cot|magistral"
    r"|deepthink|reasoning|sonar-reason|sonar-deep|reflection)\b",
    re.IGNORECASE,
)

_SKIP_RE = re.compile(
    r"\b(embed|embedding|tts|whisper|dall-e|stable-diffusion|text-to-image"
    r"|image-to-text|rerank|moderat|guard|guard2|xtts|bark|musicgen"
    r"|clip|blip|ocr|asr|stt|speech|orpheus|transcri|zai-glm|glm-4)\b",
    re.IGNORECASE,
)


def _classify(model_id: str) -> Optional[str]:
    """Return 'reasoning', 'non_reasoning', or None (skip this model)."""
    if _SKIP_RE.search(model_id):
        return None
    if _REASONING_RE.search(model_id):
        return "reasoning"
    return "non_reasoning"


# ---------------------------------------------------------------------------
# Live model store
# ---------------------------------------------------------------------------

# {provider_name: {"non_reasoning": [...], "reasoning": [...]}}
try:
    from chimera.providers.auto_models import DISCOVERED  # shared with auto_models
except Exception:
    DISCOVERED: Dict[str, Dict[str, List[str]]] = {}

_REFRESH_LOCK = asyncio.Lock()


def effective_models(provider: Dict[str, Any], bucket: str) -> List[str]:
    """
    Return the live list when available and non-empty.
    Falls back to the static catalogue entry.
    Reads from auto_models.DISCOVERED (the one actually populated at startup).
    """
    try:
        from chimera.providers.auto_models import DISCOVERED as _AM_DISC
        live = _AM_DISC.get(provider["name"], {}).get(bucket, [])
    except Exception:
        live = DISCOVERED.get(provider["name"], {}).get(bucket, [])
    static_key = "reasoning_models" if bucket == "reasoning" else "non_reasoning_models"
    return live if live else provider.get(static_key, [])


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_ids(raw: Any) -> List[str]:
    """
    Extract model IDs from any of the four shapes providers use:
      OpenAI  {"object":"list","data":[{"id":"..."},...]}
      Ollama  {"models":[{"name":"..."},...]}
      CF      {"result":[{"name":"..."},...]}
      Plain   [{"id":"..."},...]
    """
    ids: List[str] = []

    if isinstance(raw, dict):
        for key in ("data", "models", "result"):
            items = raw.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        mid = item.get("id") or item.get("name") or ""
                        if mid:
                            ids.append(str(mid))
                break

    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name") or ""
                if mid:
                    ids.append(str(mid))

    return ids


# ---------------------------------------------------------------------------
# Per-provider fetch
# ---------------------------------------------------------------------------

async def _fetch_one(
    provider: Dict[str, Any],
    client:   httpx.AsyncClient,
) -> Optional[Dict[str, List[str]]]:
    """
    GET models_path, classify results, return bucket dict or None.
    Failures are DEBUG-logged to avoid log spam in production.
    """
    name        = provider["name"]
    models_path = provider.get("models_path", "")

    if not models_path:
        return None
    if not provider.get("keyless") and not provider.get("api_key"):
        return None

    url = provider["base_url"].rstrip("/") + models_path

    hdrs: Dict[str, str] = {}
    if provider.get("api_key"):
        hdrs["Authorization"] = f"Bearer {provider['api_key']}"
    hdrs.update(provider.get("extra_headers", {}))

    try:
        resp = await client.get(url, headers=hdrs, timeout=httpx.Timeout(15.0))
    except Exception as exc:
        logger.debug("auto-model %s: connection error: %s", name, exc)
        return None

    if resp.status_code >= 400:
        logger.debug(
            "auto-model %s: HTTP %d from %s", name, resp.status_code, url
        )
        return None

    try:
        raw = resp.json()
    except Exception as exc:
        logger.debug("auto-model %s: JSON parse error: %s", name, exc)
        return None

    ids = _parse_ids(raw)
    if not ids:
        logger.debug("auto-model %s: empty model list in response", name)
        return None

    result: Dict[str, List[str]] = {"non_reasoning": [], "reasoning": []}
    for mid in ids:
        bucket = _classify(mid)
        if bucket is not None:
            result[bucket].append(mid)

    nr = len(result["non_reasoning"])
    r  = len(result["reasoning"])
    logger.info(
        "auto-model %-15s  %d models  (%d reasoning / %d non-reasoning)",
        name, nr + r, r, nr,
    )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def refresh_all(client: httpx.AsyncClient) -> None:
    """
    Concurrently fetch live model lists from every configured provider.
    Holds _REFRESH_LOCK so back-to-back calls do not race.
    Providers that fail keep their previous (or static) lists.
    """
    async with _REFRESH_LOCK:
        eligible = [
            p for p in PROVIDER_CATALOGUE
            if p.get("models_path") and (p.get("keyless") or p.get("api_key"))
        ]

        results = await asyncio.gather(
            *[_fetch_one(p, client) for p in eligible],
            return_exceptions=True,
        )

        updated = 0
        for provider, result in zip(eligible, results):
            if isinstance(result, Exception):
                logger.debug(
                    "auto-model %s: exception during refresh: %s",
                    provider["name"], result,
                )
            elif isinstance(result, dict) and (
                result["non_reasoning"] or result["reasoning"]
            ):
                DISCOVERED[provider["name"]] = result
                updated += 1

        logger.info(
            "auto-model: refresh done — %d / %d providers updated",
            updated, len(eligible),
        )


async def background_refresher(client: httpx.AsyncClient) -> None:
    """
    Background asyncio task.
    Sleeps MODEL_REFRESH_INTERVAL_SECS (default 3600) between refreshes.
    Cancelled cleanly on gateway shutdown.
    """
    while True:
        await asyncio.sleep(MODEL_REFRESH_INTERVAL_SECS)
        logger.info("auto-model: scheduled refresh starting …")
        await refresh_all(client)