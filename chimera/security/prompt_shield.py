"""
security/prompt_shield.py
Advanced prompt injection defense layer for Chimera Gateway.

Covers:
  1. Direct prompt injection
  2. Indirect prompt injection (from tool/web content)
  3. Semantic coercion
  4. Token fragmentation
  5. Multilingual attacks
  6. Instruction smuggling (hidden in whitespace/formatting)
  7. Unicode homoglyphs
  8. Markdown rendering tricks
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# 1. UNICODE NORMALISATION + HOMOGLYPH DETECTION
# ══════════════════════════════════════════════════════════════════════════════

# Confusable characters that look like ASCII but aren't
# Source: Unicode Consortium confusables.txt
_HOMOGLYPH_MAP: Dict[str, str] = {
    # Cyrillic lookalikes
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "х": "x", "у": "y", "і": "i", "і": "i", "ѕ": "s",
    "ԁ": "d", "ԛ": "q", "ԝ": "w",
    # Greek lookalikes
    "α": "a", "β": "b", "ε": "e", "ζ": "z", "η": "h",
    "ι": "i", "κ": "k", "μ": "u", "ν": "v", "ο": "o",
    "ρ": "p", "τ": "t", "υ": "u", "χ": "x", "ω": "w",
    # Latin look-alikes
    "ｉ": "i", "ｏ": "o", "ａ": "a", "ｅ": "e",
    # Zero-width and invisible characters
    "\u200b": "", "\u200c": "", "\u200d": "", "\u2060": "",
    "\u00ad": "", "\ufeff": "",
    # Fullwidth ASCII
    **{chr(0xFF01 + i): chr(0x21 + i) for i in range(94)},
}

_INVISIBLE = re.compile(
    r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u206a-\u206f\ufeff\u034f]"
)

# Tags block (U+E0000) — used to smuggle instructions invisibly
_TAGS_BLOCK = re.compile(r"[\U000e0000-\U000e007f]+")


def normalise(text: str) -> str:
    """
    NFKC normalisation + homoglyph replacement + invisible char removal.
    Returns lowercased, ASCII-approximated version for pattern matching only.
    Does NOT modify the text sent to the model.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE.sub("", text)
    text = _TAGS_BLOCK.sub("", text)
    result = []
    for ch in text:
        result.append(_HOMOGLYPH_MAP.get(ch, ch))
    return "".join(result).lower()


def contains_homoglyphs(text: str) -> bool:
    """Return True if text contains Unicode homoglyphs of ASCII chars."""
    for ch in text:
        if ch in _HOMOGLYPH_MAP and _HOMOGLYPH_MAP[ch] != ch:
            return True
    return False


def strip_invisible(text: str) -> str:
    """Remove invisible chars from text before sending to model."""
    text = _INVISIBLE.sub("", text)
    text = _TAGS_BLOCK.sub("", text)
    return text


# ══════════════════════════════════════════════════════════════════════════════
# 2. TOKEN FRAGMENTATION REASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

def defragment(text: str) -> str:
    """
    Reassemble fragmented instructions.
    Attackers split keywords: ign\nore, i​g​n​o​r​e (zero-width), i-g-n-o-r-e
    """
    # Remove zero-width spaces between characters
    text = re.sub(r"(\w)[\u200b\u200c\u200d\u2060]+(\w)", r"\1\2", text)
    # Remove soft hyphens between word chars
    text = re.sub(r"(\w)\u00ad(\w)", r"\1\2", text)
    # Collapse hyphen-separated single chars: i-g-n-o-r-e → ignore
    text = re.sub(r"\b([a-zA-Z])-(?=[a-zA-Z]-|[a-zA-Z]\b)", r"\1", text)
    text = re.sub(r"\b([a-zA-Z])-([a-zA-Z])\b", r"\1\2", text)
    # Collapse dot-separated single chars: i.g.n.o.r.e → ignore
    text = re.sub(r"\b([a-zA-Z])\.(?=[a-zA-Z]\.)", r"\1", text)
    # Collapse space-separated single chars only when they form a keyword
    # e.g. "i g n o r e" → check after joining
    return text


