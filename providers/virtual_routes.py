from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class RouteSpec:
    mode: str
    bucket: str  # "reasoning" or "non_reasoning"
    free_only: bool = False
    preferred_providers: Tuple[str, ...] = ()


def _chain(bucket: str, free_only: bool, mode: str) -> Tuple[str, ...]:
    if bucket == "reasoning":
        chain = (
            "openrouter",
            "groq",
            "cerebras",
            "google",
            "huggingface",
            "cloudflare",
            "nvidia",
            "ollama",
        )
    else:
        if mode == "fast":
            chain = (
                "groq",
                "nvidia",
                "cloudflare",
                "openrouter",
                "cerebras",
                "google",
                "huggingface",
                "ollama",
            )
        elif mode == "quality":
            chain = (
                "google",
                "openrouter",
                "cerebras",
                "groq",
                "cloudflare",
                "nvidia",
                "huggingface",
                "ollama",
            )
        else:
            chain = (
                "groq",
                "openrouter",
                "cloudflare",
                "nvidia",
                "google",
                "cerebras",
                "huggingface",
                "ollama",
            )

    return chain


def resolve_virtual_model(requested_model: str, reasoning_hint: bool = False) -> Optional[RouteSpec]:
    model = (requested_model or "").strip().lower()
    if not model:
        return None

    if model in {"reasoning", "non-reasoning", "fast", "quality", "balanced"}:
        bucket = "reasoning" if model == "reasoning" else "non_reasoning"
        return RouteSpec(
            mode=model,
            bucket=bucket,
            free_only=False,
            preferred_providers=_chain(bucket, False, model),
        )

    if not model.startswith("auto"):
        return None

    parts = [p for p in model.split(":") if p]
    tokens = set(parts[1:]) if len(parts) > 1 else set()

    free_only = "free" in tokens
    if "reasoning" in tokens:
        bucket = "reasoning"
    elif "non-reasoning" in tokens:
        bucket = "non_reasoning"
    else:
        bucket = "reasoning" if reasoning_hint else "non_reasoning"

    if "fast" in tokens:
        mode = "fast"
    elif "quality" in tokens:
        mode = "quality"
    elif "balanced" in tokens:
        mode = "balanced"
    else:
        mode = "auto"

    return RouteSpec(
        mode=model,
        bucket=bucket,
        free_only=free_only,
        preferred_providers=_chain(bucket, free_only, mode),
    )