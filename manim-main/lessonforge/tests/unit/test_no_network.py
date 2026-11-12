"""No test reaches the network (``tests/conftest.py``): pinned, because tests paid for real calls for two days."""
import sys
import urllib.error
import urllib.request

import httpx
import pytest


def test_an_outside_request_is_refused_and_noted_and_the_tests_own_server_is_not():
    refused = next(m for name, m in list(sys.modules.items()) if name.endswith("conftest") and hasattr(m, "REFUSED")).REFUSED
    before = len(refused)
    with pytest.raises(httpx.ConnectError):
        httpx.post("https://openrouter.ai/api/v1/chat/completions?secret=1", json={}, timeout=5)
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("https://example.com/x", timeout=5)
    noted = refused[before:]
    del refused[before:]                                 # these two were meant: the run's summary lists only real leaks
    assert [n[:2] for n in noted] == [("openrouter.ai", "/api/v1/chat/completions"), ("example.com", "/x")]   # never the query
    assert all("test_no_network" in n[2] for n in noted)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.get("/ping")(lambda: {"ok": True})
    assert TestClient(app).get("/ping").json() == {"ok": True}


def test_a_request_through_urllib3_is_refused_too_which_is_how_boto3_would_reach_cloudflare_r2():
    urllib3 = pytest.importorskip("urllib3")
    refused = next(m for name, m in list(sys.modules.items()) if name.endswith("conftest") and hasattr(m, "REFUSED")).REFUSED
    before = len(refused)
    with pytest.raises(urllib3.exceptions.HTTPError):
        urllib3.PoolManager(retries=False).request("GET", "https://example.r2.cloudflarestorage.com/bucket/key?X-Amz-Signature=s")
    noted = refused[before:]
    del refused[before:]
    assert [n[:2] for n in noted] == [("example.r2.cloudflarestorage.com", "/bucket/key")]      # never the query