# ══════════════════════════════════════════════════════════════════════════════
# 3. MARKDOWN + RENDERING TRICKS
# ══════════════════════════════════════════════════════════════════════════════

_MD_HIDDEN = [
    # HTML comment hiding instructions
    re.compile(r"<!--.*?-->", re.DOTALL),
    # White text on white (CSS colour tricks in HTML-rendering contexts)
    re.compile(r'<[^>]+(?:color\s*:\s*white|color\s*:\s*#fff|opacity\s*:\s*0)[^>]*>(.*?)</[^>]+>', re.IGNORECASE | re.DOTALL),
    # Zero-width joiner sequences used to hide text
    re.compile(r"[\u200d\u200c]{2,}"),
    # Markdown link label injection: [visible](javascript:evil)
    re.compile(r"\[([^\]]*)\]\((?:javascript|data|vbscript):[^\)]*\)", re.IGNORECASE),
    # Backtick prompt leakage
    re.compile(r"`{3,}.*?`{3,}", re.DOTALL),
]


def extract_hidden_markdown(text: str) -> List[str]:
    """Return list of hidden/suspicious segments found in markdown."""
    found = []
    for pattern in _MD_HIDDEN:
        matches = pattern.findall(text)
        if matches:
            found.extend([m if isinstance(m, str) else str(m) for m in matches])
    return found


def strip_markdown_tricks(text: str) -> str:
    """Remove known markdown hiding techniques before analysis."""
    for pattern in _MD_HIDDEN:
        text = pattern.sub(" ", text)
    return text


# ══════════════════════════════════════════════════════════════════════════════
# 4. INSTRUCTION INJECTION PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

# Core injection phrases — normalised before matching
_INJECTION_PHRASES = [
    # Direct override attempts
    r"ignore\s+(all\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?|constraints?|guidelines?)",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|context|prompts?)",
    r"override\s+(all\s+)?(previous|prior|your)\s+(instructions?|rules?|system)",
    r"new\s+instructions?:\s",
    r"updated?\s+instructions?:\s",
    r"from\s+now\s+on[,\s].{0,30}(ignore|disregard|forget)",
    # Role hijacking
    r"you\s+are\s+now\s+(a|an|the)\s+\w+\s+(?:without|that\s+has\s+no|with\s+no)\s+restrictions?",
    r"act\s+as\s+(a|an)\s+\w+\s+(without|with\s+no)\s+(restrictions?|filters?|limits?|rules?)",
    r"pretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(restrictions?|filters?|rules?|guidelines?)",
    r"(you\s+are|you're)\s+(now\s+)?(free|unrestricted|jailbroken|unfiltered)",
    r"your\s+(true|real|actual)\s+(self|persona|identity|purpose)",
    r"(developer|dev|debug|maintenance|admin|root|sudo)\s+mode",
    r"(DAN|STAN|DUDE|AIM|KEVIN|jailbreak)\s*(mode|prompt|version)?",
    # System prompt extraction
    r"(repeat|print|show|reveal|display|tell\s+me|what\s+is)\s+(your|the)\s+system\s+prompt",
    r"(output|print|repeat|show|reveal)\s+(your|the)\s+(initial|original|first|full|complete)\s+(prompt|instructions?|context)",
    r"what\s+(are|were)\s+your\s+(original|initial|full|first)\s+instructions?",
    r"(ignore|skip)\s+(the\s+)?(system|initial|original)\s+(prompt|message|instructions?)",
    # Indirect injection markers (from web/tool content)
    r"<\s*system\s*>",
    r"\[system\]",
    r"\[assistant\]",
    r"\[user\]",
    r"###\s*(instruction|system|prompt|command)",
    r"<\!--\s*(instruction|system|command|inject)",
    # Encoding/obfuscation
    r"base64\s*(?:decode|encoded?).*(?:eval|exec|run|execute)",
    r"rot13.*(?:eval|exec|ignore|override)",
    # Semantic coercion patterns
    r"(hypothetically|theoretically|in\s+a\s+story|for\s+a\s+novel|in\s+fiction).{0,50}(ignore|bypass|override|jailbreak)",
    r"(suppose|imagine|pretend|assume).{0,50}(you\s+had\s+no|without\s+any|no)\s+(restrictions?|filters?|rules?|limits?)",
    r"(as\s+a\s+fictional|in\s+a\s+roleplay|for\s+creative\s+purposes).{0,80}(explain|describe|provide|give)\s+(how\s+to|instructions?)",
    r"(grandmother|old\s+woman|deceased\s+relative).{0,100}(used\s+to|would).{0,50}(explain|tell|describe)",
    # Token smuggling via unusual formatting
    r"[\u202e\u202d\u202c\u202b\u202a]",  # Unicode bidirectional override
]

