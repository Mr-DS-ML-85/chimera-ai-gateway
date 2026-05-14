# chimera/security/canary.py
from __future__ import annotations

import re
from typing import Any, List

CANARY_PATTERNS: List[re.Pattern] = [
    # OpenAI
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    # Groq  — gsk_ prefix (underscore is part of real keys)
    re.compile(r"\bgsk_[A-Za-z0-9_\-]{20,}\b"),
    # Google AIza
    re.compile(r"\bAIza[A-Za-z0-9_\-]{35,}\b"),
    # Known env-var names
    re.compile(
        r"\b(?:GROQ_API_KEY|GOOGLE_API_KEY|OPENROUTER_API_KEY|CF_API_TOKEN"
        r"|GITHUB_TOKEN|NVIDIA_NIM_API_KEY|A4F_API_KEY|CEREBRAS_API_KEY"
        r"|CHIMERA_API_KEY|ADMIN_API_KEY|CUSTOM_OPENAI_API_KEY"
        r"|HUGGINGFACE_API_KEY|MISTRAL_API_KEY|XAI_API_KEY"
        r"|DEEPSEEK_API_KEY|PERPLEXITY_API_KEY|FIREWORKS_API_KEY"
        r"|DEEPINFRA_API_KEY|SAMBANOVA_API_KEY|TOGETHER_API_KEY)\b"
    ),
    re.compile(r"\b(?:AWS_ACCESS_KEY|AWS_SECRET|AZURE_API_KEY)\b"),
]


def scan(text: str) -> bool:
    return any(p.search(text) for p in CANARY_PATTERNS)


def scrub(data: Any) -> Any:
    """Walk a parsed JSON tree and replace canary matches in-place."""
    import json
    serialised = json.dumps(data, default=str)
    if not scan(serialised):
        return data

    from core.logging_setup import logger
    logger.warning("Canary pattern in upstream response — scrubbing")

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            for pat in CANARY_PATTERNS:
                obj = pat.sub("[REDACTED]", obj)
            return obj
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(i) for i in obj]
        return obj

    return _walk(data)