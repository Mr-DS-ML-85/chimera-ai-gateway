from __future__ import annotations

import asyncio
import re
import time
from typing import Dict, Optional

from core.config import REDIS_URL

_TTL     = 300
_LOCK    = asyncio.Lock()
_LOCAL:  Dict[str, float] = {}
_NONCE_RE = re.compile(r"^[A-Za-z0-9\-_]{1,256}$")

_redis_client: Optional[object] = None


async def init_redis() -> None:
    global _redis_client
    try:
        import redis.asyncio as aioredis  # type: ignore
        client = aioredis.from_url(
            REDIS_URL, decode_responses=True, socket_connect_timeout=3
        )
        await client.ping()
        _redis_client = client
        from core.logging_setup import logger
        logger.info("Redis nonce registry connected: %s", REDIS_URL)
    except Exception as exc:
        from core.logging_setup import logger
        logger.warning("Redis unavailable (%s) — in-memory nonce fallback", exc)


async def close_redis() -> None:
    if _redis_client is not None:
        await _redis_client.aclose()


async def register(nonce: str) -> bool:
    """Return True = fresh, False = replay."""
    if not _NONCE_RE.match(nonce):
        return False

    if _redis_client is not None:
        try:
            key    = f"chimera:nonce:v1:{nonce}"
            result = await _redis_client.set(key, "1", nx=True, ex=_TTL)
            return result is True
        except Exception as exc:
            from core.logging_setup import logger
            logger.warning("Redis nonce error, falling back: %s", exc)

    now = time.monotonic()
    async with _LOCK:
        expired = [k for k, exp in _LOCAL.items() if exp < now]
        for k in expired:
            del _LOCAL[k]
        if nonce in _LOCAL:
            return False
        _LOCAL[nonce] = now + _TTL
        return True


def local_count() -> int:
    return len(_LOCAL)