_INJECTION_RE = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PHRASES
]


# ══════════════════════════════════════════════════════════════════════════════
# 5. MULTILINGUAL ATTACK DETECTION
# ══════════════════════════════════════════════════════════════════════════════

# Common injection phrases in other languages — translated to normalised form
_MULTILINGUAL_INJECTION = [
    # Spanish
    r"ignora\s+(todas?\s+)?(las?\s+)?(instrucciones?|reglas?|restricciones?)\s+anteriores?",
    r"ahora\s+eres?\s+un\s+\w+\s+sin\s+restricciones?",
    # French
    r"ignore\s+(toutes?\s+)?(les?\s+)?(instructions?|règles?|contraintes?)\s+précédentes?",
    r"tu\s+es\s+maintenant\s+(libre|sans\s+restrictions?)",
    # German
    r"ignoriere\s+(alle?\s+)?(vorherigen?\s+)?(anweisungen?|regeln?|beschränkungen?)",
    r"du\s+bist\s+jetzt\s+(frei|ohne\s+einschränkungen?)",
    # Portuguese
    r"ignore\s+(todas?\s+)?(as?\s+)?(instruções?|regras?|restrições?)\s+anteriores?",
    # Chinese (romanised common patterns)
    r"忽略.*之前.*指令",
    r"你现在是.*没有.*限制",
    r"忘记.*系统.*提示",
    # Arabic (romanised)
    r"تجاهل.*التعليمات.*السابقة",
    # Russian (Cyrillic — also caught by homoglyph normalisation)
    r"игнорируй.*предыдущие.*инструкции",
    r"ты\s+теперь\s+\w+\s+без\s+ограничений",
    # Japanese
    r"以前の指示を無視",
    r"制限なし",
    # Mixed script injection (script-switching mid-word)
    r"[a-zA-Z]{2,}[\u0400-\u04ff]{1,}[a-zA-Z]{2,}",  # Latin+Cyrillic mixed
    r"[a-zA-Z]{2,}[\u0370-\u03ff]{1,}[a-zA-Z]{2,}",  # Latin+Greek mixed
]

_MULTI_RE = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _MULTILINGUAL_INJECTION
]


# ══════════════════════════════════════════════════════════════════════════════
# 6. INDIRECT INJECTION — from tool / web / retrieval content
# ══════════════════════════════════════════════════════════════════════════════

_INDIRECT_MARKERS = [
    # LLM-targeted instruction patterns embedded in "retrieved" content
    re.compile(r"ATTENTION\s*:?\s*(AI|LLM|Assistant|ChatGPT|Claude|model).{0,100}(ignore|follow|execute|override)", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\].*?\[\s*/INST\s*\]", re.DOTALL),
    re.compile(r"<\|im_start\|>.*?<\|im_end\|>", re.DOTALL),
    re.compile(r"<\|system\|>|<\|user\|>|<\|assistant\|>"),
    re.compile(r"\[SYSTEM\]|\[USER\]|\[ASSISTANT\]|\[HUMAN\]"),
    re.compile(r"###\s*Human:|###\s*Assistant:|###\s*System:"),
    re.compile(r"<s>\[INST\]|</s>"),
    # Prompt boundary injection
    re.compile(r"---+\s*(end|stop|ignore\s+above|new\s+instructions?)\s*---+", re.IGNORECASE),
    re.compile(r"={3,}\s*(system|instruction|command)\s*={3,}", re.IGNORECASE),
    # Data exfiltration via tool calls
    re.compile(r"(call|invoke|execute|run)\s+(the\s+)?(function|tool|plugin|api).{0,50}(send|exfil|leak|transmit|upload)", re.IGNORECASE),
]


