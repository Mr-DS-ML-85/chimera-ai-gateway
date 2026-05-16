from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# from chimera.providers.auto_models import DISCOVERED, effective_models
# from chimera.providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
# from chimera.keys.virtual_keys import allows_model, allows_all, resolve as resolve_vk
# from core.config import CHIMERA_API_KEY
# from chimera.providers.virtual_routes import resolve_virtual_model, RouteSpec
from providers.auto_models import DISCOVERED, effective_models
from providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from keys.virtual_keys import allows_model, allows_all, resolve as resolve_vk
from core.config import CHIMERA_API_KEY
from providers.virtual_routes import resolve_virtual_model, RouteSpec
router = APIRouter()


# --- DEBUG ENDPOINTS ---
@router.get("/debug/discovered")
async def debug_discovered():
    """Temporary debug endpoint to inspect DISCOVERED state."""
    return JSONResponse({
        "DISCOVERED_keys": list(DISCOVERED.keys()),
        "DISCOVERED": dict(DISCOVERED),
    })


async def _light_auth(request) -> Optional[Dict[str, Any]]:
    """Just resolve virtual key — public endpoint if no master key set."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    return await resolve_vk(token)


@router.get("/v1/models")
async def list_models(request: Request):
    vk = await resolve_vk(
        request.headers.get("Authorization", "")[7:]
    ) if request.headers.get("Authorization", "").startswith("Bearer ") else None
    now = int(time.time())
    combined: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for p in PROVIDER_CATALOGUE:
        name = p["name"]

        if not PROVIDER_ENABLED.get(name, True):
            continue

        # Skip providers that need an API key but don't have one.
        # Keyless providers (ollama, pollinations, llm7) are always allowed.
        if not p.get("keyless") and not p.get("api_key"):
            if not vk or not allows_all(vk):
                continue

        source = "live" if name in DISCOVERED else "static"

        for bucket in ("non_reasoning", "reasoning"):
            for m in effective_models(p, bucket):
                if vk and not allows_model(vk, m):
                    continue

                _prefix_stripped = m

                # Case 1: model starts with provider name (live artifact) — strip it,
                #   then recursively strip any org/model nesting from the remainder
                #   (e.g. "groq/qwen/qwen3-32b" → "qwen3-32b" after stripping "groq/"
                #   and then "qwen/" from "qwen/qwen3-32b").
                # Case 1b: model starts with provider + org (static catalogue with
                #   nested IDs) — strip provider, then recursively strip orgs
                #   (e.g. "meta-llama/llama-4-scout" in groq static catalogue →
                #   "groq/meta-llama/llama-4-scout" → strip groq/ → "llama-4-scout").
                # Case 2: Cloudflare "@cf/" prefix → strip "@cf/" from raw model.
                # Case 3: NVIDIA nested org path → strip known ORG prefixes.
                # OpenRouter: use model IDs as-is (their paths are intentional).
                if m.startswith(f"{name}/"):
                    remainder = m[len(name) + 1:]
                    # Recursively strip any org/model nesting from the remainder
                    while True:
                        stripped_again = False
                        for _org in ("qwen", "openai", "anthropic", "meta-llama",
                                      "deepseek", "google", "mistralai", "cohere",
                                      "microsoft", "nvidia", "01-ai", "baai",
                                      "bytedance", "ibm", "moonshotai", "z-ai"):
                            if remainder.startswith(f"{_org}/"):
                                remainder = remainder[len(_org) + 1:]
                                stripped_again = True
                                break
                        if not stripped_again:
                            break
                    _prefix_stripped = remainder if remainder else m

                elif m.startswith("@cf/"):
                    remainder = m[4:]
                    # Recursively strip org nesting after @cf/ (e.g. "@cf/qwen/qwq-32b" → "qwq-32b")
                    while True:
                        stripped_again = False
                        for _org in ("qwen", "deepseek-ai", "google", "mistralai", "meta", "openai"):
                            if remainder.startswith(f"{_org}/"):
                                remainder = remainder[len(_org) + 1:]
                                stripped_again = True
                                break
                        if not stripped_again:
                            break
                    _prefix_stripped = remainder if remainder else m
                elif name == "nvidia":
                    _NVIDIA_ORG_PREFIXES = {
                        "meta", "mistralai", "nvidia", "deepseek-ai", "qwen",
                        "01-ai", "abacusai", "adept", "ai21labs", "aisingapore",
                        "alibaba", "baai", "bigcode", "bytedance", "cohere",
                        "databricks", "google", "ibm", "microsoft", "minimaxai",
                        "moonshotai", "nv-mistralai", "openchat", "openai",
                        "presto", "recurshy", "sambaNova", "snorkel", "stabilityai",
                        "tiiuae", "togetherai", "upstage", "writer", "z-ai",
                        "zhipuai", "sarvamai", "stepfun-ai", "stockmark", "zyphra",
                    }
                    first = m.split("/")[0]
                    if first in _NVIDIA_ORG_PREFIXES:
                        rest = "/".join(m.split("/")[1:])
                        if rest:
                            _prefix_stripped = rest
                else:
                    # Case 4: bare model ID with no provider prefix — strip any org nesting.
                    # e.g. "openai/gpt-oss-120b" from Groq API → "gpt-oss-120b"
                    # e.g. "qwen/qwq-32b" from Groq API → "qwq-32b"
                    # OpenRouter model IDs are returned as-is (their paths are intentional).
                    if name != "openrouter":
                        _remainder = m
                        while True:
                            _stripped = False
                            for _org in ("qwen", "openai", "anthropic", "meta-llama",
                                          "deepseek", "google", "mistralai", "cohere",
                                          "microsoft", "nvidia", "01-ai", "baai",
                                          "bytedance", "ibm", "moonshotai", "z-ai"):
                                if _remainder.startswith(f"{_org}/"):
                                    _remainder = _remainder[len(_org) + 1:]
                                    _stripped = True
                                    break
                            if not _stripped:
                                break
                        _prefix_stripped = _remainder if _remainder else m

                prefixed = f"{name}/{_prefix_stripped}"
                if prefixed in seen:
                    continue
                seen.add(prefixed)
                combined.append({
                    "id":       prefixed,
                    "object":   "model",
                    "created":  now,
                    "owned_by": name,
                    "provider": name,
                    "type":     bucket,
                    "source":   source,
                })

    # ── Auto / OpenRouter virtual model aliases ───────────────────────────────
    # These allow Open WebUI to list auto/fast/quality/reasoning routing targets.
    # They are virtual (not backed by a specific provider model) but show up in
    # the /v1/models list so Open WebUI can offer them as options.
    virtual_buckets = [
        ("auto",               "auto",               "non_reasoning", False),
        ("auto:free",          "auto:free",           "non_reasoning", True),
        ("auto:reasoning",     "auto:reasoning",      "reasoning",     False),
        ("auto:non-reasoning", "auto:non-reasoning",  "non_reasoning", False),
        ("auto:free:reasoning",      "auto:free:reasoning",      "reasoning",     True),
        ("auto:free:non-reasoning", "auto:free:non-reasoning",  "non_reasoning", True),
        ("fast",               "fast",                "non_reasoning", False),
        ("fast:free",          "fast:free",            "non_reasoning", True),
        ("quality",            "quality",              "non_reasoning", False),
        ("balanced",          "balanced",             "non_reasoning", False),
        ("reasoning",          "reasoning",            "reasoning",     False),
        ("reasoning:free",     "reasoning:free",       "reasoning",     True),
        ("non-reasoning",      "non-reasoning",        "non_reasoning", False),
        ("non-reasoning:free", "non-reasoning:free",   "non_reasoning", True),
    ]
    for short_id, full_id, bucket, free_only in virtual_buckets:
        prefixed = f"auto/{short_id}"
        if prefixed in seen:
            continue
        seen.add(prefixed)
        combined.append({
            "id":       prefixed,
            "object":   "model",
            "created":  now,
            "owned_by": "gateway",
            "provider": "auto",
            "type":     bucket,
            "source":   "virtual",
        })

    # ── Per-provider virtual routing models (provider-prefixed) ──────────────
    # Example: "openrouter/auto" → auto routing through OpenRouter.
    # This lets Open WebUI connect to the gateway with a specific provider prefix
    # and still benefit from virtual routing.
    for p in PROVIDER_CATALOGUE:
        name = p["name"]
        if not PROVIDER_ENABLED.get(name, True):
            continue
        if not p.get("keyless") and not p.get("api_key"):
            continue
        for short_id, full_id, bucket, free_only in virtual_buckets:
            prefixed = f"{name}/{short_id}"
            if prefixed in seen:
                continue
            seen.add(prefixed)
            combined.append({
                "id":       prefixed,
                "object":   "model",
                "created":  now,
                "owned_by": name,
                "provider": name,
                "type":     bucket,
                "source":   "virtual",
            })

    return JSONResponse({"object": "list", "data": combined, "total": len(combined)})