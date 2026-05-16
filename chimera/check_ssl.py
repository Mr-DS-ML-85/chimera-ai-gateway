#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/home/irfan/chimera')
sys.path.insert(0, '/home/irfan/chimera/chimera')

import importlib.util
spec = importlib.util.find_spec('uvicorn')
if spec:
    print(f"uvicorn: {spec.origin}")
    import uvicorn
    print(f"version: {getattr(uvicorn, '__version__', 'unknown')}")
else:
    print("uvicorn not found")

# Test SSL
cert = '/home/irfan/chimera/chimera/cert.pem'
key = '/home/irfan/chimera/chimera/key.pem'
print(f"cert exists: {os.path.exists(cert)}")
print(f"key exists: {os.path.exists(key)}")
print(f"cert size: {os.path.getsize(cert)}")
print(f"key size: {os.path.getsize(key)}")

# Try loading with ssl module
import ssl
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
try:
    ctx.load_cert_chain(cert, key)
    print("SSL cert chain loaded OK")
except Exception as e:
    print(f"SSL error: {e}")