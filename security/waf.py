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


# ── XSS safe-verb allowlist ─────────────────────────────────────────────────
_XSS_PATTERN = re.compile(
    r"""(?:"""
    r"""<script[\s>]|<iframe[\s>]"""
    r"""|<svg[^>]{0,100}>\s*<script"""
    r"""|<img[^>]{0,200}on\w+\s*="""
    r"""|<svg[^>]{0,200}on\w+\s*="""
    r"""|<body[^>]{0,200}on\w+\s*="""
    r"""|<input[^>]{0,200}on\w+\s*="""
    r"""|<form[^>]{0,200}on\w+\s*="""
    r"""|<marquee[^>]{0,100}on\w+\s*="""
    r"""|<video[^>]{0,200}on\w+\s*="""
    r"""|<audio[^>]{0,200}on\w+\s*="""
    r"""|<details[^>]{0,200}on\w+\s*="""
    r"""|<meta[^>]{0,200}on\w+\s*="""
    r"""|<svg\s+on\w+\s*="""
    r"""|javascript\s*:[^s]"""
    r"""|vbscript\s*:[^s]"""
    r"""|data\s*:\s*text/html"""
    r"""|<object[^>]{0,100}data\s*="""
    r"""|<embed[^>]{0,100}src\s*="""
    r"""|<link[^>]{0,100}href\s*="""
    r"""|<base[^>]{0,100}href\s*="""
    r"""|<style[^>]{0,100}@import"""
    r"""|<iframe[^>]{0,100}src\s*=["']javascript:"""
    r"""|<meta[^>]{0,100}http-equiv\s*="""
    r"""|expression\s*\("""
    r""")""",
    re.IGNORECASE,
)
_XSS_SAFE_VERBS = re.compile(
    r"""(?i)\b(explain|what\s+is|learn\s+about|tell\s+me|show\s+me|"""
    r"""example\s+of|demonstrate|describe|illustrate|teach\s+me|"""
    r"""how\s+to\s+use|how\s+does|in\s+html|using\s+html|in\s+xml|using\s+xml|"""
    r"""in\s+javascript|using\s+javascript|in\s+css|using\s+css|"""
    r"""for\s+(?:example|demonstration|learning))\s*(?:tag|element|attribute|"""
    r"""syntax|code|script|iframe|img|object|embed|link|base|meta|style)\b"""
)
# Generic safe pattern for math/bitwise pipe operators
_XSS_SAFE = re.compile(
    r"""(?i)\b(and|or|add|del|set|get|put|val|ref|idx|key|ids?|list|"""
    r"""map|arr|foo|bar|baz|nums?|items?|names?|ids?|rows?|cols?|"""
    r"""path|file|dir|node|data|payload|body|result|response|"""
    r"""x|y|xy|x1|x2|x3|y1|y2|a|b|c|d|e|f|g|h|i|j|k|l|m|n|"""
    r"""num|val|cnt|sum|prod|min|max|avg|std|point|coord|vector|matrix|"""
    r"""col|row|cel|ent|obj|ref|key|uri|loc|pos|dim|size)\s*\|"""
    r"""|\]\s*\|"""
    r"""|\|\s*\["""
    r"""|\(?\s*\|\s*\d"""
    r"""|\)\s*\|"""
    r"""|\|\s*\("""
    r"""|^\s*\|"""
    r"""|\b\d+\s*\|\s*\d+\b"""
    r"""|\[\d+\s*\|\s*\d+\]"""
    r"""|\(\d+\s*\|\s*\d+\)"""
    r"""|[A-Za-z_][A-Za-z0-9_]*\s*\|\s*[A-Za-z_][A-Za-z0-9_]*"""
    r"""|^\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\|"""
)


def _is_safe_xss(text: str) -> bool:
    return bool(_XSS_SAFE_VERBS.search(text)) or bool(_XSS_SAFE.search(text))


# ── LDAP injection safe-pattern allowlist ───────────────────────────────────
_LDAP_INJECTION = re.compile(
    r"""(?:"""
    r"""\(\s*[&|]"""
    r"""|[&|]\s*\("""
    r"""|[&|!]\s*\w+\s*="""
    r"""|\\{2,}\w{2,}"""
    r""")""",
    re.IGNORECASE,
)


def _is_safe_ldap(text: str) -> bool:
    return bool(_XSS_SAFE.search(text))


# ── Path traversal safe-pattern allowlist ───────────────────────────────────
_PATH_SAFE = re.compile(
    r"""(?i)\b(path|file|dir|src|loc|location|uri|url|link|href|"""
    r"""ref|reference|route|dest|target|folder|folder_path|"""
    r"""workdir|root|base|directory|pathname|path_|filepath)\s*[:=]\s*\\"""
    r"""|^\s*\\"""
    r"""|[A-Za-z_][A-Za-z0-9_]*\s*=\s*\\"""
    r"""|\s=\s*\\\\"""
)
_PATH_TRAVERSAL = re.compile(
    r"""(?:"""
    r"""\.\./|\.\.\\|\.\.%2f|\.\.%5c|%2e%2e[%/\\]|%252e%252e"""
    r"""|\.\.[\x00-\x1f]"""
    r"""|/etc/(?:passwd|shadow|hosts|crontab)"""
    r"""|\\windows\\system32"""
    r""")""",
    re.IGNORECASE,
)


