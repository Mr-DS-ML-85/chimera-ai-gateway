"""Direct Anthropic API client — used when ANTHROPIC_API_KEY is set.
When not set, the gateway translates Anthropic→OpenAI format instead.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from core.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    REQUEST_TIMEOUT_SECS,
)
from core.logging_setup import logger


def is_configured() -> bool:
    return bool(
        ANTHROPIC_API_KEY
        and str(ANTHROPIC_API_KEY).strip()
        and ANTHROPIC_BASE_URL
        and str(ANTHROPIC_BASE_URL).strip()
    )


def _base_url() -> str:
    base = str(ANTHROPIC_BASE_URL).strip().rstrip("/")
    return base


def _headers(extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": str(ANTHROPIC_API_KEY).strip(),
        "anthropic-version": "2023-06-01",
    }

    # Let caller add headers, but never allow them to overwrite auth/version.
    if extra_headers:
        safe_extra = {
            k: v
            for k, v in extra_headers.items()
            if k.lower() not in {"x-api-key", "anthropic-version", "content-type"}
        }
        headers.update(safe_extra)

    return headers


async def call_messages(
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Call Anthropic /v1/messages directly."""
    url = f"{_base_url()}/v1/messages"
    headers = _headers(extra_headers)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECS) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def stream_messages(
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> AsyncGenerator[str, None]:
    """Call Anthropic /v1/messages with streaming, yield SSE lines."""
    url = f"{_base_url()}/v1/messages"
    headers = _headers(extra_headers)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECS * 2) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line + "\n"


async def count_tokens(body: Dict[str, Any]) -> Dict[str, Any]:
    """Call Anthropic /v1/messages/count_tokens."""
    url = f"{_base_url()}/v1/messages/count_tokens"
    headers = _headers()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECS) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()