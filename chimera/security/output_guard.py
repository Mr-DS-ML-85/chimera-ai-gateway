from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

OutputPattern = Tuple[str, re.Pattern[str], str]

OUTPUT_PATTERNS: List[OutputPattern] = [
    (
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
        "[OPENAI_KEY]",
    ),
    (
        "groq_key",
        re.compile(r"\bgsk_[A-Za-z0-9_\-]{20,}\b"),
        "[GROQ_KEY]",
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[A-Za-z0-9_\-]{35,}\b"),
        "[GOOGLE_API_KEY]",
    ),
    (
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        "[GH_TOKEN]",
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
        "[SLACK_TOKEN]",
    ),
    (
        "aws_access_key_id",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[AWS_ACCESS_KEY_ID]",
    ),
    (
        "bearer_token",
        re.compile(
            r"(?i)\bBearer\s+[A-Za-z0-9._~+/=\-]{16,}\b"
        ),
        "Bearer [BEARER_TOKEN]",
    ),
    (
        "jwt",
        re.compile(
            r"\beyJ[a-zA-Z0-9_\-]{8,}\.[a-zA-Z0-9._\-]{8,}\.[a-zA-Z0-9._\-]{8,}\b"
        ),
        "[JWT]",
    ),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.S,
        ),
        "[PRIVATE_KEY]",
    ),
]


def screen_text(text: str) -> Tuple[str, Dict[str, int]]:
    counts: Dict[str, int] = {}

    out = text

    for label, pattern, replacement in OUTPUT_PATTERNS:
        out, n = pattern.subn(replacement, out)

        if n:
            counts[label] = counts.get(label, 0) + n

    return out, counts


def screen_json(data: Any) -> Tuple[Any, Dict[str, int]]:
    total: Dict[str, int] = {}

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            cleaned, counts = screen_text(obj)

            for k, v in counts.items():
                total[k] = total.get(k, 0) + v

            return cleaned

        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}

        if isinstance(obj, list):
            return [_walk(v) for v in obj]

        return obj

    return _walk(data), total