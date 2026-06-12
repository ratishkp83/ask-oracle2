"""B4 — read-only /packs API (Phase 7)."""

from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_list_packs_returns_all_five_modules():
    resp = client.get("/packs")
    assert resp.status_code == 200
    modules = {p["module"] for p in resp.json()}
    assert modules == {"GL", "AP", "AR", "PO", "OM"}


def test_get_pack_by_module():
    resp = client.get("/packs/AP")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module"] == "AP"
    assert any(t["table"] == "AP_INVOICES_ALL" for t in body["tables"])
    assert any(g["term"] == "invoice" for g in body["glossary"])


def test_get_pack_case_insensitive():
    assert client.get("/packs/ap").json()["module"] == "AP"


def test_unknown_module_is_404():
    resp = client.get("/packs/ZZ")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"] == "Unknown EBS module."
    assert body["error_id"]  # uniform error envelope


def test_packs_response_is_metadata_only():
    # No row-data-ish fields should appear in the contract (names/descriptions only).
    blob = client.get("/packs").text
    assert "password" not in blob.lower()


# Review P7-R1-F1 — /nl2sql validates ebs_modules instead of silently ignoring.
def test_nl2sql_rejects_unknown_ebs_module():
    resp = client.post("/nl2sql", json={"natural_language": "x", "ebs_modules": ["BOGUS"]})
    assert resp.status_code == 422
    assert "Unknown EBS module" in resp.text


def test_nl2sql_accepts_known_ebs_module_case_insensitive():
    # A valid (lower-case) module passes validation; the call then 400s on the
    # empty schema — i.e. it reached the handler, it was NOT rejected as 422.
    resp = client.post("/nl2sql", json={"natural_language": "x", "ebs_modules": ["ap"]})
    assert resp.status_code == 400
