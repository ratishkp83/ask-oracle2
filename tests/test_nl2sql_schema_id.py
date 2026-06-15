"""Phase 9 B5b-3 (Decision 1) — `schema_id` on POST /nl2sql.

A saved schema can supply NL→SQL context by id: the server loads it via
schema_from_dict (table/column **names only** — invariant 3) and feeds it to the
existing generator. No row data, no DB hit, no change to the SELECT-only
chokepoint. The LLM itself is monkeypatched out; these tests exercise the wiring.
"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.core.schema_store import SchemaRecord

client = TestClient(app)

DEFINITION = {
    "tables": {
        "AR_OPEN_ITEMS": [
            {"table_name": "AR_OPEN_ITEMS", "column_name": "REGION"},
            {"table_name": "AR_OPEN_ITEMS", "column_name": "OUTSTANDING_AMOUNT"},
        ]
    },
    "relationships": [],
}


def _record(definition=DEFINITION) -> SchemaRecord:
    return SchemaRecord(
        id="abc",
        name="AOR_DEMO",
        source="introspection",
        table_count=1,
        created_at="2026-06-14T00:00:00Z",
        updated_at="2026-06-14T00:00:00Z",
        definition=definition,
    )


def _capture_schema(monkeypatch):
    """Replace the generator with a stub that records the schema it was handed."""
    captured = {}

    def fake_generate(nl, schema, **kwargs):
        captured["schema"] = schema
        return SimpleNamespace(
            sql="SELECT region FROM ar_open_items", explanation=None, confidence=None, answerable=True, message=None
        )

    monkeypatch.setattr(api_module, "generate_sql_from_nl", fake_generate)
    return captured


def test_schema_id_loads_saved_definition(monkeypatch):
    captured = _capture_schema(monkeypatch)

    class Store:
        def get(self, sid):
            return _record() if sid == "abc" else None

    monkeypatch.setattr(api_module, "_schema_store", Store())

    resp = client.post("/nl2sql", json={"natural_language": "outstanding AR by region", "schema_id": "abc"})
    assert resp.status_code == 200
    assert resp.json()["sql"] == "SELECT region FROM ar_open_items"
    # The generator received the saved schema, names only.
    schema = captured["schema"]
    assert "AR_OPEN_ITEMS" in schema.tables
    assert schema.list_columns("AR_OPEN_ITEMS") == ["REGION", "OUTSTANDING_AMOUNT"]


def test_unknown_schema_id_returns_404(monkeypatch):
    _capture_schema(monkeypatch)  # never reached, but keep the LLM stubbed

    class EmptyStore:
        def get(self, sid):
            return None

    monkeypatch.setattr(api_module, "_schema_store", EmptyStore())

    resp = client.post("/nl2sql", json={"natural_language": "anything", "schema_id": "missing"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Schema not found."


def test_schema_csv_takes_precedence_over_schema_id(monkeypatch):
    captured = _capture_schema(monkeypatch)

    class ExplodingStore:
        def get(self, sid):
            raise AssertionError("schema_id must be ignored when schema_csv is provided")

    monkeypatch.setattr(api_module, "_schema_store", ExplodingStore())

    csv = (
        "table_name,column_name,data_type,is_primary_key,is_foreign_key,references_table,references_column\n"
        "EMP,EMP_ID,NUMBER,true,false,,\n"
    )
    resp = client.post(
        "/nl2sql",
        json={"natural_language": "show employees", "schema_csv": csv, "schema_id": "abc"},
    )
    assert resp.status_code == 200
    # The CSV schema was used, not the saved one (store.get never called).
    assert "EMP" in captured["schema"].tables
