from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Gateway long-lived key pair — regenerated on every process start
_GW_PRIVATE_KEY: X25519PrivateKey  = X25519PrivateKey.generate()
GW_PUBLIC_KEY_BYTES: bytes         = _GW_PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
)
GW_PUBLIC_KEY_B64:         str     = base64.b64encode(GW_PUBLIC_KEY_BYTES).decode()
GW_PUBLIC_KEY_FINGERPRINT: str     = hashlib.sha256(GW_PUBLIC_KEY_BYTES).hexdigest()[:16]

_HKDF_INFO = b"chimera-e2ee-v1"


def _derive_key(client_pub_bytes: bytes) -> bytes:
    shared = _GW_PRIVATE_KEY.exchange(X25519PublicKey.from_public_bytes(client_pub_bytes))
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared)


def encrypt(plaintext: str, client_pub_bytes: bytes) -> Dict[str, Any]:
    key   = _derive_key(client_pub_bytes)
    nonce = secrets.token_bytes(12)
    ct    = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    del key
    return {
        "encrypted":          True,
        "alg":                "X25519-ECDH+HKDF-SHA256+AES-256-GCM",
        "nonce":              base64.b64encode(nonce).decode(),
        "ciphertext":         base64.b64encode(ct).decode(),
        "gw_key_fingerprint": GW_PUBLIC_KEY_FINGERPRINT,
    }