# chimera/api/routes/root.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.config import GATEWAY_VERSION, ROUTE_BY, WAF_RULE_VERSION
from crypto.e2ee import GW_PUBLIC_KEY_FINGERPRINT
from providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from providers.auto_models import DISCOVERED
from transparency.log import CONFIG_FINGERPRINT

router = APIRouter()


@router.get("/")
async def root():
    configured = [
        p["name"] for p in PROVIDER_CATALOGUE
        if p.get("keyless") or p.get("api_key")
    ]
    healthy = [
        p["name"] for p in PROVIDER_CATALOGUE
        if PROVIDER_ENABLED.get(p["name"], True)
        and (p.get("keyless") or p.get("api_key"))
    ]
    return JSONResponse({
        "gateway":              "Chimera Gateway",
        "version":              GATEWAY_VERSION,
        "status":               "operational",
        "configured_providers": configured,
        "healthy_providers":    healthy,
        "virtual_models": [
            "non-reasoning-auto",
            "reasoning-auto",
            "fast-auto",
            "local-auto",
            "custom-auto",
        ],
        "route_by":             ROUTE_BY,
        "waf_rule_version":     WAF_RULE_VERSION,
        "config_fingerprint":   CONFIG_FINGERPRINT,
        "e2ee_fingerprint":     GW_PUBLIC_KEY_FINGERPRINT,
        "endpoints": {
            "chat":              "/v1/chat/completions",
            "models":            "/v1/models",
            "health":            "/v1/health",
            "e2ee_pubkey":       "/v1/e2ee/pubkey",
            "transparency":      "/v1/transparency",
            "metrics":           "/metrics",
            "admin_usage":       "/v1/admin/usage",
            "admin_models":      "/v1/admin/models",
            "admin_keys":        "/v1/admin/keys",
            "docs":              "/docs",
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    })