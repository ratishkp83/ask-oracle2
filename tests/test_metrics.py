"""B3 — in-process metrics module + GET /metrics endpoint.

No network, no Oracle: run_select is monkeypatched. Counters are reset before
each test for isolation.
"""

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core import metrics
from src.core.profiles import InMemoryProfileStore
from src.db import OracleClient, QueryResult

client = TestClient(app)

INLINE = {"host": "db", "port": 1521, "service_name": "XE", "username": "u", "password": "p"}


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    metrics.reset()
    monkeypatch.setattr(api_module, "_store", InMemoryProfileStore())
    yield
    metrics.reset()


@pytest.fixture
def ok_db(monkeypatch):
    def fake(self, sql, limits=None, binds=None):
        return QueryResult(columns=["N"], rows=[(1,)], elapsed_seconds=0.05, truncated=False, row_count=1)

    monkeypatch.setattr(OracleClient, "run_select", fake)


def test_snapshot_shape_and_defaults():
    snap = metrics.snapshot()
    assert set(snap["counters"]) >= {"queries_executed", "queries_rejected", "queries_errored"}
    assert snap["latency_seconds"]["count"] == 0


def test_executed_increments_counter_and_latency(ok_db):
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "connection": INLINE})
    assert resp.status_code == 200
    snap = metrics.snapshot()
    assert snap["counters"]["queries_executed"] == 1
    assert snap["latency_seconds"]["count"] == 1
    assert snap["latency_seconds"]["max"] == pytest.approx(0.05, abs=1e-3)


def test_rejected_increments_counter():
    resp = client.post("/execute", json={"sql": "DROP TABLE emp", "connection": INLINE})
    assert resp.status_code == 400
    assert metrics.snapshot()["counters"]["queries_rejected"] == 1


def test_errored_increments_counter(monkeypatch):
    def boom(self, sql, limits=None, binds=None):
        raise RuntimeError("driver blew up")

    monkeypatch.setattr(OracleClient, "run_select", boom)
    resp = client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "connection": INLINE})
    assert resp.status_code == 400
    assert metrics.snapshot()["counters"]["queries_errored"] == 1


def test_metrics_endpoint_returns_json_snapshot(ok_db):
    client.post("/execute", json={"sql": "SELECT 1 FROM DUAL", "connection": INLINE})
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["counters"]["queries_executed"] == 1
    # No secrets / data — only counts + latency keys.
    assert set(body) == {"counters", "latency_seconds"}
    assert "password" not in resp.text
