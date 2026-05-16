from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from providers.capabilities import ProviderCaps
from providers.catalogue import PROVIDER_ENABLED
from providers.circuit_breaker import (
    CircuitState, allow as cb_allow,
    default_cb_state, record_failure as cb_fail, record_success as cb_ok,
)
from core.logging_setup import logger


class RateLimitTracker:
    _EMA = 0.2

    def __init__(self) -> None:
        self._lock  = asyncio.Lock()
        self._state: Dict[str, Dict[str, Any]] = defaultdict(self._default)

    @staticmethod
    def _default() -> Dict[str, Any]:
        base = {
            "rpm": 0, "rpd": 0, "tpd": 0,
            "rpm_ts":          time.time(),
            "rpd_date":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "exhausted_until": 0.0,
            "ema_latency_ms":  0.0,
            "total_requests":  0,
            "total_errors":    0,
        }
        base.update(default_cb_state())
        return base

    def _reset_window(self, name: str) -> None:
        now   = time.time()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        s     = self._state[name]
        if now - s["rpm_ts"] >= 60.0:
            s["rpm"] = 0; s["rpm_ts"] = now
        if s["rpd_date"] != today:
            s["rpd"] = 0; s["tpd"] = 0
            s["rpd_date"] = today; s["exhausted_until"] = 0.0

    async def is_available(self, provider) -> bool:
        from providers.catalogue import PROVIDER_CATALOGUE
        if isinstance(provider, str):
            name = provider
            provider = next((p for p in PROVIDER_CATALOGUE if p["name"] == name), {})
        else:
            name = provider["name"]
        if not PROVIDER_ENABLED.get(name, True):
            return False
        async with self._lock:
            self._reset_window(name)
            s = self._state[name]
            if not cb_allow(name, s):           return False
            if s["exhausted_until"] > time.time(): return False
            return (
                (provider["rpm_limit"] == 0 or s["rpm"] < provider["rpm_limit"]) and
                (provider["rpd_limit"] == 0 or s["rpd"] < provider["rpd_limit"]) and
                (provider["tpd_limit"] == 0 or s["tpd"] < provider["tpd_limit"])
            )

    async def record_success(
        self, name: str, tokens: int = 0, latency_ms: float = 0.0
    ) -> None:
        async with self._lock:
            self._reset_window(name)
            s = self._state[name]
            s["rpm"] += 1; s["rpd"] += 1; s["tpd"] += tokens; s["total_requests"] += 1
            s["ema_latency_ms"] = (
                latency_ms if s["ema_latency_ms"] == 0.0
                else self._EMA * latency_ms + (1 - self._EMA) * s["ema_latency_ms"]
            )
            cb_ok(s)

    async def record_rate_limited(self, name: str) -> None:
        """
        Called on HTTP 429. Sets a short cooldown (30 s) without tripping
        the circuit breaker — 429 means 'slow down', not 'provider broken'.
        """
        async with self._lock:
            s = self._state[name]
            # Only extend cooldown if not already locked out longer
            new_until = time.time() + 30.0
            if new_until > s["exhausted_until"]:
                s["exhausted_until"] = new_until

    async def record_failure(self, name: str, until_tomorrow: bool = False) -> None:
        async with self._lock:
            s = self._state[name]
            s["total_errors"] += 1
            cb_fail(name, s)
            if until_tomorrow:
                tomorrow = (
                    datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    + timedelta(days=1)
                )
                s["exhausted_until"] = tomorrow.timestamp()
            else:
                s["exhausted_until"] = time.time() + 60.0

    async def get_ema_latency(self, name: str) -> float:
        async with self._lock:
            return self._state[name]["ema_latency_ms"]

    async def get_usage(self) -> Dict[str, Any]:
        async with self._lock:
            now = time.time()
            return {
                name: {
                    "rpm":            s["rpm"],
                    "rpd":            s["rpd"],
                    "tpd":            s["tpd"],
                    "exhausted":      s["exhausted_until"] > now,
                    "ema_latency_ms": round(s["ema_latency_ms"], 2),
                    "total_requests": s["total_requests"],
                    "total_errors":   s["total_errors"],
                    "circuit_state":  s["cb_state"],
                    "enabled":        PROVIDER_ENABLED.get(name, True),
                }
                for name, s in self._state.items()
            }


# Singleton
rate_limiter = RateLimitTracker()