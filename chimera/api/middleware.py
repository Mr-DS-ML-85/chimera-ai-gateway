from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import (
    IP_RATE_LIMIT_RPM, MAX_BODY_BYTES,
    REQUEST_TIMEOUT_SECS, TRUSTED_PROXIES,
)
from core.logging_setup import logger

# ── Global burst limiter (catches XFF-rotation bypass) ────────────────────────
# Tracks total gateway-wide requests per second regardless of IP.
# Attacker rotating IPs still hits this ceiling.
import os as _os
_GLOBAL_RPS_LIMIT   = int(_os.getenv("GLOBAL_RPS_LIMIT", "200"))   # req/s across all IPs
_global_hits: Deque[float] = deque()
_global_lock  = asyncio.Lock()


async def _global_rps_allowed() -> bool:
    if not _GLOBAL_RPS_LIMIT:
        return True
    now = time.monotonic()
    async with _global_lock:
        while _global_hits and _global_hits[0] < now - 1.0:
            _global_hits.popleft()
        if len(_global_hits) >= _GLOBAL_RPS_LIMIT:
            return False
        _global_hits.append(now)
        return True


# ── IP extraction ─────────────────────────────────────────────────────────────
_PRIVATE_RE = re.compile(
    r"^(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.|127\.|::1$|fc00:|fe80:)",
    re.IGNORECASE,
)


def client_ip(request: Request) -> str:
    """
    Secure XFF extraction (v8.3 fix).

    Rules:
    - Only trust X-Forwarded-For when the *direct* TCP peer is explicitly listed
      in TRUSTED_PROXIES AND is not itself a loopback/private address.
    - This prevents two common misconfigurations:
        a) TRUSTED_PROXIES accidentally contains 127.0.0.1 (same-host nginx)
           allowing clients to spoof IPs via XFF from loopback.
        b) Empty TRUSTED_PROXIES silently trusting all XFF values.
    - In legitimate deployments where nginx/Caddy runs on the same host, list
      the *nginx socket IP* (usually 127.0.0.1) in TRUSTED_PROXIES AND ensure
      external clients cannot reach port 8000 directly (firewall/bind).
    """
    direct = request.client.host if request.client else "unknown"

    # Peer must be (a) an explicit trusted proxy AND (b) not loopback/private.
    # Condition (b) stops same-host loopback proxies from being spoofed by
    # clients who can also reach port 8000 directly (typical in dev/test).
    peer_is_trusted = (
        TRUSTED_PROXIES
        and direct in TRUSTED_PROXIES
        and not _PRIVATE_RE.match(direct)
    )
    if not peer_is_trusted:
        return direct

    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if not forwarded:
        return direct
    # Walk right-to-left; skip trusted/private relays; return first client IP.
    for ip in reversed([x.strip() for x in forwarded.split(",")]):
        if ip not in TRUSTED_PROXIES and not _PRIVATE_RE.match(ip):
            return ip
    return forwarded.split(",")[0].strip()


# ── IP rate limiter ───────────────────────────────────────────────────────────
_ip_hits: Dict[str, Deque[float]] = defaultdict(deque)
_ip_lock  = asyncio.Lock()


async def _ip_allowed(ip: str) -> bool:
    if not IP_RATE_LIMIT_RPM:
        return True
    now = time.monotonic()
    async with _ip_lock:
        dq = _ip_hits[ip]
        while dq and dq[0] < now - 60.0:
            dq.popleft()
        if len(dq) >= IP_RATE_LIMIT_RPM:
            return False
        dq.append(now)
        return True


# ── Middleware registration ───────────────────────────────────────────────────
def register_middleware(app: FastAPI) -> None:

    @app.middleware("http")
    async def _request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        t0  = time.perf_counter()
        response = await call_next(request)
        ms  = (time.perf_counter() - t0) * 1000
        response.headers["X-Request-ID"]    = rid
        response.headers["X-Response-Time"] = f"{ms:.1f}ms"
        logger.info(
            "method=%s path=%s status=%d ms=%.1f rid=%s ip=%s",
            request.method, request.url.path,
            response.status_code, ms, rid, client_ip(request),
        )
        return response

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options":    "nosniff",
            "X-Frame-Options":           "DENY",
            # Modern browsers: disable legacy XSS auditor (causes its own vulns).
            # OWASP 2024+ recommendation is "0", not "1; mode=block".
            "X-XSS-Protection":          "0",
            "Content-Security-Policy":   "default-src 'none'; frame-ancestors 'none'",
            "Referrer-Policy":           "no-referrer",
            "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
            "Cache-Control":             "no-store",
            # Server header explicitly deleted — uvicorn's server_header=False handles
            # the uvicorn banner; we must also pop any residual value ourselves.
        })
        if "server" in resp.headers:        # MutableHeaders has no .pop(); use del
            del resp.headers["server"]
        return resp

    @app.middleware("http")
    async def _body_size(request: Request, call_next):
        cl = request.headers.get("Content-Length")
        if cl and int(cl) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"error": "Request body too large"})
        return await call_next(request)

    @app.middleware("http")
    async def _timeout(request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request), timeout=REQUEST_TIMEOUT_SECS + 5
            )
        except asyncio.TimeoutError:
            return JSONResponse(status_code=504, content={"error": "Gateway timeout"})

    @app.middleware("http")
    async def _global_burst(request: Request, call_next):
        """Second-level rate limit: global RPS cap catches XFF-rotation attacks."""
        if not await _global_rps_allowed():
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "1"},
                content={"error": "Rate limit exceeded (global)"},
            )
        return await call_next(request)

    @app.middleware("http")
    async def _ip_rate_limit(request: Request, call_next):
        if not await _ip_allowed(client_ip(request)):
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={"error": "Rate limit exceeded (IP)"},
            )
        return await call_next(request)

    @app.middleware("http")
    async def _path_traversal(request: Request, call_next):
        traversal = re.compile(
            r"(?:\.\.[\\/]|%2e%2e|%252e%252e|\.\.%2f|\.\.%5c)", re.IGNORECASE
        )
        for part in (request.url.path, str(request.url.query)):
            if traversal.search(part):
                return JSONResponse(status_code=400, content={"error": "invalid_path"})
        if "\x00" in request.url.path or "%00" in request.url.path:
            return JSONResponse(status_code=400, content={"error": "invalid_path"})
        return await call_next(request)
    
    