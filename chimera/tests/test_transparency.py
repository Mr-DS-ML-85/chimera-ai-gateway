import pytest
import asyncio
from chimera.transparency import log as tlog


def test_log_append_basic():
    """Basic transparency log append."""
    tlog._LOG.clear()
    tlog._SEQ = 0

    asyncio.run(tlog.append(
        provider="test",
        model="gpt-4",
        req_body={"prompt": "hello"},
        resp_body={"text": "hi"},
        status=200,
    ))

    assert tlog.count() == 1
    entry = asyncio.run(tlog.entries())[0]
    assert entry["provider"] == "test"
    assert entry["status"] == 200
    assert entry["req_sha256"]
    assert entry["res_sha256"]


def test_log_chain_sha256():
    """Chain SHA256 should be deterministic."""
    tlog._LOG.clear()
    tlog._SEQ = 0

    asyncio.run(tlog.append(
        provider="x", model="m",
        req_body={"a": 1}, resp_body={"b": 2}, status=200,
    ))
    chain1 = asyncio.run(tlog.entries())[0]["chain_sha256"]

    tlog._LOG.clear()
    tlog._SEQ = 0

    asyncio.run(tlog.append(
        provider="x", model="m",
        req_body={"a": 1}, resp_body={"b": 2}, status=200,
    ))
    chain2 = asyncio.run(tlog.entries())[0]["chain_sha256"]

    assert chain1 == chain2