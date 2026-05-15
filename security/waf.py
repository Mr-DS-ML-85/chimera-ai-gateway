# chimera/security/waf.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from chimera.core.config import ENABLE_WAF


def _waf_decode(text: str) -> str:
    """Multi-pass URL-decode + HTML-entity normalise + zero-width strip."""
    result = text
    for _ in range(3):
        try:
            decoded = unquote(result)
        except Exception:
            break
        if decoded == result:
            break
        result = decoded

    result = (
        result.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#x27;", "'")
        .replace("&#39;", "'")
        .replace("\x00", "")
    )
    return re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", result)


# IMPORTANT: Order matters — more specific patterns must come before general ones.
# NoSQL must precede SQL ($ prefix). XXE must precede path_traversal (<!DOCTYPE).
WAF_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # 1. XXE — must come before path_traversal (shares <! tokens)
    ("xxe", re.compile(
        r"(?:"
        r"<!ENTITY\s"
        r"|<!DOCTYPE[^>]*\["
        r"|SYSTEM\s+[\"'](?:file|http|ftp|php|expect)://"
        r")",
        re.IGNORECASE,
    )),

    # 2. NoSQL — must come before sql_injection ($-prefix operators)
    ("nosql_injection", re.compile(
        r"(?:"
        r"\$(?:where|gt|lt|gte|lte|ne|in|nin|or|and|not|nor|exists|type|mod|regex|text|near)\b"
        r"|\bdb\.\w+\.(?:find|update|remove|drop)\s*\("
        r")",
        re.IGNORECASE,
    )),

    # 3. SQL injection
    ("sql_injection", re.compile(
        r"(?:"
        r"\bUNION\b[\s\S]{0,40}\bSELECT\b"
        r"|\bDROP\b\s+\bTABLE\b|\bDELETE\b\s+\bFROM\b|\bINSERT\b\s+\bINTO\b"
        r"|\bEXEC(?:UTE)?\b\s*\(|\bxp_cmdshell\b"
        r"|\bOR\b[\s/\*]{0,10}['\"]?1['\"]?[\s/\*]{0,10}=[\s/\*]{0,10}['\"]?1"
        r"|\bAND\b[\s/\*]{0,10}['\"]?1['\"]?[\s/\*]{0,10}=[\s/\*]{0,10}['\"]?1"
        r"|--[\s]*$|;\s*--"
        r"|\bSLEEP\s*\(\d|\bBENCHMARK\s*\(|\bWAITFOR\s+DELAY\b|\bPG_SLEEP\s*\("
        r")",
        re.IGNORECASE | re.MULTILINE,
    )),

    # 4. XSS
    ("xss", re.compile(
        r"(?:"
        r"<\s*script[\s>]|<\s*iframe[\s>]"
        r"|<\s*img[^>]{0,200}on\w+\s*=|<\s*svg[^>]{0,200}on\w+\s*="
        r"|javascript\s*:|vbscript\s*:|data\s*:\s*text/html"
        r"|on(?:load|error|click|focus|blur|mouseover|keydown|keyup"
        r"|submit|input|change|dragstart|drop|paste)\s*="
        r"|<\s*(?:object|embed|link|meta|base)\b|expression\s*\("
        r")",
        re.IGNORECASE,
    )),

    # 5. Path traversal
    ("path_traversal", re.compile(
        r"(?:"
        r"\.\./|\.\.\\|\.\.%2f|\.\.%5c|%2e%2e[%/\\]|%252e%252e"
        r"|\.\.[\x00-\x1f]"
        r"|/etc/(?:passwd|shadow|hosts|crontab)"
        r"|\\windows\\system32"
        r")",
        re.IGNORECASE,
    )),

    # 6. Command injection
    ("cmd_injection", re.compile(
        r"(?:"
        r"[|;&`]\s*(?:rm|ls|cat|curl|wget|bash|sh|dash|python3?|perl|ruby"
        r"|php|nc\b|ncat|id\b|whoami|chmod|chown|kill|nmap)\b"
        r"|\$\([^)]{0,200}\)|`[^`]{0,200}`"
        r"|\beval\s+[\"'$]|\bexec\s+[\"'$]"
        r"|\$\{IFS\}|>\s*/dev/(?:null|tcp|udp)"
        r"|\bdd\s+if=|\bcrontab\s+-"
        r")",
        re.IGNORECASE,
    )),

    # 7. Template injection
    ("template_injection", re.compile(
        r"(?:"
        r"\{\{[\s\S]{0,200}?\}\}"
        r"|\$\{[\s\S]{0,200}?\}"
        r"|#\{[\s\S]{0,200}?\}"
        r"|<%[\s\S]{0,200}?%>"
        r"|\{%[\s\S]{0,200}?%\}"
        r")",
        re.DOTALL,
    )),

