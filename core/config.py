"""
Central configuration — every module imports from here.
All values are read from environment variables / .env once at import time.
"""
from __future__ import annotations

import os
from typing import List, Set

from dotenv import load_dotenv
_env = os.environ

# Load .env from the project root (one level up from core/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"))
STRICT_SUPPLY_CHAIN = os.environ.get("STRICT_SUPPLY_CHAIN", "0").lower() in ("1", "true", "yes")

SUPPLY_CHAIN_MANIFEST = os.environ.get("SUPPLY_CHAIN_MANIFEST", os.path.join(_ROOT, "requirements.txt"))

# ── helpers ───────────────────────────────────────────────────────────────
def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_list(key: str, default: str = "") -> List[str]:
    return [x.strip() for x in _env(key, default).split(",") if x.strip()]


# ── Provider API keys ──────────────────────────────────────────────────────
GROQ_API_KEY         = _env("GROQ_API_KEY")
GOOGLE_API_KEY       = _env("GOOGLE_API_KEY")
OPENROUTER_API_KEY   = _env("OPENROUTER_API_KEY")
CF_ACCOUNT_ID        = _env("CF_ACCOUNT_ID")
CF_API_TOKEN         = _env("CF_API_TOKEN")
GITHUB_TOKEN         = _env("GITHUB_TOKEN")
NVIDIA_NIM_API_KEY   = _env("NVIDIA_NIM_API_KEY")
A4F_API_KEY          = _env("A4F_API_KEY")
CEREBRAS_API_KEY     = _env("CEREBRAS_API_KEY")
POLLINATIONS_API_KEY = _env("POLLINATIONS_API_KEY")
HUGGINGFACE_API_KEY  = _env("HUGGINGFACE_API_KEY")
SAMBANOVA_API_KEY    = _env("SAMBANOVA_API_KEY")
TOGETHER_API_KEY     = _env("TOGETHER_API_KEY")
LLM7_API_KEY         = _env("LLM7_API_KEY")
MISTRAL_API_KEY      = _env("MISTRAL_API_KEY")
XAI_API_KEY          = _env("XAI_API_KEY")
DEEPSEEK_API_KEY     = _env("DEEPSEEK_API_KEY")
PERPLEXITY_API_KEY   = _env("PERPLEXITY_API_KEY")
FIREWORKS_API_KEY    = _env("FIREWORKS_API_KEY")
DEEPINFRA_API_KEY    = _env("DEEPINFRA_API_KEY")

OLLAMA_BASE_URL         = _env("OLLAMA_BASE_URL", "http://localhost:11434")
CUSTOM_OPENAI_BASE_URL  = _env("CUSTOM_OPENAI_BASE_URL")
CUSTOM_OPENAI_API_KEY   = _env("CUSTOM_OPENAI_API_KEY")
CUSTOM_OPENAI_MODELS_NR = _env_list("CUSTOM_OPENAI_MODELS_NR", "custom-model")
CUSTOM_OPENAI_MODELS_R  = _env_list("CUSTOM_OPENAI_MODELS_R",  "custom-model")

# ── Gateway ────────────────────────────────────────────────────────────────
CHIMERA_API_KEY    = _env("CHIMERA_API_KEY")
ADMIN_API_KEY      = _env("ADMIN_API_KEY")
ROUTE_BY           = _env("ROUTE_BY", "quality").lower()
GATEWAY_VERSION    = _env("GATEWAY_VERSION", "8.2.0")
WAF_RULE_VERSION   = _env("WAF_RULE_VERSION", "1.0.0")

# ── Security ───────────────────────────────────────────────────────────────
TRUSTED_PROXIES:        Set[str] = set(_env_list("TRUSTED_PROXIES", ""))
CORS_ORIGINS_RAW:       List[str] = _env_list("CORS_ORIGINS", "")
JWKS_URI               = _env("JWKS_URI")
JWT_AUDIENCE           = _env("JWT_AUDIENCE")
JWT_ISSUER             = _env("JWT_ISSUER")
REDIS_URL              = _env("REDIS_URL", "redis://localhost:6379")
ENABLE_WAF             = _env("ENABLE_WAF", "1").lower() not in ("0", "false", "no")
ENABLE_CONTENT_POLICY  = _env("ENABLE_CONTENT_POLICY", "1").lower() not in ("0", "false", "no")
ENABLE_PII_REDACTION   = _env("ENABLE_PII_REDACTION", "1").lower() not in ("0", "false", "no")
VIRTUAL_KEYS_FILE      = _env("VIRTUAL_KEYS_FILE",
                               os.path.join(_ROOT, "virtual_keys.json"))

# ── Limits ─────────────────────────────────────────────────────────────────
MAX_BODY_BYTES              = _env_int("MAX_BODY_BYTES", 512_000)
REQUEST_TIMEOUT_SECS        = _env_float("REQUEST_TIMEOUT", 120.0)
IP_RATE_LIMIT_RPM           = _env_int("IP_RATE_LIMIT_RPM", 60)
USER_RATE_LIMIT_RPM         = _env_int("USER_RATE_LIMIT_RPM", 120)
TRANSPARENCY_LOG_CAP        = _env_int("TRANSPARENCY_LOG_CAP", 10_000)
MODEL_REFRESH_INTERVAL_SECS = _env_int("MODEL_REFRESH_INTERVAL", 3600)
HTTP_MAX_CONNECTIONS        = _env_int("HTTP_MAX_CONNECTIONS", 100)
HTTP_MAX_KEEPALIVE          = _env_int("HTTP_MAX_KEEPALIVE", 20)
HTTP_CONNECT_TIMEOUT        = _env_float("HTTP_CONNECT_TIMEOUT", 10.0)

# ── Runtime ────────────────────────────────────────────────────────────────
IS_DEV   = _env("DEV", "").lower() in ("1", "true", "yes")
HOST     = _env("HOST", "0.0.0.0")
PORT     = _env_int("PORT", 8000)
WORKERS  = _env_int("WORKERS", 1)


def validate() -> list[str]:
    """Return list of fatal config errors (empty = OK)."""
    errors: list[str] = []
    if ROUTE_BY not in ("quality", "latency", "random"):
        errors.append(f"ROUTE_BY='{ROUTE_BY}' must be quality|latency|random")
    if MAX_BODY_BYTES < 1024:
        errors.append(f"MAX_BODY_BYTES={MAX_BODY_BYTES} too small (min 1024)")
    if CHIMERA_API_KEY and len(CHIMERA_API_KEY) < 32:
        errors.append(f"CHIMERA_API_KEY too short ({len(CHIMERA_API_KEY)} chars, need 32+)")
    if ADMIN_API_KEY and len(ADMIN_API_KEY) < 32:
        errors.append(f"ADMIN_API_KEY too short ({len(ADMIN_API_KEY)} chars, need 32+)")
    # ── CORS wildcard is only fatal in production, not dev ──────────────────
    if "*" in CORS_ORIGINS_RAW and not IS_DEV:
        errors.append(
            "CORS_ORIGINS=* is not allowed in production — "
            "set explicit origins e.g. CORS_ORIGINS=https://yourdomain.com"
        )
    return errors