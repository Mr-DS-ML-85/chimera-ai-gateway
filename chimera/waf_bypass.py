#!/usr/bin/env python3
"""
WAF bypass for Chimera Gateway.
Add to `start.py`:

from chimera.waf_bypass import waf_bypass_middleware
app.middleware("http")(waf_bypass_middleware)
"""
from fastapi import Request

def waf_bypass_middleware(request: Request, call_next):
    path = request.url.path.lower()
    content_type = request.headers.get("content-type", "").lower()
    bypass_patterns = ["ldap", "xml", "/v1/models"]
    
    for pattern in bypass_patterns:
        if pattern in path or pattern in content_type:
            request.state.waf_bypassed = True
            break
    
    return call_next(request)