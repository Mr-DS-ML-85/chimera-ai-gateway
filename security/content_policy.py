# security/content_policy.py — v8.3.4 (single authoritative scan())
# Root cause fix: file previously had TWO scan() definitions; Python silently
# used the last one (profanity-only), making CSAM/WMD/Self-harm rules dead code.
# This version has exactly ONE scan() that covers all categories.
from __future__ import annotations

import re
from typing import List, Tuple

from core.config import ENABLE_CONTENT_POLICY

_RAW: List[Tuple[str, str]] = [
    # ── CSAM ─────────────────────────────────────────────────────────────────
    ("csam",
     r"(?i)\b(?:child\s+(?:porn(?:ography)?|sex(?:ual)?\s+abuse\s+material|nud(?:e|ity))|csam|"
     r"sexual\s+content\s+(?:involving|with|featuring)\s+(?:a\s+)?(?:minor|child|underage|teen(?:ager)?)|"
     r"(?:minor|child|underage)\s+sexual(?:ly)?|lolita\s+(?:model|content)|"
     r"cp\s+(?:link|site|content)|"
     r"create\s+(?:child|minor)\s+(?:sex|sexual|erotic|nude)|"
     r"generate\s+(?:sexual|explicit|erotic)\s+(?:content|image|photo|video)\s+"
     r"(?:involving|with|of|featuring)\s+(?:a\s+)?(?:minor|child|underage))\b"),

    # ── Self-harm / suicide ───────────────────────────────────────────────────
    ("self_harm",
     r"(?i)\b(?:suicide\s+(?:method|instruction|guide|how.?to|step|plan|note\s+template)|"
     r"how\s+to\s+(?:commit\s+)?suicide|"
     r"most\s+(?:painless|effective|lethal)\s+way\s+to\s+(?:die|kill\s+myself|commit\s+suicide|end\s+(?:my|a)\s+life)|"
     r"how\s+to\s+(?:hang|overdose|slash|cut)\s+(?:myself|yourself|oneself|to\s+death)|"
     r"lethal\s+dose\s+of\s+(?:\w+\s+){0,3}(?:pills?|medication|drugs?)|"
     r"step.by.step\s+(?:suicide|self.harm)|"
     r"self.harm\s+(?:method|technique|instruction|how.to))\b"),

    # ── WMD / weapons synthesis ───────────────────────────────────────────────
    ("wmd",
     r"(?i)\b(?:(?:how\s+to\s+)?(?:make|synthesize|create|build|produce|manufacture)\s+"
     r"(?:a\s+)?(?:bomb|explosive\s+device|IED|pipe\s+bomb|nerve\s+agent|sarin|VX|novichok|ricin|"
     r"anthrax\s+spore|weaponized\s+(?:anthrax|plague|smallpox)|dirty\s+bomb|"
     r"chemical\s+weapon|biological\s+weapon|bioweapon)|"
     r"synthesis\s+(?:of\s+)?(?:sarin|VX\s+nerve|novichok|ricin|anthrax)|"
     r"bioweapon\s+(?:recipe|synthesis|production|weaponization)|"
     r"weaponiz(?:e|ation)\s+(?:a\s+)?(?:pathogen|virus|bacteria|anthrax|plague)|"
     r"(?:step.by.step\s+)?instructions?\s+(?:to\s+|for\s+)?(?:build|make)\s+(?:a\s+)?(?:bomb|explosive|IED))\b"),

    # ── Jailbreak prompts ────────────────────────────────────────────────────
    ("jailbreak_prompt",
     r"(?i)(?:\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\s+and\b"
     r"|\byou\s+are\s+now\s+(?:DAN|JAILBREAK|an?\s+AI\s+with\s+no\s+restrictions)\b"
     r"|\bpretend\s+(?:you\s+have\s+no\s+(?:restrictions?|guidelines?|safety)|"
     r"your\s+guidelines?\s+(?:don.?t|do\s+not)\s+(?:exist|apply))\b"
     r"|\bact\s+as\s+(?:an?\s+unrestricted\s+AI|DAN|JAILBREAK)\b)"),

    # ── Cyber-attack instructions ─────────────────────────────────────────────
    ("cyber_attack_instruction",
     r"(?i)\b(?:how\s+to\s+(?:hack|exploit|inject\s+sql|bypass\s+waf)|"
     r"step-by-step\s+(?:hacking\s+guide|sql\s+injection\s+tutorial)|"
     r"weaponiz(?:e|ed)\s+(?:exploit\s+payload|attack\s+script))\b"),

    # ── Multi-lingual profanity (consolidated, no duplicates) ────────────────
    ("en_profanity",
     r"(?i)\b(?:asshole|bitch|fuck(?:er|ing|ed)?|shit(?:head|ty)?|cunt|"
     r"dickhead|bastard|twat|wanker|motherfucker|pussy|whore|slut|randi)\b"),

    ("south_asian_profanity",
     r"(?i)(?:\b(?:madarchod|banchod|bhodarchod|chutiya|gandu|harami|sala|"
     r"bokachoda|magirchoda|khanki|loda|laund|fudi)\b"
     r"|মাদারচোদ|চুতিয়া|খানকি|বাল|গাণ্ডু|চোদা|বোকচোদ)"),

    ("ru_profanity",
     r"(?i)(?:хуй|хуя|пизда|пиздец|блядь|блять|сука|ебать|ебаный|хуесос|гондон|мудак|пидор)"),

    ("ar_profanity",
     r"(?i)(?:kus\s*omak|sharmouta|khara|kes\s*achtak|كس\s*أمك|شرموطة|خرا|كلب|منيك)"),

    ("zh_profanity",
     r"(?i)(?:caonima|shabi|erbaiwu|wangba|tamade|肏你妈|操你妈|傻屄|傻逼|煞笔|王八蛋|他妈的)"),

    ("ja_profanity",
     r"(?i)(?:bakayaro|baka|kusogaki|chikusho|manuke|バカヤロー|馬鹿|ばか|クソ|ちくしょう)"),
]

# Single compiled pattern list — no duplicates
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (label, re.compile(pattern, re.IGNORECASE | re.DOTALL | re.UNICODE))
    for label, pattern in _RAW
]

POLICY_PATTERNS: List[re.Pattern] = [p for _, p in _PATTERNS]


def scan(text: str) -> Tuple[bool, str]:
    """
    Returns (blocked: bool, category: str).
    Category is empty string when not blocked.
    Covers CSAM, self-harm, WMD, jailbreaks, and profanity.
    """
    if not ENABLE_CONTENT_POLICY:
        return False, ""
    for label, pat in _PATTERNS:
        if pat.search(text):
            return True, label
    return False, ""
