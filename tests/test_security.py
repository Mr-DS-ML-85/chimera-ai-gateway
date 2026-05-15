import pytest
from chimera.security.ssrf import is_safe, approve_base, assert_safe
from chimera.security.content_policy import POLICY_PATTERNS
from chimera.security.pii import PII_PATTERNS, redact


def test_ssrf_is_safe_allowed():
    approve_base("https://api.openai.com/")
    assert is_safe("https://api.openai.com/v1/chat/completions") is True


def test_ssrf_is_safe_blocked():
    assert is_safe("http://169.254.169.254/latest/meta-data/") is False


def test_pii_patterns_loaded():
    assert len(PII_PATTERNS) > 0


def test_pii_redact_basic():
    redacted_text, counts = redact("My email is test@example.com")
    assert counts
    assert counts.get("email", 0) > 0


def test_policy_patterns_loaded():
    assert len(POLICY_PATTERNS) > 0