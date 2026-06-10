"""Tests for Phase-5 data-dictionary helpers and schema serialization."""

from src.schema import (
    ColumnDefinition,
    RelationshipDefinition,
    Schema,
    TableDefinition,
    find_columns,
    referenced_by,
    references_out,
    schema_from_dict,
    schema_to_dict,
    table_detail,
)


def _schema() -> Schema:
    emp = TableDefinition(
        name="EMP",
        columns=[
            ColumnDefinition("EMP", "EMP_ID", "NUMBER", is_primary_key=True),
            ColumnDefinition("EMP", "NAME", "VARCHAR2"),
            ColumnDefinition(
                "EMP", "DEPT_ID", "NUMBER", is_foreign_key=True,
                references_table="DEPT", references_column="DEPT_ID",
            ),
        ],
    )
    dept = TableDefinition(
        name="DEPT",
        columns=[
            ColumnDefinition("DEPT", "DEPT_ID", "NUMBER", is_primary_key=True),
            ColumnDefinition("DEPT", "DEPT_NAME", "VARCHAR2"),
        ],
    )
    rels = [RelationshipDefinition("EMP", "DEPT_ID", "DEPT", "DEPT_ID", "many-to-one")]
    return Schema(tables={"EMP": emp, "DEPT": dept}, relationships=rels)


def test_table_detail():
    cols = table_detail(_schema(), "EMP")
    assert [c.column_name for c in cols] == ["EMP_ID", "NAME", "DEPT_ID"]
    assert table_detail(_schema(), "NOPE") == []


def test_find_columns_by_name():
    res = find_columns(_schema(), "dept")
    names = {(c.table_name, c.column_name) for c in res}
    # matches DEPT_ID in EMP, plus DEPT.DEPT_ID and DEPT.DEPT_NAME (table-name match)
    assert ("EMP", "DEPT_ID") in names
    assert ("DEPT", "DEPT_NAME") in names


def test_find_columns_filters():
    s = _schema()
    assert all(c.is_primary_key for c in find_columns(s, pk=True))
    assert {c.table_name for c in find_columns(s, pk=True)} == {"EMP", "DEPT"}
    fks = find_columns(s, fk=True)
    assert [(c.table_name, c.column_name) for c in fks] == [("EMP", "DEPT_ID")]
    # data_type substring (case-insensitive)
    assert all("char" in (c.data_type or "").lower() for c in find_columns(s, data_type="char"))


def test_references_out():
    assert references_out(_schema(), "EMP") == [("DEPT_ID", "DEPT", "DEPT_ID")]
    assert references_out(_schema(), "DEPT") == []


def test_referenced_by_where_used():
    # DEPT is referenced by EMP.DEPT_ID
    assert referenced_by(_schema(), "DEPT") == [("EMP", "DEPT_ID", "DEPT_ID")]
    assert referenced_by(_schema(), "EMP") == []


def test_serialization_round_trip():
    s = _schema()
    restored = schema_from_dict(schema_to_dict(s))
    assert restored.list_tables() == s.list_tables()
    assert [c.column_name for c in restored.tables["EMP"].columns] == ["EMP_ID", "NAME", "DEPT_ID"]
    fk = next(c for c in restored.tables["EMP"].columns if c.column_name == "DEPT_ID")
    assert fk.is_foreign_key and fk.references_table == "DEPT" and fk.references_column == "DEPT_ID"
    assert len(restored.relationships) == 1
    assert restored.relationships[0].relationship_type == "many-to-one"
