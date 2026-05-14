from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Tuple

_RATES: Dict[str, Tuple[float, float]] = {
    "groq":        (0.05,  0.08),
    "google":      (0.15,  0.60),
    "openrouter":  (0.00,  0.00),
    "cloudflare":  (0.00,  0.00),
    "github":      (0.00,  0.00),
    "nvidia":      (0.20,  0.20),
    "a4f":         (0.10,  0.20),
    "cerebras":    (0.10,  0.10),
    "pollinations":(0.00,  0.00),
    "ollama":      (0.00,  0.00),
    "custom":      (0.00,  0.00),
    "huggingface": (0.20,  0.20),
    "sambanova":   (0.40,  0.40),
    "together":    (0.20,  0.90),
    "llm7":        (0.00,  0.00),
    "mistral":     (0.30,  0.90),
    "xai":         (3.00, 15.00),
    "deepseek":    (0.14,  0.28),
    "perplexity":  (1.00,  1.00),
    "fireworks":   (0.20,  0.80),
    "deepinfra":   (0.13,  0.40),
}

_LOCK:    asyncio.Lock          = asyncio.Lock()
COST_ACC: Dict[str, float]     = defaultdict(float)
TOKEN_ACC: Dict[str, int]      = defaultdict(int)


def estimate(provider: str, in_t: int, out_t: int) -> float:
    ir, or_ = _RATES.get(provider, (0.0, 0.0))
    return (in_t * ir + out_t * or_) / 1_000_000


async def record(provider: str, in_t: int, out_t: int) -> float:
    cost = estimate(provider, in_t, out_t)
    async with _LOCK:
        COST_ACC[provider]  += cost
        TOKEN_ACC[provider] += in_t + out_t
    return cost


async def snapshot() -> Tuple[Dict[str, float], Dict[str, int]]:
    async with _LOCK:
        return dict(COST_ACC), dict(TOKEN_ACC)