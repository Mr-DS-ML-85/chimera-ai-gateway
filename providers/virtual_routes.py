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
        if free_only:
            chain = (
                "openrouter",
                "nvidia",
                "deepseek",
                "cloudflare",
                "huggingface",
            )
        else:
            chain = (
                "openrouter",
                "groq",
                "nvidia",
                "deepseek",
                "google",
                "cloudflare",
                "huggingface",
                "ollama",
            )
    else:
        if mode == "fast":
            if free_only:
                chain = (
                    "groq",
                    "openrouter",
                    "cloudflare",
                    "nvidia",
                    "huggingface",
                )
            else:
                chain = (
                    "groq",
                    "openrouter",
                    "cloudflare",
                    "nvidia",
                    "huggingface",
                    "ollama",
                )
        elif mode == "quality":
            if free_only:
                chain = (
                    "openrouter",
                    "google",
                    "groq",
                    "cloudflare",
                    "nvidia",
                    "deepseek",
                    "huggingface",
                )
            else:
                chain = (
                    "openrouter",
                    "google",
                    "groq",
                    "cloudflare",
                    "nvidia",
                    "deepseek",
                    "huggingface",
                    "ollama",
                )
        else:  # balanced / auto
            if free_only:
                chain = (
                    "groq",
                    "openrouter",
                    "cloudflare",
                    "nvidia",
                    "google",
                    "deepseek",
                    "huggingface",
                )
            else:
                chain = (
                    "groq",
                    "openrouter",
                    "cloudflare",
                    "nvidia",
                    "google",
                    "deepseek",
                    "huggingface",
                    "ollama",
                )

    return chain


def resolve_virtual_model(requested_model: str, reasoning_hint: bool = False) -> Optional[RouteSpec]:
    model = (requested_model or "").strip().lower()
    if not model:
        return None

    # Direct aliases without :auto prefix
    if model in {"reasoning", "non-reasoning", "fast", "quality", "balanced"}:
        bucket = "reasoning" if model == "reasoning" else "non_reasoning"
        return RouteSpec(
            mode=model,
            bucket=bucket,
            free_only=False,
            preferred_providers=_chain(bucket, False, model),
        )

    # Free variants of direct aliases
    if model in {"reasoning:free", "non-reasoning:free", "fast:free", "quality:free", "balanced:free"}:
        base = model.replace(":free", "")
        bucket = "reasoning" if base == "reasoning" else "non_reasoning"
        return RouteSpec(
            mode=model,
            bucket=bucket,
            free_only=True,
            preferred_providers=_chain(bucket, True, base),
        )

    # ── Legacy /v1/ shorthand aliases ───────────────────────────────────────────
    # These allow callers to use short forms like "auto" alone (no colon)
    # and match the virtual route patterns users expect from Open WebUI.
    # Map to the full "auto:..." semantics.
    if model == "auto":
        # Default: non-reasoning (fast by default)
        return RouteSpec(
            mode="auto",
            bucket="non_reasoning",
            free_only=False,
            preferred_providers=_chain("non_reasoning", False, "fast"),
        )

    if model == "auto:free":
        return RouteSpec(
            mode="auto:free",
            bucket="non_reasoning",
            free_only=True,
            preferred_providers=_chain("non_reasoning", True, "fast"),
        )

    if model == "auto:reasoning":
        return RouteSpec(
            mode="auto:reasoning",
            bucket="reasoning",
            free_only=False,
            preferred_providers=_chain("reasoning", False, "auto"),
        )

    if model == "auto:non-reasoning":
        return RouteSpec(
            mode="auto:non-reasoning",
            bucket="non_reasoning",
            free_only=False,
            preferred_providers=_chain("non_reasoning", False, "auto"),
        )

    if model == "auto:free:reasoning":
        return RouteSpec(
            mode="auto:free:reasoning",
            bucket="reasoning",
            free_only=True,
            preferred_providers=_chain("reasoning", True, "auto"),
        )

    if model == "auto:free:non-reasoning":
        return RouteSpec(
            mode="auto:free:non-reasoning",
            bucket="non_reasoning",
            free_only=True,
            preferred_providers=_chain("non_reasoning", True, "auto"),
        )

    if not model.startswith("auto"):
        return None

    parts = [p for p in model.split(":") if p]
    tokens = set(parts[1:]) if len(parts) > 1 else set()

    free_only = "free" in tokens
    if "reasoning" in tokens:
        bucket = "reasoning"
    elif "non-reasoning" in tokens or "nonreasoning" in tokens:
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