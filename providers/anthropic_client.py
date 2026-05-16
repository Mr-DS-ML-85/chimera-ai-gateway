"""Direct Anthropic API client — used when ANTHROPIC_API_KEY is set.
   When not set, the gateway translates Anthropic→OpenAI format instead."""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from chimera.core.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    REQUEST_TIMEOUT_SECS,
)
from chimera.core.logging_setup import logger


def is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL)


async def call_messages(
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Call Anthropic /v1/messages directly."""
    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        **(extra_headers or {}),
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECS) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def stream_messages(
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> AsyncGenerator[str, None]:
    """Call Anthropic /v1/messages with streaming, yield SSE lines."""
    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Transfer-Encoding": "chunked",
        **(extra_headers or {}),
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECS * 2) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line + "\n"


async def count_tokens(body: Dict[str, Any]) -> Dict[str, Any]:
    """Call Anthropic /v1/messages/count_tokens."""
    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages/count_tokens"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()