# keys/virtual_keys.py — v8.3.4
# Fix: restore create(), update(), delete() methods that admin routes require.
# Root cause: previous version stripped CRUD functions, leaving only read-only
# resolve/rpm_ok helpers, causing AttributeError on POST /v1/admin/keys.
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import time
from typing import Any, Deque, Dict, List, Optional
from collections import defaultdict, deque

_LOCK        = asyncio.Lock()
_CACHE_LOCK  = asyncio.Lock()

_KEYS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "virtual_keys.json")
)

# key_id → full record dict
STORE: Dict[str, Dict[str, Any]] = {}
_LOADED = False

# key_id → deque of monotonic timestamps (for RPM)
_USAGE: Dict[str, deque] = defaultdict(deque)


# ── Persistence ───────────────────────────────────────────────────────────────

def _save() -> None:
    """Write STORE to disk. Call while holding _LOCK."""
    with open(_KEYS_FILE, "w", encoding="utf-8") as fh:
        json.dump(list(STORE.values()), fh, indent=2, ensure_ascii=False)


async def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    async with _CACHE_LOCK:
        if _LOADED:
            return
        if os.path.exists(_KEYS_FILE):
            try:
                with open(_KEYS_FILE, encoding="utf-8") as fh:
                    records = json.load(fh)
                if isinstance(records, list):
                    for r in records:
                        kid = r.get("key_id", "")
                        if kid:
                            STORE[kid] = r
            except Exception as exc:
                import logging
                logging.getLogger("chimera").warning(
                    "virtual_keys: load failed: %s", exc
                )
        _LOADED = True


def reload_keys() -> None:
    global _LOADED
    STORE.clear()
    _LOADED = False


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create(
    name: str,
    allowed_models: List[str],
    allowed_providers: List[str],
    rpm_limit: int,
    expires_at: Optional[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new virtual key, persist it, and return the record (with token)."""
    await _ensure_loaded()
    token   = "sk-vk-" + secrets.token_hex(24)
    key_id  = "vk_" + secrets.token_hex(8)
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    record: Dict[str, Any] = {
        "key_id":            key_id,
        "name":              name,
        "token":             token,       # returned once; not stored in plaintext after first write
        "key_hash":          key_hash,
        "enabled":           True,
        "allowed_models":    allowed_models or ["*"],
        "allowed_providers": allowed_providers or [],
        "rpm_limit":         rpm_limit,
        "expires_at":        expires_at,
        "metadata":          metadata or {},
        "created_at":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    async with _LOCK:
        STORE[key_id] = record
        _save()

    # Return a copy; strip key_hash from the response
    resp = {k: v for k, v in record.items() if k != "key_hash"}
    return resp


async def update(key_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply partial updates to an existing key and persist."""
    await _ensure_loaded()
    async with _LOCK:
        rec = STORE.get(key_id)
        if rec is None:
            raise KeyError(key_id)
        # Never allow token/key_hash to be updated via PATCH
        for forbidden in ("token", "key_hash", "key_id", "created_at"):
            updates.pop(forbidden, None)
        rec.update(updates)
        _save()
    return {k: v for k, v in rec.items() if k not in ("token", "key_hash")}


async def delete(key_id: str) -> None:
    """Remove a key from the store and persist."""
    await _ensure_loaded()
    async with _LOCK:
        STORE.pop(key_id, None)
        _save()


# ── Auth / Rate-limit helpers ─────────────────────────────────────────────────

async def resolve_vk(token: str) -> Optional[Dict[str, Any]]:
    """Return key record for a bearer token, or None if not found/disabled."""
    await _ensure_loaded()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    for rec in STORE.values():
        if rec.get("key_hash") == token_hash or rec.get("token") == token:
            if not rec.get("enabled", True):
                return None
            exp = rec.get("expires_at")
            if exp and exp < time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()):
                return None
            return rec
    return None


async def rpm_ok(key_id: str, rpm_limit: int) -> bool:
    if not rpm_limit:
        return True
    now = time.monotonic()
    async with _LOCK:
        dq = _USAGE[key_id]
        while dq and dq[0] < now - 60.0:
            dq.popleft()
        if len(dq) >= rpm_limit:
            return False
        dq.append(now)
        return True


def allows_model(rec: Dict[str, Any], model: str) -> bool:
    allowed = rec.get("allowed_models", [])
    return not allowed or "*" in allowed or model in allowed


# ── Compat aliases ────────────────────────────────────────────────────────────
def load() -> None:
    pass   # lazy-loaded on first request

resolve = resolve_vk
