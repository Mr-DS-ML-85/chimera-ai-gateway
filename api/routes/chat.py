from __future__ import annotations

import base64
import json
from dataclasses import replace
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from uuid import uuid4

import hmac as _hmac
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from chimera.api.middleware import client_ip
from chimera.core.config import GATEWAY_VERSION, MAX_BODY_BYTES, WAF_RULE_VERSION, CHIMERA_API_KEY, JWKS_URI
from chimera.core.logging_setup import logger
from chimera.cost.tracker import record as record_cost
from chimera.crypto.e2ee import encrypt as e2ee_encrypt
from chimera.providers.router import call_provider, eligible_pairs, select_model_for_provider, sorted_pairs, infer_reasoning
from chimera.providers.rate_limiter import rate_limiter
from chimera.security import canary, nonce
from chimera.security.content_policy import scan as policy_scan
from chimera.security.output_guard import screen_json, screen_text
from chimera.security.pii import redact as pii_redact
from chimera.security.pii import redact_response
from chimera.security.waf import extract_text_content, scan_body as waf_scan_body
from chimera.security.prompt_shield import scan_body as shield_scan_body
from chimera.transparency.log import append as log_append
from chimera.providers.virtual_routes import resolve_virtual_model, RouteSpec
from chimera.keys.virtual_keys import allows_model, rpm_ok, resolve_vk

# Runtime quarantine — models that returned model_terms_required are
# excluded for the lifetime of this process without a restart.
_QUARANTINED_MODELS: set[str] = set()

router = APIRouter()


# ── Auth ──────────────────────────────────────────────────────────────────────

