import pytest
from chimera.providers.rate_limiter import RateLimitTracker


def test_rate_limit_tracker_default_state():
    tracker = RateLimitTracker()
    # Default state for unknown provider via defaultdict
    state = tracker._state["new-provider"]
    assert "requests" not in state  # it's rpm/rpd, not requests
    assert "rpm" in state
    assert "rpd" in state
    assert "exhausted_until" in state
    assert "ema_latency_ms" in state


@pytest.mark.asyncio
async def test_rate_limit_tracker_state_access():
    tracker = RateLimitTracker()
    # Access through defaultdict should trigger _default
    state = tracker._state["test-provider"]
    assert state["rpm"] == 0
    assert state["total_requests"] == 0
    assert state["cb_state"] == "closed"