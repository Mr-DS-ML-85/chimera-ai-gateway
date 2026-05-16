from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from crypto.e2ee import GW_PUBLIC_KEY_B64, GW_PUBLIC_KEY_FINGERPRINT

router = APIRouter()


@router.get("/v1/e2ee/pubkey")
async def e2ee_pubkey():
    return JSONResponse({
        "public_key_b64": GW_PUBLIC_KEY_B64,
        "fingerprint":    GW_PUBLIC_KEY_FINGERPRINT,
        "alg":            "X25519-ECDH+HKDF-SHA256+AES-256-GCM",
        "hkdf_info":      "chimera-e2ee-v1",
        "warning":        "Key regenerated on every process restart.",
    })