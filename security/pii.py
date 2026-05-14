# chimera/security/pii.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.config import ENABLE_PII_REDACTION


# IMPORTANT: Order matters.
# UK_NIN must come before IBAN because the IBAN regex is broad enough
# to match NIN-like patterns.  Credit card must allow optional spaces/dashes.
PII_PATTERNS: List[Tuple[str, re.Pattern, str]] = [

    # ── Credit / debit card (13–19 digits, optional space/dash separators) ──
    (
        "credit_card",
        re.compile(
            r"\b(?:"
            # Visa (13 or 16 digits, with optional 4-digit groups separated by space/dash)
            r"4[0-9]{3}(?:[-\s]?[0-9]{4}){2,3}"
            r"|"
            # Mastercard 5xxx or 2xxx
            r"(?:5[1-5][0-9]{2}|2(?:2[2-9][1-9]|[3-6][0-9]{2}|7[01][0-9]|720))"
            r"(?:[-\s]?[0-9]{4}){3}"
            r"|"
            # Amex 15 digits (4-6-5 grouping)
            r"3[47][0-9]{2}(?:[-\s]?[0-9]{6}[-\s]?[0-9]{5}|[0-9]{13})"
            r"|"
            # Discover
            r"6(?:011|5[0-9]{2})(?:[-\s]?[0-9]{4}){3}"
            r"|"
            # JCB
            r"(?:2131|1800|35[0-9]{3})(?:[-\s]?[0-9]{4}){2,3}"
            r")\b",
            re.ASCII,
        ),
        "[CREDIT_CARD]",
    ),

    # ── UK National Insurance Number (must come BEFORE IBAN) ────────────────
    (
        "uk_nin",
        re.compile(
            r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)"   # invalid prefix exclusion
            r"[A-CEGHJ-PR-TW-Z]{1}"          # first letter
            r"[A-CEGHJ-NPR-TW-Z]{1}"         # second letter
            r"[0-9]{6}"                       # 6 digits
            r"[ABCD ]?\b",                    # optional suffix
        ),
        "[UK_NIN]",
    ),

    # ── IBAN (after UK_NIN to avoid false match) ─────────────────────────────
    (
        "iban",
        re.compile(
            r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}\b",
            re.ASCII,
        ),
        "[IBAN]",
    ),

    # ── US Social Security Number ────────────────────────────────────────────
    (
        "ssn",
        re.compile(r"\b(?!000|666|9\d\d)\d{3}[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b", re.ASCII),
        "[SSN]",
    ),

    # ── Email address ────────────────────────────────────────────────────────
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL]",
    ),

    # ── Phone numbers ────────────────────────────────────────────────────────
    (
        "phone",
        re.compile(
            r"(?:"
            # NANP: (555) 867-5309 or 555-867-5309 or +1 555 867 5309
            r"\+?1?\s*[-.]?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]\d{4}"
            r"|"
            # International: +44 20 7946 0958
            r"\+[1-9]\d{0,2}[\s.-]?\(?\d{1,4}\)?(?:[\s.\-]\d{2,4}){2,4}"
            r"|"
            # 00-prefix dialling
            r"00[1-9]\d{6,14}"
            r")",
        ),
        "[PHONE]",
    ),

    # ── Passport (keyword + alphanumeric) ────────────────────────────────────
    (
        "passport",
        re.compile(
            r"\bpassport\s*(?:number|no\.?|num\.?|#)?\s*[:\-]?\s*([A-Z0-9]{6,9})\b",
            re.IGNORECASE,
        ),
        "[PASSPORT]",
    ),

    # ── Private IPv4 addresses ───────────────────────────────────────────────
    (
        "ipv4_private",
        re.compile(
            r"\b(?:"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r")\b",
            re.ASCII,
        ),
        "[PRIVATE_IP]",
    ),
]

# Fast pre-check — skip expensive patterns when no PII indicators present
_QUICK = re.compile(r"[@\+\d]")


def redact(text: str) -> Tuple[str, Dict[str, int]]:
    """Return (redacted_text, {label: count})."""
    if not ENABLE_PII_REDACTION or not _QUICK.search(text):
        return text, {}
    counts: Dict[str, int] = {}
    result = text
    for label, pattern, token in PII_PATTERNS:
        new, n = pattern.subn(token, result)
        if n:
            counts[label] = counts.get(label, 0) + n
            result = new
    return result, counts


def redact_response(data: Any) -> Tuple[Any, Dict[str, int]]:
    """Walk parsed JSON tree and redact PII from every string value."""
    total: Dict[str, int] = {}

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            scrubbed, counts = redact(obj)
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            return scrubbed
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(i) for i in obj]
        return obj

    return _walk(data), total