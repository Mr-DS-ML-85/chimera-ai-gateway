from __future__ import annotations

import hmac as _hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.config import (
    ADMIN_API_KEY, CHIMERA_API_KEY, ENABLE_CONTENT_POLICY,
    ENABLE_PII_REDACTION, ENABLE_WAF, GATEWAY_VERSION, IS_DEV,
    JWKS_URI, WAF_RULE_VERSION,
)
from keys.virtual_keys import STORE as VK_STORE
from transparency.log import CONFIG_FINGERPRINT

router = APIRouter()

# Only registered by api/app.py when IS_DEV=True


@router.get("/debug/auth", include_in_schema=False)
async def debug_auth(request: Request):
    from api.routes.chat import _authenticate
    await _authenticate(request)   # still requires a valid key in DEV

    auth  = request.headers.get("Authorization", "")
    token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
    match = (
        _hmac.compare_digest(token.encode(), CHIMERA_API_KEY.encode())
        if CHIMERA_API_KEY and token else None
    )
    return JSONResponse({
        "chimera_key_set":     bool(CHIMERA_API_KEY),
        "chimera_key_last4":   CHIMERA_API_KEY[-4:] if CHIMERA_API_KEY else "(none)",
        "chimera_key_length":  len(CHIMERA_API_KEY),
        "admin_key_set":       bool(ADMIN_API_KEY),
        "jwks_configured":     bool(JWKS_URI),
        "waf_enabled":         ENABLE_WAF,
        "pii_enabled":         ENABLE_PII_REDACTION,
        "content_policy":      ENABLE_CONTENT_POLICY,
        "waf_rule_version":    WAF_RULE_VERSION,
        "config_fingerprint":  CONFIG_FINGERPRINT,
        "gateway_version":     GATEWAY_VERSION,
        "virtual_keys_loaded": len(VK_STORE),
        "keys_match":          match,
        "verdict": (
            "✅ match"    if match is True  else
            "❌ mismatch" if match is False else
            "⚠ no key set"
        ),
    })