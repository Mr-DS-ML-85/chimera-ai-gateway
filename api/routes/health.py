from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.config import GATEWAY_VERSION, WAF_RULE_VERSION
from crypto.e2ee import GW_PUBLIC_KEY_FINGERPRINT
from providers.auto_models import DISCOVERED
from providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from providers.circuit_breaker import CircuitState
from providers.rate_limiter import rate_limiter
from transparency.log import CONFIG_FINGERPRINT

router = APIRouter()


@router.get("/v1/health")
async def health():
    usage  = await rate_limiter.get_usage()
    status = [
        {
            "name":           p["name"],
            "enabled":        PROVIDER_ENABLED.get(p["name"], True),
            "circuit_state":  usage.get(p["name"], {}).get("circuit_state", CircuitState.CLOSED),
            "exhausted":      usage.get(p["name"], {}).get("exhausted", False),
            "ema_latency_ms": usage.get(p["name"], {}).get("ema_latency_ms", 0),
            "model_source":   "live" if p["name"] in DISCOVERED else "static",
        }
        for p in PROVIDER_CATALOGUE
    ]
    healthy = any(
        s["enabled"] and not s["exhausted"] and s["circuit_state"] == CircuitState.CLOSED
        for s in status
    )
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status":             "ok" if healthy else "degraded",
            "version":            GATEWAY_VERSION,
            "waf_rule_version":   WAF_RULE_VERSION,
            "config_fingerprint": CONFIG_FINGERPRINT,
            "e2ee_fingerprint":   GW_PUBLIC_KEY_FINGERPRINT,
            "providers":          status,
            "ts":                 datetime.now(timezone.utc).isoformat(),
        },
    )