from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from chimera.core.config import ROUTE_BY
from chimera.core.logging_setup import logger
from chimera.providers.auto_models import effective_models
from chimera.providers.capabilities import ProviderCaps
from chimera.providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from chimera.providers.rate_limiter import rate_limiter
from chimera.security.ssrf import assert_safe

from chimera.providers.virtual_routes import RouteSpec

# Shared HTTP client — set by lifespan in api/app.py
_http_client: Optional[httpx.AsyncClient] = None


def set_http_client(client: httpx.AsyncClient) -> None:
    global _http_client
    _http_client = client


def get_http_client() -> httpx.AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client not initialised")
    return _http_client


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _provider_is_free(provider: Dict[str, Any]) -> bool:
    return bool(
        provider.get("free_tier")
        or provider.get("free")
        or provider.get("keyless")
    )


def _extract_texts(body: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for msg in body.get("messages", []):
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
                    url = part.get("image_url")
                    if isinstance(url, dict):
                        u = url.get("url")
                        if isinstance(u, str):
                            chunks.append(u)
    return " ".join(chunks)


def infer_reasoning(body: Dict[str, Any]) -> bool:
    text = f"{body.get('model', '')} {_extract_texts(body)}".lower()
    return any(
        kw in text
        for kw in (
            "reason",
            "think",
            "qwq",
            "r1",
            "o1",
            "o3",
            "magistral",
            "cot",
            "deepthink",
            "reflection",
        )
    )


def needs_vision(body: Dict[str, Any]) -> bool:
    for msg in body.get("messages", []):
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            if any(
                isinstance(p, dict) and p.get("type") == "image_url"
                for p in msg["content"]
            ):
                return True
    return False


def needs_tools(body: Dict[str, Any]) -> bool:
    return bool(body.get("tools") or body.get("functions"))


def needs_search(body: Dict[str, Any]) -> bool:
    return bool(body.get("web_search") or body.get("search_context_size"))


# ──────────────────────────────────────────────────────────────────────────────
# Ordering
# ──────────────────────────────────────────────────────────────────────────────

async def sorted_pairs(
    pairs: List[Tuple[Dict[str, Any], List[str]]],
    route: Optional[RouteSpec] = None,
) -> List[Tuple[Dict[str, Any], List[str]]]:
    if not pairs:
        return []

    preferred = list(route.preferred_providers) if route else []

    def preferred_rank(name: str) -> int:
        if not preferred:
            return 0
        try:
            return preferred.index(name)
        except ValueError:
            return 999

    if ROUTE_BY == "latency":
        lats = {
            p["name"]: await rate_limiter.get_ema_latency(p["name"])
            for p, _ in pairs
        }
        return sorted(
            pairs,
            key=lambda t: (preferred_rank(t[0]["name"]), lats.get(t[0]["name"], 0.0)),
        )

    if ROUTE_BY == "random":
        shuffled = list(pairs)
        random.shuffle(shuffled)
        return sorted(shuffled, key=lambda t: preferred_rank(t[0]["name"]))

    # Default: priority
    return sorted(
        pairs,
        key=lambda t: (preferred_rank(t[0]["name"]), t[0].get("priority", 99)),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Capability helpers
# ──────────────────────────────────────────────────────────────────────────────

def _infer_provider_affinity(model_id: str) -> Optional[str]:
    """Return provider name inferred from model ID naming convention."""
    # Strip provider prefix if present
    m = model_id
    if model_id:
        parts = model_id.split("/")
        if parts[0] in {
            "openrouter", "nvidia", "groq", "google", "cloudflare",
            "github", "a4f", "cerebras", "pollinations", "ollama",
            "custom", "huggingface", "sambanova", "together", "llm7",
            "mistral", "xai", "deepseek", "perplexity", "fireworks", "deepinfra",
        }:
            m = "/".join(parts[1:])

    if m.startswith("@cf/"):
        return "cloudflare"
    if m.startswith("accounts/fireworks/"):
        return "fireworks"
    _OPENROUTER_ORGS = (
        "meta-llama/", "google/", "mistralai/", "nvidia/",
        "deepseek/", "qwen/", "arcee-ai/", "microsoft/",
        "openai/", "nousresearch/", "cognitivecomputations/",
    )
    if "/" in m and any(m.startswith(o) for o in _OPENROUTER_ORGS):
        return "openrouter"
    return None


def eligible_pairs(
    body: Dict[str, Any],
    vk_record: Optional[Dict[str, Any]] = None,
    route: Optional[RouteSpec] = None,
) -> List[Tuple[Dict[str, Any], List[str]]]:
    bucket = route.bucket if route else ("reasoning" if infer_reasoning(body) else "non_reasoning")
    need_vis = needs_vision(body)
    need_tool = needs_tools(body)
    need_srch = needs_search(body)

    pairs: List[Tuple[Dict[str, Any], List[str]]] = []

    for provider in PROVIDER_CATALOGUE:
        name = provider["name"]

        if not PROVIDER_ENABLED.get(name, True):
            continue

        if not provider.get("keyless") and not provider.get("api_key"):
            continue

        if route and route.free_only and not _provider_is_free(provider):
            continue

        if vk_record:
            allowed_p = vk_record.get("allowed_providers", [])
            if allowed_p and "*" not in allowed_p and name not in allowed_p:
                continue

        caps = provider.get("capabilities", [])
        if need_vis and ProviderCaps.VISION not in caps:
            continue
        if need_tool and ProviderCaps.TOOLS not in caps:
            continue
        if need_srch and ProviderCaps.SEARCH not in caps:
            continue

        # For virtual routes, use the resolved bucket directly.
        # For direct model requests, search BOTH buckets so a model that lives
        # only in reasoning_models is still reachable when infer_reasoning()
        # returns False (e.g. "llama3.3-70b" sent explicitly to Cerebras).
        direct_model = body.get("model", "").strip() if route is None else ""

        # Strip provider prefix if present (e.g. "openrouter/meta-llama/..." → "meta-llama/...")
        raw_model = direct_model
        if direct_model and "/" in direct_model:
            parts = direct_model.split("/")
            if parts[0] in {p["name"] for p in PROVIDER_CATALOGUE}:
                raw_model = "/".join(parts[1:])

        if route is not None or not direct_model:
            models = effective_models(provider, bucket)
        else:
            nr = effective_models(provider, "non_reasoning")
            r  = effective_models(provider, "reasoning")
            # Check both the raw model and the prefixed model
            if raw_model in nr or direct_model in nr:
                models = [raw_model]
            elif raw_model in r or direct_model in r:
                models = [raw_model]
            else:
                models = []  # provider doesn't own this model — skip cleanly

        # Remove session-quarantined models (e.g. model_terms_required)
        quarantined = body.get("_quarantined", set())
        if quarantined:
            models = [m for m in models if m not in quarantined]

        if vk_record:
            allowed_m = vk_record.get("allowed_models", [])
            if allowed_m and "*" not in allowed_m:
                models = [m for m in models if m in allowed_m]

        if models:
            pairs.append((provider, models))

    # ── Provider-affinity fallback ──────────────────────────────
    # If no provider claimed the model, infer owner from model ID
    # and give that provider one direct attempt.
    if not pairs and direct_model:
        affinity = _infer_provider_affinity(direct_model)
        if affinity:
            for _p in PROVIDER_CATALOGUE:
                if _p["name"] != affinity:
                    continue
                if not PROVIDER_ENABLED.get(affinity, True):
                    break
                if not _p.get("keyless") and not _p.get("api_key"):
                    break
                if route and route.free_only and not _provider_is_free(_p):
                    break
                _caps = _p.get("capabilities", [])
                if need_vis  and ProviderCaps.VISION  not in _caps: break
                if need_tool and ProviderCaps.TOOLS   not in _caps: break
                if need_srch and ProviderCaps.SEARCH  not in _caps: break
                pairs.append((_p, [direct_model]))
                logger.debug("affinity fallback: '%s' → %s", direct_model, affinity)
                break

    return pairs


def select_model_for_provider(
    provider: Dict[str, Any],
    model_list: List[str],
    requested_model: str,
    route: Optional[RouteSpec] = None,
) -> Optional[str]:
    """
    For virtual models, use the provider's best model for the chosen bucket.
      - fast/auto mode → pick first model (lowest latency)
      - quality mode   → pick last model (highest quality — pro, 70b, etc.)
    For direct models, require that the exact model (or prefixed version) exists.
    Returns the canonical (unprefixed) model name to send upstream.
    """
    if not model_list:
        return None

    if route is not None:
        if route.mode and route.mode.startswith("quality"):
            return model_list[-1]
        return model_list[0]

    # Strip provider prefix from requested_model
    raw_requested = requested_model
    if requested_model and "/" in requested_model:
        parts = requested_model.split("/")
        if parts[0] in {p["name"] for p in PROVIDER_CATALOGUE}:
            raw_requested = "/".join(parts[1:])

    if raw_requested and raw_requested in model_list:
        return raw_requested

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Provider HTTP call
# ──────────────────────────────────────────────────────────────────────────────

async def call_provider(
    provider: Dict[str, Any],
    model: str,
    body: Dict[str, Any],
    stream: bool,
    request_id: str,
) -> Tuple[Optional[Any], int, Optional[str]]:
    name = provider["name"]

    # ── Virtual routing: resolve "auto/X" model to actual provider routing ───
    # Allows callers to use "auto/auto", "auto/fast", "auto/quality" etc.
    # by stripping the "auto/" prefix and re-invoking virtual route resolution.
    upstream_model = model
    if model.startswith("auto/"):
        virt_id = model[5:]  # e.g. "auto/fast" → "fast"
        from chimera.providers.virtual_routes import resolve_virtual_model
        inner_route = resolve_virtual_model(
            virt_id,
            reasoning_hint=infer_reasoning(body),
        )
        if inner_route:
            # Re-invoke routing with the inner virtual spec so the same
            # provider-chain logic (free_only, bucket, preferred_providers) is
            # applied to the current provider.
            body = dict(body)
            body["_route_mode"] = inner_route.mode
            if inner_route.free_only:
                body["_free_only"] = True
            body["_quarantined"] = set()
            pairs = eligible_pairs(body, vk_record=None, route=inner_route)
            if pairs:
                ordered = sorted(
                    [(p, ml) for p, ml in pairs if p["name"] == name],
                    key=lambda t: t[0].get("priority", 99),
                )
                if ordered:
                    selected = select_model_for_provider(
                        provider=name,
                        model_list=ordered[0][1],
                        requested_model=virt_id,
                        route=inner_route,
                    )
                    if selected:
                        upstream_model = selected

    # Strip provider prefix from model ID before sending to upstream.
    # e.g. "openrouter/meta-llama/llama-4-scout" → "meta-llama/llama-4-scout"
    # e.g. "nvidia/deepseek-ai/deepseek-r1" → "deepseek-ai/deepseek-r1"
    if "/" in upstream_model:
        prefix = upstream_model.split("/")[0]
        # Only strip if the prefix matches a known provider name
        if prefix in {p["name"] for p in PROVIDER_CATALOGUE}:
            upstream_model = "/".join(upstream_model.split("/")[1:])

    # Strip :free suffix from OpenRouter free-tier model IDs.
    # OpenRouter API rejects the :free suffix in the model field —
    # free models are automatically selected based on the API key / account tier.
    if name == "openrouter" and upstream_model.endswith(":free"):
        upstream_model = upstream_model[:-5]

    # MiniMax: strip base64 inline images (not supported — causes HTTP 400).
    # MiniMax only supports: text, image_url (URL), video_url.
    payload = dict(body)
    payload["model"] = upstream_model
    if name == "minimax":
        for msg in payload.get("messages", []):
            content = msg.get("content")
            if isinstance(content, list):
                msg["content"] = [
                    part for part in content
                    if not (
                        isinstance(part, dict)
                        and part.get("type") == "image_url"
                        and isinstance(part.get("url"), str)
                        and part["url"].startswith("data:")
                    )
                ]

    if provider.get("name") == "cloudflare":
        url = provider["base_url"].rstrip("/") + provider["chat_path"] + "/" + upstream_model
    else:
        url = provider["base_url"].rstrip("/") + provider["chat_path"]

    assert_safe(url, name)

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
        **provider.get("extra_headers", {}),
    }
    if provider.get("api_key"):
        headers["Authorization"] = f"Bearer {provider['api_key']}"

    for field in ("reasoning", "encrypt", "_route_mode", "_free_only", "_quarantined"):
        payload.pop(field, None)

    client = get_http_client()
    timeout = httpx.Timeout(provider.get("timeout", 60.0))

    for attempt in range(3):
        if attempt:
            await asyncio.sleep(2 ** attempt)

        try:
            t0 = time.perf_counter()

            if stream:
                req = client.build_request("POST", url, json=payload, headers=headers)
                resp = await client.send(req, stream=True)
            else:
                resp = await client.post(url, json=payload, headers=headers, timeout=timeout)

            latency = (time.perf_counter() - t0) * 1000

            if resp.status_code == 429:
                # On 429: bail out immediately, do not retry.
                # Retrying burns more quota from the same RPM window.
                await rate_limiter.record_rate_limited(name)
                return None, 429, "Rate limited by " + name

            if resp.status_code in (402, 403):
                await rate_limiter.record_failure(name, until_tomorrow=True)
                return None, resp.status_code, f"Auth/quota error {resp.status_code}"

            if resp.status_code >= 500:
                await rate_limiter.record_failure(name)
                if attempt < 2:
                    continue
                return None, resp.status_code, f"Server error {resp.status_code}"

            tokens = 0
            if not stream:
                try:
                    data = resp.json()
                    usage = data.get("usage", {})
                    tokens = (
                        usage.get("total_tokens")
                        or usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                    )
                except Exception:
                    tokens = 0

            await rate_limiter.record_success(name, tokens, latency)
            logger.info(
                "provider=%s model=%s latency_ms=%.0f tokens=%d rid=%s",
                name,
                model,
                latency,
                tokens,
                request_id,
            )
            return resp, resp.status_code, None

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            await rate_limiter.record_failure(name)
            if attempt == 2:
                return None, 0, str(exc)

    return None, 0, "All retry attempts failed"