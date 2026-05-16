"""
Entry point — run from the chimera/ directory:
    python main.py
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import uvicorn
import os
from api.app import app  # noqa: F401  (re-exported for uvicorn string import)
from core.config import HOST, IS_DEV, PORT, WORKERS
from core.logging_setup import logger


# SSL/TLS configuration
import os as _os
_SSL_CERT = _os.environ.get("SSL_CERT_FILE", "cert.pem")
_SSL_KEY  = _os.environ.get("SSL_KEY_FILE",  "key.pem")

if __name__ == "__main__":
    if not IS_DEV:
        logger.warning(
            "No built-in TLS — terminate HTTPS at nginx/Caddy before this process."
        )
    from core.config import TRUSTED_PROXIES as _TP

    _xff_trust = ",".join(_TP) if _TP else "none"

    _ssl_args = {}
    # if os.path.exists(_SSL_CERT) and os.path.exists(_SSL_KEY):
    #     _ssl_args = {
    #         "ssl_certfile": _SSL_CERT,
    #         "ssl_keyfile":  _SSL_KEY,
    #     }
    #     logger.info("TLS enabled: %s + %s", _SSL_CERT, _SSL_KEY)
    # else:
    #     logger.warning("TLS cert/key not found — HTTP only. Run `openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes` to generate.")

    uvicorn.run(
        "main:app",
        host                 = HOST,
        port                 = PORT,
        workers              = WORKERS,
        reload               = IS_DEV,
        access_log           = False,
        server_header        = False,
        date_header          = False,
        forwarded_allow_ips  = _xff_trust,
        **_ssl_args,
    )