from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from core.config import MODEL_REFRESH_INTERVAL_SECS
from core.logging_setup import logger
from providers.catalogue import PROVIDER_CATALOGUE

# ── NEW: set DISABLE_MODEL_REFRESH=1 in .env to skip live model discovery. ──
# This is the recommended setting for local stacks — it keeps the model list
# to only what is declared in the static catalogue (a handful of known-good
# models per provider) instead of 300+ live models from OpenRouter etc. which
# confuse Open WebUI and cause false-positive "Compatibility Error" warnings.
DISABLE_MODEL_REFRESH: bool = os.getenv("DISABLE_MODEL_REFRESH", "0").lower() in (
    "1", "true", "yes"
)

_REASONING_RE = re.compile(
    r"\b(r1|qwq|o1|o3|think|reason|cot|magistral|deepthink|reasoning"
    r"|sonar-reason|sonar-deep|reflection)\b",
    re.IGNORECASE,
)
_BLACKLIST_RE = re.compile(
    r"\b(embed|embedding|tts|whisper|dall-e|stable-diffusion|text-to-image"
    r"|image-to-text|rerank|moderat|guard|guard2|xtts|bark|musicgen"
    r"|clip|blip|ocr|asr|stt|orpheus|transcri|zai-glm|glm-4)\b",
    re.IGNORECASE,
)

# Populated during startup / background refresh
DISCOVERED: Dict[str, Dict[str, List[str]]] = {}
_LOCK = asyncio.Lock()


def classify(model_id: str) -> Optional[str]:
    if _BLACKLIST_RE.search(model_id):
        return None
    if _REASONING_RE.search(model_id):
        return "reasoning"
    return "non_reasoning"


def effective_models(provider: Dict[str, Any], bucket: str) -> List[str]:
    live = DISCOVERED.get(provider["name"], {}).get(bucket, [])
    static_key = "reasoning_models" if bucket == "reasoning" else "non_reasoning_models"
    return live if live else provider.get(static_key, [])


async def _fetch_one(
    provider: Dict[str, Any], client: httpx.AsyncClient
) -> Optional[Dict[str, List[str]]]:
    name        = provider["name"]
    models_path = provider.get("models_path", "")
    if not models_path:
        return None

    url  = provider["base_url"].rstrip("/") + models_path
    hdrs: Dict[str, str] = {}
    if provider.get("api_key"):
        hdrs["Authorization"] = f"Bearer {provider['api_key']}"
    hdrs.update(provider.get("extra_headers", {}))

    try:
        resp = await client.get(url, headers=hdrs, timeout=httpx.Timeout(15.0))
        if resp.status_code >= 400:
            return None
        raw = resp.json()
    except Exception as exc:
        logger.debug("auto-model %s: %s", name, exc)
        return None

    ids: List[str] = []
    if isinstance(raw, dict):
        for key in ("data", "models", "result"):
            if key in raw and isinstance(raw[key], list):
                for item in raw[key]:
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

    # Drop azureml:// registry URIs — unusable as chat model names
    ids = [i for i in ids if not i.startswith("azureml://")]
    # Strip Google "models/" prefix so names match what chat API accepts
    ids = [i[len("models/"):] if i.startswith("models/") else i for i in ids]
    if not ids:
        return None

    result: Dict[str, List[str]] = {"non_reasoning": [], "reasoning": []}
    for mid in ids:
        bucket = classify(mid)
        if bucket is not None:
            result[bucket].append(mid)

    logger.info(
        "auto-model %-15s found %d models (%d reasoning, %d non-reasoning)",
        name,
        len(result["non_reasoning"]) + len(result["reasoning"]),
        len(result["reasoning"]),
        len(result["non_reasoning"]),
    )
    return result


async def refresh_all(client: httpx.AsyncClient) -> None:
    if DISABLE_MODEL_REFRESH:
        logger.info(
            "auto-model: discovery disabled (DISABLE_MODEL_REFRESH=1) — "
            "using static catalogue only"
        )
        return
    async with _LOCK:
        provs = {
            p["name"]: p
            for p in PROVIDER_CATALOGUE
            if (p["keyless"] or p["api_key"]) and p.get("models_path")
        }
        results = await asyncio.gather(
            *[_fetch_one(p, client) for p in provs.values()],
            return_exceptions=True,
        )
        for name, result in zip(provs.keys(), results):
            if isinstance(result, dict) and result:
                DISCOVERED[name] = result


async def background_refresher(client: httpx.AsyncClient) -> None:
    if DISABLE_MODEL_REFRESH:
        return  # nothing to do
    while True:
        await asyncio.sleep(MODEL_REFRESH_INTERVAL_SECS)
        logger.info("auto-model: background refresh started")
        await refresh_all(client)
        logger.info("auto-model: background refresh complete")