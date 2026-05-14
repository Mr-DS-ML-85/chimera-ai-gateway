from __future__ import annotations

import hmac as _hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.config import ADMIN_API_KEY, GATEWAY_VERSION, JWT_AUDIENCE, JWKS_URI, JWT_ISSUER, WAF_RULE_VERSION
from core.logging_setup import logger
from cost.tracker import snapshot as cost_snapshot
from keys import virtual_keys as vk
from providers.auto_models import DISCOVERED, effective_models, refresh_all
from providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from providers.circuit_breaker import CircuitState
from providers.rate_limiter import rate_limiter
from transparency.log import CONFIG_FINGERPRINT, count as log_count
from core.config import MODEL_REFRESH_INTERVAL_SECS

router = APIRouter(prefix="/v1/admin")

# ── JWT helpers (imported here to avoid circular in chat.py) ──────────────────
try:
    import jwt as _pyjwt
    _JWT_OK = True
except ImportError:
    _JWT_OK = False

_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_AT: float = 0.0
_JWKS_TTL = 3600.0
_ALLOWED_ALGS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256"}


async def _fetch_jwks(client: httpx.AsyncClient) -> Dict[str, Any]:
    global _JWKS_CACHE, _JWKS_AT
    now = time.monotonic()
    if _JWKS_CACHE and (now - _JWKS_AT) < _JWKS_TTL:
        return _JWKS_CACHE
    resp = await client.get(JWKS_URI, timeout=10)
    resp.raise_for_status()
    _JWKS_CACHE = resp.json()
    _JWKS_AT    = now
    return _JWKS_CACHE


async def _validate_jwt(token: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    if not JWKS_URI or not _JWT_OK:
        return None
    try:
        header = _pyjwt.get_unverified_header(token)
        alg    = header.get("alg", "").upper()
        if alg not in _ALLOWED_ALGS:
            return None
        jwks = await _fetch_jwks(client)
        kid  = header.get("kid")
        key  = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") != kid:
                continue
            kty = jwk.get("kty", "").upper()
            if alg.startswith(("RS", "PS")) and kty != "RSA": return None
            if alg.startswith("ES")          and kty != "EC":  return None
            key = (
                _pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                if kty == "RSA"
                else _pyjwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk))
            )
            break
        if not key:
            return None
        extra: Dict[str, Any] = {}
        if JWT_AUDIENCE: extra["audience"] = JWT_AUDIENCE
        if JWT_ISSUER:   extra["issuer"]   = JWT_ISSUER
        payload = _pyjwt.decode(
            token, key, algorithms=[alg],
            options={"verify_exp": True, "verify_iat": True, "require": ["exp","iat","sub"]},
            **extra,
        )
        if payload.get("exp", 0) - int(time.time()) > 86400:
            return None
        return payload
    except Exception:
        return None


# ── Admin auth ────────────────────────────────────────────────────────────────

