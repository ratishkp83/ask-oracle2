"""API tests for POST /reports/export (Phase 9) — downloadable CSV/Excel.

Builds the file from the shown result (no LLM, no re-query). Excel bytes come
from the existing openpyxl helper; CSV is verified by content.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.core.auth import API_KEY_ENV, API_KEY_HEADER

client = TestClient(app)

PAYLOAD = {
    "columns": ["customer", "outstanding"],
    "rows": [["Meridian Stores", 1140200], ["Northwind Foods", 922500]],
    "filename": "top-customers",
}


def _payload(**over):
    body = dict(PAYLOAD)
    body.update(over)
    return body


def test_export_xlsx_returns_spreadsheet():
    resp = client.post("/reports/export", json=_payload(format="xlsx"))
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert 'filename="top-customers.xlsx"' in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"  # xlsx is a zip
    assert len(resp.content) > 100


def test_export_csv_returns_csv_content():
    resp = client.post("/reports/export", json=_payload(format="csv"))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.content.decode("utf-8")
    assert "customer,outstanding" in body
    assert "Meridian Stores" in body


def test_export_bad_format_returns_400():
    resp = client.post("/reports/export", json=_payload(format="pdf"))
    assert resp.status_code == 400
    assert "csv" in resp.json()["detail"].lower()


def test_export_filename_is_sanitized():
    resp = client.post("/reports/export", json=_payload(filename='../../etc/p"asswd', format="csv"))
    cd = resp.headers["content-disposition"]
    assert "/" not in cd and '"asswd' not in cd  # path + quote stripped
    assert cd.endswith('.csv"')


def test_export_empty_columns_returns_422():
    resp = client.post("/reports/export", json=_payload(columns=[], rows=[]))
    assert resp.status_code == 422


def test_export_ragged_rows_returns_400():
    resp = client.post("/reports/export", json=_payload(rows=[["only-one"]]))
    assert resp.status_code == 400


def test_export_too_many_rows_returns_400():
    big = [["x", i] for i in range(100_001)]
    resp = client.post("/reports/export", json=_payload(rows=big))
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_v1_export_requires_auth(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "k")
    assert client.post("/v1/reports/export", json=_payload()).status_code == 401
    ok = client.post("/v1/reports/export", json=_payload(), headers={API_KEY_HEADER: "k"})
    assert ok.status_code == 200
