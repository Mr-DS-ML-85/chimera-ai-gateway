from __future__ import annotations
from api.routes import root as root_route
# chimera/api/app.py  — replace the routes import block with:
from api.routes import (
    admin, chat, debug, e2ee, health, metrics,
    models, transparency as tr_route, root as root_route,
)
import asyncio
import hashlib
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import (
    CHIMERA_API_KEY, CORS_ORIGINS_RAW, GATEWAY_VERSION,
    HTTP_CONNECT_TIMEOUT, HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE,
    IS_DEV, MODEL_REFRESH_INTERVAL_SECS, REQUEST_TIMEOUT_SECS,
    ROUTE_BY, TRUSTED_PROXIES, WAF_RULE_VERSION, validate,
)
from core.logging_setup import logger
from providers import auto_models, router as prov_router
from providers.catalogue import PROVIDER_CATALOGUE
from security import nonce
from security.content_policy import POLICY_PATTERNS
from security.pii import PII_PATTERNS
from security.waf import WAF_PATTERNS
from keys.virtual_keys import load as load_vkeys
from security.ssrf import approve_base
import transparency.log as tlog

from api.middleware import register_middleware
from api.routes import (
    admin, chat, debug, e2ee, health, metrics,
    models, transparency as tr_route,
)


# ── CORS ─────────────────────────────────────────────────────────────────────
def _build_cors() -> tuple[List[str], bool]:
    if not CORS_ORIGINS_RAW:
        if not IS_DEV:
            logger.warning(
                "CORS_ORIGINS not set — cross-origin requests will be blocked. "
                "Set CORS_ORIGINS=https://yourdomain.com"
            )
        return [], False

    if "*" in CORS_ORIGINS_RAW:
        if not IS_DEV:
            # Already caught by validate() above — this branch won't normally
            # be reached in production, but guard it anyway.
            logger.critical(
                "CORS_ORIGINS=* in production — forcing empty origins (blocked)."
            )
            return [], False
        else:
            logger.warning(
                "CORS_ORIGINS=* — wildcard CORS active (DEV mode only). "
                "Set explicit origins before deploying."
            )
            return ["*"], False          # wildcard + no credentials = safe enough for dev

    return CORS_ORIGINS_RAW, True        # explicit origins → credentials allowed


def _compute_fingerprint() -> str:
    parts = [
        f"gateway_version={GATEWAY_VERSION}",
        f"waf_rule_version={WAF_RULE_VERSION}",
    ]
    for cat, pat in WAF_PATTERNS:
        parts.append(f"waf:{cat}:{pat.pattern}")
    for label, pat, token in PII_PATTERNS:
        parts.append(f"pii:{label}:{pat.pattern}:{token}")
    for pat in POLICY_PATTERNS:
        parts.append(f"policy:{pat.pattern}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:32]


# ── Lifespan ──────────────────────────────────────────────────────────────────
_bg_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    global _bg_task

    errors = validate()
    if errors:
        for e in errors:
            logger.critical("CONFIG ERROR: %s", e)
        sys.exit(1)

    # Shared HTTP pool
    http_client = httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            keepalive_expiry=30,
        ),
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECS, connect=HTTP_CONNECT_TIMEOUT),
        follow_redirects=False,  # SSRF guard: never follow redirects
        http2=True,
    )
    prov_router.set_http_client(http_client)

    await nonce.init_redis()
    load_vkeys()
    # Pre-approve all configured provider base URLs so local providers
    # (e.g. Ollama at 127.0.0.1) pass the per-request SSRF guard
    from providers.catalogue import PROVIDER_CATALOGUE
    for _p in PROVIDER_CATALOGUE:
        if _p.get("base_url"):
            approve_base(_p["base_url"])

    # Config fingerprint (must be after all rule modules loaded)
    tlog.CONFIG_FINGERPRINT = _compute_fingerprint()

    if not TRUSTED_PROXIES:
        logger.warning("TRUSTED_PROXIES empty — set it if running behind a reverse proxy")

    if CHIMERA_API_KEY:
        fp = hashlib.sha256(CHIMERA_API_KEY.encode()).hexdigest()[:16]
        logger.info("auth_key_last4=...%s sha256_prefix=%s len=%d",
                    CHIMERA_API_KEY[-4:], fp, len(CHIMERA_API_KEY))
    else:
        logger.warning("CHIMERA_API_KEY not set — /v1/ endpoints are OPEN")

    logger.info(
        "Chimera Gateway v%s | waf=%s | fp=%s | providers=%d",
        GATEWAY_VERSION, WAF_RULE_VERSION, tlog.CONFIG_FINGERPRINT, len(PROVIDER_CATALOGUE),
    )

    logger.info("auto-model: initial discovery …")
    await auto_models.refresh_all(http_client)
    logger.info("auto-model: discovery complete")

    _bg_task = asyncio.create_task(
        auto_models.background_refresher(http_client), name="model-refresher"
    )

    yield

    if _bg_task:
        _bg_task.cancel()
        try:
            await _bg_task
        except asyncio.CancelledError:
            pass

    await http_client.aclose()
    await nonce.close_redis()
    from crypto.hmac_seal import zero
    zero()
    logger.info("Chimera Gateway shut down cleanly")


# ── Build app ─────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    cors_origins, cors_creds = _build_cors()

    application = FastAPI(
        title       = "Chimera Gateway",
        version     = "8.2.0",
        description = (
            "Secure multi-provider OpenAI-compatible gateway — "
            "v8.2: PII redaction, virtual keys, config versioning, auto model detection."
        ),
        lifespan    = lifespan,
        docs_url    = "/docs" if IS_DEV else None,
        openapi_url = "/openapi.json" if IS_DEV else None,
        redoc_url   = None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins     = cors_origins or ["null"],
        allow_credentials = cors_creds,
        allow_methods     = ["GET", "POST", "OPTIONS"],
        allow_headers     = [
            "Authorization", "Content-Type",
            "X-Request-ID", "X-Request-Nonce", "X-Client-Public-Key",
        ],
        expose_headers    = [
            "X-Request-ID", "X-Provider",
            "X-Estimated-Cost-USD", "X-Response-Time", "X-PII-Redacted",
            "X-Gateway-Version", "X-WAF-Rule-Version",
        ],
    )

    register_middleware(application)

    # Routers
    application.include_router(chat.router)
    application.include_router(models.router)
    application.include_router(health.router)
    application.include_router(metrics.router)
    application.include_router(tr_route.router)
    application.include_router(e2ee.router)
    application.include_router(admin.router)
    if IS_DEV:
        application.include_router(debug.router)
        application.include_router(root_route.router) 

    return application


app = create_app()