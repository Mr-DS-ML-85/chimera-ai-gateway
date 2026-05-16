from __future__ import annotations

import ipaddress
import socket
from typing import List
from urllib.parse import urlparse

from fastapi import HTTPException

_BLOCKED: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_META_HOSTS = {
    "metadata.google.internal",
    "169.254.169.254",
    "100.100.100.200",
    "fd00:ec2::254",
}


def _is_private(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _BLOCKED)
    except ValueError:
        return False


def is_safe(url: str) -> bool:
    """Startup check — returns False if URL resolves to a private address."""
    try:
        host = urlparse(url).hostname or ""
        if not host or host.lower() in _META_HOSTS:
            return False
        addr = socket.gethostbyname(host)
        return not _is_private(addr)
    except Exception:
        return True


# Pre-approved base URLs from catalogue (populated at import time)
# These passed is_safe() at startup — exempt from per-request DNS re-check
_APPROVED_BASES: set[str] = set()

def approve_base(url: str) -> None:
    """Called at startup for each configured provider base URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    _APPROVED_BASES.add(f"{parsed.scheme}://{parsed.netloc}")


def assert_safe(url: str, provider_name: str) -> None:
    """Per-request guard — raises HTTPException(400) on SSRF.
    URLs whose base was approved at startup are exempt (e.g. local Ollama).
    """
    from urllib.parse import urlparse
    base = urlparse(url)
    base_str = f"{base.scheme}://{base.netloc}"
    if base_str in _APPROVED_BASES:
        return  # already validated at startup
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(400, f"Provider '{provider_name}': bad URL scheme")
        host = parsed.hostname or ""
        if not host:
            raise HTTPException(400, f"Provider '{provider_name}': missing host")
        if host.lower() in _META_HOSTS:
            raise HTTPException(400, f"Provider '{provider_name}': SSRF blocked (metadata)")
        try:
            addr = socket.gethostbyname(host)
        except socket.gaierror:
            return
        if _is_private(addr):
            raise HTTPException(400, f"Provider '{provider_name}': SSRF blocked ({addr})")
    except HTTPException:
        raise
    except Exception as exc:
        from core.logging_setup import logger
        logger.warning("SSRF check error provider=%s: %s", provider_name, exc)