# 8. LDAP injection — requires actual LDAP operator context, not bare brackets
    ("ldap_injection", re.compile(
        r"(?:"
        r"\(\s*[|&]\s*\("              # nested grouping: (| or (&
        r"|\\{2,}\w{2,}"              # backslash-escaped 2+ chars: \cn \xo \00
        r"|[&|]\(\w+\)"                # LDAP filter ops: (&(uid=...) or |(cn=...)
        r")",
        re.IGNORECASE,
    )),

    # 9. Untrusted Deserialization
    ("untrusted_deserialization", re.compile(
        r"(?:"
        r"!!python/object"
        r"|gASV[A-Za-z0-9+/=]{4,}"
        r"|\bcos\n|\bpickle\.loads\b"
        r"|__reduce__|__globals__"
        r")",
        re.IGNORECASE,
    )),

    # 10. XML/Prompt Tag Injection — only fire on tags with a clear injection marker,
    # not on legitimate text containing short words in angle brackets.
    # Require: opening tag + non-whitespace + closing OR explicit tag keyword.
    ("xml_prompt_injection", re.compile(
        r"(?:"
        r"<\s*\w+[^>]*>[^<]+</\w+>"       # balanced XML/HTML tag pair
        r"|<!\w+"                          # CDATA, DOCTYPE, COMMENT start
        r"|<\?xml\s"                       # XML declaration
        r"|<\s*/\w+"                       # closing tag
        r")",
        re.IGNORECASE,
    )),

    # 11. Broken Access Control & Auth Token Tampering
    ("access_control_tampering", re.compile(
        r"(?:"
        r"[\"']alg[\"']\s*:\s*[\"']none[\"']"
        r"|bearer\s+eyJhbGciOiJub25lIn"
        r"|(?:\b(?:root|admin|superuser|godmode)\b\s*:\s*true)"
        r"|\bX-Original-URL\b|\bX-Rewrite-URL\b"
        r")",
        re.IGNORECASE,
    )),

    # 12. Mass Assignment Protection
    ("mass_assignment", re.compile(
        r"(?:"
        r"[\"'](?:is_admin|privileges|permissions|scope|tier|is_staff|internal_user)[\"']\s*:"
        r"|[\"']role[\"']\s*:\s*[\"'](?:admin|root|superuser)[\"']"
        r")",
        re.IGNORECASE,
    )),

    # 13. Cloud Metadata & SSRF String Injection
    ("cloud_metadata_ssrf", re.compile(
        r"(?:"
        r"169\.254\.169\.254"
        r"|2852039166"
        r"|0251\.0376\.0251\.0376"
        r"|0xa9fe09fe"
        r"|metadata\.google\.internal"
        r"|100\.100\.100\.200"
        r")",
        re.IGNORECASE,
    )),

    # 14. Server-Side Log Injection — requires \A (start of string) to avoid
    #     false-positives on greetings like "hi" or "hello" that contain
    #     valid text followed by a newline + valid words like "hi there\nHere"
    ("log_injection", re.compile(
        r"\A[\r\n]+(?:INFO|WARN|ERROR|CRITICAL|STATUS=200|ip=127\.0\.0\.1)",
        re.IGNORECASE,
    )),

    # 15. MiniMax API support — MiniMax only supports: text, image_url, video_url.
    #     Base64 images and audio content cause HTTP 400 from MiniMax.
    #     When routing to minimax, strip unsupported content types.
    #     (Add minimax provider below once API key is configured.)
    ("minimax_unsupported", re.compile(
        r"__MINIMAX_STRIP_BASE64__",  # placeholder — active when minimax added
        re.IGNORECASE,
    )),
]


def scan(text: str) -> Optional[str]:
    """Scan decoded text. Returns attack category name or None."""
    if not ENABLE_WAF:
        return None
    decoded = _waf_decode(text)
    for category, pattern in WAF_PATTERNS:
        if pattern.search(decoded):
            return category
    return None


def extract_text_content(body: Dict[str, Any]) -> List[str]:
    """Pull every raw string from a chat body (handles list-type content)."""
    texts: List[str] = []
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    t = part.get("text", "")
                    if t:
                        texts.append(t)
    if isinstance(body.get("system"), str):
        texts.append(body["system"])
    return texts


def scan_body(body: Dict[str, Any]) -> Optional[str]:
    """Scan raw content strings first, then serialised body."""
    import json
    for raw in extract_text_content(body):
        hit = scan(raw)
        if hit:
            return hit
    return scan(json.dumps(body))