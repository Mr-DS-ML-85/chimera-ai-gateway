# chimera/api/routes/transparency.py
from __future__ import annotations

import hmac as _hmac

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.config import ADMIN_API_KEY, GATEWAY_VERSION, WAF_RULE_VERSION
from transparency.log import CONFIG_FINGERPRINT, count, entries
from crypto.e2ee import GW_PUBLIC_KEY_B64, GW_PUBLIC_KEY_FINGERPRINT

router = APIRouter()


def _require_admin(request: Request) -> None:
    """
    Transparency log requires admin auth (v8.3).

    Rationale: The log contains SHA-256 hashes of request/response bodies plus
    provider routing metadata. While no plaintext is stored, the sequence of
    hashes could reveal usage patterns. Admin-only access is appropriate.

    External auditors who need unauthenticated access should be given a
    read-only ADMIN_API_KEY scoped to this endpoint, or the operator can
    expose the log via a separate authenticated auditor endpoint.
    """
    if not ADMIN_API_KEY:
        raise HTTPException(503, "Admin API not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = auth[len("Bearer "):]
    if not _hmac.compare_digest(token.encode(), ADMIN_API_KEY.encode()):
        raise HTTPException(403, "Invalid admin key")


@router.get("/v1/transparency")
async def transparency_log(request: Request, limit: int = 100, offset: int = 0):
    """
    Transparency audit log — SHA-256 hashes and metadata only.
    No plaintext prompts or responses are ever stored or returned.
    Requires ADMIN_API_KEY for access.
    """
    _require_admin(request)
    data = await entries(limit, offset)
    return JSONResponse({
        "total":              count(),
        "offset":             offset,
        "limit":              limit,
        "gateway_version":    GATEWAY_VERSION,
        "waf_rule_version":   WAF_RULE_VERSION,
        "config_fingerprint": CONFIG_FINGERPRINT,
        "entries":            data,
        "e2ee": {
            "enabled":            True,
            "pubkey_b64":         GW_PUBLIC_KEY_B64,
            "pubkey_fingerprint": GW_PUBLIC_KEY_FINGERPRINT,
            "alg":                "X25519-ECDH+HKDF-SHA256+AES-256-GCM",
        },
        "note":               "SHA-256 hashes only — no plaintext stored. E2EE available at /v1/e2ee/pubkey.",
    })