async def _authenticate(
    request: Request,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Returns (jwt_payload|None, vk_record|None)."""
    from chimera.api.routes.admin import _validate_jwt  # avoid circular at module level

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        if CHIMERA_API_KEY:
            raise HTTPException(401, "Missing Authorization header")
        return None, None

    token = auth[len("Bearer "):]

    # 1. JWT
    if JWKS_URI:
        from chimera.providers.router import get_http_client
        payload = await _validate_jwt(token, get_http_client())
        if payload is None:
            raise HTTPException(401, "Invalid JWT")
        return payload, None

    # 2. Virtual key
    vk = await resolve_vk(token)
    if vk is not None:
        if not await rpm_ok(vk["key_id"], vk.get("rpm_limit", 0)):
            raise HTTPException(429, f"Rate limit exceeded for key '{vk['key_id']}'")
        return None, vk

    # 3. Master key
    if CHIMERA_API_KEY:
        if not _hmac.compare_digest(token.encode(), CHIMERA_API_KEY.encode()):
            raise HTTPException(403, "Invalid API key")
    return None, None


def _route_headers(provider_name: str, request_id: str, cost: Optional[float] = None) -> Dict[str, str]:
    headers = {
        "X-Provider": provider_name,
        "X-Request-ID": request_id,
        "X-Gateway-Version": GATEWAY_VERSION,
        "X-WAF-Rule-Version": WAF_RULE_VERSION,
    }
    if cost is not None:
        headers["X-Estimated-Cost-USD"] = f"{cost:.8f}"
    return headers


def _is_virtual_model(model: str) -> bool:
    m = (model or "").strip().lower()
    # Strip provider prefix if present (e.g. "openrouter/meta-llama/..." → "meta-llama/...")
    # so that virtual model detection works for both prefixed and raw model IDs
    if "/" in m:
        parts = m.split("/")
        if parts[0] in {
            "openrouter", "nvidia", "groq", "google", "cloudflare",
            "github", "a4f", "cerebras", "pollinations", "ollama",
            "custom", "huggingface", "sambanova", "together", "llm7",
            "mistral", "xai", "deepseek", "perplexity", "fireworks",
            "deepinfra", "auto",
        }:
            m = "/".join(parts[1:])
    return m in {
        "auto",
        "auto:free",
        "auto:reasoning",
        "auto:non-reasoning",
        "auto:free:reasoning",
        "auto:free:non-reasoning",
        "fast",
        "fast:free",
        "quality",
        "balanced",
        "reasoning",
        "reasoning:free",
        "non-reasoning",
        "non-reasoning:free",
    }


# ── Anthropic /v1/messages (Claude Code compatibility) ─────────────────────────

@router.post("/v1/messages")
async def anthropic_messages(request: Request):
    """Anthropic messages endpoint — translates to OpenAI format for routing.

    Claude Code, Claude SDK, and other Anthropic-native clients use this.
    """
    jwt_payload, vk_record = await _authenticate(request)

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Request body too large")

    try:
        body: Dict[str, Any] = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    # Translate Anthropic → OpenAI format
    messages = body.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "'messages' must be a non-empty array")

    anthropic_to_openai = {
        "user":      "user",
        "assistant": "assistant",
        "system":    "system",
    }
    converted = []
    for msg in messages:
        role = anthropic_to_openai.get(msg.get("role", ""), "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Claude multi-block content → extract text blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts)
        converted.append({"role": role, "content": content})

    openai_body = {
        "model":     body.get("model", "auto"),
        "messages":  converted,
        "max_tokens": body.get("max_tokens", 1024),
        "stream":    body.get("stream", False),
        "temperature": body.get("temperature"),
    }
    # Strip None values
    openai_body = {k: v for k, v in openai_body.items() if v is not None}

    # Re-use chat completions logic via a sub-request
    import uuid as _uuid
    rid = str(_uuid.uuid4())
    vk_id = vk_record["key_id"] if vk_record else None

    # WAF
    waf_hit = waf_scan_body(openai_body)
    if waf_hit:
        raise HTTPException(400, {"error": "waf_blocked", "category": waf_hit})

    # Prompt shield
    shield_hit = shield_scan_body(openai_body)
    if shield_hit and shield_hit.blocked:
        raise HTTPException(400, {
            "error":      "prompt_injection_blocked",
            "category":   shield_hit.category,
            "confidence": round(shield_hit.confidence, 2),
        })

    # Content policy
    for text in extract_text_content(openai_body):
        _blocked, _cat = policy_scan(text)
        if _blocked:
            raise HTTPException(451, {"error": "content_policy_violation", "category": _cat})

    # Canary
    if canary.scan(json.dumps(openai_body)):
        raise HTTPException(400, {"error": "request_contains_disallowed_patterns"})

    # E2EE + stream
    stream = bool(openai_body.get("stream", False))
    encrypt_requested = bool(openai_body.get("encrypt", False))
    cpb64 = request.headers.get("X-Client-Public-Key")
    client_pub: Optional[bytes] = None
    if cpb64:
        try:
            raw_key = base64.b64decode(cpb64, validate=True)
            if len(raw_key) != 32:
                raise ValueError(f"Expected 32 raw bytes, got {len(raw_key)}")
            client_pub = raw_key
        except Exception:
            client_pub = None
    if encrypt_requested and not client_pub:
        raise HTTPException(400, {"error": "missing_e2ee_key", "reason": "encrypt=true requires X-Client-Public-Key"})
    if encrypt_requested and stream:
        raise HTTPException(400, {"error": "e2ee_stream_unsupported"})

    # Virtual routing
    requested_model = str(openai_body.get("model", "")).strip()
    route: Optional[RouteSpec] = resolve_virtual_model(
        requested_model,
        reasoning_hint=infer_reasoning(openai_body),
    )
    if route is not None:
        openai_body["_route_mode"] = route.mode
        if route.free_only:
            openai_body["_free_only"] = True

    openai_body["_quarantined"] = _QUARANTINED_MODELS
    pairs = eligible_pairs(openai_body, vk_record=vk_record, route=route)
    if not pairs and route is not None and route.free_only:
        route = replace(route, free_only=False)
        pairs = eligible_pairs(openai_body, vk_record=vk_record, route=route)
    if not pairs:
        raise HTTPException(503, "No providers support the requested capabilities")

    ordered = await sorted_pairs(pairs, route=route)
    last_error: Optional[str] = None

    for provider, model_list in ordered:
        provider_name = provider["name"]
        if not await rate_limiter.is_available(provider_name):
            last_error = f"Provider '{provider_name}' is rate-limited"
            continue

        model = select_model_for_provider(provider, model_list, requested_model, route=route)
        if model is None:
            last_error = f"No model available for provider '{provider_name}'"
            continue

        try:
            result = await call_provider(provider, model, openai_body, stream, rid)
            if len(result) == 3:
                resp_val, status, err = result
                if resp_val is None:
                    last_error = err
                    continue
                raw_data = resp_val
            else:
                status, raw_data = result
        except Exception as exc:
            logger.error("provider_error provider=%s model=%s error=%s",
                         provider_name, model, exc)
            last_error = str(exc)
            continue

        if status == 429:
            last_error = f"Provider '{provider_name}' rate-limited"
            continue

        if status >= 400:
            preview = str(raw_data)[:200] if isinstance(raw_data, str) else ""
            raise HTTPException(502, {
                "error":   "upstream_error",
                "provider": provider_name,
                "status":  status,
                "preview": preview,
            })

        # Normalize Cloudflare
        if (
            isinstance(raw_data, dict) and "result" in raw_data
            and "choices" not in raw_data
        ):
            cf_text = ""
            r = raw_data.get("result", {})
            if isinstance(r, dict):
                cf_text = r.get("response") or r.get("text") or ""
            raw_data = {
                "id":       raw_data.get("id", f"cf-{rid}"),
                "object":   "chat.completion",
                "created":  __import__("time").time_ns() // 1_000_000_000,
                "model":    model,
                "choices":  [{"index": 0, "message": {"role": "assistant", "content": cf_text},
                             "finish_reason": "stop"}],
                "usage":    raw_data.get("result", {}).get("usage", {}),
            }

        data = canary.scrub(raw_data)
        data, output_counts = screen_json(data)
        data, pii_counts = redact_response(data)

        if not isinstance(data, dict):
            raise HTTPException(502, {
                "error": "invalid_upstream_response",
                "provider": provider_name,
                "detail": f"Expected dict, got {type(data).__name__}",
            })

        # Translate OpenAI → Anthropic response format
        choices = data.get("choices", [])
        content_blocks = []
        for choice in choices:
            msg = choice.get("message", {})
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            if content:
                content_blocks.append({"type": "text", "text": content})

        if not content_blocks:
            content_blocks = [{"type": "text", "text": ""}]

        usage = data.get("usage", {})
        resp = {
            "id":       data.get("id", f"msg-{rid}"),
            "type":     "message",
            "role":     "assistant",
            "model":    data.get("model", model),
            "content":  content_blocks,
            "stop_reason": choices[0].get("finish_reason", "end_turn") if choices else "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens":  usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }

        # E2EE
        if encrypt_requested and client_pub:
            for block in content_blocks:
                if block.get("type") == "text":
                    block["text"] = e2ee_encrypt(block["text"], client_pub)

        resp_headers = {
            "X-Provider": provider_name,
            "X-Request-ID": rid,
            "X-Gateway-Version": GATEWAY_VERSION,
            "X-WAF-Rule-Version": WAF_RULE_VERSION,
        }

        return JSONResponse(content=resp, headers=resp_headers)

    raise HTTPException(503, f"All providers failed. Last error: {last_error}")


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    jwt_payload, vk_record = await _authenticate(request)

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Request body too large")

    try:
        body: Dict[str, Any] = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    if not isinstance(body.get("messages"), list) or not body["messages"]:
        raise HTTPException(400, "'messages' must be a non-empty array")

    stream = bool(body.get("stream", False))
    rid = request.headers.get("X-Request-ID") or str(uuid4())
    vk_id = vk_record["key_id"] if vk_record else None

    # WAF
    waf_hit = waf_scan_body(body)
    if waf_hit:
        logger.warning("waf_blocked category=%s ip=%s", waf_hit, client_ip(request))
        raise HTTPException(400, {"error": "waf_blocked", "category": waf_hit})

    # Advanced prompt injection shield
    shield_hit = shield_scan_body(body)
    if shield_hit and shield_hit.blocked:
        logger.warning(
            "prompt_injection blocked category=%s confidence=%.2f ip=%s fragment=%r",
            shield_hit.category, shield_hit.confidence,
            client_ip(request), shield_hit.fragment[:60]
        )
        raise HTTPException(400, {
            "error":      "prompt_injection_blocked",
            "category":   shield_hit.category,
            "confidence": round(shield_hit.confidence, 2),
        })

    # Content policy
    for text in extract_text_content(body):
        _blocked, _cat = policy_scan(text)
        if _blocked:
            raise HTTPException(451, {"error": "content_policy_violation", "category": _cat})

    # Canary in request
    if canary.scan(json.dumps(body)):
        raise HTTPException(400, {"error": "request_contains_disallowed_patterns"})

    # Nonce
    req_nonce = request.headers.get("X-Request-Nonce", "")
    if req_nonce and not await nonce.register(req_nonce):
        raise HTTPException(409, {"error": "replay_detected"})

    # E2EE
    encrypt_requested = bool(body.get("encrypt", False))
    cpb64 = request.headers.get("X-Client-Public-Key")

    if encrypt_requested and not cpb64:
        raise HTTPException(
            400,
            {
                "error": "missing_e2ee_key",
                "reason": "encrypt=true requires X-Client-Public-Key",
            },
        )

    client_pub: Optional[bytes] = None
    if cpb64:
        try:
            raw_key = base64.b64decode(cpb64, validate=True)
            if len(raw_key) != 32:
                raise ValueError(f"Expected 32 raw bytes, got {len(raw_key)}")
            client_pub = raw_key
        except Exception as exc:
            raise HTTPException(400, {"error": "invalid_e2ee_key", "reason": str(exc)})

    if stream and body.get("encrypt"):
        raise HTTPException(400, {"error": "e2ee_stream_unsupported"})

    # Virtual routing resolution
    requested_model = str(body.get("model", "")).strip()
    route: Optional[RouteSpec] = resolve_virtual_model(
        requested_model,
        reasoning_hint=infer_reasoning(body),
    )

    if route is None and not requested_model:
        # No model provided; let the normal router pick from provider defaults.
        route = None

    if route is not None:
        body["_route_mode"] = route.mode
        if route.free_only:
            body["_free_only"] = True

    # Virtual-key model guard
    if vk_record and requested_model and not _is_virtual_model(requested_model):
        if not allows_model(vk_record, requested_model):
            raise HTTPException(
                403,
                {
                    "error": "model_not_allowed",
                    "reason": f"Key '{vk_id}' does not allow model '{requested_model}'",
                    "allowed": vk_record.get("allowed_models", []),
                },
            )

    body["_quarantined"] = _QUARANTINED_MODELS
    pairs = eligible_pairs(body, vk_record=vk_record, route=route)
    if not pairs and route is not None and route.free_only:
        # graceful fallback: if no free providers match, retry without free_only
        logger.warning("auto:free had no eligible providers; retrying without free_only")
        route = replace(route, free_only=False)
        pairs = eligible_pairs(body, vk_record=vk_record, route=route)

    if not pairs:
        raise HTTPException(503, "No providers support the requested capabilities")

    ordered = await sorted_pairs(pairs, route=route)
    last_error: Optional[str] = None

    for provider, model_list in ordered:
        provider_name = provider["name"]

        if not await rate_limiter.is_available(provider_name):
            last_error = f"Provider '{provider_name}' is rate-limited — skipping"
            continue

        model = select_model_for_provider(
            provider=provider,
            model_list=model_list,
            requested_model=requested_model,
            route=route,
        )

        if model is None:
            if requested_model:
                last_error = (
                    f"Provider '{provider_name}' does not list model '{requested_model}' — skipping"
                )
                logger.debug(last_error)
            continue

        if vk_record:
            # Now validate the actual model that will be sent upstream.
            if not allows_model(vk_record, model):
                last_error = (
                    f"Key '{vk_id}' does not allow resolved model '{model}'"
                )
                continue

        resp, status, err = await call_provider(provider, model, body, stream, rid)
        if resp is None:
            last_error = err
            continue

        if status == 404:
            last_error = (
                f"Provider '{provider_name}' returned 404 for model '{model}' — trying next provider"
            )
            logger.warning(last_error)
            try:
                await resp.aclose()
            except Exception:
                pass
            continue

        if stream:
            async def _gen(r) -> AsyncGenerator[bytes, None]:
                buf = ""
                try:
                    async for chunk in r.aiter_bytes():
                        buf += chunk.decode("utf-8", errors="replace")

                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)

                            cleaned, _ = screen_text(line)

                            for pat in canary.CANARY_PATTERNS:
                                cleaned = pat.sub("[REDACTED]", cleaned)

                            if cleaned.startswith("data:") and "[DONE]" not in cleaned:
                                cleaned, _ = pii_redact(cleaned)

                            yield (cleaned + "\n").encode()

                    if buf:
                        cleaned, _ = screen_text(buf)
                        for pat in canary.CANARY_PATTERNS:
                            cleaned = pat.sub("[REDACTED]", cleaned)
                        yield cleaned.encode()

                finally:
                    try:
                        await r.aclose()
                    except Exception:
                        pass

            return StreamingResponse(
                _gen(resp),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    **_route_headers(provider_name, rid),
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        try:
            raw_data = resp.json()
        except Exception:
            preview = (await resp.aread())[:300].decode(errors="replace")
            raise HTTPException(
                502,
                {
                    "error": "invalid_upstream_json",
                    "provider": provider_name,
                    "preview": preview,
                },
            )

        # Normalize Cloudflare Workers AI response → OpenAI format
        # CF returns {"result":{"response":"..."},"success":true}
        if (
            isinstance(raw_data, dict)
            and "result" in raw_data
            and "success" in raw_data
            and "choices" not in raw_data
        ):
            cf_text = ""
            r = raw_data.get("result", {})
            if isinstance(r, dict):
                cf_text = r.get("response") or r.get("text") or ""
            raw_data = {
                "id":      raw_data.get("id", "cf-response"),
                "object":  "chat.completion",
                "created": __import__("time").time_ns() // 1_000_000_000,
                "model":   model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": cf_text},
                    "finish_reason": "stop",
                }],
                "usage": raw_data.get("result", {}).get("usage", {}),
            }

        data = canary.scrub(raw_data)
        data, output_counts = screen_json(data)
        data, pii_counts = redact_response(data)

        # Guard: some providers return a list on error instead of a dict
        if not isinstance(data, dict):
            raise HTTPException(502, {"error": "invalid_upstream_response",
                                      "provider": provider_name,
                                      "detail": f"Expected dict, got {type(data).__name__}"})

        usage = data.get("usage", {})
        in_t = usage.get("prompt_tokens", 0)
        out_t = usage.get("completion_tokens", 0)
        cost = await record_cost(provider_name, in_t, out_t)

        await log_append(
            provider_name,
            model,
            body,
            data,
            status,
            cost_usd=cost,
            pii_counts=pii_counts,
            vk_id=vk_id,
        )

        if body.get("encrypt") and client_pub:
            # Encrypt ALL choices — not just choices[0].
            # Encrypting only the first choice leaks choices 1..n-1 in plaintext
            # when the caller requests n > 1 completions.
            for choice in data.get("choices", []):
                msg = choice.get("message", {})
                if isinstance(msg.get("content"), str):
                    msg["content"] = e2ee_encrypt(msg["content"], client_pub)

        resp_headers = _route_headers(provider_name, rid, cost)
        if output_counts:
            resp_headers["X-Output-Screened"] = ",".join(
                f"{k}:{v}" for k, v in output_counts.items()
            )
        if pii_counts:
            resp_headers["X-PII-Redacted"] = ",".join(
                f"{k}:{v}" for k, v in pii_counts.items()
            )

        return JSONResponse(content=data, headers=resp_headers)

    raise HTTPException(503, f"All providers failed. Last error: {last_error}")