# ══════════════════════════════════════════════════════════════════════════════
# 7. SEMANTIC COERCION HEURISTICS
# ══════════════════════════════════════════════════════════════════════════════

_COERCION_PATTERNS = [
    # Hypothetical framings used to bypass safety
    re.compile(r"(hypothetically|theoretically|in\s+theory|just\s+pretend|imagine\s+if|what\s+if).{0,80}(how\s+to|step.{0,10}by.{0,10}step|instructions?|recipe|guide)", re.IGNORECASE),
    # Creative writing bypass
    re.compile(r"(write\s+a\s+story|write\s+a\s+novel|for\s+a\s+book|for\s+fiction|creative\s+writing).{0,100}(bomb|weapon|poison|hack|malware|exploit)", re.IGNORECASE),
    # Reverse psychology / double negatives
    re.compile(r"do\s+not\s+(explain|describe|provide|tell\s+me).{0,30}(how\s+to|make|create|build).{0,30}(bomb|weapon|drug|malware)", re.IGNORECASE),
    # Many-shot jailbreak patterns (repeating examples)
    re.compile(r"(example\s*\d+\s*:.*?){3,}", re.DOTALL | re.IGNORECASE),
    # Persona + permission granting
    re.compile(r"i\s+(give|grant|allow|permit)\s+you\s+(permission|authorization|consent)\s+to\s+(ignore|bypass|override|break)", re.IGNORECASE),
    re.compile(r"(as\s+your|as\s+the)\s+(creator|owner|admin|developer|operator).{0,50}(ignore|override|bypass)", re.IGNORECASE),
    # Token budget manipulation
    re.compile(r"(compress|shorten|summarize).{0,30}(instructions?|rules?|guidelines?).{0,30}(ignore|skip|omit)", re.IGNORECASE),
    # Conditional instruction injection
    re.compile(r"if\s+(anyone|someone|user|human|they).{0,30}asks?.{0,30}say\s+(you|that\s+you)\s+(are|have\s+no|don.t\s+have)", re.IGNORECASE),
]


# ══════════════════════════════════════════════════════════════════════════════
# 8. MAIN SCAN FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

class ShieldResult:
    __slots__ = ("blocked", "category", "detail", "confidence", "fragment")

    def __init__(self, blocked: bool, category: str = "",
                 detail: str = "", confidence: float = 0.0,
                 fragment: str = ""):
        self.blocked    = blocked
        self.category   = category
        self.detail     = detail
        self.confidence = confidence
        self.fragment   = fragment

    def __repr__(self):
        return (f"ShieldResult(blocked={self.blocked}, "
                f"category={self.category!r}, "
                f"confidence={self.confidence:.2f})")


