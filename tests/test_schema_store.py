"""Tests for the schema persistence store (Phase 5)."""

import pytest

from src.core.schema_store import InMemorySchemaStore, JsonFileSchemaStore
from src.schema import ColumnDefinition, Schema, TableDefinition, schema_to_dict


def _definition() -> dict:
    s = Schema(
        tables={
            "EMP": TableDefinition("EMP", [ColumnDefinition("EMP", "EMP_ID", "NUMBER", is_primary_key=True)]),
            "DEPT": TableDefinition("DEPT", [ColumnDefinition("DEPT", "DEPT_ID", "NUMBER")]),
        }
    )
    return schema_to_dict(s)


def test_create_assigns_id_table_count_and_summary():
    store = InMemorySchemaStore()
    rec = store.create("EBS DEV", _definition(), source="upload")
    assert rec.id and rec.created_at and rec.updated_at
    assert rec.table_count == 2 and rec.source == "upload"
    # list returns summaries without the definition blob
    summaries = store.list()
    assert len(summaries) == 1
    assert not hasattr(summaries[0], "definition")
    assert summaries[0].table_count == 2


def test_duplicate_name_rejected():
    store = InMemorySchemaStore()
    store.create("S", _definition())
    with pytest.raises(ValueError):
        store.create("S", _definition())


def test_get_returns_full_definition_and_delete():
    store = InMemorySchemaStore()
    rec = store.create("S", _definition(), source="introspection", profile_id="p1")
    full = store.get(rec.id)
    assert full is not None and "tables" in full.definition
    assert full.source == "introspection" and full.profile_id == "p1"
    assert store.delete(rec.id) is True
    assert store.get(rec.id) is None
    assert store.delete("missing") is False


def test_file_store_round_trip(tmp_path):
    path = tmp_path / "schemas.json"
    store = JsonFileSchemaStore(str(path))
    rec = store.create("S", _definition())

    store2 = JsonFileSchemaStore(str(path))
    again = store2.get(rec.id)
    assert again is not None
    assert again.table_count == 2
    assert set(again.definition["tables"].keys()) == {"EMP", "DEPT"}
