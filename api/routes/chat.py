from __future__ import annotations

import base64
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional, Tuple
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
            "deepinfra", "auto", "anthropic",
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

def _translate_anthropic_to_openai(body: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Anthropic /v1/messages request to OpenAI /chat/completions format."""
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
            # Claude multi-block content → flatten text blocks for OpenAI providers
            # Note: tool_use/tool_result blocks are preserved as-is (text repr) since
            # non-Anthropic providers can't handle native tool calls
            text_parts = []
            tool_blocks = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        # Serialize tool call as a readable text block for non-Anthropic providers
                        tool_blocks.append(
                            f"[TOOL_CALL id={block.get('id')} name={block.get('name')}]"
                        )
                    elif btype == "tool_result":
                        tool_blocks.append(
                            f"[TOOL_RESULT tool_use_id={block.get('tool_use_id')}]"
                        )
            parts = text_parts + tool_blocks
            content = "\n".join(parts)
        converted.append({"role": role, "content": content})

    # Handle top-level system instruction (Anthropic-specific)
    system_instruction = body.get("system", "")
    if system_instruction:
        converted.insert(0, {"role": "system", "content": system_instruction})

    openai_body = {
        "model":        body.get("model", "auto"),
        "messages":     converted,
        "max_tokens":   body.get("max_tokens", 1024),
        "stream":       body.get("stream", False),
        "temperature":  body.get("temperature"),
        "top_p":        body.get("top_p"),
        "tools":        body.get("tools"),
        "tool_choice":  body.get("tool_choice"),
    }
    # Strip None values
    return {k: v for k, v in openai_body.items() if v is not None}


def _translate_openai_to_anthropic(
    data: Dict[str, Any],
    request_id: str,
    provider_name: str,
    model: str,
) -> Dict[str, Any]:
    """Convert OpenAI /chat/completions response to Anthropic /v1/messages format."""
    choices = data.get("choices", [])
    content_blocks = []

    for choice in choices:
        msg = choice.get("message", {})
        role = msg.get("role", "assistant")
        content = msg.get("content", "")

        # Check for tool_call in OpenAI response
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                content_blocks.append({
                    "type": "tool_use",
                    "id":   tc.get("id", f"toolu_{request_id}"),
                    "name": func.get("name", "unknown"),
                    "input": json.loads(func.get("arguments", "{}")),
                })
            if content:
                content_blocks.append({"type": "text", "text": content})
        elif content:
            content_blocks.append({"type": "text", "text": content})

    if not content_blocks:
        content_blocks = [{"type": "text", "text": ""}]

    usage = data.get("usage", {})
    stop_reason = "end_turn"
    if choices:
        fr = choices[0].get("finish_reason", "")
        if fr in ("stop", "eos", "stop_sequence"):
            stop_reason = "end_turn"
        elif fr in ("length", "max_tokens"):
            stop_reason = "max_tokens"
        elif fr == "tool_calls":
            stop_reason = "end_turn"

    return {
        "id":           data.get("id", f"msg-{request_id}"),
        "type":         "message",
        "role":         "assistant",
        "model":        data.get("model", model),
        "content":      content_blocks,
        "stop_reason":  stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens":  usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


async def _stream_openai_to_anthropic(
    resp: Any,
    request_id: str,
    model: str,
    provider_name: str,
) -> AsyncGenerator[bytes, None]:
    """Translate OpenAI SSE chunks to Anthropic SSE format for Claude Code.

    OpenAI format:
      data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}

    Anthropic format:
      data: {"type":"message_start","message":{"id":"...","type":"message","role":"assistant","model":"..."}}
      data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}
      data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}
      ...
      data: {"type":"message_stop"}
    """
    import uuid

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    msg_sent = False
    block_started = False
    block_index = 0
    tool_block_started = False
    buf = ""

    yield f'data: {json.dumps({"type":"message_start","message":{"id":msg_id,"type":"message","role":"assistant","model":model,"usage":{"input_tokens":0,"output_tokens":0}}})}\n'.encode()

    try:
        async for chunk in resp.aiter_bytes():
            buf += chunk.decode("utf-8", errors="replace")

            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    if not msg_sent:
                        yield f'data: {json.dumps({"type":"message_start","message":{"id":msg_id,"type":"message","role":"assistant","model":model}})}\n'.encode()
                        msg_sent = True
                    yield b'data: {"type":"message_stop"}\n'
                    continue

                try:
                    chunk_data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                choices = chunk_data.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                role = delta.get("role")
                content = delta.get("content")
                tool_calls = delta.get("tool_calls")
                finish_reason = choices[0].get("finish_reason", "")

                # message_start
                if role == "assistant" and not msg_sent:
                    yield f'data: {json.dumps({"type":"message_start","message":{"id":msg_id,"type":"message","role":"assistant","model":model}})}\n'.encode()
                    msg_sent = True

                # Handle tool calls in delta
                if tool_calls:
                    for tc in tool_calls:
                        if not tool_block_started:
                            yield f'data: {json.dumps({"type":"content_block_start","index":block_index,"content_block":{"type":"tool_use","id":tc.get("id",""),"name":tc.get("function",{}).get("name",""),"input":{}}})}\n'.encode()
                            tool_block_started = True
                        func = tc.get("function", {})
                        args = func.get("arguments", "")
                        try:
                            args_dict = json.loads(args) if isinstance(args, str) else args
                        except (json.JSONDecodeError, TypeError):
                            args_dict = {}
                        yield f'data: {json.dumps({"type":"content_block_delta","index":block_index,"delta":{"type":"input_json_delta","partial_json":args}})}\n'.encode()
                    continue

                # content_block_start (first content delta)
                if content and not block_started:
                    yield f'data: {json.dumps({"type":"content_block_start","index":block_index,"content_block":{"type":"text","text":""}})}\n'.encode()
                    block_started = True

                # content_block_delta
                if content and block_started:
                    yield f'data: {json.dumps({"type":"content_block_delta","index":block_index,"delta":{"type":"text_delta","text":content}})}\n'.encode()

                # message_stop
                if finish_reason and finish_reason not in (None, "null"):
                    # Send any trailing content block delta
                    if finish_reason in ("stop", "eos", "length", "max_tokens"):
                        pass
                    # StopReason event
                    yield f'data: {json.dumps({"type":"message_delta","delta":{"stop_reason":finish_reason if finish_reason in ("end_turn","max_tokens") else "end_turn"}})}\n'.encode()
                    yield b'data: {"type":"message_stop"}\n'

    finally:
        if not msg_sent:
            yield f'data: {json.dumps({"type":"message_start","message":{"id":msg_id,"type":"message","role":"assistant","model":model}})}\n'.encode()
        yield b'data: {"type":"message_stop"}\n'
        try:
            await resp.aclose()
        except Exception:
            pass


@router.post("/v1/messages")
async def anthropic_messages(request: Request):
    """Anthropic messages endpoint — translates to OpenAI format for routing.

    Claude Code, Claude SDK, and other Anthropic-native clients use this.
    When model starts with 'anthropic/' and ANTHROPIC_API_KEY is set, calls
    the Anthropic API directly. Otherwise translates Anthropic→OpenAI format
    and routes to any available provider.
    """
    from chimera.providers.anthropic_client import is_configured as anthropic_is_configured

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

    # Extract Anthropic-specific headers
    extra_h: Dict[str, str] = {}
    for h in ("anthropic-beta", "anthropic-version", "anthropic-dangerous-direct-knowledge-access"):
        val = request.headers.get(h)
        if val:
            extra_h[h] = val
    if "anthropic-version" not in extra_h:
        extra_h["anthropic-version"] = "2023-06-01"

    # Determine target model
    requested_model = str(body.get("model", "")).strip()
    model_aliases = {
        # Anthropic model shortcuts
        "sonnet": "anthropic/claude-sonnet-4-7-20250514",
        "sonnet-4-7": "anthropic/claude-sonnet-4-7-20250514",
        "haiku": "anthropic/claude-3.5-haiku-20241022",
        "opus": "anthropic/claude-3-7-sonnet-20250514",
        "3.5-haiku": "anthropic/claude-3.5-haiku-20241022",
        "3.5-sonnet": "anthropic/claude-3.5-sonnet-20241022",
        # Non-Anthropic model aliases — Claude Desktop validates model names
        # and only accepts those containing "claude", "sonnet", "opus", "haiku",
        # or "anthropic". We rewrite free/third-party model names so the gateway
        # prefix makes the name pass validation while routing correctly.
        # Routes via opencode-zen backend when ANTHROPIC_API_KEY is not set.
        "minimax-m2.5-free": "opencode-zen/minimax-m2.5-free",
        "minimax-m2.5": "opencode-zen/minimax-m2.5",
        "minimax-m2": "opencode-zen/minimax-m2",
        "gemini-3-flash": "opencode-zen/gemini-3-flash",
        "glm-5": "opencode-zen/glm-5",
        "gpt-oss-20b": "opencode-zen/gpt-oss-20b",
        "qwq-32b": "opencode-zen/qwq-32b",
    }
    raw_alias = requested_model.lower().strip()
    if raw_alias in model_aliases:
        requested_model = model_aliases[raw_alias]

    # ── Route 1: Direct Anthropic API (when ANTHROPIC_API_KEY is set and model is anthropic/*)
    if requested_model.startswith("anthropic/") and anthropic_is_configured():
        from chimera.providers.anthropic_client import call_messages, stream_messages

        # Forward the request directly to Anthropic
        direct_body = dict(body)
        direct_body["model"] = requested_model.split("/", 1)[1] if "/" in requested_model else requested_model

        if stream:
            return StreamingResponse(
                stream_messages(direct_body, extra_h),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "X-Provider": "anthropic",
                    "X-Request-ID": rid,
                    "X-Gateway-Version": GATEWAY_VERSION,
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            result = await call_messages(direct_body, extra_h)
            return JSONResponse(content=result, headers={
                "X-Provider": "anthropic",
                "X-Request-ID": rid,
                "X-Gateway-Version": GATEWAY_VERSION,
            })

    # ── Route 2: Translate Anthropic→OpenAI and route to any provider
    openai_body = _translate_anthropic_to_openai(body)

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

    # E2EE
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
    openai_body["_quarantined"] = _QUARANTINED_MODELS
    route: Optional[RouteSpec] = resolve_virtual_model(
        requested_model,
        reasoning_hint=infer_reasoning(openai_body),
    )
    if route is not None:
        openai_body["_route_mode"] = route.mode
        if route.free_only:
            openai_body["_free_only"] = True

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
            result = await call_provider(provider, model, openai_body, stream, rid, extra_h if extra_h else None)
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
            preview = (await raw_data.aread())[:300].decode(errors="replace")
            raise HTTPException(502, {
                "error":   "upstream_error",
                "provider": provider_name,
                "status":  status,
                "preview": preview,
            })

        # ── Streaming: translate OpenAI SSE → Anthropic SSE ──
        if stream:
            return StreamingResponse(
                _stream_openai_to_anthropic(raw_data, rid, model, provider_name),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "X-Provider": provider_name,
                    "X-Request-ID": rid,
                    "X-Gateway-Version": GATEWAY_VERSION,
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # ── Non-streaming: parse and translate response ──
        try:
            raw_data = raw_data.json()
        except Exception:
            preview = (await raw_data.aread())[:300].decode(errors="replace")
            raise HTTPException(502, {
                "error": "invalid_upstream_json",
                "provider": provider_name,
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

        # Translate OpenAI → Anthropic response
        resp = _translate_openai_to_anthropic(data, rid, provider_name, model)

        # E2EE
        if encrypt_requested and client_pub:
            for block in resp.get("content", []):
                if block.get("type") == "text":
                    block["text"] = e2ee_encrypt(block["text"], client_pub)

        resp_headers = {
            "X-Provider": provider_name,
            "X-Request-ID": rid,
            "X-Gateway-Version": GATEWAY_VERSION,
            "X-WAF-Rule-Version": WAF_RULE_VERSION,
        }
        if output_counts:
            resp_headers["X-Output-Screened"] = ",".join(f"{k}:{v}" for k, v in output_counts.items())
        if pii_counts:
            resp_headers["X-PII-Redacted"] = ",".join(f"{k}:{v}" for k, v in pii_counts.items())

        return JSONResponse(content=resp, headers=resp_headers)

    raise HTTPException(503, f"All providers failed. Last error: {last_error}")


@router.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    """Token counting endpoint for Claude Code pre-flight checks."""
    raw = await request.body()
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    # Simple estimation: ~1 token per 4 chars (conservative for Claude tokens)
    messages = body.get("messages", [])
    system = body.get("system", "")

    total = 0
    if system:
        total += len(system) // 4
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += len(block.get("text", "")) // 4

    # Add overhead for model name and formatting
    model_name = body.get("model", "")
    if model_name:
        total += 20  # overhead for system framing

    return JSONResponse(content={
        "tokens": total,
        "count_tokens_version": "1"
    })


@router.post("/v1/responses")
async def responses_endpoint(request: Request):
    """Anthropic Responses API — newer endpoint for Claude Code features.

    Translates the Responses API format to /v1/messages compatible format,
    routes to provider, then translates back to Responses API format.

    Responses API format (request):
      {"model":"...","input":"...","tools":[...]}

    Responses API format (response):
      {"id":"resp_...","status":"completed","output":[{"type":"message","message":{...}}],...}
    """
    import time

    jwt_payload, vk_record = await _authenticate(request)

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Request body too large")

    try:
        body: Dict[str, Any] = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    rid = request.headers.get("X-Request-ID") or str(uuid4())
    stream = bool(body.get("stream", False))

    # Extract Anthropic-specific headers
    extra_h: Dict[str, str] = {}
    for h in ("anthropic-beta", "anthropic-version", "anthropic-dangerous-direct-knowledge-access"):
        val = request.headers.get(h)
        if val:
            extra_h[h] = val
    if "anthropic-version" not in extra_h:
        extra_h["anthropic-version"] = "2023-06-01"

    # Determine target model
    requested_model = str(body.get("model", "")).strip()
    model_aliases = {
        # Anthropic model shortcuts
        "sonnet": "anthropic/claude-sonnet-4-7-20250514",
        "sonnet-4-7": "anthropic/claude-sonnet-4-7-20250514",
        "haiku": "anthropic/claude-3.5-haiku-20241022",
        "opus": "anthropic/claude-3-7-sonnet-20250514",
        "3.5-haiku": "anthropic/claude-3.5-haiku-20241022",
        "3.5-sonnet": "anthropic/claude-3.5-sonnet-20241022",
        # Non-Anthropic model aliases — Claude Desktop validates model names
        # and only accepts those containing "claude", "sonnet", "opus", "haiku",
        # or "anthropic". Rewrite to opencode-zen prefix for correct routing.
        "minimax-m2.5-free": "opencode-zen/minimax-m2.5-free",
        "minimax-m2.5": "opencode-zen/minimax-m2.5",
        "minimax-m2": "opencode-zen/minimax-m2",
        "gemini-3-flash": "opencode-zen/gemini-3-flash",
        "glm-5": "opencode-zen/glm-5",
        "gpt-oss-20b": "opencode-zen/gpt-oss-20b",
        "qwq-32b": "opencode-zen/qwq-32b",
    }
    raw_alias = requested_model.lower().strip()
    if raw_alias in model_aliases:
        requested_model = model_aliases[raw_alias]

    # ── Route 1: Direct Anthropic API ──
    from chimera.providers.anthropic_client import is_configured as anthropic_is_configured
    if requested_model.startswith("anthropic/") and anthropic_is_configured():
        from chimera.providers.anthropic_client import call_messages, stream_messages

        direct_body: Dict[str, Any] = {
            "model":       requested_model.split("/", 1)[1] if "/" in requested_model else requested_model,
            "messages":    [{"role": "user", "content": str(body.get("input", ""))}],
            "max_tokens":  body.get("max_tokens", 4096),
            "stream":      stream,
            "tools":       body.get("tools"),
        }
        if body.get("system"):
            direct_body["system"] = body["system"]

        if stream:
            async def _stream_responses(resp_iter: Any) -> AsyncGenerator[bytes, None]:
                async for line in resp_iter:
                    # Forward the raw Anthropic SSE directly
                    yield line.encode() if isinstance(line, str) else line
            return StreamingResponse(
                stream_messages(direct_body, extra_h),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "X-Provider": "anthropic",
                    "X-Request-ID": rid,
                    "X-Gateway-Version": GATEWAY_VERSION,
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            result = await call_messages(direct_body, extra_h)
            # Translate Anthropic → Responses API format
            resp_id = f"resp_{rid}"
            output = [{
                "type": "message",
                "message": {
                    "id":       result.get("id", resp_id),
                    "type":     "message",
                    "role":     result.get("role", "assistant"),
                    "model":    result.get("model", requested_model.split("/", 1)[1] if "/" in requested_model else requested_model),
                    "content":  result.get("content", [{"type": "text", "text": ""}]),
                    "stop_reason": result.get("stop_reason", "end_turn"),
                    "stop_sequence": result.get("stop_sequence"),
                    "usage":    result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                    "model_unmodified": result.get("model"),
                }
            }]
            return JSONResponse(content={
                "id":             resp_id,
                "object":         "response",
                "status":         "completed",
                "model":          requested_model.split("/", 1)[1] if "/" in requested_model else requested_model,
                "created_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "output":         output,
                "service_tier":   body.get("service_tier", "default"),
                "provider":       result.get("model", "anthropic"),
            }, headers={
                "X-Provider": "anthropic",
                "X-Request-ID": rid,
                "X-Gateway-Version": GATEWAY_VERSION,
            })

    # ── Route 2: Translate Responses API → messages → route → translate back ──
    # Convert Responses API request to Anthropic messages format
    input_content = body.get("input", "")
    if isinstance(input_content, str):
        msgs_content: Any = [{"type": "text", "text": input_content}]
    else:
        msgs_content = input_content  # already in content block format

    messages_body: Dict[str, Any] = {
        "model":       requested_model,
        "messages":    [{"role": "user", "content": msgs_content}],
        "max_tokens":  body.get("max_tokens", 4096),
        "stream":      stream,
        "temperature": body.get("temperature"),
        "tools":       body.get("tools"),
        "system":      body.get("system"),
    }

    # Forward to the /v1/messages handler logic
    openai_body = _translate_anthropic_to_openai(messages_body)

    # WAF
    waf_hit = waf_scan_body(openai_body)
    if waf_hit:
        raise HTTPException(400, {"error": "waf_blocked", "category": waf_hit})

    # Prompt shield
    shield_hit = shield_scan_body(openai_body)
    if shield_hit and shield_hit.blocked:
        raise HTTPException(400, {
            "error": "prompt_injection_blocked",
            "category": shield_hit.category,
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

    openai_body["_quarantined"] = _QUARANTINED_MODELS
    route: Optional[RouteSpec] = resolve_virtual_model(
        requested_model,
        reasoning_hint=infer_reasoning(openai_body),
    )
    if route is not None:
        openai_body["_route_mode"] = route.mode
        if route.free_only:
            openai_body["_free_only"] = True

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
            result = await call_provider(provider, model, openai_body, stream, rid, extra_h if extra_h else None)
            if len(result) == 3:
                resp_val, status, err = result
                if resp_val is None:
                    last_error = err
                    continue
                raw_data = resp_val
            else:
                status, raw_data = result
        except Exception as exc:
            logger.error("provider_error provider=%s model=%s error=%s", provider_name, model, exc)
            last_error = str(exc)
            continue

        if status == 429:
            last_error = f"Provider '{provider_name}' rate-limited"
            continue

        if status >= 400:
            preview = (await raw_data.aread())[:300].decode(errors="replace")
            raise HTTPException(502, {
                "error":   "upstream_error",
                "provider": provider_name,
                "status":  status,
                "preview": preview,
            })

        resp_id = f"resp_{rid}"

        # Streaming: translate to Responses API SSE
        if stream:
            async def _stream_responses_from_openai(resp: Any) -> AsyncGenerator[bytes, None]:
                async for chunk in _stream_openai_to_anthropic(resp, rid, model, provider_name):
                    yield chunk

            return StreamingResponse(
                _stream_responses_from_openai(raw_data),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "X-Provider": provider_name,
                    "X-Request-ID": rid,
                    "X-Gateway-Version": GATEWAY_VERSION,
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # Non-streaming: translate OpenAI → Responses API format
        try:
            raw_data = raw_data.json()
        except Exception:
            preview = (await raw_data.aread())[:300].decode(errors="replace")
            raise HTTPException(502, {
                "error": "invalid_upstream_json",
                "provider": provider_name,
                "preview": preview,
            })

        # Normalize Cloudflare
        if isinstance(raw_data, dict) and "result" in raw_data and "choices" not in raw_data:
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

        # Convert OpenAI response to Anthropic messages format
        anthropic_resp = _translate_openai_to_anthropic(data, rid, provider_name, model)

        # Now convert Anthropic messages format to Responses API format
        choices_data = data.get("choices", [])
        resp_content = anthropic_resp.get("content", [{"type": "text", "text": ""}])
        resp_stop_reason = anthropic_resp.get("stop_reason", "end_turn")

        # Convert stop_reason to Responses API status
        resp_status = "completed" if resp_stop_reason != "max_tokens" else "incomplete"

        usage = anthropic_resp.get("usage", {})
        resp_headers = {
            "X-Provider": provider_name,
            "X-Request-ID": rid,
            "X-Gateway-Version": GATEWAY_VERSION,
        }
        if output_counts:
            resp_headers["X-Output-Screened"] = ",".join(f"{k}:{v}" for k, v in output_counts.items())
        if pii_counts:
            resp_headers["X-PII-Redacted"] = ",".join(f"{k}:{v}" for k, v in pii_counts.items())

        return JSONResponse(content={
            "id":            resp_id,
            "object":        "response",
            "status":        resp_status,
            "model":         data.get("model", model),
            "created_at":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "output": [{
                "type": "message",
                "message": {
                    "id":            anthropic_resp.get("id", resp_id),
                    "type":          "message",
                    "role":          anthropic_resp.get("role", "assistant"),
                    "model":         anthropic_resp.get("model", model),
                    "content":       resp_content,
                    "stop_reason":   resp_stop_reason,
                    "stop_sequence": anthropic_resp.get("stop_sequence"),
                    "usage": {
                        "input_tokens":  usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "total_tokens":  usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    },
                    "model_unmodified": anthropic_resp.get("model", model),
                }
            }],
            "service_tier": body.get("service_tier", "default"),
            "provider":     provider_name,
        }, headers=resp_headers)

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

    # Model aliasing for non-Anthropic free/third-party models.
    # Claude Desktop validates model names and only accepts those containing
    # "claude", "sonnet", "opus", "haiku", or "anthropic" (GitHub #56990).
    # Rewrite known free model names to opencode-zen/ prefix for correct routing.
    requested_model_raw = str(body.get("model", "")).strip()
    model_aliases = {
        "minimax-m2.5-free": "opencode-zen/minimax-m2.5-free",
        "minimax-m2.5": "opencode-zen/minimax-m2.5",
        "minimax-m2": "opencode-zen/minimax-m2",
        "gemini-3-flash": "opencode-zen/gemini-3-flash",
        "glm-5": "opencode-zen/glm-5",
        "gpt-oss-20b": "opencode-zen/gpt-oss-20b",
        "qwq-32b": "opencode-zen/qwq-32b",
    }
    alias_key = requested_model_raw.lower().strip()
    if alias_key in model_aliases:
        body["model"] = model_aliases[alias_key]

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