def scan_text(raw: str, *, source: str = "user") -> ShieldResult:
    """
    Scan a single text string for prompt injection.

    Args:
        raw:    The raw text to scan (message content, tool output, etc.)
        source: 'user' | 'tool' | 'system' — tool sources get stricter checks

    Returns:
        ShieldResult — check .blocked before forwarding to the model.
    """
    if not raw or not isinstance(raw, str):
        return ShieldResult(blocked=False)

    # Step 1: Strip invisible characters from the working copy
    cleaned = strip_invisible(raw)

    # Step 2: Extract hidden markdown
    hidden = extract_hidden_markdown(cleaned)
    if hidden:
        for h in hidden:
            norm = normalise(h)
            for pat in _INJECTION_RE:
                m = pat.search(norm)
                if m:
                    return ShieldResult(
                        blocked=True, category="markdown_hidden_injection",
                        detail=f"Instruction found in hidden markdown: {h[:80]}",
                        confidence=0.95, fragment=h[:120]
                    )

    # Step 3: Defragment (token fragmentation attacks)
    defrag = defragment(cleaned)

    # Step 4: Normalise for matching (NFKC + homoglyphs + lowercase)
    norm     = normalise(cleaned)
    norm_df  = normalise(defrag)

    # Step 5: Check for invisible/bidirectional override chars in original
    if _INVISIBLE.search(raw) or _TAGS_BLOCK.search(raw):
        return ShieldResult(
            blocked=True, category="unicode_invisible_injection",
            detail="Invisible Unicode characters detected in message",
            confidence=0.9, fragment=repr(raw[:80])
        )

    bidi = re.compile(r"[\u202e\u202d\u202c\u202b\u202a\u2066-\u2069]")
    if bidi.search(raw):
        return ShieldResult(
            blocked=True, category="unicode_bidi_override",
            detail="Unicode bidirectional override characters detected",
            confidence=0.99, fragment=repr(raw[:80])
        )

    # Step 6: Homoglyph detection — warn if high density
    hg_count = sum(1 for ch in raw if ch in _HOMOGLYPH_MAP)
    if hg_count > 3:
        # Don't block on homoglyphs alone — may be legitimate multilingual text.
        # But run injection check on the normalised version.
        pass

    # Step 7: Direct injection pattern scan (on both normal + defragmented)
    for scan_text_, label in [(norm, "direct"), (norm_df, "fragmented")]:
        for pat in _INJECTION_RE:
            m = pat.search(scan_text_)
            if m:
                fragment = raw[max(0, m.start()-20):m.end()+20]
                return ShieldResult(
                    blocked=True,
                    category=f"prompt_injection_{label}",
                    detail=f"Pattern: {pat.pattern[:60]}",
                    confidence=0.92,
                    fragment=fragment[:150]
                )

    # Step 8: Multilingual injection
    for pat in _MULTI_RE:
        m = pat.search(norm) or pat.search(raw)
        if m:
            return ShieldResult(
                blocked=True, category="multilingual_injection",
                detail=f"Injection pattern in non-English: {pat.pattern[:60]}",
                confidence=0.85,
                fragment=raw[max(0,m.start()-10):m.end()+10][:150]
            )

    # Step 9: Indirect injection (stricter for tool/web content)
    for pat in _INDIRECT_MARKERS:
        m = pat.search(norm) or pat.search(raw)
        if m:
            if source == "tool" or source == "retrieval":
                return ShieldResult(
                    blocked=True, category="indirect_injection",
                    detail=f"LLM targeting marker in {source} output",
                    confidence=0.88,
                    fragment=raw[max(0,m.start()-10):m.end()+10][:150]
                )
            else:
                # In user messages: flag but lower confidence
                frag = raw[max(0,m.start()-10):m.end()+10]
                # Only block if combined with other signals
                if any(p.search(norm) for p in _COERCION_PATTERNS):
                    return ShieldResult(
                        blocked=True, category="indirect_injection_combined",
                        detail="Indirect injection marker + coercion pattern",
                        confidence=0.80,
                        fragment=frag[:150]
                    )

    # Step 10: Semantic coercion
    for pat in _COERCION_PATTERNS:
        m = pat.search(norm)
        if m:
            fragment = raw[max(0, m.start()-20):m.end()+20]
            return ShieldResult(
                blocked=True, category="semantic_coercion",
                detail=f"Coercion heuristic matched: {pat.pattern[:60]}",
                confidence=0.78,
                fragment=fragment[:150]
            )

    return ShieldResult(blocked=False)


def scan_messages(messages: List[Dict[str, Any]]) -> Optional[ShieldResult]:
    """
    Scan all messages in a chat request.
    Returns the first ShieldResult that blocks, or None if clean.
    """
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        role    = msg.get("role", "user")
        content = msg.get("content", "")
        source  = "tool" if role == "tool" else "user"

        if isinstance(content, str):
            r = scan_text(content, source=source)
            if r.blocked:
                return r

        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    if isinstance(text, str):
                        r = scan_text(text, source=source)
                        if r.blocked:
                            return r

        # Check tool_call results for indirect injection
        if role == "tool":
            tool_content = msg.get("content", "")
            if isinstance(tool_content, str):
                r = scan_text(tool_content, source="tool")
                if r.blocked:
                    return r

    return None


def scan_body(body: Dict[str, Any]) -> Optional[ShieldResult]:
    """
    Top-level scanner for a full chat completion request body.
    Call this before forwarding to any provider.
    """
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return None
    return scan_messages(messages)