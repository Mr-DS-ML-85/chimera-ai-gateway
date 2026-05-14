from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from providers.auto_models import DISCOVERED, effective_models
from providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from keys.virtual_keys import allows_model, resolve as resolve_vk
from core.config import CHIMERA_API_KEY

router = APIRouter()


async def _light_auth(request) -> Optional[Dict[str, Any]]:
    """Just resolve virtual key — public endpoint if no master key set."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    return await resolve_vk(token)


@router.get("/v1/models")
async def list_models(request: Request):
    vk = await _light_auth(request)
    now = int(time.time())
    combined: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for p in PROVIDER_CATALOGUE:
        if not PROVIDER_ENABLED.get(p["name"], True):
            continue
        source = "live" if p["name"] in DISCOVERED else "static"
        for bucket in ("non_reasoning", "reasoning"):
            for m in effective_models(p, bucket):
                if vk and not allows_model(vk, m):
                    continue
                key = f"{p['name']}/{m}"
                if key in seen:
                    continue
                seen.add(key)
                combined.append({
                    "id":       m,
                    "object":   "model",
                    "created":  now,
                    "owned_by": p["name"],
                    "provider": p["name"],
                    "type":     bucket,
                    "source":   source,
                })

    return JSONResponse({"object": "list", "data": combined, "total": len(combined)})