def _is_safe_path(text: str) -> bool:
    return bool(_PATH_SAFE.search(text))


# ── Template injection safe-pattern allowlist ───────────────────────────────
_TEMPLATE_SAFE = re.compile(
    r"""(?i)\b(use|set|create|make|show|display|render|print|output|"""
    r"""example|demo|sample|placeholder|variable|template|"""
    r"""name|user|item|key|value|data|payload|body|result|msg|message)\s*\{\{"""
)
_TEMPLATE_INJECTION = re.compile(
    r"""(?:"""
    r"""\{\{.{0,30}?\.\w+"""
    r"""|\{\{.{0,30}?_"""
    r"""|\{\{[\s\S]{0,50}?__"""
    r"""|\$\{[\s\S]{0,50}?\$\{"""
    r"""|#\{[\s\S]{0,50}?#\{"""
    r"""|<%[\s\S]{0,50}?<%"""
    r"""|\{%[\s\S]{0,50}?\{%"""
    r"""|\{\{.{0,30}?\["""
    r"""|\{\{[\s\S]{0,80}?\|\s*\w+"""
    r"""|\{\{.{0,50}?(?:class|mro|bases|globals|locals|import)\b"""
    r"""|\{%[^%]{0,30}?include"""
    r"""|\{%[^%]{0,30}?import"""
    r"""|\{%[^%]{0,30}?exec"""
    r""")""",
    re.DOTALL,
)


def _is_safe_template(text: str) -> bool:
    return bool(_TEMPLATE_SAFE.search(text))


# IMPORTANT: Order matters — more specific patterns must come before general ones.
# NoSQL must precede SQL ($ prefix). XXE must precede path_traversal (<!DOCTYPE).
WAF_PATTERNS: List[Tuple[str, object]] = [
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
        r"|\bSLEEP\s*\(\d|\bBENCHMARK\s*\(|\\bWAITFOR\s+DELAY\b|\bPG_SLEEP\s*\("
        r")",
        re.IGNORECASE | re.MULTILINE,
    )),

    # 4. XSS — callable (safe-verb allowlisting)
    ("xss", lambda t: bool(_XSS_PATTERN.search(t)) and not _is_safe_xss(t)),

    # 5. Path traversal — callable (safe-pattern allowlisting)
    ("path_traversal", lambda t: bool(_PATH_TRAVERSAL.search(t)) and not _is_safe_path(t)),

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

    # 7. Template injection — callable (safe-pattern allowlisting)
    ("template_injection", lambda t: bool(_TEMPLATE_INJECTION.search(t)) and not _is_safe_template(t)),

    # 8. LDAP injection — callable (safe-pattern allowlisting)
    ("ldap_injection", lambda t: bool(_LDAP_INJECTION.search(t)) and not _is_safe_ldap(t)),

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

    # 10. XML/Prompt Tag Injection
    ("xml_prompt_injection", re.compile(
        r"(?:"
        r"<\s*\w+[^>]*>[^<]+</\w+>"
        r"|<\w+[^>]*>[\s\S]{0,200}?</\w+>"
        r"|<!\w+"
        r"|<\?xml\s"
        r"|<\s*/\w+"
        r")",
        re.IGNORECASE,
    )),

    # 11. Broken Access Control & Auth Token Tampering
    ("access_control_tampering", re.compile(
        r"(?:"
        r"[\"']alg[\"']\s*:\s*[\"']none[\"']"
        r"|bearer\s+eyJhbG...5lIn"
        r"|(?:\b(?:root|admin|superuser|godmode)\b\s*:\s*true)"
        r"|\bX-Original-URL\b|\bX-Rewrite-URL\b"
        r")",
        re.IGNORECASE,
    )),

    # 12. Mass Assignment Protection
    ("mass_assignment", re.compile(
        r"(?:"
        r"[\"'(?:is_admin|privileges|permissions|scope|tier|is_staff|internal_user)[\"']\s*:"
        r"|[\"']role[\"']\s*:\s*[\"'(?:admin|root|superuser)[\"']"
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

    # 14. Server-Side Log Injection — requires \A (start of string)
    ("log_injection", re.compile(
        r"\A[\r\n]+(?:INFO|WARN|ERROR|CRITICAL|STATUS=200|ip=127\.0\.0\.1)",
        re.IGNORECASE,
    )),

    # 15. MiniMax API support — placeholder
    ("minimax_unsupported", re.compile(
        r"__MINIMAX_STRIP_BASE64__",
        re.IGNORECASE,
    )),
]


def scan(text: str) -> Optional[str]:
    """Scan decoded text. Returns attack category name or None."""
    if not ENABLE_WAF:
        return None
    decoded = _waf_decode(text)
    for category, pattern in WAF_PATTERNS:
        if callable(pattern):
            if pattern(decoded):
                return category
        elif hasattr(pattern, 'search') and pattern.search(decoded):
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
    """Scan all raw content strings from the body.
    
    NOTE: We only scan the extracted message content strings (not the
    serialised JSON body) to avoid false positives on JSON structure
    tokens like 'role' that legitimately appear in chat bodies.
    """
    for raw in extract_text_content(body):
        hit = scan(raw)
        if hit:
            return hit
    return None