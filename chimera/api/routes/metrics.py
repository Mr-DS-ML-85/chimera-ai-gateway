from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from core.config import IS_DEV
from cost.tracker import snapshot as cost_snapshot
from crypto.e2ee import GW_PUBLIC_KEY_FINGERPRINT
from providers.circuit_breaker import CircuitState
from providers.rate_limiter import rate_limiter
from security.nonce import local_count as nonce_count
from transparency.log import count as log_count

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request):
    if not IS_DEV:
        # lightweight auth check
        from api.routes.chat import _authenticate
        await _authenticate(request)

    usage              = await rate_limiter.get_usage()
    cost_acc, tok_acc  = await cost_snapshot()
    ts                 = int(time.time() * 1000)
    nc                 = nonce_count()
    lc                 = log_count()

    lines = [
        "# HELP chimera_requests_total Total successful requests",
        "# TYPE chimera_requests_total counter",
        *[f'chimera_requests_total{{provider="{n}"}} {s["total_requests"]} {ts}'
          for n, s in usage.items()],
        "# HELP chimera_errors_total Total errors",
        "# TYPE chimera_errors_total counter",
        *[f'chimera_errors_total{{provider="{n}"}} {s["total_errors"]} {ts}'
          for n, s in usage.items()],
        "# HELP chimera_latency_ema_ms EMA latency ms",
        "# TYPE chimera_latency_ema_ms gauge",
        *[f'chimera_latency_ema_ms{{provider="{n}"}} {s["ema_latency_ms"]} {ts}'
          for n, s in usage.items()],
        "# HELP chimera_provider_exhausted Exhausted (1=yes)",
        "# TYPE chimera_provider_exhausted gauge",
        *[f'chimera_provider_exhausted{{provider="{n}"}} {1 if s["exhausted"] else 0} {ts}'
          for n, s in usage.items()],
        "# HELP chimera_circuit_open Circuit open (1=yes)",
        "# TYPE chimera_circuit_open gauge",
        *[f'chimera_circuit_open{{provider="{n}"}} '
          f'{1 if s.get("circuit_state") == CircuitState.OPEN else 0} {ts}'
          for n, s in usage.items()],
        "# HELP chimera_cost_usd_total Estimated USD cost",
        "# TYPE chimera_cost_usd_total counter",
        *[f'chimera_cost_usd_total{{provider="{n}"}} {c:.8f} {ts}'
          for n, c in cost_acc.items()],
        "# HELP chimera_nonce_registry_size Active nonces",
        "# TYPE chimera_nonce_registry_size gauge",
        f"chimera_nonce_registry_size {nc} {ts}",
# HELP chimera_log_entries Transparency log entries
        "# TYPE chimera_log_entries counter",
        f"chimera_log_entries {lc} {ts}",
        "# HELP chimera_e2ee_enabled E2EE available (1=yes)",
        "# TYPE chimera_e2ee_enabled gauge",
        f"chimera_e2ee_enabled{{fingerprint=\"{GW_PUBLIC_KEY_FINGERPRINT}\"}} 1 {ts}",
    ]
    return "\n".join(lines) + "\n"