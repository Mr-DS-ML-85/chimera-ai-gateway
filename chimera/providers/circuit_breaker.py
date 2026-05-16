from __future__ import annotations

import time
from typing import Any, Dict

from core.logging_setup import logger


class CircuitState:
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


_FAILURE_THRESH = 5
_OPEN_SECONDS   = 60
_PROBE_TIMEOUT  = 10


def default_cb_state() -> Dict[str, Any]:
    return {
        "cb_state":         CircuitState.CLOSED,
        "cb_failures":      0,
        "cb_opened_at":     0.0,
        "cb_last_probe_at": 0.0,
    }


def allow(name: str, s: Dict[str, Any]) -> bool:
    now = time.time()
    if s["cb_state"] == CircuitState.CLOSED:
        return True
    if s["cb_state"] == CircuitState.OPEN:
        if now - s["cb_opened_at"] >= _OPEN_SECONDS:
            s["cb_state"]         = CircuitState.HALF_OPEN
            s["cb_last_probe_at"] = now
            return True
        return False
    # HALF_OPEN
    if now - s["cb_last_probe_at"] >= _PROBE_TIMEOUT:
        s["cb_last_probe_at"] = now
        return True
    return False


def record_success(s: Dict[str, Any]) -> None:
    s["cb_state"]    = CircuitState.CLOSED
    s["cb_failures"] = 0


def record_failure(name: str, s: Dict[str, Any]) -> None:
    s["cb_failures"] += 1
    if s["cb_failures"] >= _FAILURE_THRESH:
        if s["cb_state"] != CircuitState.OPEN:
            logger.warning("Circuit breaker OPENED for '%s'", name)
        s["cb_state"]     = CircuitState.OPEN
        s["cb_opened_at"] = time.time()