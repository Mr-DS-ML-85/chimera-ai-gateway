from __future__ import annotations

import asyncio
import hashlib
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional

from core.config import GATEWAY_VERSION, TRANSPARENCY_LOG_CAP, WAF_RULE_VERSION

# Computed by api/app.py after all rule modules are loaded
CONFIG_FINGERPRINT: str = ""

_LOG:  Deque[Dict[str, Any]] = deque(maxlen=TRANSPARENCY_LOG_CAP)
_SEQ:  int                    = 0
_LOCK: asyncio.Lock           = asyncio.Lock()


async def append(
    provider:    str,
    model:       str,
    req_body:    Dict[str, Any],
    resp_body:   Any,
    status:      int,
    cost_usd:    float = 0.0,
    pii_counts:  Optional[Dict[str, int]] = None,
    vk_id:       Optional[str] = None,
) -> None:
    global _SEQ
    async with _LOCK:
        _SEQ += 1
        rq = hashlib.sha256(
            json.dumps(req_body,  sort_keys=True, default=str).encode()
        ).hexdigest()
        rs = hashlib.sha256(
            json.dumps(resp_body, sort_keys=True, default=str).encode()
        ).hexdigest()
        _LOG.append({
            "seq":                _SEQ,
            "ts":                 datetime.now(timezone.utc).isoformat(),
            "provider":           provider,
            "model":              model,
            "status":             status,
            "req_sha256":         rq,
            "res_sha256":         rs,
            "cost_usd":           round(cost_usd, 8),
            "gateway_version":    GATEWAY_VERSION,
            "waf_rule_version":   WAF_RULE_VERSION,
            "config_fingerprint": CONFIG_FINGERPRINT,
            "pii_redacted":       pii_counts or {},
            "virtual_key_id":     vk_id,
            "chain_sha256":       hashlib.sha256(
                f"{_SEQ - 1}:{rq}:{rs}:{GATEWAY_VERSION}".encode()
            ).hexdigest(),
        })


def count() -> int:
    return len(_LOG)


async def entries(limit: int = 100, offset: int = 0) -> list:
    async with _LOCK:
        return list(_LOG)[offset: offset + limit]