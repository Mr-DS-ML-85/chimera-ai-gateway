"""
Entry point — run from the chimera/ directory:
    python main.py
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import uvicorn
from api.app import app  # noqa: F401  (re-exported for uvicorn string import)
from core.config import HOST, IS_DEV, PORT, WORKERS
from core.logging_setup import logger

if __name__ == "__main__":
    if not IS_DEV:
        logger.warning(
            "No built-in TLS — terminate HTTPS at nginx/Caddy before this process."
        )
    from core.config import TRUSTED_PROXIES as _TP

    # Tell uvicorn which IP(s) are allowed to set X-Forwarded-For.
    # Must match TRUSTED_PROXIES in .env.  An empty set means "trust nobody"
    # which is correct for direct-internet or local-dev deployments.
    # Example production value: TRUSTED_PROXIES=10.0.0.1 (your load balancer)
    _xff_trust = ",".join(_TP) if _TP else "none"

    uvicorn.run(
        "main:app",
        host                 = HOST,
        port                 = PORT,
        workers              = WORKERS,
        reload               = IS_DEV,
        access_log           = False,   # structured log from middleware
        server_header        = False,
        date_header          = False,
        forwarded_allow_ips  = _xff_trust,  # align uvicorn XFF trust with app config
    )