async def require_admin(request: Request) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(503, "Admin API not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = auth[len("Bearer "):]
    if not _hmac.compare_digest(token.encode(), ADMIN_API_KEY.encode()):
        raise HTTPException(403, "Invalid admin key")


# ── Usage ─────────────────────────────────────────────────────────────────────

@router.get("/usage")
async def admin_usage(request: Request):
    await require_admin(request)
    cost_acc, tok_acc = await cost_snapshot()
    usage = await rate_limiter.get_usage()
    rows  = [
        {
            "provider":       p["name"],
            "total_cost_usd": round(cost_acc.get(p["name"], 0.0), 6),
            "total_tokens":   tok_acc.get(p["name"], 0),
            "total_requests": usage.get(p["name"], {}).get("total_requests", 0),
            "total_errors":   usage.get(p["name"], {}).get("total_errors", 0),
            "circuit_state":  usage.get(p["name"], {}).get("circuit_state", CircuitState.CLOSED),
            "enabled":        PROVIDER_ENABLED.get(p["name"], True),
        }
        for p in PROVIDER_CATALOGUE
    ]
    return JSONResponse({
        "total_cost_usd":     round(sum(cost_acc.values()), 6),
        "providers":          rows,
        "log_entries":        log_count(),
        "gateway_version":    GATEWAY_VERSION,
        "waf_rule_version":   WAF_RULE_VERSION,
        "config_fingerprint": CONFIG_FINGERPRINT,
    })


# ── Provider toggle ───────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers(request: Request):
    """List all providers with their current enabled/circuit state."""
    await require_admin(request)
    usage = await rate_limiter.get_usage()
    rows = [
        {
            "provider":      p["name"],
            "enabled":       PROVIDER_ENABLED.get(p["name"], True),
            "circuit_state": usage.get(p["name"], {}).get("circuit_state", "closed"),
            "exhausted":     usage.get(p["name"], {}).get("exhausted", False),
            "base_url":      p.get("base_url", ""),
            "priority":      p.get("priority", 99),
        }
        for p in PROVIDER_CATALOGUE
    ]
    return JSONResponse({"providers": rows, "total": len(rows)})


class ProviderToggle(BaseModel):
    """
    Runtime provider toggle.

    `base_url` is intentionally NOT accepted here — provider base URLs are
    set at startup via .env and validated for SSRF on startup.  Accepting
    arbitrary URLs at runtime would bypass that protection.
    Unknown fields are rejected (extra='forbid') so callers get an explicit
    error instead of silent field stripping.
    """
    model_config = ConfigDict(extra="forbid")

    provider: str
    enabled:  bool


@router.post("/providers")
async def toggle_provider(body: ProviderToggle, request: Request):
    await require_admin(request)
    known = {p["name"] for p in PROVIDER_CATALOGUE}
    if body.provider not in known:
        raise HTTPException(404, f"Unknown provider: {body.provider}")
    PROVIDER_ENABLED[body.provider] = body.enabled
    logger.info("Provider '%s' %s", body.provider, "enabled" if body.enabled else "disabled")
    return JSONResponse({"provider": body.provider, "enabled": body.enabled})


# ── Model refresh ─────────────────────────────────────────────────────────────

@router.post("/refresh-models")
async def refresh_models(request: Request):
    await require_admin(request)
    from providers.router import get_http_client
    import asyncio
    asyncio.create_task(refresh_all(get_http_client()), name="model-refresh-manual")
    return JSONResponse({"status": "refresh_triggered",
                         "interval_secs": MODEL_REFRESH_INTERVAL_SECS})


@router.get("/models")
async def discovered_models(request: Request):
    await require_admin(request)
    report = [
        {
            "provider":             p["name"],
            "source":               "live" if p["name"] in DISCOVERED else "static",
            "non_reasoning_models": effective_models(p, "non_reasoning"),
            "reasoning_models":     effective_models(p, "reasoning"),
            "live_non_reasoning":   DISCOVERED.get(p["name"], {}).get("non_reasoning", []),
            "live_reasoning":       DISCOVERED.get(p["name"], {}).get("reasoning", []),
            "static_non_reasoning": p.get("non_reasoning_models", []),
            "static_reasoning":     p.get("reasoning_models", []),
        }
        for p in PROVIDER_CATALOGUE
    ]
    return JSONResponse({"providers": report,
                         "refresh_interval_secs": MODEL_REFRESH_INTERVAL_SECS})


# ── Virtual-key CRUD ──────────────────────────────────────────────────────────

class VKCreate(BaseModel):
    name:               str
    allowed_models:     List[str] = Field(default_factory=list)
    allowed_providers:  List[str] = Field(default_factory=list)
    rpm_limit:          int       = Field(default=60, ge=0)
    expires_at:         Optional[str] = None
    metadata:           Dict[str, Any] = Field(default_factory=dict)


class VKUpdate(BaseModel):
    name:               Optional[str]       = None
    allowed_models:     Optional[List[str]] = None
    allowed_providers:  Optional[List[str]] = None
    rpm_limit:          Optional[int]       = Field(default=None, ge=0)
    expires_at:         Optional[str]       = None
    enabled:            Optional[bool]      = None
    metadata:           Optional[Dict[str, Any]] = None


@router.get("/keys")
async def list_keys(request: Request):
    await require_admin(request)
    records = [{k: v for k, v in r.items() if k != "key_hash"} for r in vk.STORE.values()]
    return JSONResponse({"keys": records, "total": len(records)})


@router.post("/keys", status_code=201)
async def create_key(body: VKCreate, request: Request):
    await require_admin(request)
    record = await vk.create(
        body.name, body.allowed_models, body.allowed_providers,
        body.rpm_limit, body.expires_at, body.metadata,
    )
    return JSONResponse(record, status_code=201)


@router.patch("/keys/{key_id}")
async def update_key(key_id: str, body: VKUpdate, request: Request):
    await require_admin(request)
    if key_id not in vk.STORE:
        raise HTTPException(404, f"Key '{key_id}' not found")
    updates = body.model_dump(exclude_none=True)
    record  = await vk.update(key_id, updates)
    return JSONResponse(record)


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, request: Request):
    await require_admin(request)
    if key_id not in vk.STORE:
        raise HTTPException(404, f"Key '{key_id}' not found")
    await vk.delete(key_id)
    return JSONResponse({"deleted": key_id})


@router.get("/keys/{key_id}/usage")
async def key_usage(key_id: str, request: Request):
    await require_admin(request)
    if key_id not in vk.STORE:
        raise HTTPException(404, f"Key '{key_id}' not found")
    rec = vk.STORE[key_id]
    return JSONResponse({
        "key_id":      key_id,
        "name":        rec["name"],
        "rpm_limit":   rec.get("rpm_limit", 0),
        "current_rpm": vk.current_rpm(key_id),
    })