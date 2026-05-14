from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any, Dict

_SECRET: bytes = secrets.token_bytes(32)


def seal(body: Dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hmac.new(_SECRET, canonical.encode(), digestmod=hashlib.sha256).hexdigest()


def zero() -> None:
    """Zero the secret on shutdown (best-effort)."""
    global _SECRET
    _SECRET = b"\x00" * len(_SECRET)